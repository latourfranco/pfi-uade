"""Clickstream sintético con el formato de ingesta (ingesta.eventos.COLUMNAS) para las pruebas.

Un sitio genérico: inicio, listados, fichas de producto, carrito y un pago en dos pasos. El camino normal llega a la
compra con frecuencia; quien pasa por la página de ayuda después de la ficha casi nunca compra. Esa bifurcación es la
fricción que la detección tiene que encontrar. Sin datos reales: todo se genera en memoria con una semilla fija.
"""
import numpy as np
import pandas as pd

DOMINIO = "https://tienda.ejemplo.com"
COLUMNAS = ["id_usuario", "nombre_evento", "tipo_evento", "ruta", "timestamp", "detalle_click",
            "termino_busqueda", "porcentaje_scroll", "tiempo_engagement_ms", "items", "promociones",
            "pais", "ciudad", "tipo_dispositivo", "navegador", "sistema_operativo", "id_sesion"]
EVENTOS_CLAVE = ["add_to_cart", "begin_checkout", "purchase"]
INICIO = pd.Timestamp("2021-01-01 00:00:00", tz="UTC")


def _fila(uid, evento, ruta, ts, sid, disp, scroll=np.nan, items=None):
    return {"id_usuario": uid, "nombre_evento": evento, "tipo_evento": "interaccion", "ruta": DOMINIO + ruta,
            "timestamp": ts, "detalle_click": None, "termino_busqueda": None, "porcentaje_scroll": scroll,
            "tiempo_engagement_ms": 1500.0, "items": items, "promociones": None, "pais": "Argentina",
            "ciudad": "CABA", "tipo_dispositivo": disp, "navegador": "Chrome", "sistema_operativo": "Android"
            if disp == "mobile" else "Windows", "id_sesion": sid}


def generar(n_usuarios: int = 160, sesiones_por_usuario: int = 3, dias: int = 20, seed: int = 0,
            sin_id: float = 0.0) -> pd.DataFrame:
    """Eventos crudos. sin_id: fracción de sesiones sin id_sesion (como un evento de GA4 sin ga_session_id)."""
    rng = np.random.default_rng(seed)
    filas = []
    for u in range(n_usuarios):
        uid = f"u{u:04d}"
        disp = "mobile" if u % 3 == 0 else "desktop"
        for k in range(sesiones_por_usuario):
            ts = INICIO + pd.Timedelta(days=int(rng.integers(0, dias)), hours=int(rng.integers(1, 22)),
                                       minutes=int(rng.integers(0, 60)))
            sid = None if rng.random() < sin_id else int(ts.timestamp()) + k
            ses = []

            def ev(evento, ruta, dt=20, **kw):
                nonlocal ts
                ses.append(_fila(uid, evento, ruta, ts, sid, disp, **kw))
                ts = ts + pd.Timedelta(seconds=dt)

            ev("page_view", "/", dt=0)
            if rng.random() < 0.3:
                ev("user_engagement", "/")
            ev("view_promotion", "/")
            cat = str(rng.choice(["remeras", "tazas", "gorras", "buzos"]))
            ev("page_view", f"/c/{cat}", dt=0)
            ev("view_item_list", f"/c/{cat}")
            prod = int(rng.integers(1000, 1300))
            ev("select_item", f"/c/{cat}", items=f'[{{"item_name": "Producto {prod}"}}]')
            ev("page_view", f"/p/{prod}", dt=0)
            ev("view_item", f"/p/{prod}", dt=0)   # de carga: mismo instante que el page_view
            if rng.random() < 0.5:
                ev("scroll", f"/p/{prod}", scroll=90.0)
            desvio = rng.random()
            if desvio < 0.4:      # fricción: desde la ayuda casi nadie sigue
                ev("page_view", "/ayuda")
                ev("view_faq", "/ayuda")
                sigue = rng.random() < 0.1
            elif desvio < 0.8:    # desvío neutral: desde envíos casi todos siguen (la referencia)
                ev("page_view", "/envios")
                ev("view_faq", "/envios")
                sigue = rng.random() < 0.9
            else:
                sigue = rng.random() < 0.9
            if sigue:
                ev("add_to_cart", f"/p/{prod}", items=f'[{{"item_name": "Producto {prod}"}}]')
                ev("page_view", "/carrito")
                ev("view_cart", "/carrito")
                if rng.random() < 0.85:
                    ev("begin_checkout", "/carrito")
                    ev("page_view", "/pago?paso=envio", dt=0)
                    ev("add_shipping_info", "/pago?paso=envio")
                    ev("page_view", "/pago?paso=tarjeta", dt=0)
                    ev("add_payment_info", "/pago?paso=tarjeta")
                    if rng.random() < 0.9:
                        ev("purchase", "/pago?paso=tarjeta")
            filas.extend(ses)
    df = pd.DataFrame(filas, columns=COLUMNAS)
    df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S.%f") + " UTC"
    return df.sort_values(["id_usuario", "timestamp"], kind="stable").reset_index(drop=True)


def lector(df: pd.DataFrame):
    """leer(desde, hasta) sobre un DataFrame de eventos crudos, como ventana.lector_bigquery."""
    dia = df["timestamp"].str.slice(0, 10)

    def leer(desde, hasta):
        return df[(dia >= desde.isoformat()) & (dia <= hasta.isoformat())].reset_index(drop=True)
    return leer
