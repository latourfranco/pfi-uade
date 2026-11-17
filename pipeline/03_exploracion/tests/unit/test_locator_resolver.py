"""Pruebas unitarias para LocatorResolver (búsqueda semántica y Link Traversal)."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from app.agent.locator_resolver import LocatorResolver


@pytest.mark.asyncio
@pytest.mark.unit
async def test_find_link_to_route_success():
    """Verifica que find_link_to_route retorne el primer enlace visible hacia la ruta."""
    mock_page = MagicMock()
    mock_locator = AsyncMock()
    mock_locator.is_visible.return_value = True

    mock_wrapper = MagicMock()
    mock_wrapper.first = mock_locator
    mock_page.locator.return_value = mock_wrapper

    found = await LocatorResolver.find_link_to_route(mock_page, "/carrito")
    assert found == mock_locator


@pytest.mark.asyncio
@pytest.mark.unit
async def test_find_link_to_route_empty_returns_none():
    """Verifica que rutas vacías retornen None sin consultar selectores."""
    mock_page = MagicMock()
    assert await LocatorResolver.find_link_to_route(mock_page, "") is None
    assert await LocatorResolver.find_link_to_route(mock_page, "   ") is None
    mock_page.locator.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_find_link_to_route_strict_root_selectors():
    """Verifica que '/' use solo selectores estrictos de Home (nunca href*='/' ni href$='/')."""
    mock_page = MagicMock()
    mock_page.url = "https://tienda.ejemplo.com/productos/remera"

    mock_locator = AsyncMock()
    mock_locator.is_visible.side_effect = [False, True, False]

    mock_wrapper = MagicMock()
    mock_wrapper.first = mock_locator
    mock_page.locator.return_value = mock_wrapper

    found = await LocatorResolver.find_link_to_route(mock_page, "/")
    assert found == mock_locator

    queried_selectors = [call.args[0] for call in mock_page.locator.call_args_list]
    assert queried_selectors == [
        "a[href='/']",
        "a[href='https://tienda.ejemplo.com/']",
    ]

    # También cubre el caso sin coincidencia ni URL HTTP válida
    mock_page_no_http = MagicMock()
    mock_page_no_http.url = "about:blank"
    mock_loc_hidden = AsyncMock()
    mock_loc_hidden.is_visible.return_value = False
    mock_wrapper_hidden = MagicMock()
    mock_wrapper_hidden.first = mock_loc_hidden
    mock_page_no_http.locator.return_value = mock_wrapper_hidden

    assert await LocatorResolver.find_link_to_route(mock_page_no_http, "/") is None
    assert [call.args[0] for call in mock_page_no_http.locator.call_args_list] == ["a[href='/']"]

    # Y URL malformada sin netloc
    mock_page_bad_url = MagicMock()
    mock_page_bad_url.url = "https://"
    mock_page_bad_url.locator.return_value = mock_wrapper_hidden
    assert await LocatorResolver.find_link_to_route(mock_page_bad_url, "/") is None
    assert [call.args[0] for call in mock_page_bad_url.locator.call_args_list] == ["a[href='/']"]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_find_link_to_route_not_found():
    """Verifica que si no hay enlaces visibles retorne None."""
    mock_page = MagicMock()
    mock_locator = AsyncMock()
    mock_locator.is_visible.return_value = False

    mock_wrapper = MagicMock()
    mock_wrapper.first = mock_locator
    mock_page.locator.return_value = mock_wrapper

    found = await LocatorResolver.find_link_to_route(mock_page, "/ofertas")
    assert found is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_find_element_by_text_empty():
    """Verifica que texto vacío retorne None inmediatamente."""
    mock_page = MagicMock()
    assert await LocatorResolver.find_element_by_text(mock_page, "") is None
    assert await LocatorResolver.find_element_by_text(mock_page, "   ") is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_find_element_by_text_with_role():
    """Verifica la búsqueda semántica prioritaria por get_by_role."""
    mock_page = MagicMock()
    mock_loc = AsyncMock()
    mock_loc.is_visible.return_value = True

    mock_wrapper = MagicMock()
    mock_wrapper.first = mock_loc
    mock_page.get_by_role.return_value = mock_wrapper

    found = await LocatorResolver.find_element_by_text(
        mock_page, text="Continuar compra", role="button"
    )
    assert found == mock_loc
    mock_page.get_by_role.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_find_element_by_text_fallback():
    """Verifica fallback a get_by_text cuando no se provee rol."""
    mock_page = MagicMock()
    mock_loc = AsyncMock()
    mock_loc.is_visible.return_value = True

    mock_wrapper = MagicMock()
    mock_wrapper.first = mock_loc
    mock_page.get_by_text.return_value = mock_wrapper

    found = await LocatorResolver.find_element_by_text(mock_page, text="Ver detalles")
    assert found == mock_loc


@pytest.mark.asyncio
@pytest.mark.unit
async def test_find_search_input():
    """Verifica la localización del campo de búsqueda principal."""
    mock_page = MagicMock()
    mock_loc = AsyncMock()
    mock_loc.is_visible.return_value = True

    mock_wrapper = MagicMock()
    mock_wrapper.first = mock_loc
    mock_page.locator.return_value = mock_wrapper

    found = await LocatorResolver.find_search_input(mock_page)
    assert found == mock_loc


@pytest.mark.asyncio
@pytest.mark.unit
async def test_find_element_by_text_role_not_visible_falls_back_to_text():
    """Verifica que si el elemento por rol no es visible, recurra a get_by_text."""
    mock_page = MagicMock()
    mock_role_loc = AsyncMock()
    mock_role_loc.is_visible.return_value = False
    mock_role_wrapper = MagicMock()
    mock_role_wrapper.first = mock_role_loc
    mock_page.get_by_role.return_value = mock_role_wrapper

    mock_text_loc = AsyncMock()
    mock_text_loc.is_visible.return_value = True
    mock_text_wrapper = MagicMock()
    mock_text_wrapper.first = mock_text_loc
    mock_page.get_by_text.return_value = mock_text_wrapper

    found = await LocatorResolver.find_element_by_text(mock_page, text="Continuar", role="button")
    assert found == mock_text_loc


@pytest.mark.asyncio
@pytest.mark.unit
async def test_find_element_by_text_role_exception_handled():
    """Verifica que si get_by_role lanza excepción, se capture y recurra a get_by_text."""
    mock_page = MagicMock()
    mock_page.get_by_role.side_effect = Exception("Role search failed")

    mock_text_loc = AsyncMock()
    mock_text_loc.is_visible.return_value = True
    mock_text_wrapper = MagicMock()
    mock_text_wrapper.first = mock_text_loc
    mock_page.get_by_text.return_value = mock_text_wrapper

    found = await LocatorResolver.find_element_by_text(mock_page, text="Continuar", role="button")
    assert found == mock_text_loc


@pytest.mark.asyncio
@pytest.mark.unit
async def test_find_element_by_text_falls_back_to_selectors():
    """Verifica el fallback a selectores CSS cuando get_by_text no es visible."""
    mock_page = MagicMock()
    mock_text_loc = AsyncMock()
    mock_text_loc.is_visible.return_value = False
    mock_text_wrapper = MagicMock()
    mock_text_wrapper.first = mock_text_loc
    mock_page.get_by_text.return_value = mock_text_wrapper

    # Primer selector fallback invisible, segundo selector fallback visible
    mock_css_loc1 = AsyncMock()
    mock_css_loc1.is_visible.return_value = False
    mock_css_wrap1 = MagicMock()
    mock_css_wrap1.first = mock_css_loc1

    mock_css_loc2 = AsyncMock()
    mock_css_loc2.is_visible.return_value = True
    mock_css_wrap2 = MagicMock()
    mock_css_wrap2.first = mock_css_loc2

    mock_page.locator.side_effect = [mock_css_wrap1, mock_css_wrap2]

    found = await LocatorResolver.find_element_by_text(mock_page, text="Agregar al carrito")
    assert found == mock_css_loc2


@pytest.mark.asyncio
@pytest.mark.unit
async def test_find_element_by_text_not_found_returns_none():
    """Verifica que si ningún método ni selector es visible, retorne None."""
    mock_page = MagicMock()
    mock_text_loc = AsyncMock()
    mock_text_loc.is_visible.return_value = False
    mock_text_wrapper = MagicMock()
    mock_text_wrapper.first = mock_text_loc
    mock_page.get_by_text.return_value = mock_text_wrapper

    mock_css_loc = AsyncMock()
    mock_css_loc.is_visible.return_value = False
    mock_css_wrap = MagicMock()
    mock_css_wrap.first = mock_css_loc
    mock_page.locator.return_value = mock_css_wrap

    found = await LocatorResolver.find_element_by_text(mock_page, text="Elemento inexistente")
    assert found is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_find_search_input_second_selector_and_not_found():
    """Verifica que find_search_input continúe iterando selectores hasta encontrar uno visible o None."""
    mock_page = MagicMock()

    # Intento 1: primer selector invisible, segundo selector visible
    mock_loc1 = AsyncMock()
    mock_loc1.is_visible.return_value = False
    mock_wrap1 = MagicMock()
    mock_wrap1.first = mock_loc1

    mock_loc2 = AsyncMock()
    mock_loc2.is_visible.return_value = True
    mock_wrap2 = MagicMock()
    mock_wrap2.first = mock_loc2

    mock_page.locator.side_effect = [mock_wrap1, mock_wrap2]
    found = await LocatorResolver.find_search_input(mock_page)
    assert found == mock_loc2

    # Intento 2: ninguno visible retorna None
    mock_page2 = MagicMock()
    mock_loc_none = AsyncMock()
    mock_loc_none.is_visible.return_value = False
    mock_wrap_none = MagicMock()
    mock_wrap_none.first = mock_loc_none
    mock_page2.locator.return_value = mock_wrap_none
    assert await LocatorResolver.find_search_input(mock_page2) is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_find_add_to_cart_button_success_and_fallback():
    """Verifica que find_add_to_cart_button identifique el botón o retorne None si no existe."""
    mock_page = MagicMock()

    # Caso 1: encuentra en segundo selector
    mock_loc1 = AsyncMock()
    mock_loc1.is_visible.return_value = False
    mock_wrap1 = MagicMock()
    mock_wrap1.first = mock_loc1

    mock_loc2 = AsyncMock()
    mock_loc2.is_visible.return_value = True
    mock_wrap2 = MagicMock()
    mock_wrap2.first = mock_loc2

    mock_page.locator.side_effect = [mock_wrap1, mock_wrap2]
    found = await LocatorResolver.find_add_to_cart_button(mock_page)
    assert found == mock_loc2

    # Caso 2: excepción y fallback a None
    mock_page_err = MagicMock()
    mock_loc_err = AsyncMock()
    mock_loc_err.is_visible.side_effect = Exception("timeout")
    mock_wrap_err = MagicMock()
    mock_wrap_err.first = mock_loc_err
    mock_page_err.locator.return_value = mock_wrap_err
    assert await LocatorResolver.find_add_to_cart_button(mock_page_err) is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_find_checkout_or_continue_button_success_and_fallback():
    """Verifica que find_checkout_or_continue_button identifique el botón o retorne None."""
    mock_page = MagicMock()

    mock_loc = AsyncMock()
    mock_loc.is_visible.return_value = True
    mock_wrap = MagicMock()
    mock_wrap.first = mock_loc
    mock_page.locator.return_value = mock_wrap

    found = await LocatorResolver.find_checkout_or_continue_button(mock_page)
    assert found == mock_loc

    # Caso no visible
    mock_page_none = MagicMock()
    mock_loc_none = AsyncMock()
    mock_loc_none.is_visible.return_value = False
    mock_wrap_none = MagicMock()
    mock_wrap_none.first = mock_loc_none
    mock_page_none.locator.return_value = mock_wrap_none
    assert await LocatorResolver.find_checkout_or_continue_button(mock_page_none) is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_find_cart_and_login_buttons():
    """Verifica que find_cart_button y find_login_button encuentren controles visibles o retornen None."""
    mock_page = MagicMock()
    mock_loc = AsyncMock()
    mock_loc.is_visible.return_value = True
    mock_wrap = MagicMock()
    mock_wrap.first = mock_loc
    mock_page.locator.return_value = mock_wrap

    assert await LocatorResolver.find_cart_button(mock_page) == mock_loc
    assert await LocatorResolver.find_login_button(mock_page) == mock_loc

    mock_page_none = MagicMock()
    mock_loc_none = AsyncMock()
    mock_loc_none.is_visible.return_value = False
    mock_wrap_none = MagicMock()
    mock_wrap_none.first = mock_loc_none
    mock_page_none.locator.return_value = mock_wrap_none

    assert await LocatorResolver.find_cart_button(mock_page_none) is None
    assert await LocatorResolver.find_login_button(mock_page_none) is None

    # Verifica que incluya variantes Basket / Login por aria-label y enlace <a> sin href
    queried_cart_selectors = [call.args[0] for call in mock_page_none.locator.call_args_list[:12]]
    assert "[aria-label*='basket' i]" in queried_cart_selectors
    assert "a:has-text('Basket')" in queried_cart_selectors
    queried_login_selectors = [call.args[0] for call in mock_page_none.locator.call_args_list[12:]]
    assert queried_login_selectors[0] == ".google-login-button"
    assert "[aria-label*='login' i]" in queried_login_selectors
    assert "a:has-text('Login')" in queried_login_selectors


@pytest.mark.asyncio
@pytest.mark.unit
async def test_find_quick_view_for_item_success():
    """Verifica que find_quick_view_for_item localice el botón Quick View único dentro de la tarjeta."""
    mock_page = MagicMock()
    mock_item_loc = MagicMock()
    mock_card_loc = MagicMock()
    mock_qv_btn = AsyncMock()
    mock_qv_btn.is_visible.return_value = True

    mock_matches = MagicMock()
    mock_matches.count = AsyncMock(return_value=1)
    mock_matches.first = mock_qv_btn

    mock_card_loc.locator.return_value = mock_matches
    mock_item_loc.locator.return_value = mock_card_loc

    with patch.object(LocatorResolver, "find_element_by_text", return_value=mock_item_loc):
        found = await LocatorResolver.find_quick_view_for_item(mock_page, "Google Grey Organic NYC Tee")

    assert found == mock_qv_btn
    mock_card_loc.locator.assert_called_once_with(LocatorResolver.QUICK_VIEW_SELECTORS[0])


@pytest.mark.asyncio
@pytest.mark.unit
async def test_find_quick_view_for_item_edge_cases():
    """Verifica manejo de ítems vacíos, no encontrados, múltiples tarjetas, no visibles y excepciones."""
    mock_page = MagicMock()
    assert await LocatorResolver.find_quick_view_for_item(mock_page, "   ") is None

    with patch.object(LocatorResolver, "find_element_by_text", return_value=None):
        assert await LocatorResolver.find_quick_view_for_item(mock_page, "Producto") is None

    # Caso: múltiples botones Quick View en un contenedor padre -> rechazar por ambigüedad
    mock_item = MagicMock()
    mock_card = MagicMock()
    mock_ambiguous = MagicMock()
    mock_ambiguous.count = AsyncMock(return_value=4)
    mock_hidden_btn = AsyncMock()
    mock_hidden_btn.is_visible.return_value = False
    mock_hidden_matches = MagicMock()
    mock_hidden_matches.count = AsyncMock(return_value=1)
    mock_hidden_matches.first = mock_hidden_btn
    mock_err_matches = MagicMock()
    mock_err_matches.count = AsyncMock(side_effect=Exception("DOM detached"))

    mock_card.locator.side_effect = [
        mock_ambiguous,
        mock_hidden_matches,
        mock_err_matches,
        mock_ambiguous,
        mock_ambiguous,
        mock_ambiguous,
    ]
    mock_item.locator.return_value = mock_card

    with patch.object(LocatorResolver, "find_element_by_text", return_value=mock_item):
        assert await LocatorResolver.find_quick_view_for_item(mock_page, "Producto") is None

    # Caso: falla al resolver ancestor
    mock_item_err = MagicMock()
    mock_item_err.locator.side_effect = Exception("XPath error")
    with patch.object(LocatorResolver, "find_element_by_text", return_value=mock_item_err):
        assert await LocatorResolver.find_quick_view_for_item(mock_page, "Producto") is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_find_first_visible_skips_hidden_first_match():
    """Verifica que si el primer match en el DOM está oculto (ej. desktop), evalúe nth(i)."""
    mock_page = MagicMock()
    hidden_first = AsyncMock()
    hidden_first.is_visible.return_value = False
    visible_second = AsyncMock()
    visible_second.is_visible.return_value = True

    mock_wrapper = MagicMock()
    mock_wrapper.first = hidden_first
    mock_wrapper.count = AsyncMock(return_value=2)
    mock_wrapper.nth.return_value = visible_second
    mock_page.locator.return_value = mock_wrapper

    found = await LocatorResolver.find_link_to_route(mock_page, "/shop/clearance")
    assert found is visible_second
    mock_wrapper.nth.assert_called_once_with(1)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_find_link_in_mobile_menu_direct_and_submenu_and_close():
    """Verifica apertura del menú mobile, expansión de submenú por prefijo y cierre al no encontrar."""
    mock_page = MagicMock()

    # 1. Ruta vacía, '/' o sin toggle visible retorna None
    assert await LocatorResolver.find_link_in_mobile_menu(mock_page, "") is None
    assert await LocatorResolver.find_link_in_mobile_menu(mock_page, "/") is None

    with patch.object(LocatorResolver, "_find_first_visible", return_value=None):
        assert await LocatorResolver.find_link_in_mobile_menu(mock_page, "/shop/clearance") is None

    # 2. Fallo al clickear toggle retorna None
    bad_toggle = AsyncMock()
    bad_toggle.click.side_effect = Exception("Click failed")
    with patch.object(LocatorResolver, "_find_first_visible", return_value=bad_toggle):
        assert await LocatorResolver.find_link_in_mobile_menu(mock_page, "/shop/clearance") is None

    # 3. Coincidencia directa tras abrir el menú
    toggle_ok = AsyncMock()
    direct_link = AsyncMock()
    with (
        patch.object(LocatorResolver, "_find_first_visible", side_effect=[toggle_ok, direct_link]),
        patch("app.agent.locator_resolver.asyncio.sleep", new_callable=AsyncMock),
    ):
        found_direct = await LocatorResolver.find_link_in_mobile_menu(mock_page, "/shop/clearance")
    assert found_direct is direct_link
    toggle_ok.click.assert_awaited_once_with(timeout=1000)

    # 4. Coincidencia dentro de submenú padre (/shop/apparel -> /shop/apparel/mens)
    toggle_ok_2 = AsyncMock()
    parent_link = MagicMock()
    submenu_toggle = AsyncMock()
    submenu_toggle.is_visible.return_value = True
    parent_container = MagicMock()
    parent_container.locator.return_value.first = submenu_toggle
    parent_link.locator.return_value = parent_container
    child_link = AsyncMock()

    with (
        patch.object(
            LocatorResolver,
            "_find_first_visible",
            side_effect=[toggle_ok_2, None, parent_link, child_link],
        ),
        patch("app.agent.locator_resolver.asyncio.sleep", new_callable=AsyncMock),
    ):
        found_sub = await LocatorResolver.find_link_in_mobile_menu(mock_page, "/shop/apparel/mens")
    assert found_sub is child_link
    submenu_toggle.click.assert_awaited_once_with(timeout=1000)

    # 5. No encontrado -> debe cerrar el menú mobile antes de retornar None
    toggle_ok_3 = AsyncMock()
    parent_err = MagicMock()
    parent_err.locator.side_effect = Exception("No parent")
    with (
        patch.object(
            LocatorResolver,
            "_find_first_visible",
            side_effect=[toggle_ok_3, None, parent_err, None],
        ),
        patch.object(LocatorResolver, "close_mobile_menu", new_callable=AsyncMock) as mock_close,
        patch("app.agent.locator_resolver.asyncio.sleep", new_callable=AsyncMock),
    ):
        not_found = await LocatorResolver.find_link_in_mobile_menu(mock_page, "/shop/inexistente/item")
    assert not_found is None
    mock_close.assert_awaited_once_with(mock_page, toggle_loc=toggle_ok_3, timeout_ms=400)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_close_mobile_menu_strategies():
    """Verifica cierre por botón dedicado, toggle fallback, sin target y error tolerado."""
    mock_page = MagicMock()

    close_btn = AsyncMock()
    with (
        patch.object(LocatorResolver, "_find_first_visible", return_value=close_btn),
        patch("app.agent.locator_resolver.asyncio.sleep", new_callable=AsyncMock),
    ):
        await LocatorResolver.close_mobile_menu(mock_page)
    close_btn.click.assert_awaited_once_with(timeout=1000)

    toggle_fb = AsyncMock()
    toggle_fb.click.side_effect = Exception("Closed already")
    with patch.object(LocatorResolver, "_find_first_visible", return_value=None):
        await LocatorResolver.close_mobile_menu(mock_page, toggle_loc=toggle_fb)
    toggle_fb.click.assert_awaited_once()

    with patch.object(LocatorResolver, "_find_first_visible", return_value=None):
        await LocatorResolver.close_mobile_menu(mock_page, toggle_loc=None)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_desktop_menu_context_and_reset_hover():
    """Verifica detección de enlaces de menú/submenú desktop y reseteo seguro de puntero."""
    loc_top = AsyncMock()
    loc_top.evaluate.return_value = {"inDesktopMenu": True, "linkLabel": "Apparel", "parentLabel": ""}
    assert await LocatorResolver.get_desktop_menu_context(loc_top) == (True, "Apparel", "")

    loc_sub = AsyncMock()
    loc_sub.evaluate.return_value = {"inDesktopMenu": True, "linkLabel": "Women's", "parentLabel": "Apparel"}
    assert await LocatorResolver.get_desktop_menu_context(loc_sub) == (True, "Women's", "Apparel")

    loc_body = AsyncMock()
    loc_body.evaluate.return_value = {"inDesktopMenu": False, "linkLabel": "Shop", "parentLabel": ""}
    assert await LocatorResolver.get_desktop_menu_context(loc_body) == (False, "", "")

    loc_err = AsyncMock()
    loc_err.evaluate.side_effect = RuntimeError("Detached")
    assert await LocatorResolver.get_desktop_menu_context(loc_err) == (False, "", "")

    mock_page = MagicMock()
    mock_page.mouse = AsyncMock()
    await LocatorResolver.reset_mouse_hover(mock_page)
    mock_page.mouse.move.assert_awaited_once_with(0, 0)

    mock_page.mouse.move.side_effect = RuntimeError("Closed")
    await LocatorResolver.reset_mouse_hover(mock_page)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_find_link_in_desktop_submenu_prefix_fallback_and_reset():
    """Verifica despliegue por prefijo padre, fallback por selectores y reseteo si no halla."""
    mock_page = MagicMock()
    assert await LocatorResolver.find_link_in_desktop_submenu(mock_page, "") is None
    assert await LocatorResolver.find_link_in_desktop_submenu(mock_page, "/") is None

    # 1. Coincidencia en Fase 1 por prefijo padre (/shop/apparel -> /shop/apparel/womens)
    parent_trigger = AsyncMock()
    child_womens = AsyncMock()
    with (
        patch.object(LocatorResolver, "_find_first_visible", side_effect=[parent_trigger, child_womens]),
        patch("app.agent.locator_resolver.asyncio.sleep", new_callable=AsyncMock),
    ):
        found_prefix = await LocatorResolver.find_link_in_desktop_submenu(mock_page, "/shop/apparel/womens")
    assert found_prefix is child_womens
    parent_trigger.hover.assert_awaited_once_with(timeout=800)

    # 2. Coincidencia en Fase 2 explorando triggers visibles de DESKTOP_SUBMENU_PARENT_SELECTORS
    trigger_visible = AsyncMock()
    trigger_visible.is_visible.return_value = True
    trigger_hidden = AsyncMock()
    trigger_hidden.is_visible.return_value = False
    wrapper_fallback = MagicMock()
    wrapper_fallback.count = AsyncMock(return_value=2)
    wrapper_fallback.nth.side_effect = [trigger_hidden, trigger_visible]
    mock_page_fb = MagicMock()
    mock_page_fb.locator.return_value = wrapper_fallback
    found_fb_child = AsyncMock()

    with (
        patch.object(
            LocatorResolver,
            "_find_first_visible",
            side_effect=[None, found_fb_child],
        ),
        patch("app.agent.locator_resolver.asyncio.sleep", new_callable=AsyncMock),
    ):
        found_fb = await LocatorResolver.find_link_in_desktop_submenu(mock_page_fb, "/shop/clearance")
    assert found_fb is found_fb_child
    trigger_visible.hover.assert_awaited_once_with(timeout=800)

    # 3. No encontrado tras intentar hover -> resetea puntero y retorna None
    bad_parent = AsyncMock()
    bad_parent.hover.side_effect = Exception("Hover blocked")
    ok_parent = AsyncMock()
    empty_wrapper = MagicMock()
    empty_wrapper.count = AsyncMock(return_value=0)
    mock_page_none = MagicMock()
    mock_page_none.locator.return_value = empty_wrapper

    with (
        patch.object(
            LocatorResolver,
            "_find_first_visible",
            side_effect=[bad_parent, ok_parent, None],
        ),
        patch.object(LocatorResolver, "reset_mouse_hover", new_callable=AsyncMock) as mock_reset,
        patch("app.agent.locator_resolver.asyncio.sleep", new_callable=AsyncMock),
    ):
        not_found = await LocatorResolver.find_link_in_desktop_submenu(mock_page_none, "/shop/apparel/unknown")
    assert not_found is None
    mock_reset.assert_awaited_once_with(mock_page_none)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_find_first_visible_skips_occluded_match():
    """Verifica que _find_first_visible descarte un nodo tapado por un modal/drawer y tome el libre."""
    mock_page = MagicMock()
    occluded_first = AsyncMock()
    occluded_first.is_visible.return_value = True
    occluded_first.evaluate.return_value = False

    visible_second = AsyncMock()
    visible_second.is_visible.return_value = True
    visible_second.evaluate.return_value = True

    mock_wrapper = MagicMock()
    mock_wrapper.first = occluded_first
    mock_wrapper.count = AsyncMock(return_value=2)
    mock_wrapper.nth.return_value = visible_second
    mock_page.locator.return_value = mock_wrapper

    found = await LocatorResolver._find_first_visible(mock_page, ["a[aria-label*='login' i]"], timeout_ms=300)
    assert found is visible_second
    mock_wrapper.nth.assert_called_once_with(1)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_scroll_and_find_element_by_text_cases():
    """Verifica búsqueda progresiva con scroll y restauración al inicio si no encuentra el elemento."""
    mock_page_empty = MagicMock()
    assert await LocatorResolver.scroll_and_find_element_by_text(mock_page_empty, " ") is None

    # 1. Encuentra en el segundo paso de scroll
    mock_page_found = MagicMock()
    mock_page_found.evaluate = AsyncMock(
        side_effect=[
            {"moved": True, "atEnd": False},
            {"moved": True, "atEnd": False},
        ]
    )
    target_loc = AsyncMock()
    with (
        patch.object(LocatorResolver, "find_element_by_text", side_effect=[None, target_loc]) as mock_find,
        patch("app.agent.locator_resolver.asyncio.sleep", new_callable=AsyncMock),
    ):
        found = await LocatorResolver.scroll_and_find_element_by_text(mock_page_found, "Google Nara Hoodie")
    assert found is target_loc
    assert mock_find.await_count == 2

    # 2. Llega al final sin crecer el documento -> corta y restaura scroll a (0, 0)
    mock_page_end = MagicMock()
    mock_page_end.evaluate = AsyncMock(
        side_effect=[{"moved": True, "atEnd": True, "docHeight": 1800}, 1800, None]
    )
    with (
        patch.object(LocatorResolver, "find_element_by_text", return_value=None),
        patch("app.agent.locator_resolver.asyncio.sleep", new_callable=AsyncMock),
    ):
        not_found = await LocatorResolver.scroll_and_find_element_by_text(mock_page_end, "Inexistente")
    assert not_found is None
    assert mock_page_end.evaluate.await_count == 3

    # 2b. Infinite scroll: llega al borde, scrollHeight crece y logra hallar en el siguiente tramo
    mock_page_inf = MagicMock()
    mock_page_inf.evaluate = AsyncMock(
        side_effect=[
            {"moved": True, "atEnd": True, "docHeight": 1800},
            2600,
            {"moved": True, "atEnd": False, "docHeight": 2600},
        ]
    )
    inf_loc = AsyncMock()
    with (
        patch.object(LocatorResolver, "find_element_by_text", side_effect=[None, inf_loc]),
        patch("app.agent.locator_resolver.asyncio.sleep", new_callable=AsyncMock),
    ):
        found_inf = await LocatorResolver.scroll_and_find_element_by_text(mock_page_inf, "Cargado tarde")
    assert found_inf is inf_loc

    # 3. Excepción en evaluate o sin movimiento -> corta rápido
    mock_page_err = MagicMock()
    mock_page_err.evaluate = AsyncMock(side_effect=Exception("evaluate error"))
    assert await LocatorResolver.scroll_and_find_element_by_text(mock_page_err, "Item") is None

    mock_page_nomove = MagicMock()
    mock_page_nomove.evaluate = AsyncMock(side_effect=[{"moved": False, "atEnd": True}, None])
    assert await LocatorResolver.scroll_and_find_element_by_text(mock_page_nomove, "Item") is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_begin_checkout_disabled_and_page_state_summary():
    """Verifica find_begin_checkout_button, is_locator_disabled y extract_page_state_summary."""
    mock_page = MagicMock()
    mock_btn = AsyncMock()
    mock_btn.is_visible.return_value = True
    wrap = MagicMock()
    wrap.first = mock_btn
    mock_page.locator.return_value = wrap
    assert await LocatorResolver.find_begin_checkout_button(mock_page) is mock_btn

    # is_locator_disabled por is_disabled(), por aria-disabled, habilitado y ante error
    loc_dis = AsyncMock()
    loc_dis.is_disabled.return_value = True
    assert await LocatorResolver.is_locator_disabled(loc_dis) is True

    loc_aria = AsyncMock()
    loc_aria.is_disabled.return_value = False
    loc_aria.get_attribute.return_value = "true"
    assert await LocatorResolver.is_locator_disabled(loc_aria) is True

    loc_ok = AsyncMock()
    loc_ok.is_disabled.return_value = False
    loc_ok.get_attribute.return_value = "false"
    assert await LocatorResolver.is_locator_disabled(loc_ok) is False

    loc_err = AsyncMock()
    loc_err.is_disabled.side_effect = Exception("detached")
    loc_err.get_attribute.side_effect = Exception("detached")
    assert await LocatorResolver.is_locator_disabled(loc_err) is False

    # extract_page_state_summary
    mock_page_sum = MagicMock()
    mock_page_sum.evaluate = AsyncMock(return_value="  Sold out for now  ")
    assert await LocatorResolver.extract_page_state_summary(mock_page_sum) == "Sold out for now"

    mock_page_empty = MagicMock()
    mock_page_empty.evaluate = AsyncMock(return_value=None)
    assert await LocatorResolver.extract_page_state_summary(mock_page_empty) is None

    mock_page_fail = MagicMock()
    mock_page_fail.evaluate = AsyncMock(side_effect=Exception("boom"))
    assert await LocatorResolver.extract_page_state_summary(mock_page_fail) is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_ensure_positive_quantity_selected_cases():
    """Verifica pre-selección de cantidad 1 mediante '+' o fill() cuando inicia en 0."""
    # 1. Sin inputs de cantidad -> False
    mock_page_none = MagicMock()
    empty_wrap = MagicMock()
    empty_wrap.count = AsyncMock(return_value=0)
    mock_page_none.locator.return_value = empty_wrap
    assert await LocatorResolver.ensure_positive_quantity_selected(mock_page_none) is False

    # 2. Ya tiene valor > 0 -> False sin modificar
    mock_page_pos = MagicMock()
    qty_pos = AsyncMock()
    qty_pos.is_visible.return_value = True
    qty_pos.evaluate.return_value = True
    qty_pos.input_value.return_value = "2"
    wrap_pos = MagicMock()
    wrap_pos.count = AsyncMock(return_value=1)
    wrap_pos.nth.return_value = qty_pos
    mock_page_pos.locator.return_value = wrap_pos
    assert await LocatorResolver.ensure_positive_quantity_selected(mock_page_pos) is False

    # 3. Inicia en 0 y control '+' incrementa a 1 -> True
    mock_page_plus = MagicMock()
    qty_zero = AsyncMock()
    qty_zero.is_visible.return_value = True
    qty_zero.evaluate.return_value = True
    qty_zero.input_value.side_effect = ["0", "1"]
    plus_btn = AsyncMock()
    plus_btn.is_visible.return_value = True
    plus_wrap = MagicMock()
    plus_wrap.first = plus_btn
    container_loc = MagicMock()
    container_loc.locator.return_value = plus_wrap
    qty_zero.locator = MagicMock(return_value=container_loc)
    wrap_zero = MagicMock()
    wrap_zero.count = AsyncMock(return_value=1)
    wrap_zero.nth.return_value = qty_zero
    mock_page_plus.locator.return_value = wrap_zero
    assert await LocatorResolver.ensure_positive_quantity_selected(mock_page_plus) is True
    plus_btn.click.assert_awaited_once()

    # 4. Inicia en 0, '+' no está visible -> cae a fill("1") -> True
    mock_page_fill = MagicMock()
    qty_fill = AsyncMock()
    qty_fill.is_visible.return_value = True
    qty_fill.evaluate.return_value = True
    qty_fill.input_value.side_effect = ["0", "1"]
    plus_hidden = AsyncMock()
    plus_hidden.is_visible.return_value = False
    plus_wrap_h = MagicMock()
    plus_wrap_h.first = plus_hidden
    container_h = MagicMock()
    container_h.locator.return_value = plus_wrap_h
    qty_fill.locator = MagicMock(return_value=container_h)
    wrap_fill = MagicMock()
    wrap_fill.count = AsyncMock(return_value=1)
    wrap_fill.nth.return_value = qty_fill
    mock_page_fill.locator.return_value = wrap_fill
    assert await LocatorResolver.ensure_positive_quantity_selected(mock_page_fill) is True
    qty_fill.fill.assert_awaited_once_with("1", timeout=500)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_ensure_required_option_selected_cases():
    """Verifica selección automática de opción válida en <select> con placeholder."""
    # 1. Sin candidatos / error en evaluate -> None
    mock_page_none = MagicMock()
    mock_page_none.evaluate = AsyncMock(return_value=[])
    assert await LocatorResolver.ensure_required_option_selected(mock_page_none) is None

    mock_page_err = MagicMock()
    mock_page_err.evaluate = AsyncMock(side_effect=Exception("eval fail"))
    assert await LocatorResolver.ensure_required_option_selected(mock_page_err) is None

    # 2. Candidato válido -> selecciona primera opción y retorna (placeholder, chosen)
    mock_page_ok = MagicMock()
    mock_page_ok.evaluate = AsyncMock(
        return_value=[
            {"index": 0, "placeholderText": "Choose Size", "optionValue": "0", "optionText": "SM"}
        ]
    )
    select_loc = AsyncMock()
    select_loc.evaluate.return_value = True
    select_wrap = MagicMock()
    select_wrap.nth.return_value = select_loc
    mock_page_ok.locator.return_value = select_wrap

    res = await LocatorResolver.ensure_required_option_selected(mock_page_ok)
    assert res == ("Choose Size", "SM")
    select_loc.select_option.assert_awaited_once_with(value="0", timeout=500)

    # 3. Selector ocluido -> se omite y retorna None
    mock_page_occ = MagicMock()
    mock_page_occ.evaluate = AsyncMock(
        return_value=[
            {"index": 0, "placeholderText": "Choose Size", "optionValue": "0", "optionText": "SM"}
        ]
    )
    select_occ = AsyncMock()
    select_occ.evaluate.return_value = False
    select_wrap_occ = MagicMock()
    select_wrap_occ.nth.return_value = select_occ
    mock_page_occ.locator.return_value = select_wrap_occ
    assert await LocatorResolver.ensure_required_option_selected(mock_page_occ) is None
    select_occ.select_option.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_detect_blocking_overlay_cases():
    """Verifica detección de modal/panel superpuesto en primer plano y manejo seguro de fallos."""
    mock_page_hit = MagicMock()
    mock_page_hit.evaluate = AsyncMock(return_value="  Login — Sign in to continue  ")
    assert await LocatorResolver.detect_blocking_overlay(mock_page_hit) == "Login — Sign in to continue"

    mock_page_blank = MagicMock()
    mock_page_blank.evaluate = AsyncMock(return_value="   ")
    assert await LocatorResolver.detect_blocking_overlay(mock_page_blank) is None

    mock_page_non_str = MagicMock()
    mock_page_non_str.evaluate = AsyncMock(return_value=AsyncMock())
    assert await LocatorResolver.detect_blocking_overlay(mock_page_non_str) is None

    mock_page_err = MagicMock()
    mock_page_err.evaluate = AsyncMock(side_effect=Exception("eval fail"))
    assert await LocatorResolver.detect_blocking_overlay(mock_page_err) is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_is_login_barrier_and_clear_cart_items():
    """Verifica detección de barrera de login y limpieza acotada de ítems en carrito."""
    mock_page = MagicMock()
    mock_page.url = "https://shop.example.com/checkout"
    assert await LocatorResolver.is_login_barrier(mock_page, "Login — Sign in to continue") is True
    assert await LocatorResolver.is_login_barrier(mock_page, "Select your country") is False

    mock_page_login_url = MagicMock()
    mock_page_login_url.url = "https://shop.example.com/login"
    with patch.object(LocatorResolver, "find_login_button", return_value=AsyncMock()):
        assert await LocatorResolver.is_login_barrier(mock_page_login_url, None) is True

    # clear_cart_items: abre carrito, remueve 1 ítem fuera de chrome y detiene cuando ya no quedan
    cart_btn = AsyncMock()
    cart_btn.get_attribute.return_value = "/cart"
    remove_btn = AsyncMock()
    remove_btn.is_visible.return_value = True
    remove_btn.evaluate.return_value = False
    remove_btn.is_disabled.return_value = False
    remove_btn.get_attribute.return_value = "false"

    mock_cart_page = MagicMock()
    mock_cart_page.goto = AsyncMock()

    with (
        patch.object(LocatorResolver, "find_cart_button", return_value=cart_btn),
        patch.object(LocatorResolver, "_find_cart_remove_control", side_effect=[remove_btn, None]),
    ):
        removed = await LocatorResolver.clear_cart_items(mock_cart_page, "https://shop.example.com")

    assert removed == 1
    mock_cart_page.goto.assert_awaited_once_with(
        "https://shop.example.com/cart", wait_until="domcontentloaded", timeout=10000
    )
    remove_btn.click.assert_awaited_once_with(timeout=1500)

    # Fallback por ícono SVG / × en carrito cuando no hay botones de texto
    mock_icon_page = MagicMock()
    mock_icon_page.goto = AsyncMock()
    mock_icon_page.evaluate = AsyncMock(side_effect=[[640, 320], None])
    mock_icon_page.mouse = AsyncMock()
    with (
        patch.object(LocatorResolver, "find_cart_button", return_value=cart_btn),
        patch.object(LocatorResolver, "_find_cart_remove_control", return_value=None),
    ):
        removed_icon = await LocatorResolver.clear_cart_items(mock_icon_page, "https://shop.example.com")

    assert removed_icon == 1
    mock_icon_page.mouse.click.assert_awaited_once_with(640.0, 320.0)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_login_barrier_and_cart_cleanup_edge_branches():
    """Cubre ramas de is_login_barrier, _find_cart_remove_control y clear_cart_items."""
    from app.safety.action_guard import ActionGuard

    # 1. is_login_barrier por password visible en /login y fallo de locator
    mock_login_page = MagicMock()
    mock_login_page.url = "https://shop.example.com/login"
    pwd_vis = AsyncMock()
    pwd_vis.is_visible.return_value = True
    wrap_pwd = MagicMock()
    wrap_pwd.first = pwd_vis
    mock_login_page.locator.return_value = wrap_pwd
    with patch.object(LocatorResolver, "find_login_button", return_value=None):
        assert await LocatorResolver.is_login_barrier(mock_login_page, None) is True

    mock_login_err = MagicMock()
    mock_login_err.url = "https://shop.example.com/signin"
    mock_login_err.locator.side_effect = Exception("dom error")
    with patch.object(LocatorResolver, "find_login_button", return_value=None):
        assert await LocatorResolver.is_login_barrier(mock_login_err, None) is False

    # 2. _find_cart_remove_control: oculto, dentro de header, disabled, válido
    cand_hidden = AsyncMock()
    cand_hidden.is_visible.return_value = False
    cand_chrome = AsyncMock()
    cand_chrome.is_visible.return_value = True
    cand_chrome.evaluate.return_value = True
    cand_disabled = AsyncMock()
    cand_disabled.is_visible.return_value = True
    cand_disabled.evaluate.return_value = False
    cand_valid = AsyncMock()
    cand_valid.is_visible.return_value = True
    cand_valid.evaluate.return_value = False

    wrap_ctrl = MagicMock()
    wrap_ctrl.count = AsyncMock(return_value=4)
    wrap_ctrl.nth.side_effect = [cand_hidden, cand_chrome, cand_disabled, cand_valid]
    mock_ctrl_page = MagicMock()
    mock_ctrl_page.locator.return_value = wrap_ctrl
    with patch.object(LocatorResolver, "is_locator_disabled", side_effect=[True, False]):
        res = await LocatorResolver._find_cart_remove_control(mock_ctrl_page)
    assert res is cand_valid

    # 3. clear_cart_items: click sin href -> fallback routes -> action_guard bloquea y mouse error
    cart_no_href = AsyncMock()
    cart_no_href.get_attribute.return_value = None
    cart_no_href.click.side_effect = Exception("occluded")

    mock_guard = AsyncMock(spec=ActionGuard)
    mock_guard.inspect_locator.return_value = (False, "blocked")

    mock_fallback_page = MagicMock()
    mock_fallback_page.goto = AsyncMock(side_effect=[Exception("404"), None])
    mock_fallback_page.wait_for_load_state = AsyncMock()
    remove_cand = AsyncMock()
    with (
        patch.object(LocatorResolver, "find_cart_button", return_value=cart_no_href),
        patch.object(LocatorResolver, "_find_cart_remove_control", side_effect=[None, remove_cand]),
        patch.object(LocatorResolver, "_find_cart_remove_icon_coords", return_value=None),
    ):
        assert (
            await LocatorResolver.clear_cart_items(
                mock_fallback_page, "https://shop.example.com", action_guard=mock_guard
            )
            == 0
        )

    # 4. clear_cart_items: mouse.click falla en icon_coords
    mock_mouse_fail = MagicMock()
    mock_mouse_fail.goto = AsyncMock()
    mock_mouse_fail.mouse = AsyncMock()
    mock_mouse_fail.mouse.click.side_effect = Exception("mouse fail")
    with (
        patch.object(LocatorResolver, "find_cart_button", return_value=None),
        patch.object(LocatorResolver, "_find_cart_remove_control", return_value=None),
        patch.object(LocatorResolver, "_find_cart_remove_icon_coords", side_effect=[(10.0, 20.0), None]),
    ):
        assert await LocatorResolver.clear_cart_items(mock_mouse_fail, "https://shop.example.com") == 0

    # 5. ensure_required_option_selected ignora payloads inválidos o fallos en select_option
    mock_sel_page = MagicMock()
    mock_sel_page.evaluate = AsyncMock(
        return_value=["bad", {"index": "x"}, {"index": 0, "optionValue": "1", "optionText": "L"}]
    )
    sel_err_loc = AsyncMock()
    sel_err_loc.evaluate.return_value = True
    sel_err_loc.select_option.side_effect = Exception("select failed")
    wrap_sel = MagicMock()
    wrap_sel.nth.return_value = sel_err_loc
    mock_sel_page.locator.return_value = wrap_sel
    assert await LocatorResolver.ensure_required_option_selected(mock_sel_page) is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_find_quick_view_for_item_scroll_and_hover_fallback() -> None:
    """Verifica fallback de scroll en catálogo y reintento con hover sobre la tarjeta en desktop."""
    mock_page = MagicMock()

    # 1. Scroll no encuentra el ítem -> retorna None
    with (
        patch.object(LocatorResolver, "find_element_by_text", return_value=None),
        patch.object(LocatorResolver, "scroll_and_find_element_by_text", return_value=None),
    ):
        assert await LocatorResolver.find_quick_view_for_item(mock_page, "Producto Oculto") is None

    # 2. Scroll encuentra el ítem; Quick View solo se vuelve visible tras hover sobre la tarjeta
    mock_item = MagicMock()
    mock_card = MagicMock()
    mock_card.hover = AsyncMock()

    qv_hidden = AsyncMock()
    qv_hidden.is_visible.return_value = False
    matches_hidden = MagicMock()
    matches_hidden.count = AsyncMock(return_value=1)
    matches_hidden.first = qv_hidden

    qv_visible = AsyncMock()
    qv_visible.is_visible.return_value = True
    matches_visible = MagicMock()
    matches_visible.count = AsyncMock(return_value=1)
    matches_visible.first = qv_visible

    # Primera pasada (6 selectores ocultos), segunda pasada tras hover (primer selector visible)
    mock_card.locator.side_effect = [matches_hidden] * 6 + [matches_visible]
    mock_item.locator.return_value = mock_card

    with (
        patch.object(LocatorResolver, "find_element_by_text", return_value=None),
        patch.object(LocatorResolver, "scroll_and_find_element_by_text", return_value=mock_item),
    ):
        found = await LocatorResolver.find_quick_view_for_item(mock_page, "Producto Hover")

    assert found is qv_visible
    mock_card.hover.assert_awaited_once()

    # 3. Tras hover sigue sin haber Quick View -> limpia el cursor y retorna None
    mock_card_none = MagicMock()
    mock_card_none.hover = AsyncMock()
    mock_card_none.locator.return_value = matches_hidden
    mock_item_none = MagicMock()
    mock_item_none.locator.return_value = mock_card_none

    with (
        patch.object(LocatorResolver, "find_element_by_text", return_value=mock_item_none),
        patch.object(LocatorResolver, "reset_mouse_hover", new_callable=AsyncMock) as mock_reset,
    ):
        assert await LocatorResolver.find_quick_view_for_item(mock_page, "Producto Sin QV") is None
    mock_reset.assert_awaited_once_with(mock_page)
