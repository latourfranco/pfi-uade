"""entrenamiento y principal: decisiones del flujo por cliente, con la red, la nube y el LLM reemplazados."""
import json
import sys
from datetime import date
from types import SimpleNamespace
from unittest import mock

import pytest

from modulo import entrenamiento as E, principal as P

pytestmark = pytest.mark.unit


# ------------------------------------------------------------------------------------------ entrenamiento
class TestEventosClave:
    def test_a_mano(self):
        ek = E.elegir_eventos_clave(None, ["a", "b"])
        assert ek == dict(clave=["a", "b"], objetivo="b", origen="manual", hitos=None)
        assert E.nombres_hitos(ek) == []

    def test_con_llm(self):
        hitos = [dict(evento="purchase", nombre_legible="Comprar", es_objetivo_principal=True),
                 dict(evento="add_to_cart", nombre_legible="Agregar", es_objetivo_principal=False)]
        with mock.patch("modulo.eventos_clave.resumir_eventos", return_value={"eventos": [1, 2]}), \
                mock.patch("modulo.llm.buscar_endpoint", return_value="url"), \
                mock.patch("modulo.llm.consultar_json", return_value={"respuesta": {}, "uso": {"t": 1}}) as consulta, \
                mock.patch("modulo.eventos_clave.validar", return_value=hitos):
            ek = E.elegir_eventos_clave("prep", None)
        assert ek["clave"] == ["add_to_cart", "purchase"] and ek["objetivo"] == "purchase"
        assert ek["origen"].startswith("llm:") and ek["uso"] == {"t": 1}
        assert consulta.call_args.args[0] == "url"
        assert E.nombres_hitos(ek) == ["Agregar", "Comprar"]


class TestEntrenarCliente:
    def test_pocas_sesiones_no_entrena(self):
        assert E.entrenar_cliente("c", SimpleNamespace(sesiones=10), "2021-02-01") is None

    def test_evento_clave_ausente(self, ventana, monkeypatch):
        monkeypatch.setattr(E, "UMBRAL_ENTRENAMIENTO", 1)
        with pytest.raises(ValueError, match="no aparecen en la ventana"):
            E.entrenar_cliente("c", ventana, "2021-02-01", ["no_existe", "purchase"])

    def test_reentrenamiento_reutiliza_lo_aprendido(self, ventana, entrenado, monkeypatch):
        modelo, _ = entrenado
        monkeypatch.setattr(E, "UMBRAL_ENTRENAMIENTO", 1)
        info = dict(auc=0.7, auc_ic95_inf=0.6)
        with mock.patch.object(E.R, "entrenar", return_value=(E.R.Red(len(modelo["vocab"]), 3), 1.0, info)), \
                mock.patch.object(E.nodos, "aprender") as aprender:
            nuevo, fila = E.entrenar_cliente("c", ventana, "2021-02-02", base=modelo)
        aprender.assert_not_called()
        assert nuevo["aprendido"] is modelo["aprendido"] and nuevo["eventos_clave"] is modelo["eventos_clave"]
        assert set(modelo["vocab"]) <= set(nuevo["vocab"]) and fila["id_modelo"] == "c_2021-02-02"


# --------------------------------------------------------------------------------------------- principal
@pytest.fixture
def nube(monkeypatch):
    """Dobles de todo lo externo de procesar_cliente. Devuelve el espacio de nombres para ajustar cada caso."""
    n = SimpleNamespace(
        cfg=SimpleNamespace(supabase_db_url="db", gcp_project="p"), n_dia=5,
        ventana=SimpleNamespace(sesiones=5000, eventos="eventos"), vigente=None,
        modelo={"id_modelo": "m1"}, fila={"id_modelo": "m1"},
        patrones=[{"objetivo": "o", "secuencia": ["x"], "sesiones": 9, "usuarios": 5, "llegada_grupo": 0.1,
                   "llegada_referencia": 0.6, "sesiones_perdidas": 4.5, "pasos": [{"nombre_evento": "a", "es_paso_friccion": True,
                                                                         "tipo_dispositivo": "mobile"}]}],
        auc=0.8)
    n.escribir = mock.Mock(return_value={"job_id": "j", "bytes_procesados": 0})
    n.guardar = mock.Mock(return_value="gs://b/modelo.pkl")
    n.entrenar = mock.Mock(side_effect=lambda *a, **k: (n.modelo, dict(n.fila)))
    n.detectar = mock.Mock(side_effect=lambda *a, **k: (list(n.patrones), {"auc_del_dia": n.auc}))
    n.armar = mock.Mock(side_effect=lambda leer, a, b: (leer(a, b), n.ventana)[1])
    n.leer = mock.Mock(return_value="crudos")
    monkeypatch.setattr("ingesta.config_nube.cargar_config", lambda: n.cfg)
    monkeypatch.setattr("ingesta.clientes.buscar_fuente", lambda c, url: "fuente")
    monkeypatch.setattr("ingesta.eventos.contar_eventos_dia", lambda f, p, d: n.n_dia)
    monkeypatch.setattr("ingesta.eventos.rango_fechas", lambda f, p: (date(2021, 1, 1), date(2021, 1, 31)))
    monkeypatch.setattr("ingesta.eventos.leer_eventos", n.leer)
    monkeypatch.setattr("google.cloud.bigquery.Client", mock.Mock())
    monkeypatch.setattr("modulo.ventana.armar_ventana", n.armar)
    monkeypatch.setattr("modulo.almacen.ultimo_modelo", lambda bq, p, c: n.vigente)
    monkeypatch.setattr("modulo.almacen.cargar_modelo", lambda ruta: n.modelo)
    monkeypatch.setattr("modulo.almacen.guardar_modelo", n.guardar)
    monkeypatch.setattr("modulo.entrenamiento.entrenar_cliente", n.entrenar)
    monkeypatch.setattr("modulo.deteccion.detectar", n.detectar)
    monkeypatch.setattr("modulo.escritura.escribir", n.escribir)
    return n


