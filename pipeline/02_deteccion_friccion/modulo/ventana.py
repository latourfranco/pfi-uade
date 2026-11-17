"""Ventana: las últimas VENTANA_SESIONES sesiones válidas y completas de un cliente (PLAN §14, "Ventana única").

Entrenamiento y corrida diaria leen la misma ventana. Cómo se arma (decidido con el usuario, 2026-11-15):

1. Se cuenta hacia atrás desde el último día con datos del cliente (no desde el calendario).
2. Se leen DIAS_INICIALES días, se mide cuántas sesiones completas da cada día y se trae en UNA consulta lo que
   falta con MARGEN de más. Si todavía no alcanza se repite. Todo lo leído se sesioniza junto, así una sesión
   que cruza el borde entre dos lecturas no queda partida.
3. Se descartan las sesiones que pueden estar cortadas en los bordes de lo leído:
   - borde reciente: termina a menos de SESION_SIN_ID_S (30 min, el corte de sesión de GA4) del último dato;
     puede seguir en curso y parecería un abandono;
   - borde viejo: empieza a menos de ese corte del primer dato leído; puede haber empezado antes.
   Los bordes se miden con el primer y el último evento reales de cada sesión (antes de sacar view_promotion o
   plegar scroll) y con los eventos que entran a la sesionización (sin user_engagement).
4. De las sesiones válidas (>= 4 eventos) y completas quedan las VENTANA_SESIONES que empiezan más tarde.

Si el cliente no tiene tantas en todo su histórico se devuelve lo que hay con completa=False; el
entrenamiento no corre por debajo de su umbral (decidido con el usuario, 2026-11-15).

La lectura entra como parámetro (leer(desde, hasta) -> eventos crudos, días inclusive); en producción es
lector_bigquery.
"""
import math
import os
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # raíz del repo
from modulo import registro  # noqa: E402
from modulo.config import VENTANA_SESIONES, SESION_SIN_ID_S  # noqa: E402
from modulo.preparar import preparar_con_limites  # noqa: E402

log = registro.logger("ventana")

DIAS_INICIALES = 7   # una semana: cubre el ciclo semanal del tráfico en la primera estimación
MARGEN = 1.2         # 20% de días de más en la segunda lectura, para que casi siempre alcance con 2 consultas

Lector = Callable[[date, date], pd.DataFrame]


@dataclass
class Ventana:
    eventos: pd.DataFrame       # eventos preparados de las sesiones de la ventana, por sesión y tiempo
    sesiones: int
    completa: bool              # llegó a VENTANA_SESIONES
    desde: date                 # días leídos, inclusive
    hasta: date
    consultas: int
    crudos_leidos: int
    descartadas_borde: int      # sesiones válidas que se sacaron por poder estar cortadas
    sesionizacion: dict         # resumen de preparar_con_limites sobre todo lo leído


def sesiones_completas(limites: pd.DataFrame, validas: pd.Index, corte_s: float) -> pd.DataFrame:
    """Límites de las sesiones válidas que no tocan ningún borde de lo leído."""
    corte = pd.Timedelta(seconds=corte_s)
    primero, ultimo = limites["inicio"].min(), limites["fin"].max()
    lim = limites[limites["session_id"].isin(validas)]
    ok = (lim["inicio"] >= primero + corte) & (lim["fin"] <= ultimo - corte)
    return lim[ok]


def armar_ventana(leer: Lector, primer_dia: date, ultimo_dia: date, n: int = VENTANA_SESIONES,
                  corte_s: float = SESION_SIN_ID_S) -> Ventana:
    with registro.paso(log, "Ventana y sesionización", sesiones_buscadas=n, ultimo_dia=str(ultimo_dia)) as res:
        desde = max(primer_dia, ultimo_dia - timedelta(days=DIAS_INICIALES - 1))
        crudos = [leer(desde, ultimo_dia)]
        while True:
            eventos = pd.concat(crudos, ignore_index=True)
            prep, limites, resumen = preparar_con_limites(eventos, corte_s)
            validas = pd.Index(prep["session_id"].unique())
            completas = sesiones_completas(limites, validas, corte_s)
            dias = (ultimo_dia - desde).days + 1
            log.info(f"Lectura {len(crudos)}: {dias} días ({desde} a {ultimo_dia}), "
                     f"{len(completas):,} sesiones completas", extra={"paso": "Ventana y sesionización"})
            if len(completas) >= n or desde <= primer_dia:
                break
            faltan = n - len(completas)
            extra = dias if len(completas) == 0 else math.ceil(faltan / (len(completas) / dias) * MARGEN)
            nuevo_desde = max(primer_dia, desde - timedelta(days=extra))
            crudos.insert(0, leer(nuevo_desde, desde - timedelta(days=1)))
            desde = nuevo_desde

        elegidas = completas.nlargest(n, "inicio")["session_id"]   # las que empiezan más tarde
        ev = prep[prep["session_id"].isin(elegidas)].reset_index(drop=True)
        v = Ventana(eventos=ev, sesiones=len(elegidas), completa=len(elegidas) >= n, desde=desde,
                    hasta=ultimo_dia, consultas=len(crudos), crudos_leidos=len(eventos),
                    descartadas_borde=len(validas) - len(completas), sesionizacion=resumen)
        res.update(sesiones=v.sesiones, completa=v.completa, dias=f"{desde} a {ultimo_dia}", consultas=v.consultas,
                   eventos_crudos=v.crudos_leidos, descartadas_borde=v.descartadas_borde,
                   pct_eventos_sin_id_sesion=resumen["pct_eventos_sin_id_sesion"])
        if not v.completa:
            log.warning(f"El cliente tiene {v.sesiones:,} sesiones completas en todo su histórico, menos que {n:,}",
                        extra={"paso": "Ventana y sesionización"})
    return v


# --- Lector ------------------------------------------------------------------------------------------------

def lector_bigquery(cliente_id: str) -> tuple[Lector, date, date]:
    from ingesta.clientes import buscar_fuente
    from ingesta.config_nube import cargar_config
    from ingesta.eventos import leer_eventos, rango_fechas
    cfg = cargar_config()
    fuente = buscar_fuente(cliente_id, cfg.supabase_db_url)
    rango = rango_fechas(fuente, cfg.gcp_project)
    if rango is None:
        raise RuntimeError(f"El cliente {cliente_id} no tiene eventos en {fuente.tabla}")
    return (lambda d, h: leer_eventos(fuente, cfg.gcp_project, d, h)), rango[0], rango[1]
