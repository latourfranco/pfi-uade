"""Pruebas unitarias para BrowserManager utilizando mocks para aislamiento de sandbox."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from app.browser.browser_manager import (
    DEFAULT_DESKTOP_UA,
    DEFAULT_MOBILE_UA,
    BrowserManager,
)
from app.models.session_trace import DeviceInfo


@pytest.mark.asyncio
@pytest.mark.unit
async def test_browser_manager_lifecycle():
    """Verifica el ciclo de vida de inicio y detención del navegador."""
    manager = BrowserManager()
    assert manager._browser is None
    assert manager._playwright is None

    mock_playwright = AsyncMock()
    mock_browser = AsyncMock()
    mock_playwright.chromium.launch.return_value = mock_browser

    with patch("app.browser.browser_manager.async_playwright") as mock_ap:
        mock_ap.return_value.start = AsyncMock(return_value=mock_playwright)

        await manager.start()
        assert manager._browser == mock_browser
        assert manager._playwright == mock_playwright
        mock_playwright.chromium.launch.assert_awaited_once()

        # Segundo llamado a start no debe relanzar
        await manager.start()
        assert mock_playwright.chromium.launch.await_count == 1

        await manager.close()
        assert manager._browser is None
        assert manager._playwright is None
        mock_browser.close.assert_awaited_once()
        mock_playwright.stop.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_browser_manager_context_manager():
    """Verifica el soporte de context manager asíncrono (async with)."""
    manager = BrowserManager()
    mock_playwright = AsyncMock()
    mock_browser = AsyncMock()
    mock_playwright.chromium.launch.return_value = mock_browser

    with patch("app.browser.browser_manager.async_playwright") as mock_ap:
        mock_ap.return_value.start = AsyncMock(return_value=mock_playwright)

        async with manager as mgr:
            assert mgr._browser == mock_browser

        assert manager._browser is None
        mock_browser.close.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_desktop_context():
    """Verifica la creación de un contexto aislado para dispositivo desktop."""
    manager = BrowserManager()
    mock_browser = AsyncMock()
    mock_context = MagicMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    manager._browser = mock_browser

    device_info = DeviceInfo(tipo_dispositivo="desktop", navegador="Chrome", sistema_operativo="macOS")
    headers = {"X-Custom-Staging": "secret-token-123"}

    context = await manager.create_context(
        device_info=device_info,
        custom_headers=headers,
    )

    assert context == mock_context
    mock_browser.new_context.assert_awaited_once_with(
        viewport={
            "width": manager.settings.DESKTOP_VIEWPORT_WIDTH,
            "height": manager.settings.DESKTOP_VIEWPORT_HEIGHT,
        },
        user_agent=DEFAULT_DESKTOP_UA,
        is_mobile=False,
        has_touch=False,
        extra_http_headers=headers,
        ignore_https_errors=True,
        storage_state=None,
    )
    mock_context.set_default_timeout.assert_called_once_with(float(manager.settings.DEFAULT_TIMEOUT_MS))
    mock_context.set_default_navigation_timeout.assert_called_once_with(float(manager.settings.DEFAULT_TIMEOUT_MS))


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_mobile_context():
    """Verifica la creación de un contexto aislado para dispositivo móvil."""
    manager = BrowserManager()
    mock_browser = AsyncMock()
    mock_context = MagicMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    manager._browser = mock_browser

    device_info = DeviceInfo(tipo_dispositivo="mobile", navegador="Safari", sistema_operativo="iOS")

    context = await manager.create_context(device_info=device_info)
    assert context == mock_context
    mock_browser.new_context.assert_awaited_once_with(
        viewport={
            "width": manager.settings.MOBILE_VIEWPORT_WIDTH,
            "height": manager.settings.MOBILE_VIEWPORT_HEIGHT,
        },
        user_agent=DEFAULT_MOBILE_UA,
        is_mobile=True,
        has_touch=True,
        extra_http_headers={},
        ignore_https_errors=True,
        storage_state=None,
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_context_with_viewport_override():
    """Verifica la anulación personalizada de dimensiones de viewport."""
    manager = BrowserManager()
    mock_browser = AsyncMock()
    mock_context = MagicMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    manager._browser = mock_browser

    custom_vp = {"width": 1920, "height": 1080}
    context = await manager.create_context(viewport_override=custom_vp)

    assert context == mock_context
    mock_browser.new_context.assert_awaited_once_with(
        viewport=custom_vp,
        user_agent=DEFAULT_DESKTOP_UA,
        is_mobile=False,
        has_touch=False,
        extra_http_headers={},
        ignore_https_errors=True,
        storage_state=None,
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_context_with_storage_state():
    """Verifica la inyección de storage_state pre-autenticado en new_context."""
    manager = BrowserManager()
    mock_browser = AsyncMock()
    mock_context = MagicMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    manager._browser = mock_browser

    sample_state = {"cookies": [{"name": "sid", "value": "xyz"}], "origins": []}
    context = await manager.create_context(storage_state=sample_state)

    assert context == mock_context
    mock_browser.new_context.assert_awaited_once_with(
        viewport={
            "width": manager.settings.DESKTOP_VIEWPORT_WIDTH,
            "height": manager.settings.DESKTOP_VIEWPORT_HEIGHT,
        },
        user_agent=DEFAULT_DESKTOP_UA,
        is_mobile=False,
        has_touch=False,
        extra_http_headers={},
        ignore_https_errors=True,
        storage_state=sample_state,
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_context_auto_starts_browser():
    """Verifica que si _browser es None, create_context invoque automáticamente a start()."""
    manager = BrowserManager()
    mock_playwright = AsyncMock()
    mock_browser = AsyncMock()
    mock_context = MagicMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_playwright.chromium.launch.return_value = mock_browser

    with patch("app.browser.browser_manager.async_playwright") as mock_ap:
        mock_ap.return_value.start = AsyncMock(return_value=mock_playwright)

        context = await manager.create_context()
        assert context == mock_context
        assert manager._browser == mock_browser


@pytest.mark.asyncio
@pytest.mark.unit
async def test_browser_manager_close_idempotent():
    """Verifica que invocar close() cuando no hay procesos iniciados sea idempotente y seguro."""
    manager = BrowserManager()
    assert manager._browser is None
    assert manager._playwright is None
    # No debe lanzar excepción
    await manager.close()
    assert manager._browser is None
    assert manager._playwright is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_browser_manager_close_partial_states():
    """Verifica el cierre cuando solo playwright o browser están inicializados."""
    # Caso 1: solo playwright
    manager1 = BrowserManager()
    mock_playwright = AsyncMock()
    manager1._playwright = mock_playwright
    await manager1.close()
    mock_playwright.stop.assert_awaited_once()
    assert manager1._playwright is None

    # Caso 2: solo browser
    manager2 = BrowserManager()
    mock_browser = AsyncMock()
    manager2._browser = mock_browser
    await manager2.close()
    mock_browser.close.assert_awaited_once()
    assert manager2._browser is None
