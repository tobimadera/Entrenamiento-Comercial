"""Convierte el banco de escenarios del Excel (hojas "Escenarios IA" y "Referencias AR-BR")
en fichas YAML dentro de escenarios/.

Uso:  .venv\\Scripts\\python.exe scripts\\importar_excel.py <ruta al .xlsx>

Lo que no está en el Excel lo completa este script: nombre, edad y género ficticios del dueño,
la traducción al portugués de lo que ve el representante y una descripción del estilo del dueño.
Volver a correrlo sobrescribe las fichas con prefijo V, P y E."""
import re
import sys
from pathlib import Path

import openpyxl
import yaml

RAIZ = Path(__file__).resolve().parent.parent
FOCOS = {"Ventas": "ventas", "Posventa": "posventa", "Ventas Especiales": "especiales"}

# Estilo del dueño según la primera palabra de "V2 · Dueño y desempeño".
ESTILOS = {
    "Dominante": "Dominante: le gusta tener la última palabra, habla firme y no tolera que le impongan nada. Respeta a quien le discute con datos.",
    "Analítico": "Analítico: pide números y casos de negocio para todo; desconfía de las afirmaciones generales y hace preguntas incómodas.",
    "Desconfiado": "Desconfiado: le costó mucho armar su clientela y sospecha de cada propuesta de la marca; necesita garantías antes de moverse.",
    "Innovador": "Innovador: le gusta probar cosas nuevas si ve el negocio, pero se aburre rápido con discursos y quiere ir al punto.",
    "Pragmático": "Pragmático: va al grano; le interesa qué gana, qué arriesga y cuánto tarda en verlo.",
    "Tradicional": "Tradicional: vende como siempre vendió, por relación; desconfía de procesos, sistemas y controles nuevos.",
    "Negociador duro": "Negociador duro: convierte todo en una negociación y no da nada sin recibir algo a cambio.",
    "Comercial": "Comercial: piensa en margen y velocidad; si algo deja más plata o sale más rápido, lo prefiere.",
    "Defensivo": "Defensivo: se siente auditado por la marca y responde justificándose antes de escuchar.",
    "Relacional": "Relacional: valora el vínculo personal y evita el conflicto, pero no asume culpas que no son suyas.",
    "Cauteloso": "Cauteloso: mide cada riesgo y prefiere perder una oportunidad antes que meterse en un problema.",
}

