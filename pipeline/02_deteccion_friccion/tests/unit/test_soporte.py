"""registro, config, almacen y llm: logs, variables de entorno, guardado de modelos y cliente del LLM."""
import io
import json
import logging
import sys
from unittest import mock

import pytest
import requests

from modulo import almacen, config, llm, registro

pytestmark = pytest.mark.unit


# ------------------------------------------------------------------------------------------- registro
def _registro(msg="hola", nivel=logging.INFO, exc=None, **extra):
    r = logging.LogRecord("friccion.x", nivel, __file__, 1, msg, None, exc)
    r.__dict__.update(extra)
    return r


class TestRegistro:
    def test_json_con_contexto_extra_y_traza(self):
        t1 = registro.id_cliente_ctx.set("c1"); t2 = registro.fecha_ejecucion_ctx.set("2021-02-01")
        try:
            try:
                raise ValueError("falla")
            except ValueError:
                exc = sys.exc_info()
            d = json.loads(registro.JsonCloudFormatter().format(_registro(exc=exc, paso="Ventana", _oculto=1)))
        finally:
            registro.id_cliente_ctx.reset(t1); registro.fecha_ejecucion_ctx.reset(t2)
        assert d["severity"] == "INFO" and d["etapa"] == registro.ETAPA and d["paso"] == "Ventana"
        assert d["id_cliente"] == "c1" and d["fecha_ejecucion"] == "2021-02-01"
        assert "ValueError: falla" in d["traza_error"] and "_oculto" not in d

    def test_json_sin_contexto(self):
        t1 = registro.id_cliente_ctx.set(None); t2 = registro.fecha_ejecucion_ctx.set(None)
        try:
            d = json.loads(registro.JsonCloudFormatter().format(_registro()))
        finally:
            registro.id_cliente_ctx.reset(t1); registro.fecha_ejecucion_ctx.reset(t2)
        assert "id_cliente" not in d and "fecha_ejecucion" not in d

    def test_texto(self):
        try:
            raise KeyError("k")
        except KeyError:
            exc = sys.exc_info()
        linea = registro.TextoFormatter().format(_registro(exc=exc, sesiones=3))
        assert "[friccion.x] hola  sesiones=3" in linea and "KeyError" in linea
        assert registro.TextoFormatter().format(_registro()).endswith("[friccion.x] hola")

    def test_handler_separa_stdout_y_stderr(self, monkeypatch):
        out, err = io.StringIO(), io.StringIO()
        monkeypatch.setattr(sys, "__stdout__", out); monkeypatch.setattr(sys, "__stderr__", err)
        h = registro.CloudLoggingStreamHandler(); h.setFormatter(logging.Formatter("%(message)s"))
        h.emit(_registro("info")); h.emit(_registro("error", logging.ERROR))
        assert out.getvalue() == "info\n" and err.getvalue() == "error\n"

    def test_handler_error_al_escribir(self, monkeypatch):
        monkeypatch.setattr(sys, "__stdout__", None)
        h = registro.CloudLoggingStreamHandler()
        with mock.patch.object(h, "handleError") as he:
            h.emit(_registro())
        he.assert_called_once()

    @pytest.mark.parametrize("env, texto", [({"LOG_FORMATO": "texto"}, True),
                                            ({"LOG_FORMATO": "texto", "CLOUD_RUN_JOB": "j"}, False), ({}, False)])
    def test_configurar(self, monkeypatch, env, texto):
        raiz = logging.getLogger("friccion")
        monkeypatch.setattr(raiz, "handlers", [])
        monkeypatch.setattr(raiz, "level", raiz.level)
        for k in ("LOG_FORMATO", "CLOUD_RUN_JOB", "K_SERVICE"):
            monkeypatch.delenv(k, raising=False)
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        registro.configurar("DEBUG")
        assert isinstance(raiz.handlers[0].formatter, registro.TextoFormatter if texto else registro.JsonCloudFormatter)
        assert raiz.level == logging.DEBUG and raiz.propagate is False
        registro.configurar()   # ya configurado: no agrega otro handler
        assert len(raiz.handlers) == 1

    def test_paso_ok_y_con_error(self):
        log = mock.MagicMock()
        with registro.paso(log, "P", x=1) as res:
            print("salida de preprocesamiento")
            res["n"] = 5
        assert log.info.call_args_list[0].kwargs["extra"] == {"paso": "P", "x": 1}
        assert log.info.call_args_list[-1].kwargs["extra"]["n"] == 5
        log.debug.assert_called_once_with("salida de preprocesamiento", extra={"paso": "P"})
        log = mock.MagicMock()
        with pytest.raises(RuntimeError):
            with registro.paso(log, "P"):
                raise RuntimeError("x")
        log.exception.assert_called_once()

    def test_logger(self):
        assert registro.logger("abc").name == "friccion.abc"


# --------------------------------------------------------------------------------------------- config
class TestConfig:
    def test_env_de_entorno_y_de_dotenv(self, monkeypatch):
        monkeypatch.setenv("VAR_PRUEBA", " valor ")
        assert config.env("VAR_PRUEBA") == "valor"
        monkeypatch.delenv("VAR_PRUEBA")
        with mock.patch("dotenv.dotenv_values", return_value={"VAR_PRUEBA": "del_env"}):
            assert config.env("VAR_PRUEBA") == "del_env"
        with mock.patch("dotenv.dotenv_values", return_value={}):
            with pytest.raises(RuntimeError, match="VAR_PRUEBA"):
                config.env("VAR_PRUEBA")


