"""
Preprocesamiento: normalización de rutas (§3.2), filtros de calidad (§3.3).

Lo usa modulo/preparar.py, en este orden: drop_engagement_pings -> sesionizar (modulo/preparar.py) ->
drop_promo_and_load_views -> fold_scroll_events -> filter_sessions; y modulo/nodos.py: ajustar_rutas (solo al
entrenar) / aplicar_rutas.
"""
import re
import pandas as pd
from preprocesamiento.config import MIN_EVENTS_PER_SESSION, ROUTE_PARAM_MIN_VALORES


def _parse_timestamp(series: pd.Series) -> pd.Series:
    """Convierte timestamps del formato GA4 a datetime con utc.

    format='ISO8601': el dataset completo mezcla timestamps con y sin microsegundos
    ('2020-12-08 04:01:48' vs '...:48.123456'); sin esto pandas infiere el formato de
    la primera fila y falla en las otras.
    """
    return pd.to_datetime(series.str.replace(" UTC", "", regex=False), utc=True, format="ISO8601")


def drop_engagement_pings(df: pd.DataFrame) -> pd.DataFrame:
    """Descarta los eventos 'user_engagement' de GA4.

    No son una acción del usuario: son un heartbeat automático sobre la
    página en la que ya estaba (~94% comparte la misma ruta que el evento
    anterior, medido sobre la muestra de desarrollo). Dejarlos como paso
    discreto infla la longitud de sesión en ~20-30% sin agregar información
    de navegación real. El tiempo que representan queda igual capturado por
    delta_t_prev entre los eventos reales restantes, calculado después de
    este filtro (por eso se llama antes de sessionize).
    """
    n_before = len(df)
    df = df[df["nombre_evento"] != "user_engagement"].reset_index(drop=True)
    n_dropped = n_before - len(df)
    print(f"  Eventos 'user_engagement' descartados: {n_dropped:,} "
          f"({100*n_dropped/n_before:.1f}%)")
    return df


def drop_promo_and_load_views(df: pd.DataFrame) -> pd.DataFrame:
    """Descarta 'view_promotion' y los 'view_item' de carga; el resto de view_item queda como paso (§3.7).

    Se llama DESPUÉS de sessionize (no cambia el corte de sesión) y ANTES de
    fold_scroll_events. Medido sobre el dataset:
    - view_promotion: impresión del banner al cargar la página (68% con el mismo
      timestamp que un page_view, 94% siempre el mismo banner). El clic real es
      select_promotion, que se conserva.
    - view_item con el mismo timestamp que un page_view de la sesión: se dispara con
      la carga (95% de los de fichas de producto), redundante con ese page_view.
    - el resto de view_item se conserva como un paso más: abrir un producto, y en qué orden respecto
      del add_to_cart o de irse de la página, es parte del recorrido. Revisado
      (2026-10-24): antes se plegaba como contador en el paso anterior, y eso borraba
      su posición en la secuencia.
    """
    df = df.reset_index(drop=True)
    n_before = len(df)
    es_pv = df["nombre_evento"] == "page_view"
    claves_pv = set(zip(df.loc[es_pv, "session_id"], df.loc[es_pv, "timestamp"]))
    es_vi = df["nombre_evento"] == "view_item"
    de_carga = es_vi & pd.Series([k in claves_pv for k in zip(df["session_id"], df["timestamp"])],
                                 index=df.index)
    n_promo = int((df["nombre_evento"] == "view_promotion").sum())
    df = df[(df["nombre_evento"] != "view_promotion") & ~de_carga].reset_index(drop=True)
    df["delta_t_prev"] = df.groupby("session_id")["timestamp"].diff().dt.total_seconds().fillna(0.0)
    print(f"  'view_promotion' descartados: {n_promo:,} | 'view_item' de carga descartados: "
          f"{int(de_carga.sum()):,} | 'view_item' conservados como paso: "
          f"{int((df['nombre_evento'] == 'view_item').sum()):,} (filas: {n_before:,} -> {len(df):,})")
    return df


