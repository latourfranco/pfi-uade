"""Preprocesamiento aprendido en el entrenamiento y secuencias de nodos (lo que ve la red).

Se aprende una vez por cliente, sobre su ventana, y se guarda con el modelo:
- reglas de rutas (preprocessing.ajustar_rutas): plantilla estructural de las URLs, §3.2;
- orden de los eventos simultáneos (datos_tramos.orden_tipico);
- grupos de páginas (agrupar_paginas): recalculados por cliente (decidido con el usuario, 2026-11-15), solo dentro de
  cada sección de la URL;
- vocabulario de nodos.

Nodo = evento@página, con página = grupo de la página (o su plantilla si quedó sola). Ningún evento se ignora:
los eventos clave los elige el LLM y todos van en la secuencia.
"""
import hashlib
import os
import sys

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import jensenshannon, pdist

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # raíz del repo
from preprocesamiento.preprocessing import ajustar_rutas, aplicar_rutas  # noqa: E402
from preprocesamiento.datos_tramos import orden_tipico, SIMULTANEO_S  # noqa: E402

INICIO = "inicio_de_sesion"   # marca de entrada a la sesión (primer nodo de cada secuencia)
OTRO = "OTRO"                 # evento no visto al entrenar; evento@OTRO = evento visto en una página no vista
MIN_ACCIONES = 30             # mismo valor que grupos.py: menos acciones no alcanzan para la firma de la página


def es_reserva(usuarios) -> np.ndarray:
    """Usuarios reservados (md5 % 5 == 0): parada temprana, calibración y AUC. El mismo hash que la comparación."""
    return np.array([int(hashlib.md5(str(u).encode()).hexdigest(), 16) % 5 == 0 for u in usuarios])


def _seccion(pagina: str) -> str:
    """Primer tramo de la ruta ('' para la raíz): /shop/apparel/mens -> shop, /checkout?show=x -> checkout."""
    return pagina.split("?")[0].split("#")[0].strip("/").split("/")[0]


