"""eventos_clave, seleccion, escritura y embudo: lógica sin red ni nube."""
from unittest import mock

import numpy as np
import pytest

from modulo import embudo, escritura, eventos_clave as EC, seleccion
from modulo.config import SESION_SIN_ID_S
from modulo.preparar import preparar_sesiones

pytestmark = pytest.mark.unit


# -------------------------------------------------------------------------------------- eventos clave
@pytest.fixture
def resumen(crudos):
    return EC.resumir_eventos(preparar_sesiones(crudos, SESION_SIN_ID_S))


def _etapa(hito, eventos=None, objetivo=False):
    return dict(etapa=f"etapa {hito}", eventos_de_la_etapa=eventos or [hito], es_el_objetivo_principal=objetivo,
                hito=hito, nombre_legible=hito.upper(), motivo="porque sí")


class TestEventosClave:
    def test_resumen_agregado(self, resumen):
        assert resumen["sesiones"] > 0 and resumen["usuarios"] > 0
        ev = {e["evento"]: e for e in resumen["eventos"]}
        assert {"page_view", "add_to_cart", "purchase"} <= set(ev)
        assert "user_engagement" not in ev and "view_promotion" not in ev and "scroll" not in ev
        # ordenados por sesiones; la compra es tardía y suele ser el último evento
        assert [e["sesiones"] for e in resumen["eventos"]] == sorted((e["sesiones"] for e in resumen["eventos"]), reverse=True)
        assert ev["purchase"]["posicion_en_la_sesion_mediana"] == 1.0 and ev["purchase"]["pct_es_el_ultimo_evento"] == 100.0
        assert ev["add_to_cart"]["pct_lleva_items"] == 100.0
        assert "page_view" not in ev["add_to_cart"]["pct_sesiones_con_evento_posterior"]
        assert ev["page_view"]["evento_anterior_frecuente"]["(inicio de la sesión)"] > 0
        assert any("{param}" in p for p in ev["add_to_cart"]["paginas_frecuentes"])

    def test_mensajes(self, resumen):
        m = EC.mensajes(resumen)
        assert m[0] == {"role": "system", "content": EC.CONSIGNA} and m[1]["content"].startswith("Resumen del sitio:")

    def test_validar_ok(self, resumen):
        r = {"etapas": [_etapa("add_to_cart", ["add_to_cart", "view_cart"]), _etapa("purchase", objetivo=True)]}
        hitos = EC.validar(r, resumen)
        assert [h["evento"] for h in hitos] == ["add_to_cart", "purchase"]
        assert hitos[1]["es_objetivo_principal"] and hitos[0]["sesiones"] > 0

    @pytest.mark.parametrize("etapas, motivo", [
        ([], "ninguna etapa"),
        ([_etapa("no_existe", objetivo=True)], "no existen"),
        ([_etapa("purchase", objetivo=True), _etapa("purchase")], "repetidos"),
        ([_etapa("add_to_cart", ["view_cart"]), _etapa("purchase", objetivo=True)], "no están entre los eventos"),
        ([_etapa("purchase")], "ninguna etapa marcada"),
        ([_etapa("purchase", ["add_payment_info", "purchase"], objetivo=True)], "etapa propia"),
    ])
    def test_validar_rechaza(self, resumen, etapas, motivo):
        with pytest.raises(ValueError, match=motivo):
            EC.validar({"etapas": etapas}, resumen)


# ------------------------------------------------------------------------------------------ selección
def _patron(obj, ultimo, perdidas, sesiones=20, disp="desktop", pasos=True):
    ps = [dict(es_paso_friccion=False, tipo_dispositivo="mobile"),
          dict(es_paso_friccion=True, tipo_dispositivo=disp)] if pasos else []
    return dict(objetivo=obj, secuencia=["a", ultimo], sesiones=sesiones, sesiones_perdidas=perdidas, pasos=ps)


class TestSeleccion:
    def test_formato(self):
        assert seleccion.formato(_patron("o", "x", 1, disp=" Mobile ")) == "mobile"
        assert seleccion.formato(_patron("o", "x", 1, disp=None)) == "desktop"
        assert seleccion.formato(_patron("o", "x", 1, pasos=False)) == "desktop"
        p = _patron("o", "x", 1); p["pasos"] = [dict(es_paso_friccion=False, tipo_dispositivo="mobile")]
        assert seleccion.formato(p) == "mobile"   # sin marca: el último paso

    def test_seleccionar(self):
        pats = [_patron("compra", "x", 50), _patron("compra", "x", 40),           # duplicado del punto (compra, x)
                _patron("compra", "x", 30, disp="mobile"),                        # mismo punto, otro formato
                _patron("compra", "y", 20), _patron("compra", "z", 5),
                _patron("carrito", "w", 1), _patron("carrito", "v", -3)]
        sel, res = seleccion.seleccionar(pats, "c1")
        assert res["detectados"] == 7 and res["impacto_positivo"] == 6 and res["deduplicados"] == 5
        perd = [p["sesiones_perdidas"] for p in sel]
        assert perd == sorted(perd, reverse=True) and 40 not in perd and -3 not in perd
        assert 1 in perd   # piso por objetivo: el carrito entra aunque pese poco
        assert res["cobertura"] >= seleccion.CUOTA

    def test_sin_patrones(self):
        sel, res = seleccion.seleccionar([], "c1")
        assert sel == [] and res["cobertura"] is None