def fold_scroll_events(df: pd.DataFrame) -> pd.DataFrame:
    """Pliega los eventos 'scroll' en el paso anterior de su sesión y los elimina como fila.

    Se llama DESPUÉS de sessionize, a propósito: el scroll sí es actividad real del
    usuario (a diferencia de user_engagement) y cuenta para decidir si una pausa corta
    la sesión — sacarlo antes duplicaba el umbral P95 (7 -> 14 min) y perdía ~19% de
    las sesiones válidas, medido sobre el dataset completo. Pero como paso discreto no
    aporta navegación: en GA4 se dispara una sola vez al 90% de profundidad (100% de
    los casos en este dataset) y el 87% cae en la misma ruta que el evento anterior.
    Su información queda en el paso anterior como porcentaje_scroll = 90 ("llegó al
    fondo de la página"), que es lo que leen scroll_norm/scroll_presente. Un scroll al
    inicio de la sesión, sin paso anterior, se pliega en el siguiente. delta_t_prev se
    recalcula entre los eventos que quedan.
    """
    df = df.reset_index(drop=True)
    es_scroll = df["nombre_evento"] == "scroll"
    n_scroll = int(es_scroll.sum())
    # Paso destino: n° de eventos no-scroll vistos hasta acá en la sesión (el scroll
    # queda con el número de su anterior); los scroll iniciales (0) van al primero (1).
    paso = (~es_scroll).astype(int).groupby(df["session_id"]).cumsum().clip(lower=1)
    pct = df["porcentaje_scroll"].where(es_scroll).groupby([df["session_id"], paso]).transform("max")
    df["porcentaje_scroll"] = df["porcentaje_scroll"].fillna(pct)
    df = df[~es_scroll].reset_index(drop=True)
    df["delta_t_prev"] = df.groupby("session_id")["timestamp"].diff().dt.total_seconds().fillna(0.0)
    print(f"  Eventos 'scroll' plegados en el paso anterior: {n_scroll:,} "
          f"({100*n_scroll/(len(df)+n_scroll):.1f}%)")
    return df


def _strip_url_domain(url: str) -> str:
    """Elimina protocolo y dominio, devuelve path absoluto."""
    m = re.match(r"https?://[^/]+(/.*)", url)
    return m.group(1) if m else url


def _path_segments(path: str) -> list[str]:
    """Divide path en segmentos, decodificando %XX y normalizando."""
    s = path.strip("/")
    s = re.sub(r"\+", " ", s)
    s = re.sub(r"%([0-9A-Fa-f]{2})", lambda m: chr(int(m.group(1), 16)), s)
    return [seg for seg in s.split("/") if seg]


def _is_numeric_or_hash(seg: str) -> bool:
    """True si el segmento es numérico, UUID, hash hex largo, .axd, etc."""
    if re.fullmatch(r"\d+", seg):
        return True
    if re.fullmatch(r"[0-9a-fA-F]{8,}", seg):
        return True
    if re.fullmatch(r"[0-9a-fA-F\-]{32,}", seg):
        return True
    if re.fullmatch(r"[a-zA-Z0-9]+\.axd", seg):
        return True
    return False


def _partir_urls(rutas) -> tuple[list, list]:
    partes, fragmentos = [], []
    for url in rutas:
        resto, _, frag = _strip_url_domain(url).partition("#")
        fragmentos.append(frag)
        path, _, query = resto.partition("?")
        pares = [kv.split("=", 1) if "=" in kv else [kv, ""] for kv in query.split("&") if kv]
        partes.append((_path_segments(path), pares))
    return partes, fragmentos


def _plantilla_base(segs, pares, reglas) -> str:
    tp = []
    for s in segs:
        if tp and tp[-1] == "{param}":
            break   # debajo de un {param} todo es parte de esa entidad
        es_param = _is_numeric_or_hash(s) or reglas["path"].get(tuple(tp), False)
        tp.append("{param}" if es_param else s)
    q = "&".join(f"{k}={'{param}' if reglas['query'].get(k, False) else v}" for k, v in pares)
    return "/" + "/".join(tp) + (f"?{q}" if q else "")


