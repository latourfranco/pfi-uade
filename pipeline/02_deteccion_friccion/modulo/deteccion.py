"""Detección diaria: con el modelo guardado, los patrones de fricción de la ventana y su sesión representativa.

Mismo método que el motor C de la comparación de métodos (motor_c + motor_ab, en el respaldo), sin juez
(decidido con el usuario, 2026-11-15: se reportan los patrones que marca el motor sobre toda la ventana; es el
supuesto con el que se midió el umbral de ejecución):
- bifurcación = contexto (historia que termina en el nodo actual, con la marca de entrada) + objetivo inmediato
  + paso siguiente; familia = las de >= MIN_SES sesiones; referencia V3;
- la red estima la llegada al objetivo después de cada paso; prueba = z con el desvío de un bootstrap de
  usuarios (pesos de Poisson) sobre los promedios del grupo y la referencia, con la red fija; BH;
- poda por dominancia, control del usuario que más aporta, mitades de usuarios y reparto (raices);
- orden por impacto: sesiones × (llegada de la referencia − llegada del grupo), contado (2026-11-15).
Las funciones vienen de motor_ab/motor_c con los
eventos clave como parámetro. No se cambió ningún valor del método.
"""
import numpy as np
import pandas as pd
import torch
from scipy.stats import norm
from statsmodels.stats.multitest import multipletests

from modulo import nodos, embudo, red as R

MIN_SES, KMAX, Bh = 10, 30, np.uint64(1_000_003)
REPS_SE = 200   # réplicas del bootstrap de usuarios (motor_ab.REPS_SE)


# =========================================================================== bifurcaciones (motor_ab)
def hashes(A, k_hasta):
    T1 = (A["T"] + 1).astype(np.uint64); H = T1.copy()
    with np.errstate(over="ignore"):
        yield 1, H
        for k in range(2, k_hasta + 1):
            Hs = np.zeros_like(H); Hs[1:] = H[:-1]
            H = Hs * Bh + T1
            yield k, H


def hash_seq(seq):
    h = 0
    for t in seq:
        h = (h * 1_000_003 + int(t) + 1) % (1 << 64)
    return np.uint64(h)


def mezclar(H, g):
    with np.errstate(over="ignore"):
        return H * np.uint64(4) + np.asarray(g).astype(np.uint64)


def niveles(A, valid, y, adv, goal):
    n = A["n"]; alive = valid.copy(); tablas, filas = {}, {}
    for k, H in hashes(A, KMAX):
        idx = np.nonzero(alive & (A["P"] >= k - 1))[0]
        if len(idx) == 0:
            break
        d = pd.DataFrame({"h": mezclar(H[idx], goal[idx]), "nx": A["NXT"][idx], "u": A["U"][idx], "y": y[idx],
                          "a": adv[idx], "s": A["S"][idx], "i": idx, "g": goal[idx]})
        d["ya"] = d.y & d.a
        d_todas = d
        d = d.drop_duplicates(["h", "s"], keep="first")
        ctx = d.groupby("h").agg(n=("y", "size"), ys=("y", "sum"), na=("a", "sum"), ya=("ya", "sum"),
                                 users=("u", "nunique"))
        pr = d[d.nx >= 0].groupby(["h", "nx"]).agg(n=("y", "size"), ys=("y", "sum"), na=("a", "sum"),
                                                   users=("u", "nunique"), g=("g", "first"))
        pr = pr[pr.n >= MIN_SES]
        if len(pr) == 0:
            break
        hs = pr.index.get_level_values(0).unique()
        tablas[k] = (ctx.loc[hs], pr)
        filas[k] = d[d.h.isin(hs)]
        vivos = d_todas.h.isin(ctx.index[ctx.n >= MIN_SES]).values
        alive = np.zeros(n, dtype=bool); alive[idx[vivos]] = True
    return tablas, filas


