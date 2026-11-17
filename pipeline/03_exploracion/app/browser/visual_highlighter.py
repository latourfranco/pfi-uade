"""Módulo de resaltado visual e instrumentación semántica de elementos para el LLM multimodal."""

import logging
from typing import Any, Optional, Tuple
from playwright.async_api import Locator, Page
from app.models.exploration_report import BoundingBox, BoundingBoxContext

logger = logging.getLogger(__name__)

# CSS inyectado temporalmente para destacar el elemento en la captura de pantalla
HIGHLIGHT_STYLE = (
    "outline: 3px solid #4A5ED6 !important; "
    "outline-offset: 3px !important; "
    "box-shadow: 0 0 12px rgba(74, 94, 214, 0.7) !important; "
    "transition: none !important;"
)

OVERLAY_ID = "__eureka_highlight_overlay__"

# Evalúa con elementFromPoint si un elemento en viewport está cubierto por otra capa (modales/drawers).
_IS_UNOCCLUDED_FN_JS = """(el) => {
    if (!el || typeof el.getBoundingClientRect !== 'function' || typeof document.elementFromPoint !== 'function') {
        return null;
    }
    const rect = el.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) {
        return false;
    }
    const vw = window.innerWidth || document.documentElement.clientWidth || 0;
    const vh = window.innerHeight || document.documentElement.clientHeight || 0;
    const cy = rect.top + rect.height / 2;
    const sampleXs = [
        rect.left + rect.width * 0.25,
        rect.left + rect.width * 0.5,
        rect.left + rect.width * 0.75,
    ];
    const inViewport = sampleXs.some((x) => x >= 0 && x < vw && cy >= 0 && cy < vh);
    if (!inViewport) {
        return 'offscreen';
    }
    const controlSelector = "a, button, [role='button'], [role='link']";
    const elControl = typeof el.closest === 'function' ? el.closest(controlSelector) : null;
    for (const sx of sampleXs) {
        if (sx < 0 || sx >= vw || cy < 0 || cy >= vh) continue;
        const top = document.elementFromPoint(sx, cy);
        if (!top) continue;
        if (top === el || el.contains(top)) return true;
        if (elControl && typeof top.closest === 'function' && top.closest(controlSelector) === elControl) {
            return true;
        }
    }
    return false;
}"""


