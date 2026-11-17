"""Pruebas unitarias para UrlResolver (normalización y resolución zero-friction)."""

import pytest
from app.agent.url_resolver import UrlResolver


@pytest.mark.unit
def test_empty_base_url_raises_error():
    """Verifica que una base_url vacía dispare ValueError."""
    with pytest.raises(ValueError, match="no puede estar vacía"):
        UrlResolver.resolve_url("", "/carrito")


@pytest.mark.unit
def test_resolve_relative_routes():
    """Verifica la resolución correcta de rutas relativas sobre la base_url."""
    base = "https://staging.mitienda.com"

    # Ruta con barra inicial
    res1 = UrlResolver.resolve_url(base, "/productos/remeras")
    assert res1 == "https://staging.mitienda.com/productos/remeras"

    # Ruta sin barra inicial
    res2 = UrlResolver.resolve_url(base, "checkout/step1")
    assert res2 == "https://staging.mitienda.com/checkout/step1"

    # Ruta vacía o raíz
    res3 = UrlResolver.resolve_url(base, "")
    assert res3 == "https://staging.mitienda.com/"
    res4 = UrlResolver.resolve_url(base, "/")
    assert res4 == "https://staging.mitienda.com/"


@pytest.mark.unit
def test_resolve_and_replace_production_domain():
    """Verifica que URLs absolutas de producción sean reescritas hacia el dominio base del cliente."""
    base = "https://staging.mitienda.com"
    prod_url = "https://www.mitienda.com/producto/456?color=azul&talle=M"

    resolved = UrlResolver.resolve_url(base, prod_url)
    assert resolved == "https://staging.mitienda.com/producto/456?color=azul&talle=M"


@pytest.mark.unit
def test_filtering_tracking_parameters():
    """Verifica que se filtren parámetros UTM y rastreadores de analítica de la URL."""
    base = "https://staging.mitienda.com"
    url_with_utm = (
        "https://www.mitienda.com/catalogo?categoria=calzado&utm_source=google&utm_medium=cpc&gclid=XYZ123&fbclid=ABC"
    )

    resolved = UrlResolver.resolve_url(base, url_with_utm)
    assert "utm_source" not in resolved
    assert "utm_medium" not in resolved
    assert "gclid" not in resolved
    assert "fbclid" not in resolved
    assert "categoria=calzado" in resolved


@pytest.mark.unit
def test_base_url_without_protocol():
    """Verifica que si la base_url no tiene esquema, se le añada https:// por defecto."""
    base = "staging.mitienda.com"
    resolved = UrlResolver.resolve_url(base, "/contacto")
    assert resolved == "https://staging.mitienda.com/contacto"


@pytest.mark.unit
def test_extract_route_path():
    """Verifica la extracción normalizada del path limpio."""
    assert UrlResolver.extract_route_path("") == "/"
    assert UrlResolver.extract_route_path("/") == "/"
    assert UrlResolver.extract_route_path("/productos/123") == "/productos/123"
    assert UrlResolver.extract_route_path("/carrito/") == "/carrito"
    assert UrlResolver.extract_route_path("catalogo") == "/catalogo"
    assert (
        UrlResolver.extract_route_path("https://www.tienda.com/checkout?step=2#payment")
        == "/checkout"
    )
