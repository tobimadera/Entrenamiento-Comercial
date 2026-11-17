"""Servidor web del entrenador: sirve la página de chat y expone la simulación."""
import hmac
import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

import anthropic  # noqa: E402
from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from app import simulador  # noqa: E402

app = FastAPI(title="Entrenador de Ventas")
SESIONES: dict[str, dict] = {}
CARPETA_SESIONES = Path(os.getenv("DATOS_DIR") or RAIZ / "datos") / "sesiones"
MARCA_ERROR = "\n[[ERROR]] "
# Si está definido, la página lo pide antes de dejar usar el entrenador. Vacío = sin control (uso local).
CODIGO_ACCESO = (os.getenv("CODIGO_ACCESO") or "").strip()


@app.middleware("http")
async def exigir_codigo(request: Request, call_next):
    if CODIGO_ACCESO and request.url.path.startswith("/api/"):
        recibido = request.headers.get("x-codigo", "")
        if not hmac.compare_digest(recibido.encode(), CODIGO_ACCESO.encode()):
            return JSONResponse({"detail": "Código de acceso incorrecto."}, status_code=401)
    return await call_next(request)


def explicar_error(e: Exception) -> str:
    """Mensaje en lenguaje llano para mostrar en pantalla."""
    if isinstance(e, anthropic.AuthenticationError) or "api_key" in str(e) or "auth" in str(e).lower():
        return "Falta la clave de Anthropic o no es válida. Revisá ANTHROPIC_API_KEY en el archivo .env."
    if isinstance(e, anthropic.RateLimitError):
        return "Se alcanzó el límite de uso de la cuenta de Anthropic. Esperá un minuto y reintentá."
    if isinstance(e, anthropic.APIConnectionError):
        return "No se pudo conectar con Anthropic. Revisá la conexión a internet."
    if isinstance(e, anthropic.APIStatusError):
        return f"Anthropic devolvió un error ({e.status_code}): {e.message}"
    return str(e)


def guardar(sesion: dict) -> None:
    CARPETA_SESIONES.mkdir(parents=True, exist_ok=True)
    (CARPETA_SESIONES / f"{sesion['id']}.json").write_text(
        json.dumps(sesion, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def buscar(sesion_id: str) -> dict:
    if sesion_id not in SESIONES:
        # Tras un reinicio del servidor, la sesión se recupera del archivo guardado.
        ruta = CARPETA_SESIONES / f"{sesion_id}.json"
        if not re.fullmatch(r"[0-9a-f-]+", sesion_id) or not ruta.exists():
            raise HTTPException(404, "La sesión no existe. Empezá una nueva.")
        SESIONES[sesion_id] = json.loads(ruta.read_text(encoding="utf-8"))
    return SESIONES[sesion_id]


class NuevaSesion(BaseModel):
    escenario_id: str
    pais: str
    nombre: str = ""


class Mensaje(BaseModel):
    texto: str = ""


@app.get("/")
def pagina():
    return FileResponse(RAIZ / "web" / "index.html")


@app.get("/api/escenarios")
def escenarios():
    return [
        {k: f[k] for k in ("id", "foco", "dificultad", "titulo", "consigna")}
        for f in simulador.cargar_escenarios().values()
    ]


@app.post("/api/sesiones")
def crear_sesion(datos: NuevaSesion):
    fichas = simulador.cargar_escenarios()
    if datos.escenario_id not in fichas or datos.pais not in simulador.IDIOMAS:
        raise HTTPException(400, "Escenario o país inválido.")
    sesion = {
        "id": datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6],
        "inicio": datetime.now().isoformat(timespec="seconds"),
        "representante": datos.nombre.strip(),
        "pais": datos.pais,
        "escenario_id": datos.escenario_id,
        "ficha": fichas[datos.escenario_id],  # copia de la ficha usada, por si después se edita
        "mensajes": [],
        "evaluacion": None,
    }
    SESIONES[sesion["id"]] = sesion
    return {"id": sesion["id"], "dueno": simulador.nombre_dueno(sesion["ficha"], datos.pais)}


@app.post("/api/sesiones/{sesion_id}/mensaje")
def mensaje(sesion_id: str, datos: Mensaje):
    """Recibe lo que dijo el representante y devuelve la respuesta del dueño a medida que se genera.
    Con la conversación vacía, el dueño abre la reunión."""
    sesion = buscar(sesion_id)
    texto = datos.texto.strip()
    if not sesion["mensajes"]:
        # Si la apertura había fallado y el representante escribe igual, su texto va después de ella.
        texto = simulador.APERTURA + ("\n\n" + texto if texto else "")
    elif not texto:
        raise HTTPException(400, "El mensaje está vacío.")
    pendientes = sesion["mensajes"] + [{"role": "user", "content": texto}]

    def generar():
        partes = []
        try:
            for fragmento in simulador.responder(sesion["ficha"], sesion["pais"], pendientes):
                partes.append(fragmento)
                yield fragmento
        except Exception as e:  # el error viaja dentro de la respuesta ya iniciada
            yield MARCA_ERROR + explicar_error(e)
            return
        sesion["mensajes"] = pendientes + [{"role": "assistant", "content": "".join(partes)}]
        guardar(sesion)

    return StreamingResponse(generar(), media_type="text/plain; charset=utf-8")


@app.post("/api/sesiones/{sesion_id}/evaluacion")
def evaluacion(sesion_id: str):
    sesion = buscar(sesion_id)
    if len(sesion["mensajes"]) < 4:
        raise HTTPException(400, "La conversación es muy corta para evaluarla.")
    try:
        sesion["evaluacion"] = simulador.evaluar(sesion["ficha"], sesion["pais"], sesion["mensajes"])
    except Exception as e:
        raise HTTPException(502, explicar_error(e))
    guardar(sesion)
    return sesion["evaluacion"]
