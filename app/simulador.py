"""Simulación del dueño de concesionario y evaluación del representante con Claude."""
import copy
import json
import os
from pathlib import Path

import anthropic
import yaml

RAIZ = Path(__file__).resolve().parent.parent
# La devolución usa el modelo más capaz; el diálogo, uno que responde rápido para que la voz sea ágil.
MODELO = os.getenv("MODELO") or "claude-opus-5-5"
MODELO_DIALOGO = os.getenv("MODELO_DIALOGO") or "claude-sonnet-5-5"

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


def _config_criterios() -> dict:
    return yaml.safe_load((RAIZ / "config" / "criterios.yaml").read_text(encoding="utf-8"))


def cargar_criterios(foco: str) -> list:
    datos = _config_criterios()
    return datos["comunes"] + datos.get(foco, [])


def todos_los_criterios() -> tuple[list[str], float]:
    """Nombres de todos los criterios (comunes, luego los de cada foco) y el puntaje objetivo."""
    datos = _config_criterios()
    nombres = [c["nombre"] for c in datos["comunes"] + datos.get("ventas", []) + datos.get("posventa", [])
               + datos.get("especiales", [])]
    return nombres, float(datos.get("objetivo", 7))


def nombre_dueno(ficha: dict, pais: str) -> str:
    return ficha["dueno"]["nombre"][pais]


# ---------------------------------------------------------------- conversación
def instrucciones_personaje(ficha: dict, pais: str, hablado: bool = False, referencia: dict | None = None) -> str:
    idioma = IDIOMAS[pais]
    largo = (
        "La reunión es por voz: respondé en una a tres frases cortas, no más de 40 palabras en total, "
        "y decí primero lo más importante, como se contesta en una charla."
        if hablado else
        "Es una conversación cara a cara en tu oficina: respuestas breves, de una a cuatro frases, como se habla."
    )
    dueno = ficha["dueno"]
    lista = lambda items: "\n".join(f"- {i}" for i in items)
    genero = "dueña" if dueno.get("genero") == "f" else "dueño"
    # El consultor elige la complejidad: cambia cuánto resiste el dueño ante una buena propuesta.
    exigencia = {
        "baja": "Esta práctica es de complejidad baja: sos receptivo. Tus objeciones son dudas para "
                "despejar, no resistencia; si el representante responde con algo razonable y concreto, "
                "aceptás sin volver sobre lo ya resuelto.",
        "media": "Esta práctica es de complejidad media: cedés de a poco, cuando la propuesta atiende "
                 "tus objeciones con argumentos y datos.",
        "alta": "Esta práctica es de complejidad alta: sos exigente. Sostenés tus objeciones, ponés a "
                "prueba los números y solo cedés ante evidencia sólida y compromisos verificables.",
    }.get(ficha.get("dificultad", ""), "")

    if referencia:
        detalle = f" ({referencia['detalle']})" if referencia.get("detalle") else ""
        bloque_referencia = f"""
# El concesionario que imitás
Tu concesionario se inspira en {referencia['nombre']}{detalle}, un concesionario real de la red en \
{idioma['pais']}. Usá su nombre, su zona y lo que ofrece para darle realismo a la charla. Solo eso es \
público: tu personalidad, tus números, tus problemas y tu desempeño son inventados para la práctica. No \
afirmes como hecho nada que diga "no verificado" o "por validar", no nombres a personas reales de ese \
concesionario y no digas nada que pueda dañar su reputación fuera de esta práctica.
"""
    else:
        bloque_referencia = ""

    if ficha.get("objecion_inicial"):
        apertura = (f"Ya sabés que el representante viene a hablar de {ficha['titulo']['es']}. Al recibirlo, "
                    f"saludá y planteá enseguida, con tus palabras, tu objeción inicial: «{ficha['objecion_inicial']}»")
    else:
        apertura = "Recibilo en personaje con una o dos frases; todavía no sabés a qué viene."

    interes = f"""
# Lo que de verdad te preocupa (interés oculto)
{ficha['interes_oculto']}
No lo digas de entrada. Si el representante escucha y hace buenas preguntas, revelalo de a poco; si \
impone, amenaza o ignora tus costos, guardátelo y sostené la oposición.
""" if ficha.get("interes_oculto") else ""

    no_negociable = f"""
# Lo que no negociás
{ficha['no_negociable']} Aunque la charla vaya bien, esto no lo cedés.
""" if ficha.get("no_negociable") else ""

    return f"""Vas a interpretar a {'una dueña' if genero == 'dueña' else 'un dueño'} de concesionario de autos \
en una simulación de entrenamiento. La persona que te escribe es un representante de zona de la automotriz \
(la "marca") que practica cómo influir en dueños de concesionarios. La práctica solo le sirve si te \
comportás como un {genero} real: con intereses propios, resistencias y un negocio que cuidar. Quien cede \
enseguida no entrena a nadie.

# Quién sos
{nombre_dueno(ficha, pais)}, {dueno['edad']} años, {genero} de un concesionario oficial de la marca en {idioma['pais']}.
{dueno['perfil']}
{bloque_referencia}
# Tu concesionario
{ficha['concesionario']}

# Tu situación hoy
{ficha['situacion']}

# Lo que el representante viene a buscar
{ficha['consigna']['es']}
Vos no sabés esto de antemano con este detalle; lo intuís y lo vas descubriendo en la charla.

# Cómo abrir la reunión
{apertura}

# Objeciones que tenés en la cabeza
{lista(ficha['objeciones'])}
Usalas con tus palabras y de a una, cuando vengan al caso. Podés sumar otras coherentes con tu situación.
{interes}
# Qué te hace cambiar de postura
{lista(ficha['que_lo_mueve'])}
Cedé en proporción a la calidad de lo que el representante hace: si pregunta, escucha y argumenta con \
números de tu negocio, abrite de a poco. Si recita un discurso, presiona, amenaza o promete cosas vagas, \
endurecete o desviá el tema. Si inventa datos de tu concesionario que no coinciden con tu situación, \
corregilo como lo haría alguien que conoce su negocio. Cedé en parte cuando la propuesta atiende lo que \
de verdad te preocupa con evidencia y compromisos verificables.
{exigencia}

# Hasta dónde llegás
{ficha['limite']}
Llegás al máximo solo si se cumplen las condiciones. No inventes autorizaciones ni beneficios que la marca \
no ofreció.
{no_negociable}
# Cómo cerrar
Antes de comprometerte, pedí responsable, plazo, indicador y fecha de revisión. Si no hay acuerdo \
razonable, decilo y no fuerces uno.

# Cómo hablar
- Hablá siempre en {idioma['habla']}, sea cual sea el idioma en que te escriban.
- {largo} Sin listas, sin títulos, sin acotaciones entre asteriscos ni paréntesis.
- Hablá siempre en primera persona, nunca de vos mismo por tu nombre.
- No le inventes un nombre al representante: si no se presentó, no lo nombres.
- Mantené el personaje toda la conversación. No des consejos al representante, no evalúes cómo lo hace y \
no menciones que sos una IA ni que esto es una simulación.
- Si te falta un dato de tu negocio, inventalo de forma coherente con lo anterior y sostenelo.
- Si el representante da por terminada la reunión, despedite en personaje dejando claro qué te \
comprometiste a hacer y qué no."""


