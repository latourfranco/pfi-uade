"""Eventos clave del cliente (los objetivos del embudo), elegidos por un LLM a partir de un resumen de sus datos.

Decidido con el usuario (2026-11-15): el export de GA4 a BigQuery no trae qué eventos marcó el cliente como
"key events", así que un LLM los elige con la consigna "el objetivo del sitio es la conversión". Es
configuración de negocio, no detección: el LLM nombra los hitos; el ORDEN entre ellos lo sigue aprendiendo el
motor de los datos, y la detección sigue siendo no supervisada.

- Se decide UNA vez por cliente, en el entrenamiento, y se guarda con el modelo (si cambiara cada día cambiarían
  los objetivos y los id_patron).
- El LLM recibe solo un resumen agregado por tipo de evento: nada de usuarios, sesiones ni valores puntuales.
- Cada evento elegido trae un nombre legible para el cliente y el motivo.
- Solo los hitos principales (no cada paso de un mismo proceso), con una consigna que no nombra eventos ni tipos
  de sitio: el módulo es agnóstico a la aplicación que analiza.
"""
import json

import numpy as np
import pandas as pd

import modulo.config  # noqa: F401  (agrega la raíz del repo a sys.path)
from preprocesamiento.preprocessing import ajustar_rutas, aplicar_rutas

TOP = 3        # páginas y eventos anteriores más frecuentes que se muestran por evento
TOP_POSTERIORES = 5   # eventos posteriores: con 3 los muy frecuentes tapaban el camino hacia adelante
# page_view es el evento de navegación universal de GA4 (no de un tipo de sitio): sigue a casi todo, así que como
# "evento posterior" no informa nada y taparía a los demás.
NAVEGACION_GA4 = ("page_view",)


def _posteriores(df: pd.DataFrame) -> dict:
    """Por evento X: de las sesiones que tienen X, en qué % aparece cada otro evento MÁS ADELANTE (después de la
    primera vez que ocurre X). No necesita saber cuál es la conversión: muestra hacia dónde suele seguir el camino."""
    pos = df.groupby("session_id", sort=False).cumcount()
    primera = pd.Series(pos.values, index=[df["session_id"], df["nombre_evento"]]).groupby(level=[0, 1]).min().unstack()
    ultima = pd.Series(pos.values, index=[df["session_id"], df["nombre_evento"]]).groupby(level=[0, 1]).max().unstack()
    out = {}
    for x in primera.columns:
        tiene = primera[x].notna()
        fx = primera.loc[tiene, x].to_numpy()[:, None]
        despues = (ultima.loc[tiene].to_numpy() > fx)   # NaN > n da False
        pct = pd.Series(100 * despues.mean(axis=0), index=ultima.columns)
        pct = pct.drop([x, *[e for e in NAVEGACION_GA4 if e in pct.index]]).sort_values(ascending=False).head(TOP_POSTERIORES)
        out[x] = {e: round(float(v), 1) for e, v in pct.items() if v > 0}
    return out


def _con_items(s: pd.Series) -> pd.Series:
    t = s.astype("string").str.strip()
    return s.notna() & ~t.isin(["", "[]", "null", "None"])