def familia(tablas):
    out = []
    for k, (ctx, pr) in tablas.items():
        t = pr.reset_index().rename(columns={"n": "n_g", "ys": "ys_g", "na": "na_g", "users": "us_g"}).merge(
            ctx.rename(columns={"n": "n_c", "ys": "ys_c", "na": "na_c", "ya": "ya_c", "users": "us_c"}),
            left_on="h", right_index=True)
        t["k"] = k; out.append(t)
    t = pd.concat(out, ignore_index=True)
    t["adv_g"] = t.na_g == t.n_g
    t["nR"] = np.where(t.adv_g, t.n_c - t.na_c, t.n_c - t.n_g - t.na_c)
    t["yR"] = np.where(t.adv_g, t.ys_c - t.ya_c, t.ys_c - t.ys_g - t.ya_c)
    return t[t.nR >= MIN_SES].reset_index(drop=True)


def marcar(t, p, d, se):
    t = t.copy()
    t["p"], t["d"], t["se"] = p, d, se
    t["marca"] = multipletests(t.p, method="fdr_bh")[0] & (t.d > 0)
    t["cons"] = t.d - 1.96 * t.se
    return t


def filas_B(fam, filas):
    partes = [pd.DataFrame({"k": k, "h": f.h.values, "nx": f.nx.values, "u": f.u.values, "a": f.a.values,
                            "i": f.i.values}) for k, f in filas.items()]
    Rr = pd.concat(partes, ignore_index=True)
    Rr["cid"] = Rr.groupby(["k", "h"], sort=False).ngroup()
    key = fam[["k", "h", "nx"]].reset_index().rename(columns={"index": "pid"})
    Rr = Rr.merge(key, on=["k", "h", "nx"], how="left")
    Rr["pid"] = Rr.pid.fillna(-1).astype(np.int64)
    fam_cid = fam[["k", "h"]].merge(Rr[["k", "h", "cid"]].drop_duplicates(), on=["k", "h"], how="left").cid.values
    return Rr, fam_cid


def sumas_B(Rr, fam, fam_cid, w, p):
    na = ~Rr.a.values
    S_c = np.bincount(Rr.cid.values, weights=w * p * na, minlength=Rr.cid.max() + 1)
    N_c = np.bincount(Rr.cid.values, weights=w * na, minlength=Rr.cid.max() + 1)
    ok = Rr.pid.values >= 0
    G_p = np.bincount(Rr.pid.values[ok], weights=(w * p)[ok], minlength=len(fam))
    G_n = np.bincount(Rr.pid.values[ok], weights=w[ok], minlength=len(fam))
    adv = fam.adv_g.values
    Rp = S_c[fam_cid] - np.where(adv, 0, G_p); Rn = N_c[fam_cid] - np.where(adv, 0, G_n)
    return G_p / np.maximum(G_n, 1e-12), Rp / np.maximum(Rn, 1e-12)


def prob_c(A, P, goal, adv):
    """Probabilidad estimada por la red después del paso de cada posición (motor_c.prob_c)."""
    sig = np.minimum(np.arange(A["n"]) + 1, A["n"] - 1)
    PC = np.where(goal > 0, P[sig, np.maximum(goal - 1, 0)], 0.0)
    PC[A["NXT"] == -1] = 0.0
    PC[adv] = 1.0
    return PC


def prueba_C(fam, filas, A, PC, reps, rng):
    """motor_c.prueba_C sin grupos al azar (eran el control de la comparación)."""
    Rr, fam_cid = filas_B(fam, filas)
    u = Rr.u.values; p0 = PC[Rr.i.values]
    pg, pr = sumas_B(Rr, fam, fam_cid, np.ones(len(Rr)), p0)
    ds = np.empty((reps, len(fam)))
    for r in range(reps):
        wr = rng.poisson(1.0, A["nus"]).astype(float)[u]
        a, b = sumas_B(Rr, fam, fam_cid, wr, p0); ds[r] = b - a
    se = np.maximum(ds.std(axis=0), 1e-9); d = pr - pg
    t = marcar(fam, norm.sf(d / se), d, se)
    t["pg"], t["pr"] = pg, pr
    return t


# =========================================================================== poda y reparto (motor_ab.raices)
def contexto_de(A, filas, k, h):
    f = filas[k]; i = int(f.i.values[np.argmax(f.h.values == h)])
    return A["T"][i - k + 1:i + 1]


def _sin_mayor_usuario(g):
    top = g.u.value_counts().index[0]
    return g[g.u.values != top]


def _llegan_menos(n1, p1, n2, p2):
    if n1 < MIN_SES or n2 < 1:
        return -np.inf
    se = np.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    return p2 - p1 - 1.96 * se


