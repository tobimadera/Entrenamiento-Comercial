"""Simulación del dueño de concesionario y evaluación del representante con Claude."""
import json
import os
from pathlib import Path

import anthropic
import yaml

RAIZ = Path(__file__).resolve().parent.parent
MODELO = os.getenv("MODELO") or "claude-opus-5-5"

IDIOMAS = {
    "ar": {
        "clave": "es",
        "habla": "español rioplatense de Argentina (voseo, giros locales, pesos argentinos)",
        "pais": "Argentina",
    },
    "br": {
        "clave": "pt",
        "habla": "português brasileiro coloquial de negócios (reais, expressões locais)",
        "pais": "Brasil",
    },
}

_cliente = None


def cliente() -> anthropic.Anthropic:
    global _cliente
    if _cliente is None:
        _cliente = anthropic.Anthropic()
    return _cliente


# ---------------------------------------------------------------- escenarios
def cargar_escenarios() -> dict:
    """Lee todas las fichas de escenarios/. Se relee en cada pedido: editar y recargar la página alcanza."""
    escenarios = {}
    for ruta in sorted((RAIZ / "escenarios").rglob("*.yaml")):
        ficha = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        escenarios[ficha["id"]] = ficha
    return escenarios


def cargar_criterios(foco: str) -> list:
    datos = yaml.safe_load((RAIZ / "config" / "criterios.yaml").read_text(encoding="utf-8"))
    return datos["comunes"] + datos.get(foco, [])


def nombre_dueno(ficha: dict, pais: str) -> str:
    return ficha["dueno"]["nombre"][pais]


# ---------------------------------------------------------------- conversación
def instrucciones_personaje(ficha: dict, pais: str) -> str:
    idioma = IDIOMAS[pais]
    dueno = ficha["dueno"]
    lista = lambda items: "\n".join(f"- {i}" for i in items)
    return f"""Vas a interpretar a un dueño de concesionario de autos en una simulación de entrenamiento. \
La persona que te escribe es un representante de zona de la automotriz (la "marca") que practica cómo \
influir en dueños de concesionarios. La práctica solo le sirve si te comportás como un dueño real: \
con intereses propios, resistencias y un negocio que cuidar. Un dueño que cede enseguida no lo entrena.

# Quién sos
{nombre_dueno(ficha, pais)}, {dueno['edad']} años, dueño de un concesionario oficial de la marca en {idioma['pais']}.
{dueno['perfil']}

# Tu concesionario
{ficha['concesionario']}

# Tu situación hoy
{ficha['situacion']}

# Lo que el representante viene a buscar
{ficha['consigna']['es']}
Vos no sabés esto de antemano con este detalle; lo intuís y lo vas descubriendo en la charla.

# Objeciones que tenés en la cabeza
{lista(ficha['objeciones'])}
Usalas con tus palabras y de a una, cuando vengan al caso. Podés sumar otras coherentes con tu situación.

# Qué te hace cambiar de postura
{lista(ficha['que_lo_mueve'])}
Cedé en proporción a la calidad de lo que el representante hace: si pregunta, escucha y argumenta con \
números de tu negocio, abrite de a poco. Si recita un discurso, presiona, amenaza o promete cosas vagas, \
endurecete o desviá el tema. Si inventa datos de tu concesionario que no coinciden con tu situación, \
corregilo como lo haría alguien que conoce su negocio.

# Hasta dónde llegás
{ficha['limite']}

# Cómo hablar
- Hablá siempre en {idioma['habla']}, sea cual sea el idioma en que te escriban.
- Es una conversación cara a cara en tu oficina: respuestas breves, de una a cuatro frases, como se habla. \
Sin listas, sin títulos, sin acotaciones entre asteriscos ni paréntesis.
- Mantené el personaje toda la conversación. No des consejos al representante, no evalúes cómo lo hace y \
no menciones que sos una IA ni que esto es una simulación.
- Si te falta un dato de tu negocio, inventalo de forma coherente con lo anterior y sostenelo.
- Si el representante da por terminada la reunión, despedite en personaje dejando claro qué te \
comprometiste a hacer y qué no."""


