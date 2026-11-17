"""Pipeline punta a punta con datos sintéticos: ventana -> entrenamiento -> detección -> selección -> filas.

El sitio sintético tiene una fricción conocida: después de la ficha de producto, quien pasa por la página de
ayuda casi nunca agrega al carrito, y quien pasa por envíos casi siempre sigue. La detección tiene que encontrarla
sin que nada en el módulo sepa qué es una ayuda o un carrito.
"""
import pytest

from modulo import deteccion, escritura, seleccion
from tests.conftest import CLIENTE, FECHA

pytestmark = pytest.mark.integration


def test_ventana(ventana, crudos_pipeline):
    assert ventana.sesiones > 400 and not ventana.completa   # se pidió más de lo que hay: se usa todo
    assert ventana.eventos.groupby("session_id").size().min() >= 4


def test_modelo_entrenado(entrenado):
    modelo, fila = entrenado
    assert modelo["eventos_clave"]["clave"] == ["add_to_cart", "begin_checkout", "purchase"]
    assert sorted(modelo["orden_embudo"]) == [0, 1, 2]
    assert fila["id_modelo"] == f"{CLIENTE}_{FECHA}" and fila["nombres_hitos"] == []
    assert 0.5 < fila["auc"] <= 1 and fila["auc_ic95_inf"] <= fila["auc"]
    assert fila["sesiones"] == modelo["ventana"]["sesiones"]


def test_detecta_la_friccion_de_la_ayuda(detectado):
    patrones, resumen = detectado
    assert resumen["patrones"] == len(patrones) > 0 and resumen["nodos_no_vistos"] == 0
    perd = [p["sesiones_perdidas"] for p in patrones]
    assert perd == sorted(perd, reverse=True)
    top = patrones[0]
    assert top["objetivo"] == "add_to_cart" and "/ayuda" in top["secuencia"][-1]
    assert top["llegada_grupo"] < top["llegada_referencia"] and top["usuarios"] > 1
    assert not any(k.startswith("_") for k in top)


def test_sesion_representativa(detectado):
    top = detectado[0][0]
    pasos = top["pasos"]
    assert pasos and len({p["id_sesion"] for p in pasos}) == 1
    assert sum(p["es_paso_friccion"] for p in pasos) >= 1
    assert all(p["en_patron"] for p in pasos if p["es_paso_friccion"])
    assert any("/ayuda" in p["ruta"] for p in pasos if p["es_paso_friccion"])
    assert not any(p["nombre_evento"] == "add_to_cart" for p in pasos)   # el ejemplo no llegó al objetivo


def test_seleccion_y_filas(detectado):
    sel, res = seleccion.seleccionar(detectado[0], CLIENTE)
    assert 0 < res["seleccionados"] <= res["deduplicados"]
    pats, pasos = escritura.filas(sel, CLIENTE, "m", FECHA)
    assert len({p["id_patron"] for p in pats}) == len(pats)
    assert {p["id_patron"] for p in pasos} <= {p["id_patron"] for p in pats}


def test_detectar_es_determinista(entrenado, ventana, detectado):
    import logging
    otra, _ = deteccion.detectar(entrenado[0], ventana.eventos, logging.getLogger("friccion.pruebas"))
    assert [p["secuencia"] for p in otra] == [p["secuencia"] for p in detectado[0]]


def test_helpers_de_deteccion():
    assert deteccion._txt("x") == "x" and deteccion._txt(float("nan")) is None
    assert deteccion._llegan_menos(1, 0.5, 10, 0.5) == float("-inf")
    assert deteccion._p_menos(1, 0.5, 10, 0.5) == 1.0
    assert deteccion._p_menos(20, 0.0, 20, 0.0) == 1.0 and deteccion._p_menos(20, 0.0, 20, 1.0) == 0.0