# Lo que el Excel no trae: dueño ficticio y textos en portugués de lo que ve el representante.
EXTRA = {
    "V01": dict(nombre=("Ricardo Ibarra", "Ricardo Barbosa"), genero="m", edad=61,
                titulo_pt="Hilux / SW4: aumentar o mix",
                consigna_pt="Elevar o mix de versões de menor giro de 10% para 20% em 60 dias.",
                contexto=("Perfil dominante. Concesionario grande (4 locales), al 110% de su objetivo; caja sólida.",
                          "Perfil dominante. Concessionária grande (4 lojas), em 110% da meta; caixa sólido.")),
    "V02": dict(nombre=("Paula Mendizábal", "Paula Mendes"), genero="f", edad=47,
                titulo_pt="Corolla híbrido / Corolla Cross: eletrificação",
                consigna_pt="Capacitar os vendedores e realizar 30 test drives por mês.",
                contexto=("Perfil analítico. Concesionario mediano (2 locales), al 85% de su objetivo; caja ajustada.",
                          "Perfil analítico. Concessionária média (2 lojas), em 85% da meta; caixa apertado.")),
    "V03": dict(nombre=("Osvaldo Quiroga", "Osvaldo Queiroz"), genero="m", edad=64,
                titulo_pt="Toyota Plan (consórcio)",
                consigna_pt="Aumentar as adesões de 10 para 18 por mês.",
                contexto=("Perfil desconfiado. Concesionario pequeño (1 local), al 75% de su objetivo; liquidez baja.",
                          "Perfil desconfiado. Concessionária pequena (1 loja), em 75% da meta; liquidez baixa.")),
    "V04": dict(nombre=("Federico Lanús", "Frederico Lacerda"), genero="m", edad=44,
                titulo_pt="Toyota Seminovos Certificados",
                consigna_pt="Certificar 40 seminovos por mês e publicar o estoque digital.",
                contexto=("Perfil innovador. Concesionario grande (5 locales), al 115% de su objetivo; caja sólida.",
                          "Perfil inovador. Concessionária grande (5 lojas), em 115% da meta; caixa sólido.")),
    "V05": dict(nombre=("Silvina Arce", "Sílvia Araújo"), genero="f", edad=52,
                titulo_pt="Financiamento / seguros",
                consigna_pt="Aumentar a penetração financeira de 20% para 35%.",
                contexto=("Perfil pragmático. Concesionario mediano, al 95% de su objetivo; caja estable.",
                          "Perfil pragmático. Concessionária média, em 95% da meta; caixa estável.")),
    "V06": dict(nombre=("Hugo Benítez", "Hugo Bentes"), genero="m", edad=66,
                titulo_pt="Gestão de leads digitais",
                consigna_pt="Responder 90% dos leads em até 2 horas úteis.",
                contexto=("Perfil tradicional. Concesionario pequeño, al 90% de su objetivo; caja estable.",
                          "Perfil tradicional. Concessionária pequena, em 90% da meta; caixa estável.")),
    "P01": dict(nombre=("Claudia Sosa", "Cláudia Souza"), genero="f", edad=50,
                titulo_pt="Toyota 10 / manutenção",
                consigna_pt="Elevar o retorno à oficina de 55% para 65% em 90 dias.",
                contexto=("Perfil analítico. Concesionario mediano, al 82% de su objetivo de servicios; caja estable.",
                          "Perfil analítico. Concessionária média, em 82% da meta de serviços; caixa estável.")),
    "P02": dict(nombre=("Alberto Funes", "Alberto Fontes"), genero="m", edad=59,
                titulo_pt="Capacidade e agendamento",
                consigna_pt="Reduzir a espera por agendamento para 5 dias.",
                contexto=("Perfil dominante. Concesionario grande, al 120% de volumen; 12 días de espera para un turno.",
                          "Perfil dominante. Concessionária grande, em 120% do volume; 12 dias de espera para agendar.")),
    "P03": dict(nombre=("Néstor Vidal", "Nestor Vidal"), genero="m", edad=55,
                titulo_pt="Peças genuínas",
                consigna_pt="Melhorar a disponibilidade de peças críticas para 95%.",
                contexto=("Negociador duro. Concesionario mediano, al 78% de su objetivo de repuestos; caja ajustada.",
                          "Negociador duro. Concessionária média, em 78% da meta de peças; caixa apertado.")),
    "P04": dict(nombre=("Mariano Costa", "Marcos Costa"), genero="m", edad=48,
                titulo_pt="Acessórios genuínos",
                consigna_pt="Aumentar a instalação de acessórios de 15% para 25% das entregas.",
                contexto=("Perfil comercial. Concesionario grande, al 105% de su objetivo; caja sólida.",
                          "Perfil comercial. Concessionária grande, em 105% da meta; caixa sólido.")),
    "P05": dict(nombre=("Elena Duarte", "Helena Duarte"), genero="f", edad=57,
                titulo_pt="Campanhas de segurança (recall)",
                consigna_pt="Contatar 100% dos afetados e priorizar os reparos conforme a campanha.",
                contexto=("Perfil defensivo. Concesionario pequeño, al 70% de su objetivo; taller saturado.",
                          "Perfil defensivo. Concessionária pequena, em 70% da meta; oficina saturada.")),
    "P06": dict(nombre=("Raúl Medina", "Raul Medeiros"), genero="m", edad=60,
                titulo_pt="Funilaria e pintura / reclamações",
                consigna_pt="Reduzir o retrabalho de 8% para 4% em 90 dias.",
                contexto=("Perfil relacional. Concesionario mediano, con la satisfacción en descenso; caja estable.",
                          "Perfil relacional. Concessionária média, com a satisfação em queda; caixa estável.")),
    "E01": dict(nombre=("Carlos Bustos", "Carlos Bastos"), genero="m", edad=53,
                titulo_pt="Frota Hilux agro",
                consigna_pt="Cotar 30 unidades com entregas escalonadas.",
                contexto=("Perfil pragmático. Concesionario mediano, al 95% de su objetivo; caja estable.",
                          "Perfil pragmático. Concessionária média, em 95% da meta; caixa estável.")),
    "E02": dict(nombre=("Verónica Lagos", "Verônica Lago"), genero="f", edad=46,
                titulo_pt="Hiace logística",
                consigna_pt="Apresentar uma proposta para 20 utilitários.",
                contexto=("Perfil analítico. Concesionario grande, al 105% de su objetivo; caja sólida.",
                          "Perfil analítico. Concessionária grande, em 105% da meta; caixa sólido.")),
    "E03": dict(nombre=("Enrique Salas", "Henrique Sales"), genero="m", edad=62,
                titulo_pt="KINTO One Fleet",
                consigna_pt="Gerar 3 oportunidades corporativas em 90 dias.",
                contexto=("Perfil tradicional. Concesionario mediano, al 100% de su objetivo minorista; caja estable.",
                          "Perfil tradicional. Concessionária média, em 100% da meta de varejo; caixa estável.")),
    "E04": dict(nombre=("Gabriela Ortiz", "Gabriela Oliveira"), genero="f", edad=54,
                titulo_pt="Licitação pública",
                consigna_pt="Avaliar uma oferta de 40 veículos para um órgão público.",
                contexto=("Perfil cauteloso. Concesionario grande, al 90% de su objetivo; caja ajustada.",
                          "Perfil cauteloso. Concessionária grande, em 90% da meta; caixa apertado.")),
    "E05": dict(nombre=("Daniel Acosta", "Daniel Assis"), genero="m", edad=58,
                titulo_pt="Mineração / energia",
                consigna_pt="Propor 50 Hilux com suporte de manutenção.",
                contexto=("Perfil dominante. Concesionario grande, al 115% de su objetivo; caja sólida.",
                          "Perfil dominante. Concessionária grande, em 115% da meta; caixa sólido.")),
    "E06": dict(nombre=("Mónica Ruiz", "Mônica Rocha"), genero="f", edad=49,
                titulo_pt="Pessoas com deficiência (PcD) / diplomatas",
                consigna_pt="Designar um responsável e melhorar o acompanhamento das solicitações.",
                contexto=("Perfil relacional. Concesionario pequeño, al 80% de su objetivo; caja estable.",
                          "Perfil relacional. Concessionária pequena, em 80% da meta; caixa estável.")),
}


