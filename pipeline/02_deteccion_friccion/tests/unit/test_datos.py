"""preparar, ventana, nodos y red: de eventos crudos a secuencias y a la red, sin entrenar de verdad."""
import logging
from datetime import date
from unittest import mock

import numpy as np
import pandas as pd
import pytest
import torch

from modulo import embudo, nodos, preparar, red as R, ventana as VEN
from modulo.config import SESION_SIN_ID_S
from tests import sinteticos as S

pytestmark = pytest.mark.unit


# -------------------------------------------------------------------------------------------- preparar
class TestPreparar:
    def test_sesion_de_ga4_y_calculada(self):
        df = pd.DataFrame({"id_usuario": ["u"] * 4,
                           "timestamp": ["2021-01-01 00:00:00 UTC", "2021-01-01 00:00:10 UTC",
                                         "2021-01-01 01:00:00 UTC", "2021-01-01 03:00:00 UTC"],
                           "id_sesion": [77, 77, None, None]})
        out, sin_id = preparar.sesionizar(df, SESION_SIN_ID_S)
        assert sin_id == 2
        ga4 = out[out.session_id == "u_77"]
        assert len(ga4) == 2 and ga4.delta_t_prev.tolist() == [0.0, 10.0]
        # sin id: cortes por más de 30 min, el inicio en segundos hace de id
        assert out.session_id.nunique() == 3 and "u_1609462800" in set(out.session_id)

    def test_sin_columna_id_sesion(self):
        df = pd.DataFrame({"id_usuario": ["u", "u"], "timestamp": ["2021-01-01 00:00:00 UTC", "2021-01-01 00:00:05 UTC"]})
        out, sin_id = preparar.sesionizar(df, SESION_SIN_ID_S)
        assert sin_id == 2 and out.session_id.nunique() == 1

    def test_preparar_con_limites(self, crudos):
        prep, limites, resumen = preparar.preparar_con_limites(crudos, SESION_SIN_ID_S)
        assert {"user_engagement", "view_promotion", "scroll"}.isdisjoint(prep.nombre_evento)
        assert prep.groupby("session_id").size().min() >= 4
        assert resumen["eventos_crudos"] == len(crudos) and resumen["sesiones"] == len(limites)
        assert 0 < resumen["pct_eventos_sin_id_sesion"] < 100
        assert preparar.preparar_sesiones(crudos, SESION_SIN_ID_S).equals(prep)


# --------------------------------------------------------------------------------------------- ventana
class TestVentana:
    def test_lee_de_a_poco_hasta_juntar_n(self, crudos):
        leer = mock.Mock(side_effect=S.lector(crudos))
        v = VEN.armar_ventana(leer, date(2021, 1, 1), date(2021, 1, 20), n=60)
        assert v.completa and v.sesiones == 60 and v.consultas == leer.call_count >= 2
        assert v.eventos.session_id.nunique() == 60 and v.hasta == date(2021, 1, 20)

    def test_historico_insuficiente(self, crudos):
        v = VEN.armar_ventana(S.lector(crudos), date(2021, 1, 1), date(2021, 1, 20), n=10_000)
        assert not v.completa and v.desde == date(2021, 1, 1) and v.sesiones < 10_000

    def test_sin_sesiones_completas_al_principio(self, crudos):
        # la primera lectura (7 días) da una sola sesión, que toca los dos bordes: se leen otros 7 días
        base = S.lector(crudos)
        una = crudos[crudos.id_usuario == crudos.id_usuario.iloc[0]].iloc[:6]
        leer = mock.Mock(side_effect=lambda d, h: una if d >= date(2021, 1, 14) else base(d, h))
        v = VEN.armar_ventana(leer, date(2021, 1, 1), date(2021, 1, 20), n=5)
        assert v.completa and v.consultas == 2 and leer.call_args_list[1].args == (date(2021, 1, 7), date(2021, 1, 13))

    def test_sesiones_completas_descarta_bordes(self):
        t = pd.Timestamp("2021-01-01", tz="UTC")
        lim = pd.DataFrame({"session_id": ["a", "b", "c"], "inicio": [t, t + pd.Timedelta(hours=2), t + pd.Timedelta(hours=4)],
                            "fin": [t, t + pd.Timedelta(hours=2), t + pd.Timedelta(hours=4)]})
        out = VEN.sesiones_completas(lim, pd.Index(["a", "b", "c"]), 1800)
        assert out.session_id.tolist() == ["b"]

    def test_lector_bigquery(self):
        fuente = mock.MagicMock(tabla="`t`")
        with mock.patch("ingesta.config_nube.cargar_config") as cfg, \
                mock.patch("ingesta.clientes.buscar_fuente", return_value=fuente), \
                mock.patch("ingesta.eventos.rango_fechas", return_value=(date(2021, 1, 1), date(2021, 1, 9))), \
                mock.patch("ingesta.eventos.leer_eventos", return_value="eventos") as leer:
            lector, a, b = VEN.lector_bigquery("c1")
            assert (a, b) == (date(2021, 1, 1), date(2021, 1, 9))
            assert lector(a, b) == "eventos"
        leer.assert_called_once_with(fuente, cfg.return_value.gcp_project, a, b)
        with mock.patch("ingesta.config_nube.cargar_config"), mock.patch("ingesta.clientes.buscar_fuente", return_value=fuente), \
                mock.patch("ingesta.eventos.rango_fechas", return_value=None):
            with pytest.raises(RuntimeError, match="no tiene eventos"):
                VEN.lector_bigquery("c1")