def _p_menos(n1, p1, n2, p2):
    if n1 < MIN_SES or n2 < 1:
        return 1.0
    se = np.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    return float(norm.sf((p2 - p1) / se)) if se > 0 else (0.0 if p2 > p1 else 1.0)


def _mitades(g, comp, ref=None):
    for h in (0, 1):
        gh = g[g.u.values % 2 == h]
        if len(gh) == 0:
            return False
        if ref is None:
            ch = comp[comp.u.values % 2 == h]
            if len(ch) == 0 or not gh.y.mean() < ch.y.mean():
                return False
        elif not gh.y.mean() < ref:
            return False
    return True


def raices(t, A, filas, PB):
    """motor_ab.raices con la estimación de la red (PB): poda por dominancia, control del usuario que más aporta,
    mitades de usuarios y reparto de cada sesión a la historia más larga que vivió. Ver el docstring original."""
    m = t[t.marca].copy()
    for c in ("raiz", "padre"):
        m[c] = pd.Series([None] * len(m), index=m.index, dtype=object)
    for c in ("extra", "extra_c", "p_resto", "n_resto", "valor", "n_asig", "p_resid"):
        m[c] = np.nan
    for c in ("desc", "ses_asig"):
        m[c] = pd.Series([None] * len(m), index=m.index, dtype=object)
    m["unidad"] = False
    if m.empty:
        return m.copy(), m
    keys = list(zip(m.k, m.h, m.nx)); pos = {key: i for i, key in enumerate(keys)}
    grupos = {}
    for k, f in filas.items():
        kk = [x for x in keys if x[0] == k]
        if not kk:
            continue
        clave = pd.DataFrame({"h": np.array([x[1] for x in kk], dtype=np.uint64),
                              "nx": np.array([x[2] for x in kk], dtype=f.nx.dtype)})
        sel = f.merge(clave, on=["h", "nx"])
        sel = sel.assign(e=PB[sel.i.values])
        for (h, nx), g in sel.groupby(["h", "nx"]):
            grupos[(k, h, nx)] = g[["s", "u", "y", "e", "i"]]
    ctxs = [tuple(int(x) for x in contexto_de(A, filas, k, h)) for k, h, _ in keys]
    gs = m.g.values
    nR, yR, eR, seR = m.nR.values, m.yR.values, m.pr.values, m.se.values
    corte_p = float(m.p.max())
    vivo, raiz, padre = {}, [None] * len(m), [None] * len(m)
    ex, exc, prs, nrs = (np.full(len(m), np.nan) for _ in range(4))
    ps = []
    for i in range(len(m)):
        c = ctxs[i]; nx = keys[i][2]
        for j in range(len(c) - 1, 0, -1):
            cand = (j, mezclar(hash_seq(c[-j:]), gs[i]), nx)
            if cand in pos:
                g = grupos[keys[i]]; gp = grupos[cand]; resto = gp[~gp.s.isin(g.s.values)]
                ps.append(_p_menos(len(g), g.y.mean(), len(resto), resto.y.mean() if len(resto) else 0.0)); break
    ok_bh = multipletests(ps, method="fdr_bh")[0] if ps else np.array([], bool)
    p_corte = float(max([p for p, o in zip(ps, ok_bh) if o], default=0.0))
    for i in np.argsort(m.k.values, kind="stable"):
        key = keys[i]; c = ctxs[i]; nx = key[2]; g = grupos[key]
        par = None
        for j in range(len(c) - 1, 0, -1):
            cand = (j, mezclar(hash_seq(c[-j:]), gs[i]), nx)
            if vivo.get(cand):
                par = cand; break
        if par is None:
            g2 = _sin_mayor_usuario(g); n2 = len(g2)
            if n2 < MIN_SES:
                ok = False
            else:
                d2 = eR[i] - g2.e.mean(); ok = d2 > 0 and norm.sf(d2 / seR[i]) <= corte_p
            vivo[key] = bool(ok); raiz[i] = key
        else:
            gp = grupos[par]; resto = gp[~gp.s.isin(g.s.values)]
            pv, pr_ = g.y.mean(), resto.y.mean() if len(resto) else np.nan
            ex[i] = len(g) * (pr_ - pv); prs[i] = pr_; nrs[i] = len(resto)
            exc[i] = len(g) * _llegan_menos(len(g), pv, len(resto), pr_)
            g2 = _sin_mayor_usuario(g)
            ok = (len(resto) > 0 and _p_menos(len(g), pv, len(resto), pr_) <= p_corte
                  and _p_menos(len(g2), g2.y.mean() if len(g2) else 1.0, len(resto), pr_) <= p_corte
                  and _mitades(g, resto))
            vivo[key] = bool(ok); padre[i] = par; raiz[i] = raiz[pos[par]]
    m["raiz"] = raiz; m["padre"] = padre
    m["extra"], m["extra_c"], m["p_resto"], m["n_resto"] = ex, exc, prs, nrs
    ref_c = yR / np.maximum(nR, 1)
    asig, tomadas, previas = {}, {}, {}
    p_resid = np.full(len(m), np.nan)
    for i in np.lexsort((-m.n_g.values, -m.k.values)):
        key = keys[i]
        if not vivo[key]:
            continue
        t_ = tomadas.setdefault(raiz[i], set()); pv_ = previas.setdefault(raiz[i], [])
        g = grupos[key]; resid = g[~g.s.isin(t_)] if t_ else g
        if len(resid) < len(g):
            pr_ = resid.y.mean() if len(resid) else 1.0
            ok = (len(resid) >= MIN_SES and _p_menos(len(resid), pr_, nR[i], ref_c[i]) <= p_corte
                  and _mitades(resid, None, ref_c[i]))
            if not ok:
                vivo[key] = False; continue
        p_resid[i] = resid.y.mean() if len(resid) else np.nan
        asig[key] = resid.s.values; t_ |= set(resid.s.values); pv_.append(key)
    m["p_resid"] = p_resid
    m["ses_asig"] = [asig.get(x) if vivo[x] else None for x in keys]
    m["unidad"] = [bool(vivo[x]) for x in keys]
    m.attrs["grupos"] = grupos
    return m[m.unidad], m


