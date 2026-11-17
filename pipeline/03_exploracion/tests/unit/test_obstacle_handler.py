"""Pruebas unitarias para ObstacleHandler (descarte de cookies y modales)."""

from unittest.mock import AsyncMock, MagicMock
import pytest
from app.browser.obstacle_handler import ObstacleHandler


@pytest.mark.asyncio
@pytest.mark.unit
async def test_dismiss_obstacles_when_found():
    """Verifica que un obstáculo visible sea clickeado y retorne True."""
    mock_page = MagicMock()
    mock_locator = AsyncMock()
    mock_locator.is_visible.return_value = True

    mock_wrapper = MagicMock()
    mock_wrapper.first = mock_locator
    mock_page.locator.return_value = mock_wrapper

    dismissed_log: list[str] = []
    dismissed = await ObstacleHandler.dismiss_obstacles(
        mock_page, timeout_ms=50, dismissed_descriptions=dismissed_log
    )

    assert dismissed is True
    assert len(dismissed_log) == 1
    mock_locator.click.assert_awaited_once_with(timeout=1000, force=True)
    mock_locator.wait_for.assert_any_await(state="hidden", timeout=1500)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_dismiss_obstacles_waits_for_overlay_containers_and_handles_wait_errors():
    """Verifica que espere el cierre de overlays visibles y tolere fallos en wait_for."""
    mock_page = MagicMock()

    mock_button = AsyncMock()
    mock_button.is_visible.return_value = True
    mock_button.wait_for.side_effect = Exception("Button already detached")

    mock_banner = AsyncMock()
    mock_banner.is_visible.return_value = True

    mock_backdrop = AsyncMock()
    mock_backdrop.is_visible.return_value = False

    def _wrapper(loc):
        w = MagicMock()
        w.first = loc
        return w

    # 1ra llamada: candidato de botón; 2da: #onetrust-banner-sdk; 3ra: .onetrust-pc-dark-filter
    mock_page.locator.side_effect = [
        _wrapper(mock_button),
        _wrapper(mock_banner),
        _wrapper(mock_backdrop),
    ]

    dismissed = await ObstacleHandler.dismiss_obstacles(mock_page, timeout_ms=50)

    assert dismissed is True
    mock_button.click.assert_awaited_once_with(timeout=1000, force=True)
    mock_banner.wait_for.assert_awaited_once_with(state="hidden", timeout=1500)
    mock_backdrop.wait_for.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_dismiss_obstacles_when_none_visible():
    """Verifica que si ningún candidato es visible retorne False sin lanzar error."""
    mock_page = MagicMock()
    mock_locator = AsyncMock()
    mock_locator.is_visible.return_value = False

    mock_wrapper = MagicMock()
    mock_wrapper.first = mock_locator
    mock_page.locator.return_value = mock_wrapper

    dismissed = await ObstacleHandler.dismiss_obstacles(mock_page, timeout_ms=50)

    assert dismissed is False
    mock_locator.click.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_dismiss_obstacles_continues_on_click_exception():
    """Verifica que si un candidato falla al clickear, continúe probando el siguiente."""
    mock_page = MagicMock()

    mock_fail_locator = AsyncMock()
    mock_fail_locator.is_visible.return_value = True
    mock_fail_locator.click.side_effect = Exception("Element detached from DOM")

    mock_success_locator = AsyncMock()
    mock_success_locator.is_visible.return_value = True

    mock_first_wrapper_1 = MagicMock()
    mock_first_wrapper_1.first = mock_fail_locator

    mock_first_wrapper_2 = MagicMock()
    mock_first_wrapper_2.first = mock_success_locator

    mock_page.locator.side_effect = [
        mock_first_wrapper_1,
        mock_first_wrapper_2,
    ]

    dismissed = await ObstacleHandler.dismiss_obstacles(mock_page, timeout_ms=50)

    assert dismissed is True
    mock_success_locator.click.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_setup_dialog_dismissal():
    """Verifica el registro y ejecución del descarte de diálogos nativos con nota contextual."""
    mock_page = MagicMock()
    notes: list[str] = []
    ObstacleHandler.setup_dialog_dismissal(mock_page, dialog_notes=notes)

    mock_page.on.assert_called_once()
    event_name, handler = mock_page.on.call_args[0]
    assert event_name == "dialog"

    mock_dialog = AsyncMock()
    mock_dialog.type = "alert"
    mock_dialog.message = "Advertencia de prueba"

    await handler(mock_dialog)
    mock_dialog.dismiss.assert_awaited_once()
    assert notes == ["Se cerró automáticamente un diálogo nativo del navegador (alert): 'Advertencia de prueba'."]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_setup_dialog_dismissal_exception():
    """Verifica que errores al descartar diálogos nativos se manejen sin propagar."""
    mock_page = MagicMock()
    ObstacleHandler.setup_dialog_dismissal(mock_page)

    _, handler = mock_page.on.call_args[0]
    mock_dialog = AsyncMock()
    mock_dialog.type = "confirm"
    mock_dialog.dismiss.side_effect = Exception("Dialog already closed")

    # No debe lanzar excepción no controlada
    await handler(mock_dialog)


@pytest.mark.unit
def test_obstacle_candidates_allowlist_excludes_generic_modal_close():
    """Verifica que OBSTACLE_CANDIDATES se limite a banners de cookies/consentimiento."""
    from app.browser.obstacle_handler import OBSTACLE_CANDIDATES

    selectors = [selector for selector, _ in OBSTACLE_CANDIDATES]
    assert not any("mainclose" in sel or sel == "button.close, button[class*=\"modal-close\"]" for sel in selectors)
    assert not any(sel in ('[aria-label="Cerrar" i]', '[aria-label="Close" i]') for sel in selectors)
    assert any("onetrust" in sel or "cookie" in sel or "consent" in sel for sel in selectors)
