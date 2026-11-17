"""Red LSTM que estima, en cada paso de la sesión, la probabilidad de llegar al objetivo (motor C).

La misma red y el mismo entrenamiento que motor_c de la comparación de métodos, con estos cambios para producción (PLAN §14 y
decisiones del 2026-11-15):
- parada temprana con paciencia 10 y mínimo 10 épocas, SIN tope de épocas (el tope de 40 se alcanzaba sin
  que cortara la parada temprana: era un número puesto porque sí);
- AUC en la reserva con IC95 por bootstrap de usuarios (pesos de Poisson, como las pruebas del motor): el
  límite inferior es la regla de reentrenamiento;
- cantidad de eventos clave variable (los elige el LLM).

Entrada de la red en cada posición: el nodo (vector aprendido) y qué eventos clave ya ocurrieron. Dos salidas:
probabilidad de llegar a cada objetivo y próximo nodo (o fin), que ayuda a aprender la estructura del sitio.
Se calibra con temperature scaling en la reserva.
"""
import logging
import time

import numpy as np
import torch
import torch.nn as nn
from scipy.optimize import minimize_scalar
from sklearn.metrics import roc_auc_score
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence

from modulo.nodos import es_reserva

EMB, HID, DROP, LR, BATCH = 32, 64, 0.1, 2e-3, 64
PACIENCIA, MIN_EP = 10, 10
REPS_IC = 200   # réplicas del bootstrap de usuarios para el IC95 de la AUC


def por_sesion(A, PEND, goal, valid, y, V):
    ach = (~PEND).T.astype(np.float32)
    sig = np.where(A["NXT"] >= 0, A["NXT"], V)
    lens = np.bincount(A["S"], minlength=A["nses"])
    cortes = np.cumsum(lens)[:-1]
    sp = lambda x: np.split(x, cortes)  # noqa: E731
    return dict(lens=lens, starts=np.cumsum(lens) - lens, tok=sp(A["T"]), ach=sp(ach), sig=sp(sig),
                goal=sp(goal), y=sp(y.astype(np.float32)), valid=sp(valid), nk=PEND.shape[0])


def lote(D, idx):
    L = int(D["lens"][idx].max()); b = len(idx); nk = D["nk"]
    tok = np.zeros((b, L), np.int64); ach = np.zeros((b, L, nk), np.float32)
    sig = np.full((b, L), -100, np.int64); goal = np.zeros((b, L), np.int64)
    y = np.zeros((b, L), np.float32); val = np.zeros((b, L), bool)
    for j, s in enumerate(idx):
        n = D["lens"][s]
        tok[j, :n] = D["tok"][s]; ach[j, :n] = D["ach"][s]; sig[j, :n] = D["sig"][s]
        goal[j, :n] = D["goal"][s]; y[j, :n] = D["y"][s]; val[j, :n] = D["valid"][s]
    t = torch.from_numpy
    return t(tok), t(ach), t(sig), t(goal), t(y), t(val), torch.from_numpy(D["lens"][idx].astype(np.int64))


