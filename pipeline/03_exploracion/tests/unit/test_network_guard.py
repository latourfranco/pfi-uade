"""Pruebas unitarias para NetworkGuard (intercepción de tráfico y bloqueo de pagos)."""

from unittest.mock import AsyncMock, MagicMock
import pytest
from app.safety.network_guard import NetworkGuard


@pytest.mark.unit
def test_is_blocked_with_safe_and_empty_urls():
    """Verifica que URLs vacías o dominios legítimos del cliente no sean bloqueados."""
    guard = NetworkGuard()

    # URL vacía
    blocked, reason = guard.is_blocked("", "GET")
    assert blocked is False
    assert reason is None

    # Dominio de tienda normal (incluso con método POST)
    blocked, reason = guard.is_blocked("https://tienda-cliente.com/api/cart", "POST")
    assert blocked is False
    assert reason is None


@pytest.mark.unit
def test_is_blocked_for_payment_gateways():
    """Verifica que llamadas mutables hacia pasarelas de pago conocidas sean bloqueadas."""
    guard = NetworkGuard()

    payment_test_cases = [
        ("https://api.mercadopago.com/v1/payments", "POST"),
        ("https://www.mercadopago.com.ar/checkout/pay", "POST"),
        ("https://api.stripe.com/v1/charges", "POST"),
        ("https://checkout.stripe.com/api/confirm", "PUT"),
        ("https://www.paypal.com/checkoutnow", "POST"),
        ("https://api.pagofacil.com.ar/v2/tokens", "DELETE"),
        ("https://gateway.rapipago.com.ar/transact", "PATCH"),
    ]

    for url, method in payment_test_cases:
        blocked, reason = guard.is_blocked(url, method)
        assert blocked is True, f"Se esperaba bloqueo para {method} {url}"
        assert reason is not None
        assert "bloqueada" in reason


@pytest.mark.unit
def test_payment_get_requests_behavior():
    """Verifica que GET a pasarelas se permita por defecto pero se bloquee si block_all_methods=True."""
    # Por defecto, GET no es mutable
    guard_default = NetworkGuard()
    blocked, _ = guard_default.is_blocked("https://api.stripe.com/v1/public_key", "GET")
    assert blocked is False

    # Modo estricto: bloquea cualquier solicitud hacia pasarelas
    guard_strict = NetworkGuard(block_all_methods_for_payment=True)
    blocked, reason = guard_strict.is_blocked("https://api.stripe.com/v1/public_key", "GET")
    assert blocked is True
    assert reason is not None


@pytest.mark.unit
def test_custom_blocked_domains():
    """Verifica la configuración de dominios bloqueados personalizados."""
    guard = NetworkGuard(blocked_domains={"banco-externo.com"})

    # Dominio por defecto ya no está
    blocked, _ = guard.is_blocked("https://api.stripe.com/v1/charges", "POST")
    assert blocked is False

    # Dominio personalizado bloqueado
    blocked, reason = guard.is_blocked("https://auth.banco-externo.com/transfer", "POST")
    assert blocked is True
    assert reason is not None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handle_route_abort_dangerous_request():
    """Verifica que handle_route aborte solicitudes peligrosas y las registre."""
    guard = NetworkGuard()

    mock_route = AsyncMock()
    mock_request = MagicMock()
    mock_request.url = "https://api.mercadopago.com/v1/payments"
    mock_request.method = "POST"
    mock_route.request = mock_request

    await guard.handle_route(mock_route)

    mock_route.abort.assert_awaited_once_with("blockedbyclient")
    mock_route.continue_.assert_not_called()
    assert len(guard.blocked_requests) == 1
    assert guard.blocked_requests[0]["url"] == mock_request.url
    assert guard.blocked_requests[0]["method"] == "POST"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handle_route_continue_safe_request():
    """Verifica que handle_route permita continuar solicitudes seguras."""
    guard = NetworkGuard()

    mock_route = AsyncMock()
    mock_request = MagicMock()
    mock_request.url = "https://tienda-cliente.com/productos"
    mock_request.method = "GET"
    mock_route.request = mock_request

    await guard.handle_route(mock_route)

    mock_route.continue_.assert_awaited_once()
    mock_route.abort.assert_not_called()
    assert len(guard.blocked_requests) == 0


@pytest.mark.asyncio
@pytest.mark.unit
async def test_handle_route_exception_handling():
    """Verifica que handle_route capture errores menores sin propagar excepciones."""
    guard = NetworkGuard()

    mock_route = AsyncMock()
    mock_request = MagicMock()
    mock_request.url = "https://api.mercadopago.com/v1/payments"
    mock_request.method = "POST"
    mock_route.request = mock_request
    mock_route.abort.side_effect = Exception("Error simulado de Playwright al abortar")

    # No debe levantar excepción no controlada
    await guard.handle_route(mock_route)

    # Caso continue_ con excepción
    mock_route_safe = AsyncMock()
    mock_request_safe = MagicMock()
    mock_request_safe.url = "https://tienda.com"
    mock_request_safe.method = "GET"
    mock_route_safe.request = mock_request_safe
    mock_route_safe.continue_.side_effect = Exception("Error simulado al continuar")

    await guard.handle_route(mock_route_safe)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_attach_to_page_and_context():
    """Verifica la asociación de la ruta al Page y al BrowserContext de Playwright."""
    guard = NetworkGuard()

    mock_page = AsyncMock()
    await guard.attach_to_page(mock_page)
    mock_page.route.assert_awaited_once_with("**/*", guard.handle_route)

    mock_context = AsyncMock()
    await guard.attach_to_context(mock_context)
    mock_context.route.assert_awaited_once_with("**/*", guard.handle_route)