# ------------------------------------------------------------------------------------------ escritura
class TestEscritura:
    def test_id_patron_estable(self):
        a = escritura.id_patron("c1", "compra", ["x", "y"])
        assert a == escritura.id_patron("c1", "compra", ["x", "y"]) and len(a) == 32
        assert a != escritura.id_patron("c2", "compra", ["x", "y"])

    def test_filas(self):
        p = dict(objetivo="compra", secuencia=["x"], sesiones=10, usuarios=8, llegada_grupo=0.1,
                 llegada_referencia=0.5, sesiones_perdidas=4.0, pasos=[{"nombre_evento": "a"}, {"nombre_evento": "b"}])
        pats, pasos = escritura.filas([p], "c1", "m1", "2021-02-01")
        assert pats[0]["id_modelo"] == "m1" and pats[0]["primera_deteccion"] == "2021-02-01"
        assert [x["orden"] for x in pasos] == [1, 2] and pasos[0]["id_patron"] == pats[0]["id_patron"]

    def test_escribir_todo_en_una_transaccion(self):
        bq = mock.MagicMock(); bq.query.return_value.job_id = "j1"; bq.query.return_value.total_bytes_processed = None
        bq.get_table.return_value.schema = []
        r = escritura.escribir(bq, "p", [{"id_patron": "x"}], [{"id_patron": "x", "orden": 1}], {"id_modelo": "m"})
        assert r == {"job_id": "j1", "bytes_procesados": 0}
        sql = bq.query.call_args.args[0]
        assert sql.startswith("BEGIN TRANSACTION;") and sql.rstrip().endswith("COMMIT TRANSACTION;")
        assert sql.count("MERGE") == 2 and "INSERT INTO `p.friccion_resultados.sesion_representativa`" in sql
        assert bq.load_table_from_json.call_count == 3 and bq.delete_table.call_count == 3

    def test_escribir_nada(self):
        bq = mock.MagicMock()
        assert escritura.escribir(bq, "p", [], [], None) == {"job_id": None, "bytes_procesados": 0}
        bq.query.assert_not_called()

    def test_temporales_se_borran_si_falla(self):
        bq = mock.MagicMock(); bq.query.side_effect = RuntimeError("falla la transacción")
        bq.get_table.return_value.schema = []
        with pytest.raises(RuntimeError):
            escritura.escribir(bq, "p", [{"id_patron": "x"}], [], None)
        bq.delete_table.assert_called_once()


# --------------------------------------------------------------------------------------------- embudo
class TestEmbudo:
    VOCAB = {"inicio_de_sesion": 0, "OTRO": 1, "a@/x": 2, "b@/x": 3, "c@/y": 4, "a@OTRO": 5}

    def _A(self, ids):
        bits = embudo.evbit(self.VOCAB, ["a", "b"])
        return embudo.construir([np.array(x) for x in ids], [f"u{i}" for i in range(len(ids))], bits)

    def test_evbit(self):
        assert embudo.evbit(self.VOCAB, ["a", "b"]).tolist() == [0, 0, 1, 2, 0, 1]

    def test_construir_y_orden(self):
        A = self._A([[0, 2, 4, 3], [0, 4, 2, 3], [0, 3]])
        assert A["n"] == 10 and A["nses"] == 3 and A["NXT"][3] == -1 and A["P"][4] == 0
        assert embudo.aprender_orden(A, 2) == [0, 1]   # a suele venir antes que b

    def test_logros_objetivos_etiquetas(self):
        A = self._A([[0, 4, 2, 4, 3], [0, 4, 4]])
        orden = [0, 1]
        PEND, NEXT = embudo.logros(A, orden)
        goal = embudo.objetivos(A, PEND, orden)
        assert goal.tolist() == [0, 1, 2, 2, 0, 0, 1, 1]
        valid, y, adv = embudo.etiquetas(A, PEND, NEXT, goal)
        assert valid.tolist() == [False, True, True, True, False, False, True, True]
        assert y.tolist()[:4] == [True, True, True, True] and not y[6] and not y[7]
        assert adv[1] and adv[3] and not adv[2]

    def test_logros_sin_eventos_clave(self):
        A = self._A([[0, 4, 4]])
        PEND, NEXT = embudo.logros(A, [0, 1])
        assert PEND.all() and (NEXT == -1).all()
