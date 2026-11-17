"""Fixtures compartidos y control de cobertura.

- Datos: clickstream sintético en memoria (tests/sinteticos.py). Ningún test lee datos reales ni toca la nube:
  Supabase, BigQuery, Cloud Storage, RunPod y el LLM se reemplazan por dobles.
- Pipeline: la ventana, el modelo entrenado y la detección se calculan una sola vez por corrida (scope session),
  con el umbral de entrenamiento y la paciencia de la red achicados para que entrenar tarde segundos.
- Cobertura: además del reporte de pytest-cov, la corrida falla si algún archivo, función o clase del módulo
  queda debajo de COBERTURA_MINIMA, en total (líneas + ramas) o en ramas solas. Son los mismos números que
  muestran los índices de reports/coverage_html (archivos, funciones y clases).
"""
import json
import logging
import os
import sys
from datetime import date

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from tests import sinteticos as S  # noqa: E402

COBERTURA_MINIMA = 85.0
REPORTE_JSON = os.path.join(RAIZ, "reports", "coverage.json")
CLIENTE = "cliente-prueba"
FECHA = "2021-01-21"


# ------------------------------------------------------------------------------------------- datos
@pytest.fixture
def crudos():
    return S.generar(n_usuarios=60, sesiones_por_usuario=2, sin_id=0.2)


@pytest.fixture(scope="session")
def crudos_pipeline():
    return S.generar(n_usuarios=160, sesiones_por_usuario=3, sin_id=0.1)


@pytest.fixture(scope="session")
def ventana(crudos_pipeline):
    from modulo import ventana as VEN
    return VEN.armar_ventana(S.lector(crudos_pipeline), date(2021, 1, 1), date(2021, 1, 20), n=100_000)


@pytest.fixture(scope="session")
def entrenado(ventana):
    """(modelo, fila del registro) entrenado una vez con los eventos clave a mano."""
    from modulo import entrenamiento as E, red as R
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(E, "UMBRAL_ENTRENAMIENTO", 50)
        mp.setattr(R, "PACIENCIA", 2)
        mp.setattr(R, "MIN_EP", 3)
        return E.entrenar_cliente(CLIENTE, ventana, FECHA, S.EVENTOS_CLAVE)


@pytest.fixture(scope="session")
def detectado(entrenado, ventana):
    """(patrones, resumen) de la detección sobre la misma ventana."""
    from modulo import deteccion
    return deteccion.detectar(entrenado[0], ventana.eventos, logging.getLogger("friccion.pruebas"))


# --------------------------------------------------------------------------- cobertura por archivo
@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtestloop(session):
    """Corre por fuera del de pytest-cov: cuando vuelve el yield, el reporte JSON ya está escrito."""
    resultado = yield
    if session.config.option.collectonly or not os.path.exists(REPORTE_JSON):
        return resultado
    with open(REPORTE_JSON, encoding="utf-8") as f:
        archivos = json.load(f)["files"]
    bajos = []
    for a, d in archivos.items():
        unidades = [("", d["summary"])] + [(f"::{n or '(módulo)'}", u["summary"])
                                           for nivel in ("functions", "classes") for n, u in d.get(nivel, {}).items()]
        for nombre, s in unidades:
            if not s["num_statements"]:
                continue
            ramas = 100 * s["covered_branches"] / s["num_branches"] if s["num_branches"] else 100.0
            if s["percent_covered"] < COBERTURA_MINIMA or ramas < COBERTURA_MINIMA:
                bajos.append(f"{a}{nombre}: total {s['percent_covered']:.1f}%, ramas {ramas:.1f}%")
    tr = session.config.pluginmanager.getplugin("terminalreporter")
    if bajos:
        tr.write_sep("=", f"cobertura debajo de {COBERTURA_MINIMA:.0f}% (archivo, función o clase)", red=True, bold=True)
        for linea in sorted(set(bajos)):
            tr.write_line(f"  {linea}", red=True)
        session.testsfailed += 1
    else:
        tr.write_sep("=", f"cobertura: archivos, funciones y clases >= {COBERTURA_MINIMA:.0f}% (total y ramas)", green=True)
    return resultado
