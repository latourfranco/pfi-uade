"""Pruebas unitarias para ActionGuard (protección contra clics destructivos y pagos)."""

from unittest.mock import AsyncMock
import pytest
from app.safety.action_guard import ActionGuard


@pytest.mark.unit
def test_safe_actions_allowed():
    """Verifica que acciones normales de navegación y carrito sean permitidas."""
    guard = ActionGuard()

    safe_texts = [
        "Ver producto",
        "Agregar al carrito",
        "Siguiente",
        "Continuar navegación",
        "Aplicar cupón de descuento",
        "Filtrar por categoría",
        "Iniciar sesión",
        "Buscar ofertas",
    ]

    for text in safe_texts:
        is_safe, reason = guard.is_safe_action(element_text=text)
        assert is_safe is True
        assert reason is None


@pytest.mark.unit
def test_dangerous_checkout_actions_blocked():
    """Verifica el bloqueo de botones de pago final y confirmación de compra."""
    guard = ActionGuard()

    dangerous_texts = [
        "Pagar",
        "Pagar ahora",
        "Comprar",
        "Finalizar compra",
        "Confirmar compra",
        "Confirmar orden",
        "Comprar ahora",
        "Pay now",
        "Place order",
        "Confirm order",
        "Complete order",
        "Submit payment",
        "Buy now",
        "Pagar con MercadoPago",
    ]

    for text in dangerous_texts:
        is_safe, reason = guard.is_safe_action(element_text=text)
        assert is_safe is False, f"Se esperaba bloqueo para: '{text}'"
        assert reason is not None
        assert "Acción bloqueada" in reason


@pytest.mark.unit
def test_destructive_actions_blocked():
    """Verifica el bloqueo de acciones destructivas de cuenta y datos."""
    guard = ActionGuard()

    destructive_texts = [
        "Eliminar cuenta",
        "Borrar cuenta",
        "Dar de baja",
        "Cancelar suscripción",
        "Vaciar carrito",
        "Delete account",
        "Terminate account",
        "Cancel subscription",
        "Empty cart",
    ]

    for text in destructive_texts:
        is_safe, reason = guard.is_safe_action(element_text=text)
        assert is_safe is False, f"Se esperaba bloqueo para: '{text}'"
        assert reason is not None
        assert "Acción bloqueada" in reason


@pytest.mark.unit
def test_detection_via_html_attributes():
    """Verifica la detección de términos peligrosos dentro de atributos HTML (aria-label, title, etc.)."""
    guard = ActionGuard()

    # Botón sin texto visible pero con aria-label peligroso
    is_safe, reason = guard.is_safe_action(
        element_text="",
        attributes={"aria-label": "Pagar con tarjeta de crédito"},
    )
    assert is_safe is False
    assert reason is not None

    # Botón con value de confirmación
    is_safe, reason = guard.is_safe_action(
        element_text=None,
        attributes={"value": "Confirmar orden", "id": "btn-submit"},
    )
    assert is_safe is False
    assert reason is not None


@pytest.mark.unit
def test_allow_destructive_mode():
    """Verifica que allow_destructive=True permita cualquier acción sin bloquear."""
    guard = ActionGuard(allow_destructive=True)

    is_safe, reason = guard.is_safe_action(element_text="Eliminar cuenta y pagar ahora")
    assert is_safe is True
    assert reason is None


@pytest.mark.unit
def test_custom_additional_patterns():
    """Verifica que se puedan agregar expresiones regulares personalizadas."""
    guard = ActionGuard(additional_patterns=[r"\b(resetear\s+datos)\b"])

    is_safe, reason = guard.is_safe_action(element_text="Resetear datos del sistema")
    assert is_safe is False
    assert reason is not None


@pytest.mark.unit
def test_empty_element_is_safe():
    """Verifica que elementos sin texto ni atributos se consideren seguros."""
    guard = ActionGuard()
    is_safe, reason = guard.is_safe_action(element_text="", attributes={})
    assert is_safe is True
    assert reason is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_inspect_locator_with_mock():
    """Verifica la inspección asíncrona de un objeto Locator de Playwright."""
    guard = ActionGuard()

    # Caso 1: Locator con texto peligroso
    mock_locator_danger = AsyncMock()
    mock_locator_danger.inner_text.return_value = "Pagar ahora"
    mock_locator_danger.get_attribute.return_value = None

    is_safe, reason = await guard.inspect_locator(mock_locator_danger)
    assert is_safe is False
    assert reason is not None

    # Caso 2: inner_text falla, input_value tiene texto peligroso
    mock_locator_input = AsyncMock()
    mock_locator_input.inner_text.side_effect = Exception("No inner text")
    mock_locator_input.input_value.return_value = "Confirmar compra"
    mock_locator_input.get_attribute.return_value = None

    is_safe, reason = await guard.inspect_locator(mock_locator_input)
    assert is_safe is False

    # Caso 3: Locator seguro
    mock_locator_safe = AsyncMock()
    mock_locator_safe.inner_text.return_value = "Ver más detalles"
    mock_locator_safe.get_attribute.return_value = "safe-btn"

    is_safe, reason = await guard.inspect_locator(mock_locator_safe)
    assert is_safe is True
    assert reason is None

    # Caso 4: allow_destructive=True en inspect_locator
    guard_unrestricted = ActionGuard(allow_destructive=True)
    is_safe, _ = await guard_unrestricted.inspect_locator(mock_locator_danger)
    assert is_safe is True
