"""Gestor del ciclo de vida del navegador Playwright y creación de contextos aislados."""

import logging
from typing import Any, Dict, Optional, Union, cast
from playwright.async_api import Browser, BrowserContext, Playwright, ViewportSize, async_playwright
from app.config import get_settings
from app.models.session_trace import DeviceInfo

logger = logging.getLogger(__name__)

# User-Agent estándar para emulación móvil y desktop
DEFAULT_DESKTOP_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 EurekaAgent/1.0"
)
DEFAULT_MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1 EurekaAgent/1.0"
)


class BrowserManager:
    """
    Administrador centralizado de la instancia de Playwright Chromium.

    Controla el proceso del navegador headless y genera contextos aislados (BrowserContext)
    para cada traza de sesión, emulando la categoría de dispositivo del usuario (desktop/mobile)
    e inyectando headers personalizados de preproducción.
    """

    def __init__(self) -> None:
        """Inicializa las referencias de Playwright y Browser."""
        self.settings = get_settings()
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None

    async def start(self) -> None:
        """Inicia el proceso de Playwright y el navegador Chromium en modo headless."""
        if self._browser is None or self._playwright is None:
            logger.info("[BrowserManager] Inicializando motor Playwright Chromium...")
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.settings.HEADLESS_MODE,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
            logger.info("[BrowserManager] Navegador Chromium iniciado exitosamente.")

    async def close(self) -> None:
        """Cierra el navegador y termina el proceso de Playwright."""
        if self._browser:
            logger.info("[BrowserManager] Cerrando navegador Chromium...")
            await self._browser.close()
            self._browser = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
            logger.info("[BrowserManager] Proceso Playwright detenido.")

    async def __aenter__(self) -> "BrowserManager":
        """Soporte para uso mediante context manager asíncrono."""
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Cierre automático al salir del context manager asíncrono."""
        await self.close()

    async def create_context(
        self,
        device_info: Optional[DeviceInfo] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        viewport_override: Optional[ViewportSize] = None,
        storage_state: Optional[Union[Dict[str, Any], str]] = None,
    ) -> BrowserContext:
        """
        Crea un nuevo BrowserContext completamente aislado para una sesión.

        :param device_info: Información de dispositivo (desktop/mobile) para configurar viewport y UA.
        :param custom_headers: Encabezados HTTP adicionales (para bypass de staging o tokens de acceso).
        :param viewport_override: Anulación explícita de dimensiones de pantalla {width, height}.
        :param storage_state: Estado de sesión pre-autenticado (dict o ruta a archivo JSON).
        :return: Instancia de BrowserContext configurada.
        """
        if self._browser is None:
            await self.start()

        assert self._browser is not None, "El navegador no pudo inicializarse correctamente."

        is_mobile = False
        has_touch = False
        default_viewport: ViewportSize

        if device_info and device_info.tipo_dispositivo.lower() == "mobile":
            is_mobile = True
            has_touch = True
            user_agent = DEFAULT_MOBILE_UA
            default_viewport = {
                "width": self.settings.MOBILE_VIEWPORT_WIDTH,
                "height": self.settings.MOBILE_VIEWPORT_HEIGHT,
            }
        else:
            user_agent = DEFAULT_DESKTOP_UA
            default_viewport = {
                "width": self.settings.DESKTOP_VIEWPORT_WIDTH,
                "height": self.settings.DESKTOP_VIEWPORT_HEIGHT,
            }

        viewport: ViewportSize = viewport_override or default_viewport
        headers = custom_headers or {}

        context_kwargs: Dict[str, Any] = {
            "viewport": viewport,
            "user_agent": user_agent,
            "is_mobile": is_mobile,
            "has_touch": has_touch,
            "extra_http_headers": headers,
            "ignore_https_errors": True,
            "storage_state": cast(Any, storage_state),
        }

        context = await self._browser.new_context(**context_kwargs)

        # Configurar timeouts por defecto en el contexto
        context.set_default_timeout(float(self.settings.DEFAULT_TIMEOUT_MS))
        context.set_default_navigation_timeout(float(self.settings.DEFAULT_TIMEOUT_MS))

        logger.info(
            f"[BrowserManager] Contexto creado: viewport={viewport['width']}x{viewport['height']}, "
            f"mobile={is_mobile}, headers={list(headers.keys())}, "
            f"storage_state={'inyectado' if storage_state else 'ninguno'}"
        )
        return context