def ajustar_rutas(df: pd.DataFrame, min_valores: int = ROUTE_PARAM_MIN_VALORES) -> dict:
    """Aprende la plantilla estructural de las URLs (§3.2); aplicar_rutas la agrega como 'plantilla_ruta'.

    Un segmento se reemplaza por '{param}' si es numérico/hash o si el lugar donde aparece
    toma más de `min_valores` valores distintos en el dataset: ese lugar es un parámetro
    (ej. el slug de /product/<slug>), no una página fija. El lugar es el prefijo ya
    convertido en plantilla, nivel por nivel (los hijos de /product/{param} se cuentan
    juntos); debajo de un {param} todo es parte de esa entidad y no se agrega nada más.
    En el query string, el valor de una clave es '{param}' con el mismo criterio
    (?keyword=<texto> sí, ?show=basket|payment no). El fragmento (#vista) se conserva como
    vista de la página con el mismo criterio por plantilla: pocos valores distintos son
    vistas (#login, #mi-cuenta), muchos son un parámetro (anclas) -> '#{param}' (2026-10-29).
    Puramente sintáctico: sin listas de páginas ni taxonomía del negocio. Se ajusta solo con los
    datos de detección y se aplica igual a gente nueva o a un período posterior (2026-11-14); un
    lugar que no aparece en los datos de ajuste queda literal al aplicar."""
    partes, fragmentos = _partir_urls(df["ruta"])
    valores_clave: dict[str, set] = {}
    for _, pares in partes:
        for k, v in pares:
            valores_clave.setdefault(k, set()).add(v)
    reglas = {"path": {}, "query": {k: len(v) > min_valores for k, v in valores_clave.items()}, "frag": {}}

    plantillas = [[] for _ in partes]
    max_depth = max((len(segs) for segs, _ in partes), default=0)
    for d in range(max_depth):
        hijos: dict[tuple, set] = {}
        for (segs, _), tp in zip(partes, plantillas):
            if len(segs) > d and not (tp and tp[-1] == "{param}"):
                hijos.setdefault(tuple(tp), set()).add(segs[d])
        for clave, valores in hijos.items():
            reglas["path"][clave] = len(valores) > min_valores
        for (segs, _), tp in zip(partes, plantillas):
            if len(segs) <= d or (tp and tp[-1] == "{param}"):
                continue
            s = segs[d]
            tp.append("{param}" if _is_numeric_or_hash(s) or reglas["path"][tuple(tp)] else s)

    vistas: dict[str, set] = {}
    for (segs, pares), frag in zip(partes, fragmentos):
        if frag:
            vistas.setdefault(_plantilla_base(segs, pares, reglas), set()).add(frag)
    reglas["frag"] = {base: len(v) > min_valores for base, v in vistas.items()}
    return reglas


def aplicar_rutas(df: pd.DataFrame, reglas: dict) -> pd.DataFrame:
    """Agrega 'plantilla_ruta' con reglas ya aprendidas (ajustar_rutas)."""
    df = df.copy()
    partes, fragmentos = _partir_urls(df["ruta"])
    resultado = []
    for (segs, pares), frag in zip(partes, fragmentos):
        base = _plantilla_base(segs, pares, reglas)
        if frag:
            base += "#{param}" if reglas["frag"].get(base, False) else f"#{frag}"
        resultado.append(base)
    df["plantilla_ruta"] = resultado
    return df


def filter_sessions(df: pd.DataFrame) -> pd.DataFrame:
    """Descarta sesiones con < MIN_EVENTS_PER_SESSION eventos (§3.3). Sin tope de largo: cortar una
    sesión fabrica un final falso ("se va del sitio") y pierde lo que pasó después (§14, 2026-10-30)."""
    before = df["session_id"].nunique()
    sizes = df.groupby("session_id").size()
    valid = sizes[sizes >= MIN_EVENTS_PER_SESSION].index
    df = df[df["session_id"].isin(valid)].copy()
    after_min = df["session_id"].nunique()
    print(f"  Sesiones después de filtro min={MIN_EVENTS_PER_SESSION}: {before} -> {after_min} "
          f"(descartadas {before - after_min})")
    return df