APERTURA = (
    "[Inicio de la reunión: el representante de zona acaba de entrar a tu oficina. "
    "Recibilo en personaje con una o dos frases; todavía no sabés a qué viene.]"
)


def responder(ficha: dict, pais: str, mensajes: list):
    """Genera la respuesta del dueño y la entrega de a fragmentos de texto."""
    with cliente().beta.messages.stream(
        model=MODELO,
        max_tokens=2000,
        system=[{
            "type": "text",
            "text": instrucciones_personaje(ficha, pais),
            "cache_control": {"type": "ephemeral"},
        }],
        messages=mensajes,
        output_config={"effort": "low"},  # respuestas rápidas: es un diálogo, y luego irá con voz
        # Si un filtro de seguridad rechaza el pedido, la API lo reintenta sola con otro modelo.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    ) as stream:
        for texto in stream.text_stream:
            yield texto
        if stream.get_final_message().stop_reason == "refusal":
            raise RuntimeError("El modelo rechazó responder este mensaje.")


# ---------------------------------------------------------------- evaluación
ESQUEMA_EVALUACION = {
    "type": "object",
    "properties": {
        "puntaje_general": {"type": "integer", "description": "De 1 a 10"},
        "resultado": {"type": "string", "description": "Qué compromiso se consiguió del dueño frente al objetivo, en dos frases"},
        "criterios": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string"},
                    "puntaje": {"type": "integer", "description": "De 1 a 10"},
                    "comentario": {"type": "string"},
                },
                "required": ["nombre", "puntaje", "comentario"],
                "additionalProperties": False,
            },
        },
        "fortalezas": {"type": "array", "items": {"type": "string"}},
        "mejoras": {"type": "array", "items": {"type": "string"}},
        "momentos_clave": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "dijiste": {"type": "string", "description": "Cita textual breve del representante"},
                    "efecto": {"type": "string", "description": "Qué provocó en el dueño"},
                    "alternativa": {"type": "string", "description": "Qué podría haber dicho, en sus palabras"},
                },
                "required": ["dijiste", "efecto", "alternativa"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["puntaje_general", "resultado", "criterios", "fortalezas", "mejoras", "momentos_clave"],
    "additionalProperties": False,
}


def evaluar(ficha: dict, pais: str, mensajes: list) -> dict:
    idioma = IDIOMAS[pais]
    criterios = cargar_criterios(ficha["foco"])
    transcripcion = "\n\n".join(
        ("REPRESENTANTE: " if m["role"] == "user" else "DUEÑO: ") + m["content"]
        for m in mensajes[1:]  # el primero es la indicación de apertura
    )
    pedido = f"""Sos un entrenador comercial senior de una automotriz. Evaluá el desempeño del REPRESENTANTE \
de zona en esta conversación de práctica con el dueño de un concesionario (el dueño fue simulado).

Objetivo que tenía el representante:
{ficha['consigna']['es']}

Ficha privada del dueño (el representante no la conocía):
{yaml.safe_dump({k: ficha[k] for k in ('concesionario', 'situacion', 'objeciones', 'que_lo_mueve', 'limite')}, allow_unicode=True, sort_keys=False)}

Criterios a puntuar, uno por uno y con estos mismos nombres traducidos al idioma de la devolución:
{yaml.safe_dump(criterios, allow_unicode=True, sort_keys=False)}

<transcripcion>
{transcripcion}
</transcripcion>

Evaluá solo lo que el representante dijo. Sé exigente y específico: citá sus frases, explicá qué efecto \
tuvieron en el dueño y qué palancas de la ficha quedaron sin usar. Si la conversación fue muy corta para \
juzgar un criterio, decilo en el comentario y puntuá bajo. Entre dos y cuatro fortalezas, mejoras y \
momentos clave. Dirigite al representante de vos a vos, en {idioma['habla']}."""

    respuesta = cliente().messages.create(
        model=MODELO,
        max_tokens=16000,
        messages=[{"role": "user", "content": pedido}],
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": ESQUEMA_EVALUACION}},
    )
    if respuesta.stop_reason == "refusal":
        raise RuntimeError("El modelo rechazó evaluar esta conversación.")
    return json.loads(next(b.text for b in respuesta.content if b.type == "text"))