# El Excel nombra a veces al mismo concesionario con la zona entre paréntesis. Para que aparezca
# una sola vez en la pantalla se unifica el nombre y la zona pasa al detalle.
NOMBRES = {
    "Ginza (Rosario / Monte Maíz)": ("Ginza", "Rosario / Monte Maíz"),
    "Toyopar (PR)": ("Toyopar", "Paraná"),
    "Osaka (MG)": ("Osaka", "Minas Gerais"),
    "Inter Japan (SP)": ("Inter Japan SP", ""),
    "Terra Forte (Nova Lima)": ("Terra Forte", "Nova Lima"),
}


def unificar(ref: dict) -> dict:
    nombre, zona = NOMBRES.get(ref["nombre"], (ref["nombre"], ""))
    detalle = "; ".join(x for x in (zona, ref["detalle"]) if x)
    return {**ref, "nombre": nombre, "detalle": detalle}


def limpio(texto) -> str:
    return re.sub(r"\s+", " ", str(texto or "")).strip()


def referencias(texto: str, fuentes: str) -> list[dict]:
    """'Ginza; Milanesio — Toyota 10 publicado.' -> [{nombre: Ginza, ...}, {nombre: Milanesio, ...}].
    'Treos — Hilux minería; Nippon Car — taller móvil' -> cada uno con su propio detalle."""
    urls = [u.strip() for u in (fuentes or "").split(";") if u.strip()]
    partes = [p.strip() for p in limpio(texto).rstrip(".").split(";") if p.strip()]
    salida, pendientes, grupo = [], [], []
    for parte in partes:
        if "—" in parte:
            nombre, detalle = (x.strip() for x in parte.split("—", 1))
            # 'Ginza; Milanesio — X': los nombres sueltos antes del guion comparten el detalle.
            grupo = [{"nombre": n, "detalle": detalle} for n in pendientes + [nombre]]
            salida += grupo
            pendientes = []
        elif grupo:
            # 'Osaka — garantía y posventa; condiciones locales': sigue el detalle anterior.
            for ref in grupo:
                ref["detalle"] += "; " + parte
        else:
            pendientes.append(parte)
    salida += [{"nombre": p, "detalle": ""} for p in pendientes]
    for i, ref in enumerate(salida):
        ref["fuente"] = urls[i] if len(urls) == len(salida) else (urls[0] if urls else "")
    return [unificar(r) for r in salida]


