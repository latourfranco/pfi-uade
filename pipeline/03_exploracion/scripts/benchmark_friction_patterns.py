"""Definición formal de los patrones de fricción sintéticos para las pruebas de performance."""

from app.models.client_config import ClientInterfaceConfig
from app.models.session_trace import DeviceInfo, EventType, SessionTrace, TraceEvent

BENCHMARK_CLIENT_ID = "client-google-merch-benchmark"
BENCHMARK_BASE_URL = "https://shop.merch.google"


def get_benchmark_client_config() -> ClientInterfaceConfig:
    """Configuración del cliente para el Google Merchandise Store."""
    return ClientInterfaceConfig(
        client_id=BENCHMARK_CLIENT_ID,
        base_url=BENCHMARK_BASE_URL,
        requires_authentication=False,
        default_timeout_ms=15000,
    )


def get_pattern_5_steps(iteration: int = 1) -> SessionTrace:
    """Variante A: Patrón de fricción corto (5 eventos) - Exploración directa."""
    return SessionTrace(
        id_patron="pattern-friction-socks-01",
        id_cliente=BENCHMARK_CLIENT_ID,
        id_sesion=f"friction_pattern_5p_iter_{iteration}",
        objetivo="select_item",
        secuencia=["page_view /", "click /", "page_view /shop/apparel/socks", "select_item /product"],
        sesiones=50,
        usuarios=42,
        llegada_grupo=0.2,
        llegada_referencia=0.45,
        sesiones_perdidas=12.5,
        device_info=DeviceInfo(tipo_dispositivo="desktop", navegador="Chrome", sistema_operativo="Mac OS"),
        events=[
            TraceEvent(
                orden=0,
                nombre_evento="page_view",
                event_type=EventType.PAGE_VIEW,
                ruta="/",
            ),
            TraceEvent(
                orden=1,
                nombre_evento="click",
                event_type=EventType.INTERACTION,
                click_detail="Apparel",
                ruta="/",
            ),
            TraceEvent(
                orden=2,
                nombre_evento="page_view",
                event_type=EventType.PAGE_VIEW,
                ruta="/shop/apparel/socks",
                scroll=True,
            ),
            TraceEvent(
                orden=3,
                nombre_evento="select_item",
                event_type=EventType.INTERACTION,
                items="Lucky Chrome Dino Socks",
                click_detail="Lucky Chrome Dino Socks",
                ruta="/shop/apparel/socks",
                en_patron=True,
            ),
            TraceEvent(
                orden=4,
                nombre_evento="page_view",
                event_type=EventType.PAGE_VIEW,
                ruta="/product/lucky-chrome-dino-socks-ggoegcxc264499",
                en_patron=True,
                es_paso_friccion=True,
            ),
        ],
    )


def get_pattern_10_steps(iteration: int = 1) -> SessionTrace:
    """Variante B: Patrón de fricción estándar (10 eventos) - Búsqueda interna, interacción y checkout."""
    return SessionTrace(
        id_patron="pattern-friction-android-02",
        id_cliente=BENCHMARK_CLIENT_ID,
        id_sesion=f"friction_pattern_10p_iter_{iteration}",
        objetivo="add_to_cart",
        secuencia=["page_view /", "search /", "select_item /shop", "add_to_cart /product"],
        sesiones=90,
        usuarios=78,
        llegada_grupo=0.15,
        llegada_referencia=0.40,
        sesiones_perdidas=22.5,
        device_info=DeviceInfo(tipo_dispositivo="desktop", navegador="Chrome", sistema_operativo="Mac OS"),
        events=[
            TraceEvent(
                orden=0,
                nombre_evento="page_view",
                event_type=EventType.PAGE_VIEW,
                ruta="/",
            ),
            TraceEvent(
                orden=1,
                nombre_evento="search",
                event_type=EventType.INTERACTION,
                search_term="Android",
                ruta="/",
            ),
            TraceEvent(
                orden=2,
                nombre_evento="page_view",
                event_type=EventType.PAGE_VIEW,
                ruta="/shop/shop-by-brand/android",
                scroll=True,
            ),
            TraceEvent(
                orden=3,
                nombre_evento="click",
                event_type=EventType.INTERACTION,
                click_detail="Filter",
                ruta="/shop/shop-by-brand/android",
            ),
            TraceEvent(
                orden=4,
                nombre_evento="select_item",
                event_type=EventType.INTERACTION,
                items="Android Head Over Heels Socks",
                click_detail="Android Head Over Heels Socks",
                ruta="/shop/shop-by-brand/android",
                en_patron=True,
            ),
            TraceEvent(
                orden=5,
                nombre_evento="page_view",
                event_type=EventType.PAGE_VIEW,
                ruta="/product/android-head-over-heels-socks-ggoeacxb217599",
                scroll=True,
                en_patron=True,
            ),
            TraceEvent(
                orden=6,
                nombre_evento="add_to_cart",
                event_type=EventType.INTERACTION,
                items="Android Head Over Heels Socks",
                click_detail="Add to Cart",
                ruta="/product/android-head-over-heels-socks-ggoeacxb217599",
                en_patron=True,
                es_paso_friccion=True,
            ),
            TraceEvent(
                orden=7,
                nombre_evento="view_cart",
                event_type=EventType.INTERACTION,
                ruta="/cart",
            ),
            TraceEvent(
                orden=8,
                nombre_evento="page_view",
                event_type=EventType.PAGE_VIEW,
                ruta="/cart",
            ),
            TraceEvent(
                orden=9,
                nombre_evento="page_view",
                event_type=EventType.PAGE_VIEW,
                ruta="/checkout",
            ),
        ],
    )