class TestProcesarCliente:
    def test_sin_eventos_del_dia(self, nube):
        nube.n_dia = 0
        assert P.procesar_cliente("c", "2021-02-01", None) == {"estado": "OMITIDO_SIN_EVENTOS"}

    def test_pocas_sesiones(self, nube):
        nube.ventana.sesiones = 100
        r = P.procesar_cliente("c", "2021-02-01", None)
        assert r == {"estado": "OMITIDO_POCAS_SESIONES", "sesiones": 100}
        nube.leer.assert_called_once_with("fuente", "p", date(2021, 1, 1), date(2021, 1, 31))

    def test_cliente_nuevo_entrena_guarda_y_escribe(self, nube):
        r = P.procesar_cliente("c", "2021-02-01", ["a", "b"])
        assert r == {"estado": "OK", "patrones": 1, "id_modelo": "m1"}
        nube.entrenar.assert_called_once()
        assert nube.escribir.call_args.args[4]["artefacto"] == "gs://b/modelo.pkl"

    def test_modelo_vigente_sin_reentrenar(self, nube):
        nube.vigente = {"id_modelo": "m1", "artefacto": "gs://x", "auc_ic95_inf": 0.6}
        nube.patrones = []
        r = P.procesar_cliente("c", "2021-02-01", None)
        assert r["estado"] == "OK" and r["patrones"] == 0
        nube.entrenar.assert_not_called(); nube.guardar.assert_not_called()
        assert nube.escribir.call_args.args[4] is None

    def test_auc_baja_reentrena(self, nube):
        nube.vigente = {"id_modelo": "m0", "artefacto": "gs://x", "auc_ic95_inf": 0.9}
        P.procesar_cliente("c", "2021-02-01", None)
        assert nube.entrenar.call_args.kwargs["base"] is nube.modelo and nube.detectar.call_count == 2
        nube.guardar.assert_called_once()

    def test_simular_no_escribe(self, nube):
        r = P.procesar_cliente("c", "2021-02-01", None, simular=True)
        assert r == {"estado": "SIMULADO", "patrones": 1, "id_modelo": "m1"}
        nube.escribir.assert_not_called(); nube.guardar.assert_not_called()


class TestEjecutarTarea:
    def _correr(self, monkeypatch, argv, env=None, resultado=None, error=None):
        monkeypatch.setattr(sys, "argv", ["principal"] + argv)
        for k in ("CLOUD_RUN_TASK_INDEX", "CLOUD_RUN_TASK_ATTEMPT", "FECHA_EJECUCION", "IDS_CLIENTES", "EVENTOS_CLAVE"):
            monkeypatch.delenv(k, raising=False)
        for k, v in (env or {}).items():
            monkeypatch.setenv(k, v)
        proc = mock.Mock(return_value=resultado or {"estado": "OK"}, side_effect=error)
        monkeypatch.setattr(P, "procesar_cliente", proc)
        with pytest.raises(SystemExit) as fin:
            P.ejecutar_tarea()
        return fin.value.code, proc

    def test_cloud_run(self, monkeypatch):
        env = {"FECHA_EJECUCION": "2021-02-01", "IDS_CLIENTES": json.dumps(["c0", "c1"]), "CLOUD_RUN_TASK_INDEX": "1",
               "EVENTOS_CLAVE": "a,b"}
        codigo, proc = self._correr(monkeypatch, [], env)
        assert codigo == 0
        proc.assert_called_once_with("c1", "2021-02-01", ["a", "b"], simular=False)

    def test_local(self, monkeypatch):
        codigo, proc = self._correr(monkeypatch, ["--cliente", "c9", "--fecha", "2021-02-01", "--simular"])
        assert codigo == 0
        proc.assert_called_once_with("c9", "2021-02-01", None, simular=True)

    def test_sin_fecha_o_indice_fuera_de_rango(self, monkeypatch):
        codigo, proc = self._correr(monkeypatch, [], {"IDS_CLIENTES": "[]"})
        assert codigo == 0 and not proc.called
        codigo, proc = self._correr(monkeypatch, [], {"FECHA_EJECUCION": "2021-02-01", "IDS_CLIENTES": '["c0"]',
                                                      "CLOUD_RUN_TASK_INDEX": "3"})
        assert codigo == 0 and not proc.called

    def test_error_sale_con_1(self, monkeypatch):
        codigo, _ = self._correr(monkeypatch, ["--cliente", "c", "--fecha", "2021-02-01"], error=RuntimeError("x"))
        assert codigo == 1
