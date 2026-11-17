"""Funciones auxiliares de la detección, con casos chicos armados a mano."""
import numpy as np
import pandas as pd
import pytest

from modulo import deteccion as D, embudo

pytestmark = pytest.mark.unit


def _A(ids):
    vocab = {"inicio_de_sesion": 0, "OTRO": 1, "a@/x": 2, "b@/x": 3, "c@/y": 4}
    return embudo.construir([np.array(x) for x in ids], [f"u{i}" for i in range(len(ids))],
                            embudo.evbit(vocab, ["a", "b"]))


class TestHashes:
    def test_hash_de_contexto_coincide_con_hash_seq(self):
        A = _A([[0, 4, 2, 3]])
        por_k = {k: H.copy() for k, H in D.hashes(A, 3)}
        # el hash de largo 3 en la posición 3 es el de la secuencia (4, 2, 3)
        assert por_k[3][3] == D.hash_seq([4, 2, 3]) and por_k[1][0] == D.hash_seq([0])
        assert D.mezclar(np.array([np.uint64(5)]), [2])[0] == np.uint64(22)

    def test_contexto_de(self):
        A = _A([[0, 4, 2, 3]])
        filas = {2: pd.DataFrame({"h": [np.uint64(7)], "i": [2]})}
        assert D.contexto_de(A, filas, 2, np.uint64(7)).tolist() == [4, 2]


class TestPruebas:
    def test_llegan_menos_y_p_menos(self):
        assert D._llegan_menos(20, 0.1, 20, 0.9) > 0
        assert D._llegan_menos(20, 0.5, 0, 0.5) == -np.inf
        assert D._p_menos(30, 0.1, 30, 0.9) < 0.01 and D._p_menos(30, 0.9, 30, 0.1) > 0.99

    def test_sin_mayor_usuario(self):
        g = pd.DataFrame({"u": [1, 1, 1, 2, 3]})
        assert D._sin_mayor_usuario(g).u.tolist() == [2, 3]

    def test_mitades(self):
        g = pd.DataFrame({"u": [0, 1, 2, 3], "y": [0, 0, 0, 0]})
        comp = pd.DataFrame({"u": [0, 1], "y": [1, 1]})
        assert D._mitades(g, comp)
        assert not D._mitades(g, comp.assign(y=0))                         # no llegan menos
        assert not D._mitades(g, comp[comp.u == 0])                        # una mitad sin comparación
        assert not D._mitades(g[g.u % 2 == 0], comp)                       # una mitad sin grupo
        assert D._mitades(g, None, ref=0.5) and not D._mitades(g, None, ref=0.0)

    def test_marcar(self):
        t = pd.DataFrame({"x": [1, 2]})
        out = D.marcar(t, np.array([0.001, 0.9]), np.array([0.3, -0.1]), np.array([0.05, 0.05]))
        assert out.marca.tolist() == [True, False] and out.cons.iloc[0] == pytest.approx(0.3 - 1.96 * 0.05)

    def test_prob_c(self):
        A = _A([[0, 4, 2]])
        P = np.array([[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]])
        goal = np.array([0, 1, 1]); adv = np.array([False, True, False])
        assert D.prob_c(A, P, goal, adv).tolist() == [0.0, 1.0, 0.0]

    def test_raices_sin_marcadas(self):
        t = pd.DataFrame({"marca": [False], "k": [1], "h": [np.uint64(1)], "nx": [2], "g": [1], "nR": [10],
                          "yR": [5], "pr": [0.5], "se": [0.1], "p": [0.5], "n_g": [10]})
        u, m = D.raices(t, _A([[0, 2]]), {}, np.zeros(2))
        assert u.empty and m.empty


class TestSesionRepresentativa:
    def test_elegir_ejemplo_sin_sesiones_que_no_llegan(self):
        grp = pd.DataFrame({"s": [0], "u": [0], "y": [1], "e": [0.5], "i": [1]})
        assert D._elegir_ejemplo(_A([[0, 2, 3]]), grp, 1, None, np.array([3])) is None

    def test_elegir_ejemplo_prefiere_las_asignadas(self):
        A = _A([[0, 4, 4, 2], [0, 4, 4, 2], [0, 4, 4]])
        grp = pd.DataFrame({"s": [0, 1, 2], "u": [0, 1, 2], "y": [0, 0, 0], "e": [0.1] * 3, "i": [1, 5, 9]})
        largo = np.array([4, 4, 3])
        assert D._elegir_ejemplo(A, grp, 1, np.array([2]), largo) == (2, 1)
        assert D._elegir_ejemplo(A, grp, 1, np.array([]), largo)[0] in (0, 1)

    def test_pasos_marca_el_patron(self):
        ses = pd.DataFrame({"tok": [["page_view@/a", "click@/a", "page_view@/b"]], "filas": [[0, 1, 2, 3]],
                            "n_filas": [[2, 1, 1]]}, index=["u_1"])
        ev = pd.DataFrame({"nombre_evento": ["page_view", "view_item", "click", "page_view"],
                           "ruta": ["/a", "/a", "/a", "/b"], "items": [None, "Prod", None, None],
                           "porcentaje_scroll": [np.nan, 90.0, np.nan, np.nan],
                           "tipo_dispositivo": ["mobile"] * 4, "navegador": [None] * 4, "sistema_operativo": ["Android"] * 4})
        pasos = D._pasos(ses, ev, 0, 2, 2)   # contexto termina en el nodo 2, patrón = nodos 2 y 3
        assert [p["en_patron"] for p in pasos] == [False, False, True, True]
        assert [p["es_paso_friccion"] for p in pasos] == [False, False, False, True]
        assert pasos[1]["items"] == "Prod" and pasos[1]["scroll"] and pasos[0]["navegador"] is None
        assert {p["id_sesion"] for p in pasos} == {"u_1"}