# -------------------------------------------------------------------------------------------- almacen
class TestAlmacen:
    def test_local(self, tmp_path, monkeypatch):
        monkeypatch.delenv("MODELOS_BUCKET", raising=False)
        monkeypatch.setattr(almacen, "DIR_LOCAL", str(tmp_path))
        ruta = almacen.guardar_modelo({"a": 1}, "c1", "2021-02-01")
        assert ruta == str(tmp_path / "modelos" / "c1" / "2021-02-01" / "modelo.pkl")
        assert almacen.cargar_modelo(ruta) == {"a": 1}

    def test_gcs(self, monkeypatch):
        monkeypatch.setenv("MODELOS_BUCKET", "mi-bucket")
        assert almacen.ruta_modelo("c1", "f") == "gs://mi-bucket/modelos/c1/f/modelo.pkl"
        guardado = {}
        blob = mock.MagicMock()
        blob.upload_from_string.side_effect = lambda b, content_type: guardado.update(b=b)
        blob.download_as_bytes.side_effect = lambda: guardado["b"]
        storage = mock.MagicMock()
        storage.Client.return_value.bucket.return_value.blob.return_value = blob
        with mock.patch.dict(sys.modules, {"google.cloud.storage": storage}), \
                mock.patch("google.cloud.storage", storage, create=True):
            ruta = almacen.guardar_modelo({"b": 2}, "c1", "f")
            assert almacen.cargar_modelo(ruta) == {"b": 2}
        storage.Client.return_value.bucket.assert_called_with("mi-bucket")

    def test_ultimo_modelo(self):
        fila = mock.MagicMock(); fila.items.return_value = [("id_modelo", "m1")]
        bq = mock.MagicMock(); bq.query.return_value.result.return_value = [fila]
        assert almacen.ultimo_modelo(bq, "p", "c1") == {"id_modelo": "m1"}
        bq.query.return_value.result.return_value = []
        assert almacen.ultimo_modelo(bq, "p", "c1") is None


# ------------------------------------------------------------------------------------------------ llm
def _resp(json_=None, ok=True, status=200, lineas=None, texto=""):
    r = mock.MagicMock(ok=ok, status_code=status, text=texto)
    r.json.return_value = json_
    r.iter_lines.return_value = lineas or []
    r.__enter__.return_value = r
    return r


@pytest.fixture
def claves(monkeypatch):
    for k, v in {"LLM_POD_NOMBRE": "friccion-llm", "RUNPOD_API_KEY": "k", "VLLM_API_KEY": "v"}.items():
        monkeypatch.setenv(k, v)


POD = {"id": "abc", "name": "friccion-llm", "status": "RUNNING", "ports": [f"{config.LLM_PUERTO}/http"]}


class TestBuscarEndpoint:
    def test_ok(self, claves):
        modelos = _resp({"data": [{"id": config.LLM_MODELO}]})
        with mock.patch.object(llm.requests, "get", side_effect=[_resp({"pods": [POD]}), modelos]) as get:
            url = llm.buscar_endpoint()
        assert url == f"https://abc-{config.LLM_PUERTO}.proxy.runpod.net/v1"
        assert get.call_args.kwargs["headers"]["User-Agent"] == "modulo-friccion/0.1"

    @pytest.mark.parametrize("pods, motivo", [
        ([], "no hay ningún Pod"),
        ([POD, dict(POD, id="def")], "hay 2 Pods"),
        ([dict(POD, ports=["22/tcp"])], "no expone"),
    ])
    def test_pods_invalidos(self, claves, pods, motivo):
        with mock.patch.object(llm.requests, "get", return_value=_resp({"pods": pods})):
            with pytest.raises(llm.LLMNoDisponible, match=motivo):
                llm.buscar_endpoint()

    @pytest.mark.parametrize("segunda, motivo", [
        (requests.ConnectionError("x"), "no contesta"),
        (_resp(ok=False, status=502), "contesta 502"),
        (_resp({"data": [{"id": "otro"}]}), "sirve"),
    ])
    def test_modelo_no_listo(self, claves, segunda, motivo):
        with mock.patch.object(llm.requests, "get", side_effect=[_resp({"pods": [POD]}), segunda]):
            with pytest.raises(llm.LLMNoDisponible, match=motivo):
                llm.buscar_endpoint()


def _chunk(content=None, razon=None, fin=None, usage=None):
    d = {"choices": [{"delta": {"content": content, "reasoning_content": razon}, "finish_reason": fin}]}
    if usage:
        d["usage"] = usage
    return "data: " + json.dumps(d)


class TestConsultarJson:
    def test_ok(self, claves):
        lineas = ["", ": comentario", _chunk(razon="pienso"), _chunk('{"a": '), _chunk("1}", fin="stop"),
                  "data: " + json.dumps({"choices": [], "usage": {"total_tokens": 9}}), "data: [DONE]"]
        with mock.patch.object(llm.requests, "post", return_value=_resp(lineas=lineas)) as post:
            r = llm.consultar_json("u", [{"role": "user", "content": "x"}], {"type": "object"})
        assert r == {"respuesta": {"a": 1}, "razonamiento": "pienso", "uso": {"total_tokens": 9}}
        assert post.call_args.kwargs["json"]["stream"] is True

    def test_errores(self, claves):
        with mock.patch.object(llm.requests, "post", return_value=_resp(ok=False, status=524, texto="timeout")):
            with pytest.raises(RuntimeError, match="respondió 524"):
                llm.consultar_json("u", [], {})
        with mock.patch.object(llm.requests, "post", return_value=_resp(lineas=[_chunk('{"a"', fin="length")])):
            with pytest.raises(RuntimeError, match="no terminó"):
                llm.consultar_json("u", [], {})
        with mock.patch.object(llm.requests, "post", return_value=_resp(lineas=[_chunk("no json", fin="stop")])):
            with pytest.raises(RuntimeError, match="JSON válido"):
                llm.consultar_json("u", [], {})
