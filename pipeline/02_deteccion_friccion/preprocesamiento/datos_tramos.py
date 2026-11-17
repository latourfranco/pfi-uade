"""Orden de los eventos simultáneos (lo usa modulo/nodos.py).

Los eventos de la misma página a menos de SIMULTANEO_S del anterior son un solo momento, y dentro de él el
orden es fijo, aprendido de los datos (orden_tipico). El orden de registro de eventos casi simultáneos es
ruido: add_shipping_info / begin_checkout salen 0,0014 s separados en la mediana, a veces en un orden y a
veces en el otro (revisión de los patrones con el usuario, 2026-10-29).
"""
import pandas as pd

SIMULTANEO_S = 1.0


def orden_tipico(df: pd.DataFrame) -> dict[str, float]:
    """Orden de los tipos de evento dentro de un momento simultáneo, sacado de los datos:
    posición típica en la visita. Visita = racha de eventos en la misma página. En cada visita
    con dos o más tipos distintos se ordenan los tipos por su primera aparición; el puntaje de
    un tipo es su lugar promedio relativo (0 = primero, 1 = último). Menor = más adelante."""
    g = df.groupby("session_id", sort=False)
    visita = (df.plantilla_ruta != g.plantilla_ruta.shift(1)).cumsum()
    primeros = df.assign(visita=visita).drop_duplicates(["visita", "nombre_evento"])
    tipos = primeros.groupby("visita").nombre_evento.transform("size")
    primeros = primeros[tipos >= 2]
    lugar = primeros.groupby("visita").cumcount() / (tipos[tipos >= 2] - 1)
    return lugar.groupby(primeros.nombre_evento).mean().to_dict()