def get_pattern_20_steps(iteration: int = 1) -> SessionTrace:
    """Variante C: Patrón de fricción largo (20 eventos) - Bucles de navegación y desorientación."""
    return SessionTrace(
        id_patron="pattern-friction-wander-03",
        id_cliente=BENCHMARK_CLIENT_ID,
        id_sesion=f"friction_pattern_20p_iter_{iteration}",
        objetivo="purchase",
        sesiones=140,
        usuarios=120,
        llegada_grupo=0.08,
        llegada_referencia=0.33,
        sesiones_perdidas=35.0,
        device_info=DeviceInfo(tipo_dispositivo="desktop", navegador="Chrome", sistema_operativo="Mac OS"),
        events=[
            TraceEvent(
                orden=0,
                nombre_evento="page_view",
                event_type=EventType.PAGE_VIEW,
                ruta="/",
            ),
            TraceEvent(
                orden=1,
                nombre_evento="click",
                event_type=EventType.INTERACTION,
                click_detail="Collections",
                ruta="/",
            ),
            TraceEvent(
                orden=2,
                nombre_evento="page_view",
                event_type=EventType.PAGE_VIEW,
                ruta="/shop/collections",
                scroll=True,
            ),
            TraceEvent(
                orden=3,
                nombre_evento="click",
                event_type=EventType.INTERACTION,
                click_detail="1998 Retro Collection",
                ruta="/shop/collections",
            ),
            TraceEvent(
                orden=4,
                nombre_evento="page_view",
                event_type=EventType.PAGE_VIEW,
                ruta="/shop/collections/1998-retro-collection",
                scroll=True,
            ),
            TraceEvent(
                orden=5,
                nombre_evento="select_item",
                event_type=EventType.INTERACTION,
                items="Google 1998 Socks",
                click_detail="Google 1998 Socks",
                ruta="/shop/collections/1998-retro-collection",
            ),
            TraceEvent(
                orden=6,
                nombre_evento="page_view",
                event_type=EventType.PAGE_VIEW,
                ruta="/product/google-1998-socks-gmssgcxb121099",
            ),
            TraceEvent(
                orden=7,
                nombre_evento="click",
                event_type=EventType.INTERACTION,
                click_detail="Wishlist",
                ruta="/product/google-1998-socks-gmssgcxb121099",
            ),
            TraceEvent(
                orden=8,
                nombre_evento="search",
                event_type=EventType.INTERACTION,
                search_term="YouTube",
                ruta="/product/google-1998-socks-gmssgcxb121099",
            ),
            TraceEvent(
                orden=9,
                nombre_evento="page_view",
                event_type=EventType.PAGE_VIEW,
                ruta="/shop/shop-by-brand/youtube",
                scroll=True,
            ),
            TraceEvent(
                orden=10,
                nombre_evento="select_item",
                event_type=EventType.INTERACTION,
                items="YouTube Old School Socks",
                click_detail="YouTube Old School Socks",
                ruta="/shop/shop-by-brand/youtube",
            ),
            TraceEvent(
                orden=11,
                nombre_evento="page_view",
                event_type=EventType.PAGE_VIEW,
                ruta="/product/youtube-old-school-socks-ggoeycxq242599",
                scroll=True,
            ),
            TraceEvent(
                orden=12,
                nombre_evento="add_to_cart",
                event_type=EventType.INTERACTION,
                items="YouTube Old School Socks",
                click_detail="Add to Cart",
                ruta="/product/youtube-old-school-socks-ggoeycxq242599",
                en_patron=True,
            ),
            TraceEvent(
                orden=13,
                nombre_evento="view_cart",
                event_type=EventType.INTERACTION,
                ruta="/cart",
            ),
            TraceEvent(
                orden=14,
                nombre_evento="page_view",
                event_type=EventType.PAGE_VIEW,
                ruta="/cart",
            ),
            TraceEvent(
                orden=15,
                nombre_evento="click",
                event_type=EventType.INTERACTION,
                click_detail="Shipping",
                ruta="/product/youtube-old-school-socks-ggoeycxq242599",
            ),
            TraceEvent(
                orden=16,
                nombre_evento="page_view",
                event_type=EventType.PAGE_VIEW,
                ruta="/shipping-information",
            ),
            TraceEvent(
                orden=17,
                nombre_evento="add_shipping_info",
                event_type=EventType.INTERACTION,
                ruta="/checkout",
                en_patron=True,
            ),
            TraceEvent(
                orden=18,
                nombre_evento="add_payment_info",
                event_type=EventType.INTERACTION,
                ruta="/checkout",
                en_patron=True,
                es_paso_friccion=True,
            ),
            TraceEvent(
                orden=19,
                nombre_evento="page_view",
                event_type=EventType.PAGE_VIEW,
                ruta="/checkout",
            ),
        ],
    )


# Alias semánticos alineados al concepto de eventos
get_pattern_5_events = get_pattern_5_steps
get_pattern_10_events = get_pattern_10_steps
get_pattern_20_events = get_pattern_20_steps


def get_friction_patterns_catalog() -> dict[str, SessionTrace]:
    """Catálogo indexado de patrones de fricción disponibles para pruebas."""
    return {
        "5_eventos": get_pattern_5_steps(1),
        "10_eventos": get_pattern_10_steps(1),
        "20_eventos": get_pattern_20_steps(1),
        "5_steps": get_pattern_5_steps(1),
        "10_steps": get_pattern_10_steps(1),
        "20_steps": get_pattern_20_steps(1),
    }
