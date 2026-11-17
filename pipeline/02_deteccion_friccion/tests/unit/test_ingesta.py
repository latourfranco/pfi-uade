import json
from datetime import date
from unittest import mock

import numpy as np
import pandas as pd
import pytest

from ingesta import clientes as C, config_nube as CN, eventos as EV

pytestmark = pytest.mark.unit
FUENTE = C.FuenteEventos("c1", "US", "pruebas-pfi", "dw_analytics_us", "eventos_usuario", "US")


def _conexion(fila):
    cur = mock.MagicMock()
    cur.fetchone.return_value = fila
    con = mock.MagicMock()
    con.cursor.return_value.__enter__.return_value = cur
    return con, cur


class TestBuscarFuente:
    FILA = ("c1", True, "US", "pruebas-pfi", "dw_analytics_us", "eventos_usuario", "US", True)

    def test_cliente_valido(self):
        con, cur = _conexion(self.FILA)
        with mock.patch.object(C.psycopg2, "connect", return_value=con) as conectar:
            f = C.buscar_fuente("c1", "postgresql://x")
        assert f == FUENTE and f.tabla == "`pruebas-pfi.dw_analytics_us.eventos_usuario`"
        assert "read_only=on" in conectar.call_args.kwargs["options"]
        cur.execute.assert_called_once_with(C._SQL, ("c1",))
        con.close.assert_called_once()

    @pytest.mark.parametrize("fila, motivo", [
        (None, "no existe"),
        (("c1", False, "US", "p", "d", "t", "US", True), "inactivo"),
        (("c1", True, "XX", None, None, None, None, None), "no tiene fuente"),
        (("c1", True, "US", "pruebas-pfi", "d", "t", "US", False), "región 'US' del cliente c1 está inactiva"),
        (("c1", True, "US", "Proyecto Malo", "d", "t", "US", True), "mal configurada"),
        (("c1", True, "US", "pruebas-pfi", "d;drop", "t", "US", True), "mal configurada"),
    ])
    def test_cliente_no_disponible(self, fila, motivo):
        con, _ = _conexion(fila)
        with mock.patch.object(C.psycopg2, "connect", return_value=con):
            with pytest.raises(C.ClienteNoDisponible, match=motivo):
                C.buscar_fuente("c1", "postgresql://x")
        con.close.assert_called_once()


class TestConfigNube:
    def test_lee_variables(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_DB_URL_MODULO", "postgresql://m")
        monkeypatch.setenv("GCP_PROJECT", "pruebas-pfi")
        assert CN.cargar_config() == CN.ConfigNube("postgresql://m", "pruebas-pfi")

    def test_faltan_variables(self, monkeypatch):
        monkeypatch.delenv("SUPABASE_DB_URL_MODULO", raising=False)
        monkeypatch.setenv("GCP_PROJECT", "")
        with pytest.raises(RuntimeError, match="SUPABASE_DB_URL_MODULO, GCP_PROJECT"):
            CN.cargar_config()


class TestConsultas:
    def test_consulta_con_y_sin_fechas(self):
        sql, params = EV.consulta(FUENTE, None, None)
        assert "where cliente_id = @cliente_id" in sql and len(params) == 1
        sql, params = EV.consulta(FUENTE, date(2021, 1, 1), date(2021, 1, 31))
        assert "fecha_evento >= @desde" in sql and "fecha_evento <= @hasta" in sql and len(params) == 3

    def _cliente(self, filas=None, df=None):
        cli = mock.MagicMock()
        cli.query.return_value.result.return_value = filas
        cli.query.return_value.to_dataframe.return_value = df
        return cli

    def test_rango_fechas(self):
        cli = self._cliente([(date(2021, 1, 1), date(2021, 1, 31))])
        with mock.patch.object(EV.bigquery, "Client", return_value=cli) as Cliente:
            assert EV.rango_fechas(FUENTE, "p") == (date(2021, 1, 1), date(2021, 1, 31))
        assert Cliente.call_args.kwargs == {"project": "p", "location": "US"}
        cli = self._cliente([(None, None)])
        with mock.patch.object(EV.bigquery, "Client", return_value=cli):
            assert EV.rango_fechas(FUENTE, "p") is None

    def test_contar_eventos_dia(self):
        cli = self._cliente([(42,)])
        with mock.patch.object(EV.bigquery, "Client", return_value=cli):
            assert EV.contar_eventos_dia(FUENTE, "p", date(2021, 1, 31)) == 42

    def test_leer_eventos_con_tope(self):
        crudo = pd.DataFrame({"id_usuario": ["u"], "nombre_evento": ["page_view"], "timestamp": ["2021-01-01T00:00:00Z"],
                              "id_sesion": [1]})
        cli = self._cliente(df=crudo)
        with mock.patch.object(EV.bigquery, "Client", return_value=cli):
            out = EV.leer_eventos(FUENTE, "p", max_bytes=10)
            assert cli.query.call_args.kwargs["job_config"].maximum_bytes_billed == 10
            EV.leer_eventos(FUENTE, "p")
            assert cli.query.call_args.kwargs["job_config"].maximum_bytes_billed is None
        assert list(out.columns) == EV.COLUMNAS


class TestFormatoMotor:
    def test_nombres(self):
        assert np.isnan(EV._nombres(None, "item_name"))
        assert EV._nombres("texto suelto", "item_name") == "texto suelto"
        assert np.isnan(EV._nombres("null", "item_name"))
        assert EV._nombres('{"a": 1}', "item_name") == '{"a": 1}'
        assert EV._nombres(json.dumps([{"item_name": "A"}, {"item_name": ""}, {"x": 1}, "s", {"item_name": "B"}]),
                           "item_name") == "A; B"
        assert np.isnan(EV._nombres("[]", "item_name"))

    def test_a_formato_motor(self):
        df = pd.DataFrame({
            "id_usuario": ["b", "a", "a"], "nombre_evento": ["page_view", "scroll", "page_view"],
            "timestamp": pd.to_datetime(["2021-01-01 00:00:05", "2021-01-01 00:00:01", "2021-01-01 00:00:01"], utc=True),
            "porcentaje_scroll": [None, "90", None], "items": [json.dumps([{"item_name": "X"}]), None, None],
            "promociones": [None, json.dumps([{"promotion_name": "P"}]), None], "id_sesion": [None, 10, 10],
            "ruta": ["/", None, "/"]})
        out = EV.a_formato_motor(df)
        assert list(out.columns) == EV.COLUMNAS
        assert out.id_usuario.tolist() == ["a", "a", "b"]
        assert out.nombre_evento.tolist() == ["page_view", "scroll", "page_view"]   # desempate por nombre
        assert out.timestamp.iloc[0] == "2021-01-01 00:00:01.000000 UTC"
        assert out.porcentaje_scroll.dtype == "float64" and out.porcentaje_scroll.iloc[1] == 90.0
        assert str(out.id_sesion.dtype) == "Int64" and pd.isna(out.id_sesion.iloc[2])
        assert out["items"].iloc[2] == "X" and out.promociones.iloc[1] == "P"
        assert np.isnan(out.ruta.iloc[1])
