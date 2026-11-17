"""Selección de los patrones que se publican (PLAN §14, "Selección de patrones", 2026-11-16).

Sobre los patrones de un cliente (deteccion.detectar), antes de escribir. Plan del usuario
(PLAN_SELECCION_PATRONES_DETECCION.md), con un cambio acordado el 2026-11-16 para no meter vocabulario
de un sitio en el módulo:
1. Impacto positivo: solo sesiones_perdidas > 0. Orden: sesiones_perdidas desc, sesiones desc, id_patron asc.
2. Un punto de fricción = (objetivo, paso de la fricción). El paso es el último de la secuencia, en el vocabulario
   de páginas del modelo (plantilla estructural, §3.2), no la URL de la sesión de ejemplo (el plan filtraba
   parámetros por nombre). Por punto queda el de más impacto de cada formato: mobile o desktop (tablet y el resto
   van con desktop). El formato es el del paso de fricción de la sesión representativa, como en el plan (el
   usuario decidió que no importa si no coincide con la mayoría del grupo, 2026-11-16).
3. Hasta PISO_POR_OBJETIVO por objetivo (que ningún escalón del embudo quede afuera por tener menos volumen) y
   después, por impacto, hasta cubrir CUOTA de las sesiones perdidas de los deduplicados.
Cada cliente se evalúa solo: esto corre dentro de su tarea.
"""
from modulo.escritura import id_patron

PISO_POR_OBJETIVO = 2
CUOTA = 0.70


def formato(p: dict) -> str:
    """mobile o desktop según el paso de fricción de la sesión representativa (si hay varios eventos, el último;
    sin marca, el último paso de la sesión)."""
    pasos = [x for x in p["pasos"] if x["es_paso_friccion"]] or p["pasos"]
    disp = (pasos[-1].get("tipo_dispositivo") or "") if pasos else ""
    return "mobile" if disp.strip().lower() == "mobile" else "desktop"


def seleccionar(patrones: list[dict], id_cliente: str) -> tuple[list[dict], dict]:
    """Devuelve (seleccionados en orden de impacto, resumen de las etapas para el log)."""
    ids = {id(p): id_patron(id_cliente, p["objetivo"], p["secuencia"]) for p in patrones}
    e1 = sorted((p for p in patrones if p["sesiones_perdidas"] > 0),
                key=lambda p: (-p["sesiones_perdidas"], -p["sesiones"], ids[id(p)]))
    vistos, dedup = set(), []
    for p in e1:
        punto = (p["objetivo"], p["secuencia"][-1], formato(p))
        if punto not in vistos:
            vistos.add(punto); dedup.append(p)
    total = sum(p["sesiones_perdidas"] for p in dedup)
    por_objetivo: dict[str, int] = {}
    elegidos = set()
    for p in dedup:
        if por_objetivo.get(p["objetivo"], 0) < PISO_POR_OBJETIVO:
            por_objetivo[p["objetivo"]] = por_objetivo.get(p["objetivo"], 0) + 1
            elegidos.add(id(p))
    cubierto = sum(p["sesiones_perdidas"] for p in dedup if id(p) in elegidos)
    for p in dedup:
        if cubierto >= CUOTA * total:
            break
        if id(p) not in elegidos:
            elegidos.add(id(p)); cubierto += p["sesiones_perdidas"]
    sel = [p for p in dedup if id(p) in elegidos]
    resumen = dict(detectados=len(patrones), impacto_positivo=len(e1),
                   perdidas_positivas=round(sum(p["sesiones_perdidas"] for p in e1), 2),
                   deduplicados=len(dedup), perdidas_deduplicados=round(total, 2), seleccionados=len(sel),
                   perdidas_seleccionados=round(cubierto, 2),
                   cobertura=round(cubierto / total, 4) if total else None)
    return sel, resumen