# ----------------------------------------------------------------------------------------------- nodos
class TestNodos:
    def test_reserva_y_seccion(self):
        r = nodos.es_reserva([f"u{i}" for i in range(500)])
        assert r.dtype == bool and 0.1 < r.mean() < 0.3
        assert nodos._seccion("/shop/apparel/mens") == "shop" and nodos._seccion("/checkout?show=x") == "checkout"
        assert nodos._seccion("/") == ""

    def test_aprender_y_secuencias(self, crudos):
        prep = preparar.preparar_sesiones(crudos, SESION_SIN_ID_S)
        apr, tabla = nodos.aprender(prep)
        assert set(apr) == {"reglas_rutas", "orden_eventos", "grupos"}
        assert set(tabla.columns) == {"pagina", "grupo", "visitas"}
        ses, ev = nodos.secuencias(prep, apr, con_filas=True)
        assert len(ses) == prep.session_id.nunique()
        assert all(len(f) == sum(n) for f, n in zip(ses.filas, ses.n_filas))
        vocab = nodos.vocabulario(ses)
        assert {nodos.INICIO, nodos.OTRO, f"page_view@{nodos.OTRO}"} <= set(vocab)
        ids = nodos.a_ids(ses, vocab)
        assert all(x[0] == vocab[nodos.INICIO] for x in ids)
        # nodos no vistos: evento conocido en página nueva -> evento@OTRO; evento nuevo -> OTRO
        raro = pd.DataFrame({"tok": [["page_view@/nueva", "evento_nuevo@/x"]]})
        assert nodos.a_ids(raro, vocab)[0].tolist() == [vocab[nodos.INICIO], vocab[f"page_view@{nodos.OTRO}"], vocab[nodos.OTRO]]

    def test_recargas_y_misma_pagina(self):
        t = pd.Timestamp("2021-01-01", tz="UTC")
        filas = [("page_view", "/a", 0), ("page_view", "/a", 5), ("click", "/a", 10), ("page_view", "/a", 20),
                 ("page_view", "/b", 30)]
        prep = pd.DataFrame([{"session_id": "s", "id_usuario": "u", "nombre_evento": e, "ruta": "https://x.com" + r,
                              "timestamp": t + pd.Timedelta(seconds=s)} for e, r, s in filas])
        apr = dict(reglas_rutas={"path": {}, "query": {}, "frag": {}}, orden_eventos={}, grupos={"/b": "/…"})
        ses = nodos.secuencias(prep, apr)
        assert ses.tok.iloc[0] == ["page_view@/a", "click@/a", "page_view@/a·misma", "page_view@/…"]

    def test_agrupar_paginas_por_seccion(self):
        """Dentro de /c, las páginas con la misma composición de acciones forman un grupo y las de otra
        composición otro; una página con pocas acciones o en una sección sin otras páginas queda sola."""
        t = pd.Timestamp("2021-01-01", tz="UTC")
        filas, k = [], 0
        for pagina, accion, n in [("/c/a", "select_item", 60), ("/c/b", "select_item", 60), ("/c/d", "select_item", 60),
                                  ("/c/e", "add_to_cart", 60), ("/c/f", "add_to_cart", 60), ("/c/g", "add_to_cart", 60),
                                  ("/c/sub/x", "select_item", 1), ("/otra", "x", 60)]:
            for _ in range(n):
                k += 1
                for j, e in enumerate(["page_view", accion]):
                    filas.append(dict(session_id=f"s{k}", id_usuario=f"u{k}", nombre_evento=e, plantilla_ruta=pagina,
                                      timestamp=t + pd.Timedelta(seconds=j)))
        grupos, tabla = nodos.agrupar_paginas(pd.DataFrame(filas))
        assert grupos["/c/a"] == grupos["/c/b"] == grupos["/c/d"] != "sola"
        assert grupos["/c/e"] == grupos["/c/f"] != grupos["/c/a"]
        assert grupos["/otra"] == "sola" and grupos["/c/sub/x"] == "sola" and len(tabla) == len(grupos)