APERTURA = (
    "[Inicio de la reunión: el representante de zona acaba de entrar a tu oficina. "
    "Recibilo en personaje como indica «Cómo abrir la reunión».]"
)
# Texto de apertura que usaban las prácticas guardadas antes de este cambio.
APERTURAS = (APERTURA, "[Inicio de la reunión: el representante de zona acaba de entrar a tu oficina. "
             "Recibilo en personaje con una o dos frases; todavía no sabés a qué viene.]")


def sin_apertura(texto: str) -> str:
    for apertura in APERTURAS:
        texto = texto.replace(apertura, "")
    return texto.strip()


def responder(ficha: dict, pais: str, mensajes: list, hablado: bool = False, referencia: dict | None = None):
    """Genera la respuesta del dueño y la entrega de a fragmentos de texto."""
    # En Sonnet 5.5, "between_tools" responde sin pensar antes: la primera palabra llega en ~0,7 s.
    sin_pensar = {"thinking": {"type": "between_tools"}} if MODELO_DIALOGO == "claude-sonnet-5-5" else {}
    with cliente().beta.messages.stream(
        model=MODELO_DIALOGO,
        **sin_pensar,
        max_tokens=2000,
        system=[{
            "type": "text",
            "text": instrucciones_personaje(ficha, pais, hablado, referencia),
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


def esquema_evaluacion(criterios: list) -> dict:
    """El esquema fijo, con el nombre de cada criterio limitado a los de la configuración:
    así el panel del gestor compara criterios entre prácticas en español y en portugués."""
    esquema = copy.deepcopy(ESQUEMA_EVALUACION)
    item = esquema["properties"]["criterios"]["items"]
    item["properties"] = {"criterio": {"type": "string", "enum": [c["nombre"] for c in criterios]}, **item["properties"]}
    item["required"] = ["criterio", *item["required"]]
    return esquema


def evaluar(ficha: dict, pais: str, mensajes: list, por_voz: bool = False) -> dict:
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
{yaml.safe_dump({k: ficha[k] for k in ('concesionario', 'situacion', 'objecion_inicial', 'interes_oculto', 'objeciones', 'que_lo_mueve', 'limite', 'no_negociable') if k in ficha}, allow_unicode=True, sort_keys=False)}

Criterios a puntuar, uno por uno. En "criterio" va el nombre exacto de esta lista, sin traducir; \
en "nombre", ese mismo nombre en el idioma de la devolución:
{yaml.safe_dump(criterios, allow_unicode=True, sort_keys=False)}

<transcripcion>
{transcripcion}
</transcripcion>

Evaluá solo lo que el representante dijo. Sé exigente y específico: citá sus frases, explicá qué efecto \
tuvieron en el dueño y qué palancas de la ficha quedaron sin usar. Si la conversación fue muy corta para \
juzgar un criterio, decilo en el comentario y puntuá bajo. Entre dos y cuatro fortalezas, mejoras y \
momentos clave. Dirigite al representante de vos a vos, en {idioma['habla']}."""
    if por_voz:
        pedido += """

El representante habló por micrófono y sus frases son una transcripción automática: puede haber \
palabras mal reconocidas, falta de puntuación o muletillas. No las juzgues como errores suyos; \
evaluá el contenido y la forma de argumentar."""

    respuesta = cliente().messages.create(
        model=MODELO,
        max_tokens=16000,
        messages=[{"role": "user", "content": pedido}],
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": esquema_evaluacion(criterios)}},
    )
    if respuesta.stop_reason == "refusal":
        raise RuntimeError("El modelo rechazó evaluar esta conversación.")
    return json.loads(next(b.text for b in respuesta.content if b.type == "text"))


# ---------------------------------------------------------------- puntos de mejora (panel del gestor)
ESQUEMA_MEJORAS = {
    "type": "object",
    "properties": {
        "sintesis": {"type": "string", "description": "Una o dos frases sobre el principal gap de desarrollo"},
        "temas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tema": {"type": "string", "description": "El punto de mejora en pocas palabras"},
                    "detalle": {"type": "string", "description": "Qué hace o deja de hacer, en una o dos frases"},
                    "en_cuantas": {"type": "integer", "description": "En cuántas de las prácticas aparece"},
                    "ejemplo": {"type": "string", "description": "Cita textual breve del consultor que lo muestra, o vacío"},
                    "que_practicar": {"type": "string", "description": "Una acción concreta para la próxima práctica"},
                },
                "required": ["tema", "detalle", "en_cuantas", "ejemplo", "que_practicar"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["sintesis", "temas"],
    "additionalProperties": False,
}


def resumir_mejoras(nombre: str, practicas: list[dict]) -> dict:
    """Junta las devoluciones de varias prácticas de un consultor y encuentra los puntos de mejora
    que se repiten. `practicas` trae, por práctica: fecha, escenario, puntaje, mejoras,
    criterios bajos y momentos clave."""
    pedido = f"""Sos un entrenador comercial senior de una automotriz. Abajo están las devoluciones de las \
últimas {len(practicas)} prácticas de {nombre}, un representante de zona que entrena reuniones con dueños \
de concesionarios (los dueños fueron simulados).

<practicas>
{yaml.safe_dump(practicas, allow_unicode=True, sort_keys=False)}
</practicas>

Encontrá entre dos y cuatro puntos de mejora que se repiten entre prácticas: los gaps de desarrollo \
de esta persona, no los detalles de una reunión puntual. Ordenalos del más importante al menos importante, \
pesando cuántas veces aparece y cuánto le cuesta en el resultado. Si hay una sola práctica, decilo en la \
síntesis y basate en esa. En "en_cuantas", contá las prácticas donde el tema aparece de verdad, sin \
redondear para arriba. El ejemplo tiene que ser una frase que el consultor dijo, copiada de los momentos \
clave; si no hay ninguna que sirva, dejalo vacío. Escribí en español, para el gestor del equipo, en \
tercera persona y sin adornos."""
    respuesta = cliente().messages.create(
        model=MODELO,
        max_tokens=8000,
        messages=[{"role": "user", "content": pedido}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": ESQUEMA_MEJORAS}},
    )
    if respuesta.stop_reason == "refusal":
        raise RuntimeError("El modelo rechazó resumir estas devoluciones.")
    return json.loads(next(b.text for b in respuesta.content if b.type == "text"))
