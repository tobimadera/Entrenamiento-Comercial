"""Consultores habilitados para practicar, cada uno con su código personal.

La lista vive en la carpeta de datos (en Railway, el volumen), no en el repositorio:
los códigos son secretos y el repositorio es público."""
import hmac
import json
import os
import secrets
import threading
import uuid
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin 0/O ni 1/I, para dictarlo sin errores
_candado = threading.Lock()


def _ruta() -> Path:
    return Path(os.getenv("DATOS_DIR") or RAIZ / "datos") / "consultores.json"


def listar() -> list[dict]:
    ruta = _ruta()
    if not ruta.exists():
        return []
    return json.loads(ruta.read_text(encoding="utf-8"))


def _guardar(lista: list[dict]) -> None:
    ruta = _ruta()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(".tmp")
    temporal.write_text(json.dumps(lista, ensure_ascii=False, indent=2), encoding="utf-8")
    temporal.replace(ruta)


def _nuevo_codigo(existentes: set[str]) -> str:
    while True:
        codigo = "-".join("".join(secrets.choice(ALFABETO) for _ in range(4)) for _ in range(3))
        if codigo not in existentes:
            return codigo


def _normalizar(codigo: str) -> str:
    return codigo.strip().upper()


def crear(nombre: str, pais: str) -> dict:
    with _candado:
        lista = listar()
        consultor = {
            "id": uuid.uuid4().hex[:10],
            "nombre": nombre.strip(),
            "pais": pais,
            "codigo": _nuevo_codigo({c["codigo"] for c in lista}),
            "activo": True,
            "alta": datetime.now().isoformat(timespec="seconds"),
        }
        lista.append(consultor)
        _guardar(lista)
        return consultor


def actualizar(consultor_id: str, *, activo: bool | None = None, nuevo_codigo: bool = False) -> dict | None:
    with _candado:
        lista = listar()
        for c in lista:
            if c["id"] == consultor_id:
                if activo is not None:
                    c["activo"] = activo
                if nuevo_codigo:
                    c["codigo"] = _nuevo_codigo({x["codigo"] for x in lista})
                _guardar(lista)
                return c
    return None


def por_codigo(codigo: str) -> dict | None:
    """El consultor activo dueño de ese código, o None."""
    buscado = _normalizar(codigo).encode()
    encontrado = None
    for c in listar():  # se recorren todos para no revelar por tiempo cuál coincide
        if hmac.compare_digest(c["codigo"].encode(), buscado) and c.get("activo", True):
            encontrado = c
    return encontrado