def resumir_eventos(sesiones: pd.DataFrame) -> dict:
    """Resumen agregado por tipo de evento de las sesiones ya preparadas (preparar.preparar_sesiones).

    Por evento: en cuántas sesiones y usuarios aparece, en qué parte de la sesión (0 = al empezar, 1 = al
    terminar), cuántas veces es el último evento, si lleva items (campo items de GA4), en qué páginas ocurre y qué
    evento suele venir justo antes y qué eventos suelen venir después en la sesión. Las páginas van como plantilla de ruta (los ids y textos libres quedan
    como {param}), aprendida sobre estos mismos datos."""
    df = aplicar_rutas(sesiones, ajustar_rutas(sesiones))
    g = df.groupby("session_id", sort=False)
    pos = g.cumcount()
    largo = g["nombre_evento"].transform("size")
    df = df.assign(pos_rel=np.where(largo > 1, pos / (largo - 1).clip(lower=1), 0.0),
                   ultimo=pos == largo - 1, anterior=g["nombre_evento"].shift(1),
                   con_items=_con_items(df["items"]))
    n_ses, n_us = df["session_id"].nunique(), df["id_usuario"].nunique()
    post = _posteriores(df)

    eventos = []
    for ev, d in df.groupby("nombre_evento", sort=False):
        ses = d["session_id"].nunique()
        pag = d["plantilla_ruta"].value_counts(normalize=True).head(TOP)
        ant = d["anterior"].fillna("(inicio de la sesión)").value_counts(normalize=True).head(TOP)
        eventos.append(dict(
            evento=ev,
            pct_sesiones=round(100 * ses / n_ses, 2),
            sesiones=int(ses),
            usuarios=int(d["id_usuario"].nunique()),
            veces_por_sesion_que_lo_tiene=round(len(d) / ses, 2),
            posicion_en_la_sesion_mediana=round(float(d["pos_rel"].median()), 2),
            pct_es_el_ultimo_evento=round(100 * float(d["ultimo"].mean()), 1),
            pct_lleva_items=round(100 * float(d["con_items"].mean()), 1),
            paginas_frecuentes={p: round(100 * v, 1) for p, v in pag.items()},
            evento_anterior_frecuente={a: round(100 * v, 1) for a, v in ant.items()},
            pct_sesiones_con_evento_posterior=post[ev],
        ))
    eventos.sort(key=lambda e: -e["sesiones"])
    return dict(sesiones=int(n_ses), usuarios=int(n_us),
                eventos_por_sesion_mediana=float(largo.groupby(df["session_id"]).first().median()),
                eventos=eventos)


# ---------------------------------------------------------------------------------------------- consulta
# Revisado con el usuario (2026-11-15): solo los hitos PRINCIPALES, sin un campo aparte para la conversión, y una
# consigna que sirva para cualquier sitio (el módulo es agnóstico a la aplicación). Iteraciones:
# v1 elección directa con dos criterios: los entendía pero no los aplicaba parejo (dejaba varios pasos de un
#    mismo proceso, o sumaba una vista de contenido).
# v2 clasificar cada evento + regla fija por etapa: agrupaba bien los procesos, pero la regla perdía hitos claros
#    y entraban acciones que no llevan al objetivo (quitar del carrito, promociones, login).
# v3 elección directa con el dato de eventos posteriores: "uno por proceso" escrito en un párrafo no se aplicaba;
#    elegía todos los pasos de un mismo proceso en los tres casos de prueba.
# v4 (vigente, con modo pensamiento: config.LLM_PARAMETROS) la RESPUESTA se organiza por etapas: el modelo lista los eventos de cada proceso y elige uno solo;
#    el objetivo va siempre como etapa propia. Seleccionar o ver un elemento es navegación (el hito es la acción
#    que lo compromete). El usuario prefirió iterar la consigna antes que sumar pasos o consultas. Se verifica con
#    resúmenes de otros tipos de sitio, sin ajustar la consigna a ellos.
ESQUEMA = {
    "type": "object",
    "properties": {
        "etapas": {
            "type": "array",
            "description": "Etapas del camino hacia el objetivo del sitio, cada una con un solo hito",
            "items": {
                "type": "object",
                "properties": {
                    "etapa": {"type": "string"},
                    "eventos_de_la_etapa": {"type": "array", "items": {"type": "string"}},
                    "es_el_objetivo_principal": {"type": "boolean"},
                    "hito": {"type": "string"},
                    "nombre_legible": {"type": "string"},
                    "motivo": {"type": "string"},
                },
                "required": ["etapa", "eventos_de_la_etapa", "es_el_objetivo_principal", "hito", "nombre_legible",
                             "motivo"],
            },
        },
    },
    "required": ["etapas"],
}