# ------------------------------------------------------------------------------------------------- red
class TestRed:
    def _datos(self, n_ses=40):
        rng = np.random.default_rng(0)
        vocab = {"inicio_de_sesion": 0, "OTRO": 1, "a@/x": 2, "b@/x": 3, "c@/y": 4}
        ids = [np.array([0] + list(rng.choice([2, 3, 4], size=int(rng.integers(2, 6))))) for _ in range(n_ses)]
        A = embudo.construir(ids, [f"u{i}" for i in range(n_ses)], embudo.evbit(vocab, ["a", "b"]))
        PEND, NEXT = embudo.logros(A, [0, 1])
        goal = embudo.objetivos(A, PEND, [0, 1])
        valid, y, _ = embudo.etiquetas(A, PEND, NEXT, goal)
        return A, PEND, goal, valid, y, len(vocab)

    def test_lotes_y_forward(self):
        A, PEND, goal, valid, y, V = self._datos()
        D = R.por_sesion(A, PEND, goal, valid, y, V)
        rng = np.random.default_rng(0)
        mezclados = R.lotes(D, range(A["nses"]), mezclar=True, rng=rng)
        assert sorted(int(s) for b in mezclados for s in b) == list(range(A["nses"]))
        ordenados = R.lotes(D, range(A["nses"]), mezclar=False, rng=rng)
        tok, ach, sig, g, yy, val, lens = R.lote(D, ordenados[0])
        red = R.Red(V, 2)
        lo, ls = red(tok, ach, lens)
        assert lo.shape == (len(lens), tok.shape[1], 2) and ls.shape[-1] == V + 1
        l_obj, l_sig = R.perdidas(red, (tok, ach, sig, g, yy, val, lens))
        assert torch.isfinite(l_obj) and torch.isfinite(l_sig)
        sin_validos = (tok, ach, sig, g, yy, torch.zeros_like(val), lens)
        assert R.perdidas(red, sin_validos)[0].item() == 0
        assert R.logits(red, D, A).shape == (A["n"], 2)

    def test_metricas(self):
        assert R.logloss(np.array([0.5, 0.5]), np.array([0, 1])) == pytest.approx(np.log(2))
        rng = np.random.default_rng(0)
        y = np.array([0, 1] * 50); p = np.where(y == 1, 0.8, 0.2) + rng.normal(0, 0.2, 100)
        auc, lo, hi = R.auc_ic95(y, p, np.arange(100) % 20, rng)
        assert lo <= auc <= hi and auc > 0.8

    def test_entrenar(self, monkeypatch):
        monkeypatch.setattr(R, "PACIENCIA", 1); monkeypatch.setattr(R, "MIN_EP", 2)
        A, PEND, goal, valid, y, V = self._datos(n_ses=120)
        red, T, info = R.entrenar(A, PEND, goal, valid, y, V, logging.getLogger("friccion.pruebas"), hilos=1)
        assert isinstance(red, R.Red) and T > 0 and info["epocas"] >= 2
        assert info["auc_ic95_inf"] <= info["auc"] <= info["auc_ic95_sup"]