# =========================================================================== detección completa
def detectar(modelo: dict, prep: pd.DataFrame, log, hilos: int = 4):
    """Patrones de la ventana con el modelo guardado. Devuelve (patrones, resumen). Cada patrón trae lo que
    necesitan las tablas de resultados, con su sesión representativa (pasos)."""
    rng = np.random.default_rng(0)
    apr, vocab, clave = modelo["aprendido"], modelo["vocab"], modelo["eventos_clave"]["clave"]
    inv = {i: t for t, i in vocab.items()}
    ses, ev = nodos.secuencias(prep, apr, con_filas=True)
    no_vistos = sum(t not in vocab for ts in ses.tok for t in ts)
    A = embudo.construir(nodos.a_ids(ses, vocab), ses.user.values, embudo.evbit(vocab, clave))
    orden = modelo["orden_embudo"]
    PEND, NEXT = embudo.logros(A, orden)
    goal = embudo.objetivos(A, PEND, orden)
    valid, y, adv = embudo.etiquetas(A, PEND, NEXT, goal)

    torch.set_num_threads(hilos)
    rp = modelo["red"]
    red = R.Red(rp["V"], rp["nk"]); red.load_state_dict(rp["estado"])
    D = R.por_sesion(A, PEND, goal, valid, y, rp["V"])
    P = 1 / (1 + np.exp(-R.logits(red, D, A) / rp["temperatura"]))
    PC = prob_c(A, P, goal, adv)
    gi = np.maximum(goal - 1, 0); r = np.arange(A["n"])
    auc, auc_inf, _ = R.auc_ic95(y[valid].astype(int), P[r, gi][valid], A["U"][valid], rng)

    tablas, filas = niveles(A, valid, y, adv, goal)
    fam = familia(tablas)
    t = prueba_C(fam, filas, A, PC, REPS_SE, rng)
    u, m = raices(t, A, filas, PC)
    resumen = dict(sesiones=A["nses"], nodos_no_vistos=no_vistos, auc_del_dia=round(auc, 4),
                   bifurcaciones=len(fam), marcadas=int(t.marca.sum()), patrones=len(u),
                   corte_p=round(float(t[t.marca].p.max()), 5) if t.marca.any() else None)

    grupos = m.attrs.get("grupos", {})
    largo_ses = np.array([len(f) for f in ses.filas])
    patrones = []
    for x in u.itertuples():
        g = int(x.g); grp = grupos[(x.k, x.h, x.nx)]
        i0 = int(grp.i.values[0])
        seq = [int(v) for v in A["T"][i0 - x.k + 1:i0 + 1]] + [int(x.nx)]
        pg, pr = float(x.ys_g / x.n_g), float(x.yR / x.nR)
        ej = _elegir_ejemplo(A, grp, x.k, x.ses_asig, largo_ses)
        pasos = _pasos(ses, ev, *ej, len(seq)) if ej else []
        patrones.append(dict(objetivo=clave[g - 1], secuencia=[texto_nodo(inv[int(v)]) for v in seq], sesiones=int(x.n_g),
                             usuarios=int(x.us_g), llegada_grupo=pg, llegada_referencia=pr,
                             sesiones_perdidas=float(x.n_g * (pr - pg)), pasos=pasos,                             _seq=seq, _g=g, _n_ref=int(x.nR), _cons=float(x.cons), _grp=grp,
                             _ejemplo=ej))
    patrones.sort(key=lambda p: -p["sesiones_perdidas"])
    for p in patrones:   # lo interno no sale del módulo
        for k in [k for k in p if k.startswith("_")]:
            del p[k]
    return patrones, resumen