def lotes(D, sesiones, mezclar, rng):
    s = np.array(sesiones)
    if mezclar:
        s = rng.permutation(s)
        trozos = [c[np.argsort(D["lens"][c])] for c in np.array_split(s, max(1, len(s) // (BATCH * 50)))]
        bs = [c[i:i + BATCH] for c in trozos for i in range(0, len(c), BATCH)]
        return [bs[i] for i in rng.permutation(len(bs))]
    s = s[np.argsort(D["lens"][s])]
    return [s[i:i + BATCH * 4] for i in range(0, len(s), BATCH * 4)]


class Red(nn.Module):
    def __init__(self, V, nk):
        super().__init__()
        self.emb = nn.Embedding(V, EMB)
        self.lstm = nn.LSTM(EMB + nk, HID, batch_first=True)
        self.drop = nn.Dropout(DROP)
        self.obj = nn.Linear(HID, nk)
        self.sig = nn.Linear(HID, V + 1)

    def forward(self, tok, ach, lens):
        x = torch.cat([self.emb(tok), ach], -1)
        h, _ = self.lstm(pack_padded_sequence(x, lens, batch_first=True, enforce_sorted=False))
        h, _ = pad_packed_sequence(h, batch_first=True, total_length=tok.shape[1])
        h = self.drop(h)
        return self.obj(h), self.sig(h)


def perdidas(red, b):
    tok, ach, sig, goal, y, val, lens = b
    lo, ls = red(tok, ach, lens)
    lg = lo.gather(-1, (goal - 1).clamp(min=0).unsqueeze(-1)).squeeze(-1)
    l_obj = nn.functional.binary_cross_entropy_with_logits(lg[val], y[val]) if val.any() else lo.sum() * 0
    l_sig = nn.functional.cross_entropy(ls.reshape(-1, ls.shape[-1]), sig.reshape(-1), ignore_index=-100)
    return l_obj, l_sig


@torch.no_grad()
def logits(red, D, A, rng=None):
    red.eval(); out = np.zeros((A["n"], D["nk"]), np.float32)
    for idx in lotes(D, range(A["nses"]), mezclar=False, rng=rng):
        tok, ach, *_, lens = lote(D, idx)
        lo, _ = red(tok, ach, lens)
        for j, s in enumerate(idx):
            n = D["lens"][s]; out[D["starts"][s]:D["starts"][s] + n] = lo[j, :n].numpy()
    return out


def logloss(p, y):
    q = np.clip(p, 1e-4, 1 - 1e-4)
    return float(-np.mean(y * np.log(q) + (1 - y) * np.log(1 - q)))


def auc_ic95(y, p, usuarios, rng) -> tuple[float, float, float]:
    """AUC y su IC95 por bootstrap de usuarios: cada réplica pesa a cada usuario con un Poisson(1)."""
    auc = float(roc_auc_score(y, p))
    uc, u = np.unique(usuarios, return_inverse=True)
    reps = []
    for _ in range(REPS_IC):
        w = rng.poisson(1.0, len(uc)).astype(float)[u]
        if w.sum() > 0 and len(np.unique(y[w > 0])) == 2:
            reps.append(roc_auc_score(y, p, sample_weight=w))
    lo, hi = np.percentile(reps, [2.5, 97.5])
    return auc, float(lo), float(hi)


def entrenar(A, PEND, goal, valid, y, V, log: logging.Logger, hilos: int = 4) -> tuple[Red, float, dict]:
    torch.manual_seed(0); torch.set_num_threads(hilos)
    rng = np.random.default_rng(0)
    D = por_sesion(A, PEND, goal, valid, y, V)
    res = es_reserva(A["uc"])[A["U"]]
    ses_res = np.zeros(A["nses"], bool); ses_res[A["S"][res]] = True
    tr, rv = np.nonzero(~ses_res)[0], np.nonzero(ses_res)[0]
    m = valid & res; gi = np.maximum(goal - 1, 0); r = np.arange(A["n"])
    red = Red(V, PEND.shape[0]); opt = torch.optim.Adam(red.parameters(), lr=LR)
    mejor, estado, sin_mejora, ep = np.inf, None, 0, 0
    log.info(f"Red: {len(tr):,} sesiones para entrenar, {len(rv):,} de reserva, {V} nodos, "
             f"{PEND.shape[0]} eventos clave", extra={"paso": "Entrenamiento de la red"})
    while True:
        ep += 1; t1 = time.time(); red.train()
        for idx in lotes(D, tr, mezclar=True, rng=rng):
            l_obj, l_sig = perdidas(red, lote(D, idx))
            opt.zero_grad(); (l_obj + l_sig).backward()
            nn.utils.clip_grad_norm_(red.parameters(), 1.0); opt.step()
        lo = logits(red, D, A)
        ll = logloss(1 / (1 + np.exp(-lo[r, gi][m])), y[m])
        mejora = ll < mejor - 1e-5
        if mejora:
            mejor, sin_mejora = ll, 0
            estado = {k: v.clone() for k, v in red.state_dict().items()}
        else:
            sin_mejora += 1
        log.info(f"Época {ep}: log-loss reserva {ll:.5f}{' (mejor)' if mejora else ''}, {time.time() - t1:.0f} s",
                 extra={"paso": "Entrenamiento de la red"})
        if sin_mejora >= PACIENCIA and ep >= MIN_EP:
            break
    red.load_state_dict(estado)
    z = logits(red, D, A)[r, gi]
    f = lambda lt: logloss(1 / (1 + np.exp(-z[m] / np.exp(lt))), y[m])  # noqa: E731
    T = float(np.exp(minimize_scalar(f, bounds=(-3, 3), method="bounded").x))
    p = 1 / (1 + np.exp(-z[m] / T))
    auc, lo95, hi95 = auc_ic95(y[m].astype(int), p, A["U"][m], rng)
    info = dict(epocas=ep, epoca_elegida=ep - sin_mejora, temperatura=round(T, 4), ll_reserva=round(logloss(p, y[m]), 5),
                auc=round(auc, 4), auc_ic95_inf=round(lo95, 4), auc_ic95_sup=round(hi95, 4),
                pasos_reserva=int(m.sum()))
    return red, T, info
