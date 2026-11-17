"""Módulo para resolución escalonada de elementos del DOM a partir de metadatos de traza."""

import asyncio
import logging
import re
from typing import TYPE_CHECKING, List, Optional, Sequence, Tuple
from urllib.parse import urlparse
from playwright.async_api import Locator, Page
from app.agent.url_resolver import UrlResolver
from app.browser.visual_highlighter import VisualHighlighter

if TYPE_CHECKING:
    from app.safety.action_guard import ActionGuard

logger = logging.getLogger(__name__)


class LocatorResolver:
    """
    Resuelve localizadores de Playwright de forma resiliente para reproducir sesiones reales.

    Aplica una estrategia de resolución escalonada:
    1. Travesía de enlaces (Link Traversal): busca enlaces <a> visibles o dentro de menú mobile.
    2. Búsqueda semántica por rol accesible y texto visible.
    3. Heurísticas de inputs de búsqueda y botones clave de e-commerce.
    """

    MOBILE_MENU_TOGGLE_SELECTORS: Tuple[str, ...] = (
        ".topbar--mobile .logo > div:has(.humenu)",
        "div:has(> .humenu)",
        "header button[aria-label*='menu' i]",
        "header button[aria-label*='menú' i]",
        "header button[aria-label*='navigation' i]",
        "header button[aria-label*='navegación' i]",
        "header [role='button'][aria-label*='menu' i]",
        "header [role='button'][aria-label*='menú' i]",
        "header [class*='hamburger' i]",
        "header [class*='menu-toggle' i]",
        (
            "button[aria-label*='menu' i]"
            ":not([id*='userway' i]):not([aria-label*='accessibility' i]):not([aria-label*='accesibilidad' i])"
        ),
        (
            "[role='button'][aria-label*='menu' i]"
            ":not([id*='userway' i]):not([aria-label*='accessibility' i])"
            ":not([aria-label*='accesibilidad' i]):not([aria-label*='translation' i])"
        ),
    )

    MOBILE_MENU_CLOSE_SELECTORS: Tuple[str, ...] = (
        "[id*='nav-menu' i] button[aria-label*='close' i]",
        "[id*='nav-menu' i] button[aria-label*='cerrar' i]",
        "[class*='mobile-nav' i] button[aria-label*='close' i]",
        "[class*='drawer' i] button[aria-label*='close' i]",
    )

    DESKTOP_SUBMENU_PARENT_SELECTORS: Tuple[str, ...] = (
        "header nav li.has-dropdown > a",
        "header li.has-dropdown > a",
        "nav li.has-dropdown > a",
        "header nav li:has(ul) > a",
        "header nav li:has([class*='sub' i]) > a",
        "header nav [aria-haspopup='true']",
        "nav [aria-haspopup='true']",
        "header nav [aria-expanded]",
        "nav [aria-expanded]",
    )

    @classmethod
    async def _first_visible_in_locator(
        cls,
        wrapper: Locator,
        timeout_ms: int,
        max_candidates: int = 5,
    ) -> Optional[Locator]:
        """Retorna el primer match visible y no ocluido dentro de un wrapper de Playwright."""
        try:
            locator = wrapper.first
            if await locator.is_visible(timeout=timeout_ms) and await VisualHighlighter.is_locator_unoccluded(
                locator, allow_offscreen=True
            ):
                return locator
            total = await wrapper.count()
            if isinstance(total, int) and total > 1:
                for idx in range(1, min(total, max_candidates)):
                    candidate = wrapper.nth(idx)
                    if await candidate.is_visible(
                        timeout=timeout_ms
                    ) and await VisualHighlighter.is_locator_unoccluded(candidate, allow_offscreen=True):
                        return candidate
        except Exception:
            return None
        return None

    @classmethod
    async def _find_first_visible(
        cls,
        page: Page,
        selectors: Sequence[str],
        timeout_ms: int,
    ) -> Optional[Locator]:
        """Retorna el primer localizador visible y no ocluido entre los selectores CSS dados."""
        for selector in selectors:
            try:
                wrapper = page.locator(selector)
                found = await cls._first_visible_in_locator(wrapper, timeout_ms)
                if found is not None:
                    return found
            except Exception:
                continue
        return None

    @classmethod
    def _build_route_link_selectors(cls, page: Page, clean_path: str) -> List[str]:
        """Construye selectores CSS ordenados para localizar un enlace hacia `clean_path`."""
        if clean_path == "/":
            candidate_selectors = ["a[href='/']"]
            current_url = getattr(page, "url", "") or ""
            if isinstance(current_url, str) and current_url.startswith(("http://", "https://")):
                parsed_current = urlparse(current_url)
                if parsed_current.netloc:
                    origin = f"{parsed_current.scheme}://{parsed_current.netloc}"
                    candidate_selectors.extend([f"a[href='{origin}/']", f"a[href='{origin}']"])
            return candidate_selectors
        return [
            f"a[href='{clean_path}']",
            f"a[href$='{clean_path}']",
            f"a[href*='{clean_path}']",
            f"header [href='{clean_path}']",
            f"nav [href='{clean_path}']",
            f"header [href$='{clean_path}']",
            f"nav [href$='{clean_path}']",
        ]

    @staticmethod
    def _build_parent_route_prefixes(clean_path: str) -> List[str]:
        """Genera prefijos de ruta padre (de más específico a más general) para submenús."""
        segments = [seg for seg in clean_path.strip("/").split("/") if seg]
        return [f"/{'/'.join(segments[:end])}" for end in range(len(segments) - 1, 0, -1)]

    @classmethod
    async def find_link_to_route(
        cls,
        page: Page,
        target_route: str,
        timeout_ms: int = 1500,
    ) -> Optional[Locator]:
        """
        Busca un enlace <a> visible en la página actual que conduzca a la ruta destino.

        :param page: Página activa de Playwright.
        :param target_route: Ruta destino del siguiente evento (ej. '/carrito' o '/producto/12').
        :param timeout_ms: Tiempo máximo en ms para comprobar visibilidad.
        :return: Locator del primer enlace coincidente o None si no se encuentra.
        """
        if not target_route or not target_route.strip():
            return None

        clean_path = UrlResolver.extract_route_path(target_route)
        candidate_selectors = cls._build_route_link_selectors(page, clean_path)
        found = await cls._find_first_visible(page, candidate_selectors, timeout_ms)
        if found is not None:
            logger.info(f"[LocatorResolver] Enlace identificado hacia ruta '{clean_path}'")
        return found

    @classmethod
    async def close_mobile_menu(
        cls,
        page: Page,
        toggle_loc: Optional[Locator] = None,
        timeout_ms: int = 400,
    ) -> None:
        """Cierra el menú mobile si se abrió durante una búsqueda sin resultados."""
        close_btn = await cls._find_first_visible(page, cls.MOBILE_MENU_CLOSE_SELECTORS, timeout_ms=timeout_ms)
        target_to_click = close_btn
        if target_to_click is None:
            target_to_click = toggle_loc or await cls._find_first_visible(
                page, cls.MOBILE_MENU_TOGGLE_SELECTORS, timeout_ms=timeout_ms
            )
        if target_to_click is None:
            return
        try:
            await target_to_click.click(timeout=1000)
            await asyncio.sleep(0.3)
        except Exception:
            pass

    @classmethod
    async def find_link_in_mobile_menu(
        cls,
        page: Page,
        target_route: str,
        timeout_ms: int = 400,
    ) -> Optional[Locator]:
        """
        Abre el menú hamburguesa mobile y busca un enlace hacia `target_route`,
        expandiendo submenús padre coincidentes si fuera necesario.

        Si no encuentra coincidencia, cierra el menú antes de retornar None.
        """
        if not target_route or not target_route.strip():
            return None

        clean_path = UrlResolver.extract_route_path(target_route)
        if clean_path == "/":
            return None

        toggle_loc = await cls._find_first_visible(page, cls.MOBILE_MENU_TOGGLE_SELECTORS, timeout_ms=timeout_ms)
        if toggle_loc is None:
            return None

        try:
            await toggle_loc.click(timeout=1000)
            await asyncio.sleep(0.35)
        except Exception:
            return None

        candidate_selectors = cls._build_route_link_selectors(page, clean_path)
        found = await cls._find_first_visible(page, candidate_selectors, timeout_ms=timeout_ms)
        if found is not None:
            logger.info(f"[LocatorResolver] Enlace identificado en menú mobile hacia ruta '{clean_path}'")
            return found

        for parent_prefix in cls._build_parent_route_prefixes(clean_path):
            parent_link = await cls._find_first_visible(
                page,
                [f"a[href='{parent_prefix}']", f"a[href$='{parent_prefix}']"],
                timeout_ms=timeout_ms,
            )
            if parent_link is None:
                continue
            try:
                submenu_toggle = (
                    parent_link.locator("xpath=..")
                    .locator("button, [role='button'], [aria-expanded]")
                    .first
                )
                if await submenu_toggle.is_visible(timeout=timeout_ms):
                    await submenu_toggle.click(timeout=1000)
                    await asyncio.sleep(0.3)
                    found = await cls._find_first_visible(page, candidate_selectors, timeout_ms=timeout_ms)
                    if found is not None:
                        logger.info(
                            f"[LocatorResolver] Enlace identificado en submenú mobile '{parent_prefix}' "
                            f"hacia ruta '{clean_path}'"
                        )
                        return found
            except Exception:
                continue

        await cls.close_mobile_menu(page, toggle_loc=toggle_loc, timeout_ms=timeout_ms)
        return None

    @staticmethod
    async def reset_mouse_hover(page: Page) -> None:
        """Mueve el cursor a (0, 0) para cerrar menús desplegables activados por :hover."""
        try:
            await page.mouse.move(0, 0)
        except Exception:
            pass

    @classmethod
    async def get_desktop_menu_context(cls, locator: Locator) -> Tuple[bool, str, str]:
        """Determina si un enlace pertenece al menú de navegación desktop y extrae sus etiquetas.

        :return: Tupla (en_menu_desktop, etiqueta_enlace, etiqueta_padre_submenu).
        """
        try:
            info = await locator.evaluate(
                """(el) => {
                    if (!el || typeof el.closest !== 'function') {
                        return { inDesktopMenu: false, linkLabel: '', parentLabel: '' };
                    }
                    const inMobile = Boolean(el.closest("[class*='mobile' i], [id*='nav-menu' i], .humenu"));
                    const inFooter = Boolean(el.closest("footer"));
                    const navContainer = el.closest(
                        "header nav, nav, [role='navigation'], header .menu-list, header [class*='menu' i]"
                    );
                    const isDesktopViewport = typeof window !== 'undefined' ? window.innerWidth >= 768 : true;
                    if (!navContainer || inMobile || inFooter || !isDesktopViewport) {
                        return { inDesktopMenu: false, linkLabel: '', parentLabel: '' };
                    }
                    const linkLabel = (el.innerText || el.getAttribute('aria-label') || '').trim();
                    let parentLabel = '';
                    const submenu = el.closest(
                        "ul.sub-menu, [class*='sub-menu' i], [class*='submenu' i], [role='menu']"
                    );
                    if (submenu && submenu.parentElement) {
                        const trigger = submenu.parentElement.querySelector(
                            ":scope > a, :scope > button, :scope > [aria-haspopup], :scope > [aria-expanded]"
                        );
                        if (trigger && trigger !== el) {
                            parentLabel = (trigger.innerText || trigger.getAttribute('aria-label') || '').trim();
                        }
                    }
                    return { inDesktopMenu: true, linkLabel, parentLabel };
                }"""
            )
            if isinstance(info, dict) and info.get("inDesktopMenu"):
                return (
                    True,
                    str(info.get("linkLabel") or "").strip(),
                    str(info.get("parentLabel") or "").strip(),
                )
        except Exception:
            pass
        return False, "", ""

    @classmethod
    async def find_link_in_desktop_submenu(
        cls,
        page: Page,
        target_route: str,
        timeout_ms: int = 350,
    ) -> Optional[Locator]:
        """Despliega submenús desktop mediante hover para localizar enlaces hacia `target_route`.

        Deja desplegado únicamente el submenú donde encontró el enlace; si no halla coincidencia,
        restablece la posición del puntero para cerrar cualquier menú abierto durante la exploración.
        """
        if not target_route or not target_route.strip():
            return None

        clean_path = UrlResolver.extract_route_path(target_route)
        if clean_path == "/":
            return None

        candidate_selectors = cls._build_route_link_selectors(page, clean_path)
        attempted_hovers = 0
        max_hovers = 8

        async def _hover_and_find(trigger: Locator) -> Optional[Locator]:
            nonlocal attempted_hovers
            attempted_hovers += 1
            await trigger.hover(timeout=800)
            await asyncio.sleep(0.25)
            return await cls._find_first_visible(page, candidate_selectors, timeout_ms=timeout_ms)

        # 1. Priorizar ítems padre que compartan prefijo de ruta (ej. /shop/apparel -> /shop/apparel/womens)
        for parent_prefix in cls._build_parent_route_prefixes(clean_path):
            parent_selectors = [
                f"header nav a[href='{parent_prefix}']",
                f"header a[href='{parent_prefix}']",
                f"nav a[href='{parent_prefix}']",
                f"header nav a[href$='{parent_prefix}']",
                f"nav a[href$='{parent_prefix}']",
            ]
            parent_trigger = await cls._find_first_visible(page, parent_selectors, timeout_ms=timeout_ms)
            if parent_trigger is None:
                continue
            try:
                found = await _hover_and_find(parent_trigger)
                if found is not None:
                    logger.info(
                        f"[LocatorResolver] Enlace identificado en submenú desktop '{parent_prefix}' "
                        f"hacia ruta '{clean_path}'"
                    )
                    return found
            except Exception:
                continue

        # 2. Fallback: probar triggers desplegables visibles en cabecera/nav hasta un límite acotado
        for selector in cls.DESKTOP_SUBMENU_PARENT_SELECTORS:
            if attempted_hovers >= max_hovers:
                break
            try:
                wrapper = page.locator(selector)
                total = await wrapper.count()
                if not isinstance(total, int) or total <= 0:
                    continue
                for idx in range(min(total, max_hovers)):
                    if attempted_hovers >= max_hovers:
                        break
                    trigger = wrapper.nth(idx)
                    if not await trigger.is_visible(timeout=timeout_ms):
                        continue
                    found = await _hover_and_find(trigger)
                    if found is not None:
                        logger.info(
                            f"[LocatorResolver] Enlace identificado en submenú desktop hacia ruta '{clean_path}'"
                        )
                        return found
            except Exception:
                continue

        if attempted_hovers > 0:
            await cls.reset_mouse_hover(page)
        return None

    @classmethod
    async def find_element_by_text(
        cls,
        page: Page,
        text: str,
        role: Optional[str] = None,
        timeout_ms: int = 1500,
    ) -> Optional[Locator]:
        """
        Localiza un elemento visual mediante su texto visible o su rol accesible.

        :param page: Página activa de Playwright.
        :param text: Texto descriptivo del elemento.
        :param role: Rol ARIA opcional (button, link, heading, etc.).
        :param timeout_ms: Tiempo máximo en ms para la búsqueda.
        :return: Locator coincidente o None.
        """
        if not text or not text.strip():
            return None

        clean_text = text.strip()
        pattern = re.compile(re.escape(clean_text), re.IGNORECASE)

        # 1. Si se especificó rol, buscar por get_by_role iterando candidatos visibles
        if role:
            try:
                found_role = await cls._first_visible_in_locator(
                    page.get_by_role(role, name=pattern),  # type: ignore[arg-type]
                    timeout_ms,
                )
                if found_role is not None:
                    return found_role
            except Exception:
                pass

        # 2. Búsqueda por texto directo iterando candidatos visibles
        try:
            found_text = await cls._first_visible_in_locator(page.get_by_text(pattern), timeout_ms)
            if found_text is not None:
                return found_text
        except Exception:
            pass

        # 3. Selectores de fallback para botones y enlaces comunes
        fallback_selectors = [
            f"button:has-text('{clean_text}')",
            f"a:has-text('{clean_text}')",
            f"[aria-label*='{clean_text}' i]",
        ]
        return await cls._find_first_visible(page, fallback_selectors, timeout_ms)

    @classmethod
    async def scroll_and_find_element_by_text(
        cls,
        page: Page,
        text: str,
        role: Optional[str] = None,
        timeout_ms: int = 1500,
        max_scroll_steps: int = 10,
    ) -> Optional[Locator]:
        """Desplaza la página de forma progresiva buscando `text` en listados largos o con carga diferida."""
        if not text or not text.strip():
            return None

        scroll_step_js = """() => {
            const prevY = window.scrollY || 0;
            const prevHeight = document.documentElement ? document.documentElement.scrollHeight : 0;
            const step = Math.max(300, Math.floor((window.innerHeight || 720) * 0.85));
            window.scrollBy(0, step);
            const newY = window.scrollY || 0;
            const docHeight = document.documentElement ? document.documentElement.scrollHeight : 0;
            const maxY = Math.max(0, docHeight - (window.innerHeight || 0));
            return { moved: newY > prevY, atEnd: newY >= maxY - 2, docHeight: prevHeight };
        }"""

        step_timeout = min(timeout_ms, 500)
        for _ in range(max_scroll_steps):
            try:
                state = await page.evaluate(scroll_step_js)
            except Exception:
                break
            if not isinstance(state, dict) or not state.get("moved"):
                break

            await asyncio.sleep(0.5)
            found = await cls.find_element_by_text(page, text, role=role, timeout_ms=step_timeout)
            if found is not None:
                return found
            if state.get("atEnd"):
                # Si al llegar al final la SPA cargó más elementos (infinite scroll), continuar
                try:
                    prev_height = int(state.get("docHeight") or 0)
                    new_height = await page.evaluate(
                        "() => document.documentElement ? document.documentElement.scrollHeight : 0"
                    )
                    if isinstance(new_height, (int, float)) and new_height > prev_height:
                        continue
                except Exception:
                    pass
                break

        try:
            await page.evaluate("() => window.scrollTo(0, 0)")
        except Exception:
            pass
        return None

    QUICK_VIEW_SELECTORS = (
        "button:has-text('Quick View')",
        "button:has-text('Vista rápida')",
        "[aria-label*='quick view' i]",
        "[title*='quick view' i]",
        "[aria-label*='vista rápida' i]",
        "a:has-text('Quick View')",
    )

    @classmethod
    async def find_quick_view_for_item(
        cls,
        page: Page,
        item_name: str,
        timeout_ms: int = 1500,
    ) -> Optional[Locator]:
        """
        Localiza el botón de Quick View (vista rápida) asociado a la tarjeta del producto `item_name`.

        Si el producto está fuera del viewport inicial intenta desplazar la vista para ubicarlo,
        y ante controles visibles solo con `:hover` reintenta tras posicionar el cursor sobre la tarjeta.
        """
        if not item_name or not item_name.strip():
            return None

        clean_name = item_name.strip()
        item_loc = await cls.find_element_by_text(page, clean_name, timeout_ms=timeout_ms)
        if item_loc is None:
            item_loc = await cls.scroll_and_find_element_by_text(page, clean_name, timeout_ms=timeout_ms)
        if item_loc is None:
            return None

        async def _scan_card(card: Locator) -> Optional[Locator]:
            for selector in cls.QUICK_VIEW_SELECTORS:
                try:
                    matches = card.locator(selector)
                    if await matches.count() != 1:
                        continue
                    qv_loc = matches.first
                    if await qv_loc.is_visible(timeout=timeout_ms):
                        logger.info(
                            f"[LocatorResolver] Botón Quick View localizado para ítem '{clean_name}'"
                        )
                        return qv_loc
                except Exception:
                    continue
            return None

        try:
            card_loc = item_loc.locator(
                "xpath=ancestor::*[self::div or self::article or self::li or self::section][.//button][1]"
            )
            found = await _scan_card(card_loc)
            if found is not None:
                return found

            # Algunos catálogos desktop revelan Quick View solo al hacer hover sobre la tarjeta.
            try:
                await card_loc.hover(timeout=min(timeout_ms, 800))
            except Exception:
                return None

            found_on_hover = await _scan_card(card_loc)
            if found_on_hover is not None:
                return found_on_hover
            await cls.reset_mouse_hover(page)
        except Exception:
            return None

        return None

    @classmethod
    async def find_search_input(cls, page: Page, timeout_ms: int = 1000) -> Optional[Locator]:
        """Localiza el campo de entrada de búsqueda principal en la página."""
        search_selectors = [
            'input[type="search"]',
            'input[name*="search" i]',
            'input[name*="buscar" i]',
            'input[placeholder*="buscar" i]',
            'input[placeholder*="search" i]',
            'input[aria-label*="buscar" i]',
            'input[aria-label*="search" i]',
        ]
        return await cls._find_first_visible(page, search_selectors, timeout_ms)

    @classmethod
    async def find_add_to_cart_button(cls, page: Page, timeout_ms: int = 1500) -> Optional[Locator]:
        """Localiza el botón de agregar al carrito en páginas de producto o catálogo."""
        cart_selectors = [
            "button:has-text('Add to Cart')",
            "button:has-text('Add to bag')",
            "button:has-text('Añadir al carrito')",
            "button:has-text('Agregar al carrito')",
            "button[id*='add-to-cart' i]",
            "a:has-text('Add to Cart')",
            "a:has-text('Add to bag')",
            "a:has-text('Añadir al carrito')",
            "a:has-text('Agregar al carrito')",
            "[role='button']:has-text('Add to Cart')",
            "[role='button']:has-text('Add to bag')",
            "[role='button']:has-text('Añadir al carrito')",
            "[role='button']:has-text('Agregar al carrito')",
            "[title='Add to Cart' i]",
            "[title='Add to bag' i]",
            "[title='Añadir al carrito' i]",
            "[title='Agregar al carrito' i]",
            "[tabindex]:has-text('Add to Cart')",
            "[tabindex]:has-text('Add to bag')",
            "[tabindex]:has-text('Añadir al carrito')",
            "[tabindex]:has-text('Agregar al carrito')",
            "[data-testid*='add-to-cart' i]",
            "[data-testid*='addToCart' i]",
            "[aria-label*='add to cart' i]",
            "[aria-label*='agregar al carrito' i]",
            "[aria-label*='añadir al carrito' i]",
            "[aria-label*='cart' i]",
            "[aria-label*='carrito' i]",
        ]
        return await cls._find_first_visible(page, cart_selectors, timeout_ms)

    @classmethod
    async def ensure_positive_quantity_selected(cls, page: Page, timeout_ms: int = 500) -> bool:
        """Si todos los selectores visibles de cantidad están en 0, selecciona 1 unidad."""
        qty_selectors = (
            "input[aria-label*='quantity' i]",
            "input[aria-label*='cantidad' i]",
            "input[name*='quantity' i]",
            "input[name*='qty' i]",
            "input[name*='cantidad' i]",
            "input[class*='qty' i]",
            "input[class*='quantity' i]",
        )
        visible_inputs: List[Locator] = []
        for selector in qty_selectors:
            try:
                wrapper = page.locator(selector)
                total = await wrapper.count()
                if not isinstance(total, int) or total <= 0:
                    continue
                for idx in range(min(total, 10)):
                    candidate = wrapper.nth(idx)
                    if await candidate.is_visible(timeout=timeout_ms) and await VisualHighlighter.is_locator_unoccluded(
                        candidate, allow_offscreen=True
                    ):
                        visible_inputs.append(candidate)
            except Exception:
                continue
            if visible_inputs:
                break

        if not visible_inputs:
            return False

        # Si ya hay al menos una cantidad > 0 seleccionada, no modificar nada
        for qty_input in visible_inputs:
            try:
                raw_val = await qty_input.input_value(timeout=timeout_ms)
                if isinstance(raw_val, str) and raw_val.strip().isdigit() and int(raw_val.strip()) > 0:
                    return False
            except Exception:
                continue

        first_input = visible_inputs[0]
        try:
            container = first_input.locator("xpath=ancestor::*[.//*[normalize-space(.)='+']][1]")
            plus_loc = container.locator(
                "button:text-is('+'), [role='button']:text-is('+'), a:text-is('+'), span:text-is('+'), div:text-is('+')"
            ).first
            if await plus_loc.is_visible(timeout=timeout_ms):
                await plus_loc.click(timeout=timeout_ms)
                updated_val = await first_input.input_value(timeout=timeout_ms)
                if isinstance(updated_val, str) and updated_val.strip().isdigit() and int(updated_val.strip()) > 0:
                    logger.info("[LocatorResolver] Cantidad inicial incrementada a >= 1 mediante control '+'.")
                    return True
        except Exception:
            pass

        try:
            await first_input.fill("1", timeout=timeout_ms)
            updated_val = await first_input.input_value(timeout=timeout_ms)
            if isinstance(updated_val, str) and updated_val.strip().isdigit() and int(updated_val.strip()) > 0:
                logger.info("[LocatorResolver] Cantidad inicial establecida a 1 en input de cantidad.")
                return True
        except Exception:
            pass
        return False

    @classmethod
    async def ensure_required_option_selected(
        cls,
        page: Page,
        timeout_ms: int = 500,
    ) -> Optional[Tuple[str, str]]:
        """Si hay un `<select>` de variante/opción sin selección (ej. 'Choose Size'), elige la primera válida."""
        inspect_selects_js = """() => {
            const placeholderRe = /^(choose|select|pick|elegir|elige|selecciona|seleccionar|escoge)\\b/i;
            const ignoredAttrRe = /(sort|order|lang|locale|currency|country|filter|page|limit)/i;
            const selects = Array.from(document.querySelectorAll('select'));
            const candidates = [];
            for (let idx = 0; idx < selects.length; idx++) {
                const sel = selects[idx];
                if (sel.disabled || sel.closest('header, nav, footer, aside')) continue;
                const meta = `${sel.id || ''} ${sel.name || ''} ${sel.className || ''}`;
                if (ignoredAttrRe.test(meta)) continue;
                const style = window.getComputedStyle(sel);
                if (!style || style.display === 'none' || style.visibility === 'hidden') continue;
                const rect = sel.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0) continue;

                const selectedOpt = sel.selectedIndex >= 0 ? sel.options[sel.selectedIndex] : null;
                const selectedText = selectedOpt ? (selectedOpt.text || '').trim() : '';
                const isPlaceholder = !selectedOpt
                    || !!selectedOpt.disabled
                    || sel.value === ''
                    || sel.value === '-1'
                    || placeholderRe.test(selectedText);
                if (!isPlaceholder) continue;

                const validOpt = Array.from(sel.options).find((opt) => {
                    const txt = (opt.text || '').trim();
                    return !opt.disabled
                        && opt.value !== ''
                        && opt.value !== '-1'
                        && !placeholderRe.test(txt);
                });
                if (!validOpt) continue;
                candidates.push({
                    index: idx,
                    placeholderText: selectedText || sel.value || 'sin selección',
                    optionValue: validOpt.value,
                    optionText: (validOpt.text || validOpt.value || '').trim(),
                });
            }
            return candidates;
        }"""
        try:
            candidates = await page.evaluate(inspect_selects_js)
        except Exception:
            return None
        if not isinstance(candidates, list) or not candidates:
            return None

        first_match: Optional[Tuple[str, str]] = None
        for item in candidates:
            if not isinstance(item, dict):
                continue
            idx = item.get("index")
            opt_val = item.get("optionValue")
            opt_text = str(item.get("optionText") or opt_val or "")
            placeholder_text = str(item.get("placeholderText") or "")
            if not isinstance(idx, int) or opt_val is None:
                continue
            try:
                select_loc = page.locator("select").nth(idx)
                if not await VisualHighlighter.is_locator_unoccluded(select_loc, allow_offscreen=True):
                    continue
                await select_loc.select_option(value=str(opt_val), timeout=timeout_ms)
                logger.info(
                    f"[LocatorResolver] Opción '{opt_text}' seleccionada en selector que iniciaba en "
                    f"'{placeholder_text}'."
                )
                if first_match is None:
                    first_match = (placeholder_text, opt_text)
            except Exception:
                continue
        return first_match

    @classmethod
    async def find_checkout_or_continue_button(cls, page: Page, timeout_ms: int = 1500) -> Optional[Locator]:
        """Localiza botones de progreso de compra (checkout, shipping, billing, payment)."""
        action_selectors = [
            "button:has-text('Checkout')",
            "button:has-text('Continue')",
            "button:has-text('Continuar')",
            "button:has-text('Shipping')",
            "button:has-text('Add Address')",
            "button:has-text('Pay')",
            "button:has-text('Pagar')",
            "a:has-text('Checkout')",
        ]
        return await cls._find_first_visible(page, action_selectors, timeout_ms)

    @classmethod
    async def find_begin_checkout_button(cls, page: Page, timeout_ms: int = 1500) -> Optional[Locator]:
        """Localiza botones o enlaces que inician el flujo de checkout sin incluir acciones de pago."""
        start_selectors = [
            "button:has-text('Proceed to Checkout')",
            "a:has-text('Proceed to Checkout')",
            "button:has-text('Checkout')",
            "a:has-text('Checkout')",
            "button:has-text('Iniciar compra')",
            "a:has-text('Iniciar compra')",
            "button:has-text('Finalizar pedido')",
            "a:has-text('Finalizar pedido')",
        ]
        return await cls._find_first_visible(page, start_selectors, timeout_ms)

    @classmethod
    async def is_locator_disabled(cls, locator: Locator, timeout_ms: int = 400) -> bool:
        """Indica de forma segura si un localizador está deshabilitado (`disabled` o `aria-disabled`)."""
        try:
            disabled_res = await locator.is_disabled(timeout=timeout_ms)
            if isinstance(disabled_res, bool) and disabled_res:
                return True
        except Exception:
            pass
        try:
            aria_disabled = await locator.get_attribute("aria-disabled", timeout=timeout_ms)
            if isinstance(aria_disabled, str) and aria_disabled.strip().lower() == "true":
                return True
        except Exception:
            pass
        return False

    @classmethod
    async def extract_page_state_summary(cls, page: Page) -> Optional[str]:
        """Extrae un resumen breve de alertas o pantallas de estado compactas (agnóstico de dominio)."""
        summary_js = """() => {
            const normalize = (s) => (s || '').replace(/\\s+/g, ' ').trim();
            const isVisible = (el) => {
                if (!el) return false;
                const style = window.getComputedStyle(el);
                if (!style || style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
                    return false;
                }
                const rect = el.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
            };
            const alerts = Array.from(document.querySelectorAll('[role="alert"], [role="status"]'))
                .filter(isVisible)
                .map((el) => normalize(el.innerText))
                .filter((txt) => txt.length >= 4 && txt.length <= 220);
            if (alerts.length > 0) {
                return alerts[0].slice(0, 200);
            }
            const container = document.querySelector('main, [role="main"]') || document.body;
            if (!container) return null;
            const inContentArea = (el) => isVisible(el) && !el.closest('header, nav, footer');
            const visibleInteractive = Array.from(container.querySelectorAll('a, button, input, select'))
                .filter(inContentArea)
                .length;
            const visibleParagraphs = Array.from(container.querySelectorAll('p'))
                .filter(inContentArea)
                .map((el) => normalize(el.innerText))
                .filter((txt) => txt.length >= 10);
            const headingEl = Array.from(container.querySelectorAll('h1, h2')).find(inContentArea);
            const heading = headingEl ? normalize(headingEl.innerText) : '';
            const firstPara = visibleParagraphs.find((txt) => txt !== heading) || '';
            if (visibleInteractive <= 12 && visibleParagraphs.length <= 5 && heading && firstPara) {
                return `${heading} — ${firstPara}`.slice(0, 220);
            }
            return null;
        }"""
        try:
            summary = await page.evaluate(summary_js)
        except Exception:
            return None
        if isinstance(summary, str):
            clean = summary.strip()
            return clean if clean else None
        return None

    @classmethod
    async def detect_blocking_overlay(cls, page: Page) -> Optional[str]:
        """Detecta si un modal o panel fijo en primer plano bloquea la vista (agnóstico de dominio)."""
        overlay_js = """() => {
            const normalize = (s) => (s || '').replace(/\\s+/g, ' ').trim();
            const isVisible = (el) => {
                if (!el || el.id === '__eureka_highlight_overlay__') return false;
                const style = window.getComputedStyle(el);
                if (
                    !style ||
                    style.display === 'none' ||
                    style.visibility === 'hidden' ||
                    Number.parseFloat(style.opacity || '1') <= 0
                ) {
                    return false;
                }
                const rect = el.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
            };
            const summarizeEl = (el) => {
                const rawLines = (el.innerText || '')
                    .split(/\\r?\\n+/)
                    .map((line) => normalize(line))
                    .filter((line) => line.length >= 2);
                if (rawLines.length === 0) return null;
                if (rawLines.length === 1) return rawLines[0].slice(0, 220);
                return `${rawLines[0]} — ${rawLines.slice(1).join(' ')}`.slice(0, 220);
            };

            const vw = window.innerWidth || 0;
            const vh = window.innerHeight || 0;
            if (vw <= 0 || vh <= 0) return null;

            const ignoredTags = new Set(['BODY', 'HTML', 'MAIN', 'HEADER', 'NAV', 'FOOTER']);
            const findOverlayFromPoint = (x, y, requireFullHeightForFloating) => {
                const hit = document.elementFromPoint(x, y);
                let cur = hit;
                while (cur && cur !== document.body && cur !== document.documentElement) {
                    if (ignoredTags.has(cur.tagName) || !isVisible(cur)) {
                        cur = cur.parentElement;
                        continue;
                    }
                    const role = (cur.getAttribute('role') || '').toLowerCase();
                    const ariaModal = (cur.getAttribute('aria-modal') || '').toLowerCase();
                    const text = normalize(cur.innerText);
                    const rect = cur.getBoundingClientRect();
                    const style = window.getComputedStyle(cur);
                    const z = Number.parseInt(style.zIndex, 10);
                    const hasElevatedZ = !Number.isNaN(z) && z >= 10;
                    const meetsMinHeight = !requireFullHeightForFloating || rect.height >= vh * 0.65;

                    const isSemanticDialog =
                        (role === 'dialog' || role === 'alertdialog' || ariaModal === 'true') &&
                        meetsMinHeight &&
                        text.length >= 4 &&
                        text.length <= 700;
                    const isFixedOverlay =
                        style.position === 'fixed' &&
                        rect.width >= 220 &&
                        rect.height >= 120 &&
                        meetsMinHeight &&
                        text.length >= 4 &&
                        text.length <= 700 &&
                        (hasElevatedZ || (rect.width >= vw * 0.55 && rect.height >= vh * 0.55));

                    if (isSemanticDialog || isFixedOverlay) {
                        const summary = summarizeEl(cur);
                        if (summary) return summary;
                    }

                    const clsName = typeof cur.className === 'string' ? cur.className : '';
                    const markerText = `${cur.id || ''} ${clsName}`.toLowerCase();
                    const isLoadingMarker =
                        role === 'progressbar' ||
                        (cur.getAttribute('aria-busy') || '').toLowerCase() === 'true' ||
                        /loading|spinner|loader|overlay/.test(markerText);
                    const isBlockingLoadingOverlay =
                        isLoadingMarker &&
                        (style.position === 'fixed' || style.position === 'absolute') &&
                        style.pointerEvents !== 'none' &&
                        rect.width >= vw * 0.5 &&
                        rect.height >= vh * 0.5;
                    if (isBlockingLoadingOverlay) {
                        return 'Indicador o pantalla de carga activa superpuesta sobre la vista';
                    }
                    cur = cur.parentElement;
                }
                return null;
            };

            const probePoints = [
                [vw * 0.5, vh * 0.5, false],
                [vw * 0.5, vh * 0.35, false],
                [vw * 0.85, vh * 0.5, true],
                [vw * 0.15, vh * 0.5, true],
            ];
            for (const [x, y, reqFullH] of probePoints) {
                const found = findOverlayFromPoint(x, y, reqFullH);
                if (found) return found;
            }
            return null;
        }"""
        try:
            summary = await page.evaluate(overlay_js)
        except Exception:
            return None
        if isinstance(summary, str):
            clean = summary.strip()
            return clean if clean else None
        return None

    @classmethod
    async def find_cart_button(cls, page: Page, timeout_ms: int = 1500) -> Optional[Locator]:
        """Localiza enlaces o botones de acceso al carrito de compras."""
        cart_nav_selectors = [
            "a[href*='cart' i]",
            "a[href*='basket' i]",
            "a[href*='carrito' i]",
            "[aria-label*='cart' i]",
            "[aria-label*='basket' i]",
            "[aria-label*='carrito' i]",
            "a:has-text('Basket')",
            "button:has-text('Basket')",
            "a:has-text('Cart')",
            "button:has-text('Cart')",
            "a:has-text('Carrito')",
            "button:has-text('Carrito')",
        ]
        return await cls._find_first_visible(page, cart_nav_selectors, timeout_ms)

    @classmethod
    async def find_login_button(cls, page: Page, timeout_ms: int = 1500) -> Optional[Locator]:
        """Localiza enlaces o botones de inicio de sesión, priorizando paneles/modales abiertos."""
        login_selectors = [
            ".google-login-button",
            "[class*='login' i] button",
            "[role='dialog'] button:has-text('Sign in')",
            "[role='dialog'] button:has-text('Log in')",
            "[role='dialog'] button:has-text('Iniciar sesión')",
            "a[href*='login' i]",
            "a[href*='signin' i]",
            "[aria-label*='login' i]",
            "[aria-label*='sign in' i]",
            "a:has-text('Login')",
            "button:has-text('Login')",
            "a:has-text('Sign in')",
            "button:has-text('Sign in')",
            "a:has-text('Log in')",
            "button:has-text('Log in')",
            "a:has-text('Iniciar sesión')",
            "button:has-text('Iniciar sesión')",
            "a:has-text('Ingresar')",
            "button:has-text('Ingresar')",
        ]
        return await cls._find_first_visible(page, login_selectors, timeout_ms)

    _LOGIN_BARRIER_KEYWORDS: Tuple[str, ...] = (
        "login",
        "log in",
        "sign in",
        "signin",
        "iniciar sesión",
        "iniciar sesion",
        "ingresar",
        "acceder",
        "autentic",
        "contraseña",
        "password",
        "create an account",
    )
    _LOGIN_ROUTE_HINTS: Tuple[str, ...] = (
        "/login",
        "/signin",
        "/sign-in",
        "/auth",
        "/iniciar-sesion",
    )
    _CART_REMOVE_SELECTORS: Tuple[str, ...] = (
        "button:has-text('Vaciar carrito')",
        "button:has-text('Empty cart')",
        "button:has-text('Remove')",
        "button:has-text('Eliminar')",
        "button:has-text('Quitar')",
        "button:has-text('×')",
        "button:has-text('✕')",
        "a:has-text('Remove')",
        "a:has-text('Eliminar')",
        "[aria-label*='remove' i]",
        "[aria-label*='delete' i]",
        "[aria-label*='eliminar' i]",
        "[aria-label*='quitar' i]",
        "[title*='remove' i]",
        "[title*='delete' i]",
        "[title*='eliminar' i]",
        "[data-testid*='remove' i]",
        "[data-testid*='delete' i]",
        "button[class*='remove' i]",
        "a[class*='remove' i]",
        "[role='button'][class*='remove' i]",
    )

    @classmethod
    async def is_login_barrier(cls, page: Page, overlay_summary: Optional[str] = None) -> bool:
        """Indica de forma agnóstica si el bloqueo actual corresponde a un requerimiento de login."""
        if overlay_summary:
            lowered = overlay_summary.lower()
            if any(kw in lowered for kw in cls._LOGIN_BARRIER_KEYWORDS):
                return True

        current_url = (getattr(page, "url", "") or "").lower()
        on_login_route = any(hint in current_url for hint in cls._LOGIN_ROUTE_HINTS)
        if on_login_route:
            login_btn = await cls.find_login_button(page, timeout_ms=400)
            if login_btn is not None:
                return True
            try:
                pwd_vis = await page.locator("input[type='password']").first.is_visible(timeout=300)
                if isinstance(pwd_vis, bool) and pwd_vis:
                    return True
            except Exception:
                pass
        return False

    @classmethod
    async def _find_cart_remove_control(cls, page: Page, timeout_ms: int = 350) -> Optional[Locator]:
        """Busca un control visible de remoción de ítem fuera de header/nav/footer."""
        for selector in cls._CART_REMOVE_SELECTORS:
            try:
                group = page.locator(selector)
                count = await group.count()
                if isinstance(count, int) and count > 0:
                    for idx in range(min(count, 8)):
                        candidate = group.nth(idx)
                        vis = await candidate.is_visible(timeout=timeout_ms)
                        if not (isinstance(vis, bool) and vis):
                            continue
                        in_chrome = await candidate.evaluate(
                            "el => Boolean(el.closest('header, nav, footer'))"
                        )
                        if isinstance(in_chrome, bool) and in_chrome:
                            continue
                        if await cls.is_locator_disabled(candidate, timeout_ms=200):
                            continue
                        return candidate
            except Exception:
                continue
        return None

    @classmethod
    async def _find_cart_remove_icon_coords(cls, page: Page) -> Optional[Tuple[float, float]]:
        """Localiza coordenadas de un ícono clickeable (ej. ×/tacho SVG) dentro de filas del carrito."""
        icon_js = """() => {
            const urlLower = (window.location.href || '').toLowerCase();
            const heading = Array.from(document.querySelectorAll('h1, h2'))
                .map((h) => (h.innerText || '').toLowerCase())
                .join(' ');
            const isCartContext =
                /cart|basket|carrito/.test(urlLower) ||
                /shopping cart|basket|carrito/.test(heading);
            if (!isCartContext) return null;

            const isVisible = (el) => {
                if (!el) return false;
                const st = window.getComputedStyle(el);
                if (!st || st.display === 'none' || st.visibility === 'hidden' || st.opacity === '0') return false;
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0;
            };
            const excludedSelector = [
                'header', 'nav', 'footer', '[role="dialog"]',
                '[id*="onetrust" i]', '[class*="ot-" i]',
                '[id*="userway" i]', '[class*="Beacon" i]',
            ].join(', ');

            const root = document.querySelector('main, [role="main"]') || document.body;
            if (!root) return null;

            const candidates = Array.from(root.querySelectorAll('button, a, [role="button"], [tabindex], div, span'));
            for (const el of candidates) {
                if (!isVisible(el) || el.closest(excludedSelector)) continue;
                const elCls = (typeof el.className === 'string' ? el.className : '').toLowerCase();
                if (/qty|quantity|stepper|counter/.test(elCls)) continue;
                const r = el.getBoundingClientRect();
                if (r.width < 12 || r.width > 96 || r.height < 12 || r.height > 220) continue;
                const svgEl = el.querySelector('svg');
                const txt = (el.innerText || '').trim();
                const isCloseGlyph = txt === '×' || txt === '✕' || txt === 'x' || txt === 'X';
                if (!svgEl && !isCloseGlyph) continue;
                if (txt.length > 0 && !isCloseGlyph) continue;
                if (svgEl) {
                    const sr = svgEl.getBoundingClientRect();
                    if (sr.width < 10 || sr.width > 40 || sr.height < 10 || sr.height > 40) continue;
                }

                const st = window.getComputedStyle(el);
                const isInteractive =
                    el.tagName === 'BUTTON' ||
                    el.tagName === 'A' ||
                    el.getAttribute('role') === 'button' ||
                    el.hasAttribute('tabindex') ||
                    st.cursor === 'pointer';
                if (!isInteractive) continue;

                // Descartar botones +/- que comparten padre directo con un input numérico
                const hasParentInput = Boolean(
                    el.parentElement && el.parentElement.querySelector('input')
                );
                if (el.querySelector('input, select') || hasParentInput) {
                    continue;
                }

                // Verificar que pertenezca a una tarjeta/fila con ítem de carrito (precio o input)
                let row = el.parentElement;
                let hasItemSignals = false;
                for (let depth = 0; depth < 5 && row && row !== root; depth++) {
                    const rowText = row.innerText || '';
                    if (/[$€£]\\s*\\d/.test(rowText) && row.querySelector('input, select, img')) {
                        hasItemSignals = true;
                        break;
                    }
                    row = row.parentElement;
                }
                if (!hasItemSignals) continue;

                const targetRect = svgEl ? svgEl.getBoundingClientRect() : r;
                return [targetRect.left + targetRect.width / 2, targetRect.top + targetRect.height / 2];
            }
            return null;
        }"""
        try:
            coords = await page.evaluate(icon_js)
        except Exception:
            return None
        if (
            isinstance(coords, (list, tuple))
            and len(coords) == 2
            and isinstance(coords[0], (int, float))
            and isinstance(coords[1], (int, float))
        ):
            return float(coords[0]), float(coords[1])
        return None

    @classmethod
    async def clear_cart_items(
        cls,
        page: Page,
        base_url: str,
        action_guard: Optional["ActionGuard"] = None,
        max_removals: int = 10,
    ) -> int:
        """Limpia ítems residuales del carrito de forma acotada y segura al finalizar la sesión."""
        opened_cart = False
        cart_btn = await cls.find_cart_button(page, timeout_ms=800)
        if cart_btn is not None:
            try:
                href = await cart_btn.get_attribute("href")
                if isinstance(href, str) and href.strip():
                    target_url = UrlResolver.resolve_url(base_url, href.strip())
                    await page.goto(target_url, wait_until="domcontentloaded", timeout=10000)
                else:
                    await cart_btn.click(timeout=1500)
                try:
                    await page.wait_for_load_state("networkidle", timeout=2000)
                except Exception:
                    pass
                await asyncio.sleep(1.2)
                opened_cart = True
            except Exception:
                opened_cart = False

        remove_loc = await cls._find_cart_remove_control(page) if opened_cart else None
        icon_coords = (
            await cls._find_cart_remove_icon_coords(page)
            if (opened_cart and remove_loc is None)
            else None
        )
        if remove_loc is None and icon_coords is None:
            for fallback_route in ("/cart", "/checkout?show=basket", "/basket", "/carrito"):
                try:
                    target_url = UrlResolver.resolve_url(base_url, fallback_route)
                    await page.goto(target_url, wait_until="domcontentloaded", timeout=8000)
                    await asyncio.sleep(0.5)
                    remove_loc = await cls._find_cart_remove_control(page)
                    if remove_loc is None:
                        icon_coords = await cls._find_cart_remove_icon_coords(page)
                    if remove_loc is not None or icon_coords is not None:
                        break
                except Exception:
                    continue

        removed = 0
        while (remove_loc is not None or icon_coords is not None) and removed < max_removals:
            if remove_loc is not None:
                if action_guard is not None:
                    try:
                        is_safe, _ = await action_guard.inspect_locator(remove_loc)
                        if not is_safe:
                            break
                    except Exception:
                        break
                try:
                    await remove_loc.click(timeout=1500)
                    removed += 1
                    await asyncio.sleep(0.5)
                except Exception:
                    break
            elif icon_coords is not None:
                try:
                    await page.mouse.click(icon_coords[0], icon_coords[1])
                    removed += 1
                    await asyncio.sleep(0.6)
                except Exception:
                    break

            remove_loc = await cls._find_cart_remove_control(page)
            icon_coords = await cls._find_cart_remove_icon_coords(page) if remove_loc is None else None

        return removed