def texto_nodo(tk: str) -> str:
    """Nodo del vocabulario -> paso legible del patrón ("evento página")."""
    if tk == nodos.INICIO:
        return nodos.INICIO
    e, pg = tk.split("@", 1)
    return f"{e} {pg.replace('·misma', ' (la misma página)')}"


def _elegir_ejemplo(A, grp, k, asig, largo_ses):
    """(sesión, posición del último nodo del contexto) de la sesión representativa: SOLO entre las del grupo que no
    llegaron al objetivo; se prefieren las que el reparto le asignó al patrón; después lo más común justo antes y
    justo después del patrón y, a igual puntaje, el largo más cercano a la mediana (pagina_patrones)."""
    no = grp[grp.y == 0]
    if len(no) == 0:
        return None
    pref = no[no.s.isin(asig)] if asig is not None and len(asig) else no
    c = pref if len(pref) else no
    i = c.i.values
    antes = np.where(A["P"][i] - k >= 0, A["T"][np.maximum(i - k, 0)], -2)
    i2 = np.minimum(i + 2, A["n"] - 1)
    despues = np.where(A["S"][i2] == A["S"][i], A["T"][i2], -1)
    moda = lambda v: pd.Series(v).mode().iloc[0]  # noqa: E731
    punt = (antes == moda(antes)).astype(int) + (despues == moda(despues)).astype(int)
    largo = largo_ses[c.s.values]
    cand = np.nonzero(punt == punt.max())[0]
    e = int(cand[np.argmin(np.abs(largo[cand] - np.median(largo)))])
    return int(c.s.values[e]), int(A["P"][c.i.values[e]])


def _pasos(ses, ev, s, p_ctx, largo_seq):
    """Eventos de la sesión s con las marcas del patrón. P = n.º de nodo (la marca de entrada es 0); el patrón va
    de p_fin - largo + 1 a p_fin, con p_fin = el paso siguiente al contexto."""
    fila = ses.iloc[s]
    p_fin = p_ctx + 1; p_ini = p_fin - largo_seq + 1
    offs = np.concatenate([[0], np.cumsum(fila.n_filas)])
    out = []
    for j in range(len(fila.tok)):
        P = j + 1
        for rr in fila.filas[offs[j]:offs[j + 1]]:
            x = ev.iloc[rr]
            out.append(dict(id_sesion=fila.name, nombre_evento=x.nombre_evento, ruta=str(x.ruta),
                            items=x["items"] if isinstance(x["items"], str) else None,
                            scroll=bool(pd.notna(x.porcentaje_scroll)), en_patron=bool(p_ini <= P <= p_fin),
                            es_paso_friccion=bool(P == p_fin), tipo_dispositivo=_txt(x.tipo_dispositivo),
                            navegador=_txt(x.navegador), sistema_operativo=_txt(x.sistema_operativo)))
    return out


def _txt(v):
    return v if isinstance(v, str) else None