class VisualHighlighter:
    """
    Gestiona el resaltado visual de elementos interactuados y la extracción de metadatos semánticos.

    Permite que el modelo multimodal (Qwen 3.5) identifique con exactitud el componente web
    mediante el recuadro de alta visibilidad y el BoundingBoxContext estructurado.
    """

    @staticmethod
    async def is_locator_unoccluded(locator: Any, *, allow_offscreen: bool = True) -> bool:
        """Verifica con `elementFromPoint` si un elemento visible no está tapado por otro layer."""
        try:
            result = await locator.evaluate(_IS_UNOCCLUDED_FN_JS)
        except Exception:
            return True
        if result is False:
            return False
        if result == "offscreen":
            return allow_offscreen
        return True

    @staticmethod
    async def capture_element_with_highlight(
        page: Page,
        locator: Optional[Locator] = None,
        context_type: str = "interaction",
        screenshot_quality: int = 85,
    ) -> Tuple[bytes, Optional[BoundingBoxContext]]:
        """
        Resalta un elemento en el DOM si se especifica, extrae sus coordenadas y semántica,
        y captura la pantalla del viewport en formato WebP.

        :param page: Instancia activa de la página de Playwright.
        :param locator: Localizador opcional del elemento a destacar.
        :param context_type: Razón o tipo de contexto ('interaction', 'error_source', etc.).
        :param screenshot_quality: Calidad de compresión WebP (1-100).
        :return: Tupla (bytes_imagen_webp, bounding_box_context).
        """
        bounding_box_ctx: Optional[BoundingBoxContext] = None
        highlight_applied = False
        overlay_applied = False

        if locator is not None:
            try:
                # 1. Asegurar que el elemento esté visible en el viewport
                await locator.scroll_into_view_if_needed(timeout=2500)

                # 2. Extraer caja delimitadora (coordenadas en viewport)
                raw_box = await locator.bounding_box()
                should_highlight = True
                if raw_box:
                    box = BoundingBox(
                        x=round(raw_box["x"], 2),
                        y=round(raw_box["y"], 2),
                        width=round(raw_box["width"], 2),
                        height=round(raw_box["height"], 2),
                    )

                    # 3. Extraer metadatos semánticos y validar que otro layer no tape el elemento
                    semantic_data = await locator.evaluate(
                        f"""(el) => {{
                            const checkUnoccluded = {_IS_UNOCCLUDED_FN_JS};
                            const parentText = el.parentElement ? (el.parentElement.innerText || '') : '';
                            return {{
                                tagName: el.tagName.toLowerCase(),
                                role: el.getAttribute('role') || el.tagName.toLowerCase(),
                                ariaLabel: el.getAttribute('aria-label') || '',
                                elementText: (el.innerText || el.value || '').trim().slice(0, 200),
                                surroundingText: parentText.trim().slice(0, 300),
                                unoccluded: checkUnoccluded(el)
                            }};
                        }}"""
                    )

                    if isinstance(semantic_data, dict) and semantic_data.get("unoccluded") is False:
                        logger.info(
                            "[VisualHighlighter] Elemento ocluido en viewport por otro contenedor; se omite el bbox."
                        )
                        should_highlight = False
                    else:
                        bounding_box_ctx = BoundingBoxContext(
                            box=box,
                            tag_name=semantic_data.get("tagName", "unknown"),
                            element_text=semantic_data.get("elementText", ""),
                            role=semantic_data.get("role"),
                            aria_label=semantic_data.get("ariaLabel") or None,
                            context_type=context_type,
                            surrounding_text=semantic_data.get("surroundingText") or None,
                        )

                # 4. Renderizar overlay redondeado fijo sobre el bounding box;
                # usar outline inline solo como fallback si el overlay falla o no hay raw_box.
                if should_highlight and raw_box:
                    try:
                        await page.evaluate(
                            """([overlayId, rect]) => {
                                const existing = document.getElementById(overlayId);
                                if (existing) existing.remove();
                                const overlay = document.createElement('div');
                                overlay.id = overlayId;
                                overlay.style.cssText = [
                                    'position: fixed',
                                    `left: ${Math.max(0, rect.x - 3)}px`,
                                    `top: ${Math.max(0, rect.y - 3)}px`,
                                    `width: ${rect.width + 6}px`,
                                    `height: ${rect.height + 6}px`,
                                    'border: 3px solid #4A5ED6',
                                    'border-radius: 6px',
                                    'box-shadow: 0 0 12px rgba(74, 94, 214, 0.7)',
                                    'background: rgba(74, 94, 214, 0.08)',
                                    'pointer-events: none',
                                    'z-index: 2147483647',
                                    'box-sizing: border-box',
                                ].join('; ');
                                document.body.appendChild(overlay);
                                return new Promise((resolve) =>
                                    requestAnimationFrame(() => requestAnimationFrame(resolve))
                                );
                            }""",
                            [OVERLAY_ID, raw_box],
                        )
                        overlay_applied = True
                    except Exception as overlay_exc:
                        logger.debug(f"[VisualHighlighter] No fue posible renderizar overlay: {overlay_exc}")

                if should_highlight and not overlay_applied:
                    await locator.evaluate(
                        f"(el) => {{ el.setAttribute('data-eureka-original-style', el.getAttribute('style') || ''); el.style.cssText += '{HIGHLIGHT_STYLE}'; }}"  # noqa: E501
                    )
                    highlight_applied = True

            except Exception as exc:
                logger.warning(f"[VisualHighlighter] No fue posible aplicar resaltado visual: {exc}")

        # 5. Captura de pantalla de alta fidelidad en WebP (viewport únicamente)
        screenshot_bytes = await page.screenshot(
            type="webp",
            quality=screenshot_quality,
            full_page=False,
        )

        # 6. Revertir overlay y estilo de resaltado para no alterar capturas posteriores
        if overlay_applied:
            try:
                await page.evaluate(
                    "(overlayId) => { const el = document.getElementById(overlayId); if (el) el.remove(); }",
                    OVERLAY_ID,
                )
            except Exception as overlay_cleanup_exc:
                logger.debug(f"[VisualHighlighter] Error menor al limpiar overlay: {overlay_cleanup_exc}")

        if highlight_applied and locator is not None:
            try:
                await locator.evaluate(
                    """(el) => {
                        const original = el.getAttribute('data-eureka-original-style');
                        if (original !== null) {
                            el.setAttribute('style', original);
                            el.removeAttribute('data-eureka-original-style');
                        }
                    }"""
                )
            except Exception as exc:
                logger.debug(f"[VisualHighlighter] Error menor al limpiar estilo de resaltado: {exc}")

        return screenshot_bytes, bounding_box_ctx
