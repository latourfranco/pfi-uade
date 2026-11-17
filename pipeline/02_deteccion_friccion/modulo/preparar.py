"""Eventos crudos del cliente (formato de ingesta/) -> sesiones válidas.

Funciones de preprocesamiento/preprocessing.py, salvo la sesionización:

    drop_engagement_pings -> sesionizar -> drop_promo_and_load_views -> fold_scroll_events
    -> filter_sessions (>= 4 eventos)

Lo que viene después (normalización de rutas, orden de eventos simultáneos, nodos) se aprende en el
entrenamiento y queda guardado con el modelo, así que no va acá.

Sesión (2026-11-15): la de GA4. Cada evento trae id_sesion (ga_session_id: inicio de la sesión en segundos,
único por usuario). Si no la trae, se calcula como GA4: corte por SESION_SIN_ID_S de inactividad entre los
eventos sin sesión del usuario, y el inicio en segundos hace de id_sesion. El id de sesión del módulo es
<id_usuario>_<id_sesion>: estable entre corridas porque no depende de desde dónde se leyó.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # raíz del repo
from preprocesamiento.preprocessing import (drop_engagement_pings, _parse_timestamp,  # noqa: E402
                                            drop_promo_and_load_views, fold_scroll_events, filter_sessions)


def sesionizar(df: pd.DataFrame, corte_sin_id_s: float) -> tuple[pd.DataFrame, int]:
    """Agrega session_id (<id_usuario>_<id_sesion>) y delta_t_prev (segundos desde el evento anterior de la
    sesión, 0 en el primero), como preprocessing.sessionize. Devuelve también cuántos eventos no traían
    id_sesion y se sesionizaron con el corte."""
    df = df.copy()
    df["timestamp"] = _parse_timestamp(df["timestamp"])
    # stable: los eventos del mismo instante conservan el orden de la fuente (igual que sessionize)
    df = df.sort_values(["id_usuario", "timestamp"], kind="stable").reset_index(drop=True)
    sid = pd.to_numeric(df["id_sesion"], errors="coerce").astype("Int64") if "id_sesion" in df else \
        pd.Series(pd.NA, index=df.index, dtype="Int64")
    falta = sid.isna()
    if falta.any():
        s = df.loc[falta, ["id_usuario", "timestamp"]]
        gap = s.groupby("id_usuario")["timestamp"].diff().dt.total_seconds()
        nueva = gap.isna() | (gap > corte_sin_id_s)
        n = nueva.groupby(s["id_usuario"]).cumsum()
        inicio = s["timestamp"].groupby([s["id_usuario"], n]).transform("min")
        sid.loc[falta] = ((inicio - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(seconds=1)).to_numpy()
    df["id_sesion"] = sid
    df["session_id"] = df["id_usuario"].astype(str) + "_" + sid.astype(str)
    df = df.sort_values(["session_id", "timestamp"], kind="stable").reset_index(drop=True)
    df["delta_t_prev"] = df.groupby("session_id")["timestamp"].diff().dt.total_seconds().fillna(0.0)
    return df, int(falta.sum())


def preparar_con_limites(eventos: pd.DataFrame, corte_sin_id_s: float) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Como preparar_sesiones, y además:
    - los límites de TODAS las sesiones (también las de < 4 eventos): session_id, inicio, fin, tomados justo
      después de sesionizar. Los usa la ventana para saber qué sesiones pueden estar cortadas en los bordes de
      lo leído (después de sacar view_promotion o plegar scroll el primer y el último evento ya no son los
      reales);
    - un resumen para el log: eventos, sesiones, sesiones válidas y cuántos eventos no traían id_sesion."""
    df = drop_engagement_pings(eventos)
    df, sin_id = sesionizar(df, corte_sin_id_s)
    limites = (df.groupby("session_id", sort=False)["timestamp"].agg(inicio="min", fin="max").reset_index())
    df = drop_promo_and_load_views(df)
    df = fold_scroll_events(df)
    df = filter_sessions(df)
    df = df.sort_values(["session_id", "timestamp"], kind="stable").reset_index(drop=True)
    resumen = dict(eventos_crudos=len(eventos), sesiones=len(limites), sesiones_validas=df["session_id"].nunique(),
                   eventos_sin_id_sesion=sin_id,
                   pct_eventos_sin_id_sesion=round(100 * sin_id / max(len(eventos), 1), 2))
    return df, limites, resumen


def preparar_sesiones(eventos: pd.DataFrame, corte_sin_id_s: float) -> pd.DataFrame:
    """Eventos de un cliente -> eventos de sus sesiones válidas, ordenados por sesión y tiempo."""
    return preparar_con_limites(eventos, corte_sin_id_s)[0]