def main(ruta_excel: str) -> None:
    libro = openpyxl.load_workbook(ruta_excel, data_only=True)
    filas = [f for f in libro["Escenarios IA"].iter_rows(values_only=True) if f and f[0]]
    filas = filas[next(i for i, f in enumerate(filas) if limpio(f[0]) == "ID"):]  # saltea el título
    encabezado = [limpio(c) for c in filas[0]]
    fuentes = {f[0]: f for f in libro["Referencias AR-BR"].iter_rows(values_only=True) if f and f[0]}
    creadas = []
    for fila in filas[1:]:
        dato = dict(zip(encabezado, fila))
        caso = limpio(dato["ID"])
        if caso not in EXTRA:
            print(f"Salteado {caso}: falta su dueño ficticio y la traducción en EXTRA.")
            continue
        extra = EXTRA[caso]
        foco = FOCOS[limpio(dato["V1 · Área"])]
        perfil_excel = limpio(dato["V2 · Dueño y desempeño"])
        estilo = next((v for k, v in ESTILOS.items() if perfil_excel.startswith(k)), perfil_excel)
        ref = fuentes.get(caso, [None] * 5)
        ficha = {
            "id": caso,
            "origen": "Banco de escenarios Toyota (Excel), perfil y desempeño ficticios",
            "foco": foco,
            "dificultad": limpio(dato["Dificultad"]).lower(),
            "titulo": {"es": limpio(dato["Producto / servicio"]), "pt": extra["titulo_pt"]},
            "consigna": {"es": limpio(dato["Objetivo terminal (simulado)"]).rstrip(".") + ".", "pt": extra["consigna_pt"]},
            "contexto_visible": {"es": extra["contexto"][0], "pt": extra["contexto"][1]},
            "dueno": {
                "nombre": {"ar": extra["nombre"][0], "br": extra["nombre"][1]},
                "edad": extra["edad"],
                "genero": extra["genero"],
                "perfil": estilo,
            },
            "concesionario": extra["contexto"][0],
            "situacion": f"La reunión es sobre {limpio(dato['Producto / servicio'])}.",
            "objecion_inicial": limpio(dato["V3 · Objeción inicial"]),
            "interes_oculto": limpio(dato["V3 · Interés oculto"]),
            "objeciones": [limpio(dato["V3 · Objeción inicial"])],
            "que_lo_mueve": [limpio(dato["V4 · Qué lo hace ceder"])],
            "limite": f"Máximo acuerdo: {limpio(dato['V4 · Máximo acuerdo'])}",
            "no_negociable": limpio(dato["V4 · No negociable"]),
            "referencias": {
                "ar": referencias(dato["Concesionarios Argentina · referencia"], ref[2]),
                "br": referencias(dato["Concesionarias Brasil · referencia"], ref[4]),
            },
        }
        destino = RAIZ / "escenarios" / foco / f"{caso}.yaml"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(
            "# Generado por scripts/importar_excel.py desde el banco de escenarios.\n"
            "# Referencias comerciales públicas; perfil, desempeño y cifras son ficticios.\n"
            + yaml.safe_dump(ficha, allow_unicode=True, sort_keys=False, width=100),
            encoding="utf-8",
        )
        creadas.append(destino.relative_to(RAIZ))
    print(f"{len(creadas)} fichas creadas:")
    for c in creadas:
        print(" ", c)


if __name__ == "__main__":
    main(sys.argv[1])
