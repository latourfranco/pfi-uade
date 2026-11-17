"""Ramas que el pipeline sintético no recorre: casos borde armados a mano para cada una."""
import importlib
import sys
from types import SimpleNamespace
from unittest import mock

import numpy as np
import pandas as pd
import pytest

from modulo import deteccion as D, embudo, entrenamiento as E, nodos, preparar, red as R, registro, seleccion
from modulo.config import SESION_SIN_ID_S

pytestmark = pytest.mark.unit


def test_config_nube_sin_python_dotenv():
    """En Cloud Run no está python-dotenv: el módulo se importa igual y lee solo el entorno."""
    import ingesta.config_nube as CN
    with mock.patch.dict(sys.modules, {"dotenv": None}):
        recargado = importlib.reload(CN)
        assert callable(recargado.cargar_config)
    importlib.reload(CN)


def test_sesionizar_todos_con_id_de_ga4():
    df = pd.DataFrame({"id_usuario": ["u", "u"], "timestamp": ["2021-01-01 00:00:00 UTC", "2021-01-01 05:00:00 UTC"],
                       "id_sesion": [5, 5]})
    out, sin_id = preparar.sesionizar(df, SESION_SIN_ID_S)
    assert sin_id == 0 and set(out.session_id) == {"u_5"}   # GA4 manda: no se corta aunque pasen 5 h


def test_paso_ignora_lineas_vacias():
    log = mock.MagicMock()
    with registro.paso(log, "P"):
        print("")
        print("algo")
    log.debug.assert_called_once_with("algo", extra={"paso": "P"})


def test_auc_ic95_descarta_replicas_de_una_sola_clase():
    rng = np.random.default_rng(0)
    auc, lo, hi = R.auc_ic95(np.array([0, 1, 0, 1]), np.array([0.1, 0.9, 0.2, 0.8]), np.array([0, 0, 1, 1]), rng)
    assert auc == 1.0 and lo <= hi
    # con un usuario por clase, las réplicas que pesan a uno solo quedan afuera
    auc, lo, hi = R.auc_ic95(np.array([0, 1]), np.array([0.2, 0.7]), np.array([0, 1]), np.random.default_rng(1))
    assert lo == hi == auc == 1.0


def test_texto_nodo():
    assert D.texto_nodo(nodos.INICIO) == nodos.INICIO
    assert D.texto_nodo("page_view@/a·misma") == "page_view /a (la misma página)"
    assert D.texto_nodo("click@/…") == "click /…"


class TestNiveles:
    def _caso(self, n_ses):
        ids = [np.array([0, 4, 2, 3]) for _ in range(n_ses)]
        vocab = {"inicio_de_sesion": 0, "OTRO": 1, "a@/x": 2, "b@/x": 3, "c@/y": 4}
        A = embudo.construir(ids, [f"u{i}" for i in range(n_ses)], embudo.evbit(vocab, ["a", "b"]))
        n = A["n"]
        return A, np.ones(n, bool), np.ones(n, bool), np.zeros(n, bool), np.ones(n, np.int64)

    def test_corta_cuando_ninguna_bifurcacion_tiene_soporte(self):
        tablas, filas = D.niveles(*self._caso(D.MIN_SES - 1))
        assert tablas == {} and filas == {}

    def test_llega_al_largo_maximo_de_contexto(self, monkeypatch):
        monkeypatch.setattr(D, "KMAX", 2)
        tablas, filas = D.niveles(*self._caso(D.MIN_SES + 2))
        assert set(tablas) == {1, 2} and set(filas) == {1, 2}


def test_agrupar_paginas_hereda_grupo_de_las_hermanas():
    """/c/sel/z no tiene acciones suficientes: hereda el grupo de sus hermanas de /c/sel/. /c/otro/h es la única
    página con su composición: queda en un grupo de una página, que no es grupo."""
    t = pd.Timestamp("2021-01-01", tz="UTC")
    filas, k = [], 0
    for pagina, accion, n in [("/c/sel/a", "select_item", 60), ("/c/sel/b", "select_item", 60),
                              ("/c/sel/d", "select_item", 60), ("/c/add/e", "add_to_cart", 60),
                              ("/c/add/f", "add_to_cart", 60), ("/c/otro/h", "view_x", 60), ("/c/sel/z", "select_item", 2)]:
        for _ in range(n):
            k += 1
            for j, e in enumerate(["page_view", accion]):
                filas.append(dict(session_id=f"s{k}", id_usuario=f"u{k}", nombre_evento=e, plantilla_ruta=pagina,
                                  timestamp=t + pd.Timedelta(seconds=j)))
    grupos, _ = nodos.agrupar_paginas(pd.DataFrame(filas))
    assert grupos["/c/sel/z"] == grupos["/c/sel/a"] != "sola"
    assert grupos["/c/add/e"] == grupos["/c/add/f"] != grupos["/c/sel/a"]
    assert grupos["/c/otro/h"] == "sola"


def test_seleccion_completa_la_cuota_despues_del_piso():
    pats = [dict(objetivo="o", secuencia=["a", f"p{i}"], sesiones=10, sesiones_perdidas=10.0,
                 pasos=[dict(es_paso_friccion=True, tipo_dispositivo="desktop")]) for i in range(4)]
    sel, res = seleccion.seleccionar(pats, "c1")
    # el piso deja 2 (50% de la pérdida); se suma un tercero para pasar el 70% y se corta
    assert res["seleccionados"] == 3 and res["cobertura"] == 0.75


def test_entrenar_con_hitos_del_llm(ventana, monkeypatch):
    monkeypatch.setattr(E, "UMBRAL_ENTRENAMIENTO", 1)
    hitos = [dict(evento="add_to_cart", nombre_legible="Agregar", motivo="m", es_objetivo_principal=False),
             dict(evento="purchase", nombre_legible="Comprar", motivo="m", es_objetivo_principal=True)]
    ek = dict(clave=["add_to_cart", "purchase"], objetivo="purchase", origen="llm:x", hitos=hitos)
    log = mock.MagicMock()
    monkeypatch.setattr(E, "log", log)
    with mock.patch.object(E, "elegir_eventos_clave", return_value=ek), \
            mock.patch.object(E.R, "entrenar", return_value=(mock.MagicMock(), 1.0, dict(auc=0.7, auc_ic95_inf=0.6))):
        modelo, fila = E.entrenar_cliente("c", ventana, "2021-02-01")
    assert fila["nombres_hitos"] == ["Agregar", "Comprar"] and modelo["eventos_clave"] is ek
    assert any("Hito purchase (Comprar)" in c.args[0] for c in log.info.call_args_list)
