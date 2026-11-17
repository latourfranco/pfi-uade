import numpy as np
import pandas as pd
import pytest

from preprocesamiento import preprocessing as pp
from preprocesamiento.config import MIN_EVENTS_PER_SESSION
from preprocesamiento.datos_tramos import orden_tipico, SIMULTANEO_S

pytestmark = pytest.mark.unit
BASE = pd.Timestamp("2021-01-01 00:00:00", tz="UTC")


def _df(filas):
    """filas: (sesion, evento, ruta, segundos, scroll)."""
    return pd.DataFrame([{"session_id": s, "nombre_evento": e, "ruta": r, "timestamp": BASE + pd.Timedelta(seconds=t),
                          "porcentaje_scroll": sc} for s, e, r, t, sc in filas])


class TestTimestampYEngagement:
    def test_parse_timestamp_mezcla_con_y_sin_microsegundos(self):
        out = pp._parse_timestamp(pd.Series(["2020-12-08 04:01:48 UTC", "2020-12-08 04:01:48.123456 UTC"]))
        assert str(out.dt.tz) == "UTC"
        assert out.iloc[1] - out.iloc[0] == pd.Timedelta(microseconds=123456)

    def test_drop_engagement_pings_solo_saca_heartbeats(self, capsys):
        df = pd.DataFrame({"nombre_evento": ["page_view", "user_engagement", "click", "user_engagement"]})
        out = pp.drop_engagement_pings(df)
        assert out.nombre_evento.tolist() == ["page_view", "click"]
        assert out.index.equals(pd.RangeIndex(2))
        assert "descartados: 2" in capsys.readouterr().out


class TestPromoYCarga:
    def test_saca_view_promotion_y_view_item_de_carga(self):
        df = _df([("s1", "page_view", "/p/1", 0, np.nan), ("s1", "view_item", "/p/1", 0, np.nan),
                  ("s1", "view_promotion", "/p/1", 0, np.nan), ("s1", "view_item", "/p/1", 5, np.nan),
                  ("s2", "view_item", "/p/2", 0, np.nan)])
        out = pp.drop_promo_and_load_views(df)
        assert out.nombre_evento.tolist() == ["page_view", "view_item", "view_item"]
        # el view_item de s2 no coincide con un page_view de SU sesión: queda
        assert out.session_id.tolist() == ["s1", "s1", "s2"]
        assert out.delta_t_prev.tolist() == [0.0, 5.0, 0.0]


class TestScroll:
    def test_pliega_en_el_paso_anterior_y_recalcula_delta(self):
        df = _df([("s1", "page_view", "/a", 0, np.nan), ("s1", "scroll", "/a", 10, 90.0),
                  ("s1", "page_view", "/b", 30, np.nan)])
        out = pp.fold_scroll_events(df)
        assert out.nombre_evento.tolist() == ["page_view", "page_view"]
        assert out.porcentaje_scroll.iloc[0] == 90.0 and np.isnan(out.porcentaje_scroll.iloc[1])
        assert out.delta_t_prev.tolist() == [0.0, 30.0]

    def test_scroll_al_inicio_va_al_primer_paso(self):
        df = _df([("s1", "scroll", "/a", 0, 90.0), ("s1", "page_view", "/a", 5, np.nan)])
        out = pp.fold_scroll_events(df)
        assert len(out) == 1 and out.porcentaje_scroll.iloc[0] == 90.0


class TestRutas:
    def test_helpers_de_url(self):
        assert pp._strip_url_domain("https://x.com/a/b?q=1") == "/a/b?q=1"
        assert pp._strip_url_domain("/sin/dominio") == "/sin/dominio"
        assert pp._path_segments("/a+b/%41//c/") == ["a b", "A", "c"]
        for seg, esperado in [("123", True), ("deadbeef99", True), ("0123-4567-89ab-cdef-0123-4567-89ab-cdef", True),
                              ("WebResource.axd", True), ("remeras", False)]:
            assert pp._is_numeric_or_hash(seg) is esperado

    def test_ajustar_y_aplicar_rutas(self):
        rutas = ([f"https://x.com/p/{n}-slug" for n in range(60)]           # 60 valores: parámetro
                 + [f"https://x.com/c/{c}" for c in ("a", "b")]             # pocos valores: página fija
                 + [f"https://x.com/buscar?q=t{n}&orden=precio" for n in range(60)]
                 + ["https://x.com/cuenta#login", "https://x.com/cuenta#registro"]
                 + [f"https://x.com/doc#sec{n}" for n in range(60)]
                 + ["https://x.com/item/123/detalle"])
        df = pd.DataFrame({"ruta": rutas})
        reglas = pp.ajustar_rutas(df, min_valores=50)
        out = pp.aplicar_rutas(df, reglas).plantilla_ruta
        assert out.iloc[0] == "/p/{param}"
        assert out.iloc[60] == "/c/a"
        assert out.iloc[62] == "/buscar?q={param}&orden=precio"
        assert set(out.iloc[122:124]) == {"/cuenta#login", "/cuenta#registro"}
        assert out.iloc[124] == "/doc#{param}"
        assert out.iloc[-1] == "/item/{param}"          # debajo de un {param} no se agrega nada
        # un lugar que no se vio al ajustar queda literal
        assert pp.aplicar_rutas(pd.DataFrame({"ruta": ["https://x.com/nueva/pagina"]}), reglas).plantilla_ruta[0] \
            == "/nueva/pagina"

    def test_ajustar_rutas_sin_datos(self):
        reglas = pp.ajustar_rutas(pd.DataFrame({"ruta": pd.Series([], dtype=str)}))
        assert reglas == {"path": {}, "query": {}, "frag": {}}


class TestFiltroYOrden:
    def test_filter_sessions_descarta_cortas(self, capsys):
        df = pd.DataFrame({"session_id": ["a"] * MIN_EVENTS_PER_SESSION + ["b"] * (MIN_EVENTS_PER_SESSION - 1)})
        out = pp.filter_sessions(df)
        assert set(out.session_id) == {"a"}
        assert "descartadas 1" in capsys.readouterr().out

    def test_orden_tipico_por_posicion_en_la_visita(self):
        df = pd.DataFrame({"session_id": ["s"] * 6 + ["t"] * 2,
                           "plantilla_ruta": ["/a", "/a", "/a", "/b", "/b", "/b", "/c", "/c"],
                           "nombre_evento": ["page_view", "x", "y", "page_view", "x", "x", "page_view", "page_view"]})
        orden = orden_tipico(df)
        assert orden["page_view"] == 0.0 and orden["x"] == pytest.approx(0.75) and orden["y"] == 1.0
        assert SIMULTANEO_S == 1.0
