"""Avatar con cara (Simli): el servidor pide un permiso de sesión con la clave de Simli y el
navegador lo usa para conectarse. La clave nunca llega al navegador."""
import os
from pathlib import Path

import httpx
import yaml

RAIZ = Path(__file__).resolve().parent.parent
API = "https://api.simli.ai"


class ErrorAvatar(Exception):
    pass


def _clave() -> str:
    return (os.getenv("SIMLI_API_KEY") or "").strip()


def disponible() -> bool:
    return bool(_clave())


def cara_para(ficha: dict, pais: str) -> str:
    propia = ficha["dueno"].get("cara")
    if propia:
        return propia
    caras = yaml.safe_load((RAIZ / "config" / "voces.yaml").read_text(encoding="utf-8"))["caras"]
    return caras[pais]["mujer" if ficha["dueno"].get("genero") == "f" else "hombre"]


def pedir_sesion(ficha: dict, pais: str) -> str:
    """Devuelve el permiso de sesión (session_token) para la cara de este dueño."""
    try:
        r = httpx.post(
            f"{API}/compose/token",
            headers={"x-simli-api-key": _clave()},
            json={
                "faceId": cara_para(ficha, pais),
                "handleSilence": True,     # rellena los silencios entre frases para que no se congele
                "maxSessionLength": 1800,  # una práctica no pasa de 30 minutos
                "maxIdleTime": 180,        # si nadie habla en 3 minutos se corta, para no gastar minutos
            },
            timeout=httpx.Timeout(20.0, connect=10.0),
        )
    except httpx.HTTPError as e:
        raise ErrorAvatar(f"No se pudo conectar con Simli: {e}")
    if r.status_code in (401, 403) and "FACE" not in r.text:
        raise ErrorAvatar("La clave de Simli falta o no es válida. Revisá SIMLI_API_KEY.")
    if r.status_code != 200:
        try:
            detalle = r.json().get("detail") or r.text[:300]
        except ValueError:
            detalle = r.text[:300]
        raise ErrorAvatar(f"Simli devolvió un error ({r.status_code}): {detalle}")
    return r.json()["session_token"]
