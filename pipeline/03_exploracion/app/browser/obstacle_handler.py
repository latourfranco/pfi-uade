"""Módulo para el descarte autónomo de obstáculos de interfaz (banners de cookies y modales)."""

import asyncio
import logging
from typing import Any, List, Optional, Tuple
from playwright.async_api import Dialog, Page

logger = logging.getLogger(__name__)

# Contenedores y backdrops comunes cuya animación de cierre puede terminar después del botón
OVERLAY_CONTAINERS: Tuple[str, ...] = (
    "#onetrust-banner-sdk",
    ".onetrust-pc-dark-filter",
)

# Heurísticas explícitas (allowlist) de banners de cookies y consentimiento GDPR
OBSTACLE_CANDIDATES: List[Tuple[str, str]] = [
    # Botones de cookies en español
    ('button:has-text("Aceptar todas")', "Cookies: Aceptar todas"),
    ('button:has-text("Aceptar cookies")', "Cookies: Aceptar cookies"),
    ('button:has-text("Aceptar")', "Cookies: Aceptar"),
    ('button:has-text("Acepto")', "Cookies: Acepto"),
    ('button:has-text("Entendido")', "Cookies: Entendido"),
    ('button:has-text("De acuerdo")', "Cookies: De acuerdo"),
    # Botones de cookies en inglés
    ('button:has-text("Accept all")', "Cookies: Accept all"),
    ('button:has-text("Accept cookies")', "Cookies: Accept cookies"),
    ('button:has-text("Accept All Cookies")', "Cookies: Accept All Cookies"),
    ('button:has-text("Allow all")', "Cookies: Allow all"),
    ('button:has-text("I agree")', "Cookies: I agree"),
    # Selectores de ID/clases comunes de cookies y GDPR
    ('[id*="onetrust-accept-btn-handler"]', "OneTrust: Aceptar"),
    ('[id*="cookie" i] button', "Banner Cookie: Botón"),
    ('[class*="cookie" i] button', "Banner Cookie: Botón"),
    ('[id*="consent" i] button', "Banner Consentimiento: Botón"),
]


class ObstacleHandler:
    """
    Gestor autónomo para superar obstáculos de UI sin requerir configuración manual por cliente.

    Detecta y descarta automáticamente banners de cookies, advertencias de consentimiento
    y ventanas emergentes que impiden la interacción con los elementos clave de la página.
    """

    @staticmethod
    def setup_dialog_dismissal(
        page: Page,
        dialog_notes: Optional[List[str]] = None,
    ) -> None:
        """
        Configura el descarte automático de diálogos nativos del navegador (alert, confirm, prompt).
        """
        async def _handle_dialog(dialog: Dialog) -> None:
            logger.info(
                f"[ObstacleHandler] Diálogo nativo detectado ({dialog.type}): '{dialog.message}'. Descartando..."
            )
            try:
                await dialog.dismiss()
                if dialog_notes is not None:
                    msg_preview = (dialog.message or "").strip()[:120]
                    dialog_notes.append(
                        f"Se cerró automáticamente un diálogo nativo del navegador ({dialog.type}): '{msg_preview}'."
                    )
            except Exception as exc:
                logger.debug(f"[ObstacleHandler] Error menor al descartar diálogo nativo: {exc}")

        page.on("dialog", _handle_dialog)

    @classmethod
    async def dismiss_obstacles(
        cls,
        page: Page,
        timeout_ms: int = 600,
        dismissed_descriptions: Optional[List[str]] = None,
    ) -> bool:
        """
        Intenta descartar cualquier banner de cookies o modal emergente presente en la página.

        :param page: Instancia activa de la página de Playwright.
        :param timeout_ms: Tiempo máximo en ms para esperar cada candidato.
        :param dismissed_descriptions: Lista opcional donde registrar la descripción del obstáculo cerrado.
        :return: True si se descartó algún obstáculo, False en caso contrario.
        """
        for selector, description in OBSTACLE_CANDIDATES:
            try:
                locator = page.locator(selector).first
                if await locator.is_visible(timeout=timeout_ms):
                    logger.info(f"[ObstacleHandler] Obstáculo identificado: {description}. Procediendo a cerrar...")
                    await locator.click(timeout=1000, force=True)
                    await cls._wait_for_dismissal_transition(page, locator)
                    if dismissed_descriptions is not None:
                        dismissed_descriptions.append(description)
                    return True
            except Exception:
                # Si no está visible o no responde en el timeout, continuar al siguiente candidato
                continue

        return False

    @classmethod
    async def _wait_for_dismissal_transition(
        cls,
        page: Page,
        locator: Any,
        hide_timeout_ms: int = 1500,
    ) -> None:
        """
        Espera a que el botón descartado y los overlays asociados terminen de ocultarse.

        Evita que las capturas posteriores se tomen a mitad de una animación CSS/JS de
        desvanecimiento (fade-out).
        """
        try:
            await locator.wait_for(state="hidden", timeout=hide_timeout_ms)
        except Exception:
            pass

        for container_selector in OVERLAY_CONTAINERS:
            try:
                container = page.locator(container_selector).first
                if await container.is_visible():
                    await container.wait_for(state="hidden", timeout=hide_timeout_ms)
            except Exception:
                continue

        # Margen breve para asegurar repintado limpio tras completar transiciones de opacidad
        await asyncio.sleep(0.2)
