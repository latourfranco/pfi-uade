"""Pruebas unitarias para VisualHighlighter (resaltado de elementos y captura WebP)."""

from unittest.mock import AsyncMock
import pytest
from app.browser.visual_highlighter import VisualHighlighter


@pytest.mark.asyncio
@pytest.mark.unit
async def test_capture_without_locator():
    """Verifica la captura de pantalla general del viewport sin elemento destacado."""
    mock_page = AsyncMock()
    mock_page.screenshot.return_value = b"fake-webp-bytes"

    screenshot_bytes, context = await VisualHighlighter.capture_element_with_highlight(
        page=mock_page,
        locator=None,
    )

    assert screenshot_bytes == b"fake-webp-bytes"
    assert context is None
    mock_page.screenshot.assert_awaited_once_with(
        type="webp",
        quality=85,
        full_page=False,
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_capture_with_locator_and_highlight():
    """Verifica el flujo completo de resaltado, extracción de bounding box y captura WebP."""
    mock_page = AsyncMock()
    mock_page.screenshot.return_value = b"fake-highlighted-webp"

    mock_locator = AsyncMock()
    mock_locator.bounding_box.return_value = {
        "x": 120.456,
        "y": 340.789,
        "width": 200.0,
        "height": 45.0,
    }

    # Única llamada evaluate en el locator: extracción semántica (el overlay redondeado evita doble borde)
    mock_locator.evaluate.side_effect = [
        {
            "tagName": "button",
            "role": "button",
            "ariaLabel": "Añadir a la cesta",
            "elementText": "Comprar ahora",
            "surroundingText": "Precio $1500",
        },
    ]

    screenshot_bytes, context = await VisualHighlighter.capture_element_with_highlight(
        page=mock_page,
        locator=mock_locator,
        context_type="friction_point",
        screenshot_quality=90,
    )

    assert screenshot_bytes == b"fake-highlighted-webp"
    assert context is not None
    assert context.box.x == 120.46
    assert context.box.y == 340.79
    assert context.box.width == 200.0
    assert context.box.height == 45.0
    assert context.tag_name == "button"
    assert context.element_text == "Comprar ahora"
    assert context.aria_label == "Añadir a la cesta"
    assert context.context_type == "friction_point"
    assert context.surrounding_text == "Precio $1500"

    mock_locator.scroll_into_view_if_needed.assert_awaited_once()
    assert mock_locator.evaluate.await_count == 1
    assert mock_page.evaluate.await_count == 2
    mock_page.screenshot.assert_awaited_once_with(
        type="webp",
        quality=90,
        full_page=False,
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_capture_with_locator_exception_resilience():
    """Verifica que si falla el scroll o la extracción semántica, la captura se complete igual."""
    mock_page = AsyncMock()
    mock_page.screenshot.return_value = b"fallback-screenshot-bytes"

    mock_locator = AsyncMock()
    mock_locator.scroll_into_view_if_needed.side_effect = Exception("Element not attached")

    screenshot_bytes, context = await VisualHighlighter.capture_element_with_highlight(
        page=mock_page,
        locator=mock_locator,
    )

    assert screenshot_bytes == b"fallback-screenshot-bytes"
    assert context is None
    mock_page.screenshot.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_capture_with_locator_bounding_box_none():
    """Verifica que si bounding_box es None, no se genere BoundingBoxContext pero sí se capture."""
    mock_page = AsyncMock()
    mock_page.screenshot.return_value = b"bytes-no-box"

    mock_locator = AsyncMock()
    mock_locator.bounding_box.return_value = None

    screenshot_bytes, context = await VisualHighlighter.capture_element_with_highlight(
        page=mock_page,
        locator=mock_locator,
    )

    assert screenshot_bytes == b"bytes-no-box"
    assert context is None
    mock_page.screenshot.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_capture_with_locator_revert_style_exception():
    """Verifica que si falla el overlay y la limpieza del estilo fallback, se maneje limpiamente."""
    mock_page = AsyncMock()
    mock_page.screenshot.return_value = b"bytes-with-revert-error"
    mock_page.evaluate.side_effect = Exception("Overlay error")

    mock_locator = AsyncMock()
    mock_locator.bounding_box.return_value = {"x": 10, "y": 10, "width": 50, "height": 20}
    # Primera llamada evaluate: extracción semántica
    # Segunda llamada: inyección de estilo fallback
    # Tercera llamada: limpieza (falla)
    mock_locator.evaluate.side_effect = [
        {"tagName": "div"},
        None,
        Exception("Error al remover estilo"),
    ]

    screenshot_bytes, context = await VisualHighlighter.capture_element_with_highlight(
        page=mock_page,
        locator=mock_locator,
    )

    assert screenshot_bytes == b"bytes-with-revert-error"
    assert context is not None
    assert mock_locator.evaluate.await_count == 3


@pytest.mark.asyncio
@pytest.mark.unit
async def test_capture_with_overlay_evaluation_exceptions_resilience():
    """Verifica que fallos al crear o limpiar el overlay visual en page.evaluate no rompan la captura."""
    mock_page = AsyncMock()
    mock_page.screenshot.return_value = b"bytes-overlay-exc"
    mock_page.evaluate.side_effect = [
        Exception("Overlay inject error"),
        None,
    ]

    mock_locator = AsyncMock()
    mock_locator.bounding_box.return_value = {"x": 10, "y": 10, "width": 50, "height": 20}
    mock_locator.evaluate.side_effect = [{"tagName": "a"}, None, None]

    screenshot_bytes, context = await VisualHighlighter.capture_element_with_highlight(
        page=mock_page,
        locator=mock_locator,
    )
    assert screenshot_bytes == b"bytes-overlay-exc"
    assert context is not None
    assert mock_page.evaluate.await_count == 1
    assert mock_locator.evaluate.await_count == 3

    # Caso donde falla únicamente la limpieza del overlay tras crearlo
    mock_page_cleanup_err = AsyncMock()
    mock_page_cleanup_err.screenshot.return_value = b"bytes-cleanup-err"
    mock_page_cleanup_err.evaluate.side_effect = [None, Exception("Overlay cleanup error")]
    mock_locator2 = AsyncMock()
    mock_locator2.bounding_box.return_value = {"x": 20, "y": 30, "width": 60, "height": 25}
    mock_locator2.evaluate.side_effect = [{"tagName": "a"}]

    screenshot_bytes2, context2 = await VisualHighlighter.capture_element_with_highlight(
        page=mock_page_cleanup_err,
        locator=mock_locator2,
    )
    assert screenshot_bytes2 == b"bytes-cleanup-err"
    assert context2 is not None
    assert mock_page_cleanup_err.evaluate.await_count == 2
    assert mock_locator2.evaluate.await_count == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_is_locator_unoccluded_states():
    """Verifica el helper de oclusión ante visible, tapado, fuera de viewport y errores."""
    loc_ok = AsyncMock()
    loc_ok.evaluate.return_value = True
    assert await VisualHighlighter.is_locator_unoccluded(loc_ok) is True

    loc_occluded = AsyncMock()
    loc_occluded.evaluate.return_value = False
    assert await VisualHighlighter.is_locator_unoccluded(loc_occluded) is False

    loc_offscreen = AsyncMock()
    loc_offscreen.evaluate.return_value = "offscreen"
    assert await VisualHighlighter.is_locator_unoccluded(loc_offscreen, allow_offscreen=True) is True
    assert await VisualHighlighter.is_locator_unoccluded(loc_offscreen, allow_offscreen=False) is False

    loc_err = AsyncMock()
    loc_err.evaluate.side_effect = RuntimeError("Detached")
    assert await VisualHighlighter.is_locator_unoccluded(loc_err) is True


@pytest.mark.asyncio
@pytest.mark.unit
async def test_capture_skips_highlight_when_element_occluded():
    """Verifica que si el elemento está tapado en pantalla se omita el bbox y el overlay."""
    mock_page = AsyncMock()
    mock_page.screenshot.return_value = b"clean-webp"

    mock_locator = AsyncMock()
    mock_locator.bounding_box.return_value = {"x": 1131.7, "y": 21.98, "width": 36.0, "height": 36.0}
    mock_locator.evaluate.return_value = {
        "tagName": "a",
        "role": "a",
        "ariaLabel": "Login",
        "elementText": "Login",
        "surroundingText": "",
        "unoccluded": False,
    }

    screenshot_bytes, context = await VisualHighlighter.capture_element_with_highlight(
        page=mock_page,
        locator=mock_locator,
    )

    assert screenshot_bytes == b"clean-webp"
    assert context is None
    mock_page.evaluate.assert_not_awaited()
    assert mock_locator.evaluate.await_count == 1