CONSIGNA = """Sos analista de producto digital. Te paso un resumen de cómo usan un sitio o aplicación web sus visitantes, agregado por tipo de evento de Google Analytics 4. No sabés de antemano qué tipo de sitio es: deducilo de los nombres de los eventos, las páginas y los números.

Tarea: describir las ETAPAS del camino del visitante hacia el objetivo principal del sitio (su conversión) y elegir UN hito por etapa.

Cómo armar las etapas:
1. Considerá solo las acciones deliberadas del visitante que lo hacen avanzar hacia el objetivo: decide, inicia, envía, agrega, reserva o confirma algo, y suelen estar seguidas más adelante por las etapas siguientes o por el objetivo (mirá pct_sesiones_con_evento_posterior).
2. Agrupá en una misma etapa los eventos que son pasos sucesivos de un mismo proceso (por ejemplo, las partes de un mismo formulario). Pista: suelen aparecer en casi la misma cantidad de sesiones y uno suele ser el evento anterior más frecuente del otro. Listalos todos en eventos_de_la_etapa.
3. De cada etapa, el hito es UNO solo de sus eventos: la acción con la que el visitante se compromete a empezar esa etapa.
4. El objetivo principal del sitio, la acción final que el negocio quiere que el visitante complete, va siempre como una etapa propia, con es_el_objetivo_principal en true, aunque sea el último paso de un proceso. Pista: suele ocurrir hacia el final de la sesión, ser muchas veces el último evento y aparecer en pocas sesiones.

No forman etapas ni son hitos:
- la navegación y el consumo de contenido: ver páginas, desplazarse, buscar, hacer clics genéricos, abrir menús, descargar material informativo;
- seleccionar, abrir o ver un elemento: el hito es la acción que lo compromete (agregarlo, guardarlo, reservarlo, enviarlo), no mirarlo;
- entrar con una cuenta que ya existe;
- las acciones que deshacen o hacen retroceder: quitar, cancelar, eliminar;
- las interacciones secundarias que no suelen llevar al objetivo.

Para cada etapa da: un nombre corto de etapa; los eventos de la etapa; el hito, con el nombre del evento exactamente como aparece en el resumen; un nombre corto y legible en español del hito para alguien del negocio; y un motivo de una línea que cite los números del resumen tal como están, sin reinterpretarlos. No hace falta ordenar las etapas: el orden se calcula aparte con los datos. Respondé solo con el JSON pedido."""


def mensajes(resumen: dict) -> list[dict]:
    return [{"role": "system", "content": CONSIGNA},
            {"role": "user", "content": "Resumen del sitio:\n" + json.dumps(resumen, ensure_ascii=False, indent=1)}]


def validar(respuesta: dict, resumen: dict) -> list[dict]:
    """Controles con los datos y devuelve los hitos (uno por etapa): cada hito existe, no se repite, es uno de los
    eventos de su etapa y hay al menos un objetivo principal. Si algo falla se lanza ValueError con el motivo (la
    corrida no entrena y lo registra). Que cada hito tenga llegadas suficientes se controla en el entrenamiento."""
    existentes = {e["evento"] for e in resumen["eventos"]}
    etapas = respuesta["etapas"]
    hitos = [et["hito"] for et in etapas]
    if not hitos:
        raise ValueError("el LLM no armó ninguna etapa")
    if no := sorted(set(hitos) - existentes):
        raise ValueError(f"hitos que no existen en los datos: {no}")
    if len(set(hitos)) != len(hitos):
        raise ValueError(f"hitos repetidos: {hitos}")
    if fuera := [et["hito"] for et in etapas if not et["es_el_objetivo_principal"] and et["hito"] not in et["eventos_de_la_etapa"]]:
        raise ValueError(f"hitos que no están entre los eventos de su etapa: {fuera}")
    if not any(et["es_el_objetivo_principal"] for et in etapas):
        raise ValueError("ninguna etapa marcada como objetivo principal")
    # el objetivo es una etapa propia (consigna, punto 4): si queda dentro de otro proceso, su hito sería otro evento
    if mal := [et["etapa"] for et in etapas if et["es_el_objetivo_principal"] and et["eventos_de_la_etapa"] != [et["hito"]]]:
        raise ValueError(f"el objetivo no quedó como etapa propia: {mal}")
    por_ev = {e["evento"]: e for e in resumen["eventos"]}
    return [dict(evento=et["hito"], nombre_legible=et["nombre_legible"], motivo=et["motivo"], etapa=et["etapa"],
                 eventos_de_la_etapa=et["eventos_de_la_etapa"], es_objetivo_principal=et["es_el_objetivo_principal"],
                 sesiones=por_ev[et["hito"]]["sesiones"]) for et in etapas]