def agrupar_paginas(df: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    """Grupos de páginas por composición de acciones, dentro de cada sección de la URL.

    Método de grupos.py (2026-10-29): visita = page_view + los eventos siguientes en la misma plantilla hasta el
    próximo page_view; firma de una página = proporción de cada tipo de acción (eventos que no son page_view)
    entre sus acciones; distancia Jensen-Shannon, clustering jerárquico (average) y corte en el mayor salto
    entre alturas de fusión. Páginas con menos de MIN_ACCIONES acciones no tienen evidencia.

    Solo se agrupan páginas de la MISMA sección (decidido con el usuario, 2026-11-15): calculado en todo el sitio,
    los paneles que se abren sobre cualquier página (login, carrito, mi cuenta) dominaban la firma y juntaban el
    inicio con el carrito, y el corte único dejaba la ficha de producto con los listados. Una sección con menos
    de 3 páginas con evidencia no se agrupa (con 2 no hay saltos que comparar). Sin evidencia: hereda el grupo
    de sus hermanas (mismo padre en la ruta) si todas las hermanas con evidencia están en un único grupo.
    Un grupo de una sola página no es grupo: la página queda con su plantilla.
    Solo usuarios no reservados. Devuelve {plantilla: nombre del grupo o 'sola'} y la tabla para el log."""
    ref = df[~es_reserva(df.id_usuario)].sort_values(["session_id", "timestamp"], kind="stable").copy()
    ref["visita"] = (ref.nombre_evento == "page_view").groupby(ref.session_id).cumsum()
    pv = ref[ref.nombre_evento == "page_view"].set_index(["session_id", "visita"]).plantilla_ruta
    acc = ref[(ref.nombre_evento != "page_view") & (ref.visita > 0)]
    pagina_visita = pv.reindex(pd.MultiIndex.from_arrays([acc.session_id, acc.visita])).values
    acc = acc[acc.plantilla_ruta.values == pagina_visita]
    visitas = ref[ref.nombre_evento == "page_view"].plantilla_ruta.value_counts()
    comp = acc.groupby(["plantilla_ruta", "nombre_evento"]).size().unstack(fill_value=0)
    n_acc = comp.sum(axis=1).reindex(visitas.index, fill_value=0)
    elegibles = list(n_acc[n_acc >= MIN_ACCIONES].index)

    grupo_de: dict[str, tuple] = {}   # página con evidencia -> (sección, número de grupo en la sección)
    for sec in sorted({_seccion(p) for p in elegibles}):
        pags = [p for p in elegibles if _seccion(p) == sec]
        if len(pags) < 3:
            continue
        P = comp.loc[pags].div(comp.loc[pags].sum(axis=1), axis=0)
        Z = linkage(pdist(P.values, metric=jensenshannon), method="average")
        alturas = Z[:, 2]; saltos = np.diff(alturas)
        etiqueta = fcluster(Z, alturas[np.argmax(saltos)] + saltos.max() / 2, criterion="distance")
        grupo_de.update({p: (sec, int(g)) for p, g in zip(pags, etiqueta)})

    def padre(pg):
        path = pg.split("?")[0].split("#")[0].rstrip("/")
        return path.rsplit("/", 1)[0] if path.count("/") > 1 else None

    final = dict(grupo_de)
    for pg in visitas.index.difference(elegibles):
        g, nivel = None, padre(pg)
        while nivel is not None and g is None:
            hermanas = {grupo_de[h] for h in grupo_de if h != pg and h.split("?")[0].startswith(nivel + "/")}
            if len(hermanas) == 1:
                g = hermanas.pop()
            elif len(hermanas) > 1:
                break
            nivel = padre(nivel)
        if g is not None:
            final[pg] = g
    # nombres legibles; un grupo de una sola página no es grupo
    miembros = pd.Series(final).groupby(lambda p: final[p]).size()
    por_seccion = pd.Series([k for k in miembros.index if miembros[k] > 1]).map(lambda k: k[0]).value_counts()
    nombre = {}
    for k in miembros.index:
        if miembros[k] > 1:
            sec, n = k
            base = f"/{sec}/…" if sec else "/…"
            nombre[k] = base + (f" ({n})" if por_seccion.get(sec, 0) > 1 else "")
    grupos = {p: nombre.get(final.get(p), "sola") for p in visitas.index}
    tabla = pd.DataFrame({"pagina": list(grupos), "grupo": list(grupos.values())})
    tabla["visitas"] = tabla.pagina.map(visitas).fillna(0).astype(int)
    return grupos, tabla


def aprender(prep: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    """Reglas de rutas, orden de eventos simultáneos y grupos de páginas, aprendidos de la ventana."""
    reglas = ajustar_rutas(prep)
    df = aplicar_rutas(prep, reglas).sort_values(["session_id", "timestamp"], kind="stable")
    orden = orden_tipico(df)
    grupos, tabla = agrupar_paginas(df)
    return dict(reglas_rutas=reglas, orden_eventos=orden, grupos=grupos), tabla


def secuencias(prep: pd.DataFrame, apr: dict, con_filas: bool = False):
    """Una fila por sesión: tok (lista de nodos), user, ini (hora del primer nodo).
    Igual que datos_tramos.cargar("grupo", momentos=True, misma=True, recargas=True) sin eventos ignorados.
    con_filas: además, por sesión, las filas de eventos de cada nodo (filas, n_filas: posiciones en el
    DataFrame de eventos que también se devuelve), para armar la sesión representativa."""
    df = aplicar_rutas(prep, apr["reglas_rutas"]).sort_values(["session_id", "timestamp"], kind="stable")
    df = df.reset_index(drop=True)
    g = df.groupby("session_id", sort=False)
    # recarga: page_view de la misma URL exacta que el evento anterior, que también fue ese page_view
    df["recarga"] = ((df.nombre_evento == "page_view") & (g.nombre_evento.shift(1) == "page_view")
                     & (df.ruta == g.ruta.shift(1)))
    nuevo = (((df.plantilla_ruta != g.plantilla_ruta.shift(1))
              | ((df.timestamp - g.timestamp.shift(1)).dt.total_seconds() >= SIMULTANEO_S)) & ~df.recarga)
    df["momento"] = nuevo.groupby(df.session_id).cumsum()
    df["orden_ev"] = df.nombre_evento.map(apr["orden_eventos"]).fillna(0.5)
    df = df.sort_values(["session_id", "momento", "orden_ev", "timestamp"], kind="stable")
    grupos = apr["grupos"]
    pagina = df.plantilla_ruta.map(lambda p: p if grupos.get(p, "sola") == "sola" else grupos[p])
    df["tok"] = df.nombre_evento + "@" + pagina
    pv = df[(df.nombre_evento == "page_view") & ~df.recarga]
    repite = pv.plantilla_ruta == pv.groupby("session_id").plantilla_ruta.shift(1)
    df.loc[repite[repite].index, "tok"] += "·misma"
    df["nodo"] = (~df.recarga).groupby(df.session_id).cumsum()
    df["fila"] = np.arange(len(df))
    m = df.groupby(["session_id", "nodo"], sort=False).agg(tok=("tok", "first"), user=("id_usuario", "first"),
                                                          ts=("timestamp", "first"), filas=("fila", list)).reset_index()
    agg = dict(tok=("tok", list), user=("user", "first"), ini=("ts", "first"))
    if con_filas:
        agg.update(filas=("filas", lambda x: [f for l in x for f in l]), n_filas=("filas", lambda x: [len(l) for l in x]))
    ses = m.groupby("session_id", sort=False).agg(**agg).sort_values("ini")
    return (ses, df.reset_index(drop=True)) if con_filas else ses


def vocabulario(ses: pd.DataFrame) -> dict[str, int]:
    vistos = {t for ts in ses.tok for t in ts}
    eventos = {t.split("@")[0] for t in vistos}
    return {t: i for i, t in enumerate(sorted(vistos | {INICIO, OTRO} | {f"{e}@{OTRO}" for e in eventos}))}


def a_ids(ses: pd.DataFrame, vocab: dict[str, int]) -> list[np.ndarray]:
    def nodo(t):
        if t in vocab:
            return vocab[t]
        return vocab.get(f"{t.split('@')[0]}@{OTRO}", vocab[OTRO])
    return [np.fromiter((nodo(t) for t in [INICIO] + list(ts)), dtype=np.int64, count=len(ts) + 1) for ts in ses.tok]
