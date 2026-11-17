"""Embudo: posiciones, eventos clave alcanzados, orden aprendido y objetivo de cada paso.

Las mismas funciones que motor_ab de la comparación de métodos (construir, primera_pos, aprender_orden, logros, objetivos,
etiquetas), con los eventos clave como parámetro en vez de la constante KEY: acá los elige el LLM por cliente.
"""
import numpy as np

from modulo.nodos import OTRO


def evbit(vocab: dict[str, int], clave: list[str]) -> np.ndarray:
    """Bit de evento clave de cada nodo (0 si su evento no es clave)."""
    out = np.zeros(len(vocab), dtype=np.int64)
    for t, i in vocab.items():
        e = t.split("@")[0]
        if e in clave and t != OTRO:
            out[i] = 1 << clave.index(e)
    return out


def construir(ids: list[np.ndarray], users, bits: np.ndarray) -> dict:
    lens = np.array([len(x) for x in ids]); n = int(lens.sum())
    starts = np.cumsum(lens) - lens
    T = np.concatenate(ids)
    S = np.repeat(np.arange(len(ids)), lens)
    SS = np.repeat(starts, lens)
    P = np.arange(n) - SS
    NXT = np.empty_like(T); NXT[:-1] = T[1:]; NXT[P == np.repeat(lens - 1, lens)] = -1
    uc, U = np.unique(np.asarray(users), return_inverse=True)
    return dict(T=T, S=S, SS=SS, P=P, NXT=NXT, KM=bits[T].copy(), U=np.repeat(U, lens), n=n, nses=len(ids),
                nus=len(uc), uc=uc)


def primera_pos(A: dict, nk: int) -> np.ndarray:
    out = np.full((nk, A["nses"]), np.iinfo(np.int64).max)
    for b in range(nk):
        m = (A["KM"] >> b) & 1 == 1
        np.minimum.at(out[b], A["S"][m], A["P"][m])
    return out


def aprender_orden(A: dict, nk: int) -> list[int]:
    """Orden de los eventos clave: para cada par, en las sesiones que tienen los dos, qué fracción tiene primero
    a uno; se ordena por cuántos pares 'gana' cada evento."""
    fp = primera_pos(A, nk); NO = np.iinfo(np.int64).max
    gana = np.zeros(nk)
    for a in range(nk):
        for b in range(nk):
            if a == b:
                continue
            m = (fp[a] < NO) & (fp[b] < NO)
            if m.any():
                gana[a] += ((fp[a][m] < fp[b][m]) + 0.5 * (fp[a][m] == fp[b][m])).mean()
    return [int(i) for i in np.argsort(-gana, kind="stable")]


def logros(A: dict, orden: list[int]):
    """Para cada evento clave: pendiente en cada posición y próxima posición en que se alcanza (un evento
    posterior en el orden implica los anteriores)."""
    idx = np.arange(A["n"]); PEND, NEXT = [], []
    for b in range(len(orden)):
        mask = sum(1 << i for i in orden[orden.index(b):])
        flag = (A["KM"] & mask) != 0
        C = np.cumsum(flag)
        prev = np.where(A["SS"] > 0, C[np.maximum(A["SS"] - 1, 0)], 0)
        PEND.append((C - prev) == 0)
        F = np.nonzero(flag)[0]
        k = np.searchsorted(F, idx, side="right")
        cand = F[np.minimum(k, max(len(F) - 1, 0))] if len(F) else np.zeros(A["n"], dtype=np.int64)
        ok = (k < len(F)) & (A["S"][cand] == A["S"]) if len(F) else np.zeros(A["n"], dtype=bool)
        NEXT.append(np.where(ok, cand, -1))
    return np.array(PEND), np.array(NEXT)


def objetivos(A: dict, PEND, orden: list[int]) -> np.ndarray:
    """Objetivo de cada posición: el primer evento clave del orden que la sesión todavía no alcanzó."""
    goal = np.zeros(A["n"], dtype=np.int64)
    for b in reversed(orden):
        goal[PEND[b]] = b + 1
    goal[A["P"] == 0] = 0
    return goal   # 0 = sin objetivo; b+1 = clave[b]


def etiquetas(A: dict, PEND, NEXT, goal):
    gi = np.maximum(goal - 1, 0); r = np.arange(A["n"])
    valid = (goal > 0) & PEND[gi, r]
    nx = NEXT[gi, r]
    return valid, nx >= 0, nx == r + 1
