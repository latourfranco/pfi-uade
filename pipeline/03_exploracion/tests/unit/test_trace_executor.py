"""Pruebas unitarias para TraceExecutor (reproducción integral de trazas de sesión)."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from app.agent.trace_executor import TraceExecutor
from app.models.client_config import ClientInterfaceConfig
from app.models.exploration_report import ExplorationStatus
from app.models.session_trace import DeviceInfo, SessionTrace, TraceEvent
from app.safety.action_guard import ActionGuard
from app.storage.base import StorageUploadError


def _create_mock_page(initial_url: str = "https://staging.mitienda.com/inicio") -> MagicMock:
    """Crea un mock síncrono para la página con métodos asíncronos configurados."""
    page = MagicMock()
    page.url = initial_url
    page.goto = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.evaluate = AsyncMock()
    page.keyboard = AsyncMock()
    page.mouse = AsyncMock()
    page.on = MagicMock()
    return page


@pytest.fixture
def sample_client_config() -> ClientInterfaceConfig:
    """Configuración de interfaz de cliente de prueba."""
    return ClientInterfaceConfig(
        client_id="client_test_123",
        base_url="https://staging.mitienda.com",
        requires_authentication=False,
    )


@pytest.fixture
def sample_trace() -> SessionTrace:
    """Traza representativa con distintos tipos de eventos y scroll contextual."""
    events = [
        TraceEvent(
            orden=1,
            nombre_evento="page_view",
            ruta="/inicio",
            scroll=True,
        ),
        TraceEvent(
            orden=2,
            nombre_evento="click",
            ruta="/inicio",
            click_detail="Ver catalogo",
        ),
        TraceEvent(
            orden=3,
            nombre_evento="search",
            ruta="/inicio",
            search_term="zapatillas deportivas",
        ),
        TraceEvent(
            orden=4,
            nombre_evento="custom_event",
            ruta="/inicio",
        ),
    ]
    return SessionTrace(
        id_patron="pattern_1",
        id_cliente="client_test_123",
        id_sesion="trace_abc_999",
        fecha_exploracion="2026-11-15",
        objetivo="add_to_cart",
        secuencia=["page_view /inicio", "click /inicio"],
        sesiones=50,
        usuarios=45,
        llegada_grupo=0.2,
        llegada_referencia=0.4,
        sesiones_perdidas=10.0,
        id_modelo="lstm_2026-11-14",
        primera_deteccion="2026-11-14",
        ultima_deteccion="2026-11-14",
        device_info=DeviceInfo(tipo_dispositivo="desktop"),
        events=events,
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_full_success_and_no_scroll_execution(
    sample_trace: SessionTrace,
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica la ejecución completa sin ejecutar scroll físico, preservando scroll como contexto."""
    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page()

    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_loc = AsyncMock()
    mock_loc.is_visible.return_value = True
    mock_loc.bounding_box.return_value = {"x": 10, "y": 20, "width": 100, "height": 40}
    mock_loc.inner_text.return_value = "Ver catalogo"
    mock_loc.get_attribute.return_value = None

    with patch("app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight") as mock_vh, \
         patch("app.agent.trace_executor.LocatorResolver.find_element_by_text", return_value=mock_loc), \
         patch("app.agent.trace_executor.LocatorResolver.find_search_input", return_value=mock_loc), \
         patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False):

        mock_vh.return_value = (b"fake-webp-data", None)

        executor = TraceExecutor(browser_manager=mock_browser_manager)
        report = await executor.execute_trace(sample_trace, sample_client_config)

        assert report.status == ExplorationStatus.COMPLETED
        assert report.total_steps == 4
        assert report.completed_steps == 4
        assert report.id_patron == "pattern_1"
        assert report.id_sesion == "trace_abc_999"
        assert report.fecha_exploracion == "2026-11-15"
        assert report.sesiones_perdidas == 10.0

        # El agente NO debe ejecutar window.scrollTo vía page.evaluate
        mock_page.evaluate.assert_not_called()
        assert report.evidences[0].scroll is True
        assert report.evidences[0].nombre_evento == "page_view"
        mock_context.close.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_with_custom_evidence_saver(
    sample_trace: SessionTrace,
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica que si se pasa un evidence_saver personalizado, se utilice la ruta con orden."""
    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page()
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    async def custom_saver(screenshot_bytes: bytes, filename: str, step: int) -> str:
        return f"https://storage.googleapis.com/test-bucket/{filename}"

    with patch("app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight") as mock_vh, \
         patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False):
        mock_vh.return_value = (b"fake-bytes", None)

        executor = TraceExecutor(
            browser_manager=mock_browser_manager,
            evidence_saver=custom_saver,
        )
        report = await executor.execute_trace(sample_trace, sample_client_config)

        assert report.status == ExplorationStatus.COMPLETED
        assert report.evidences[0].screenshot_url == (
            "https://storage.googleapis.com/test-bucket/"
            "capturas/client_test_123/2026-11-15/pattern_1_1.webp"
        )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_action_guard_blocks_dangerous_click(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica que ActionGuard impida hacer clic en botones de pago durante la traza."""
    dangerous_trace = SessionTrace(
        id_patron="pat_danger",
        id_cliente="client_test_123",
        id_sesion="trace_danger",
        events=[
            TraceEvent(
                orden=1,
                nombre_evento="click",
                ruta="/checkout",
                click_detail="Pagar ahora con tarjeta",
            )
        ],
    )

    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page(initial_url="https://staging.mitienda.com/checkout")
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_loc = AsyncMock()
    mock_loc.inner_text.return_value = "Pagar ahora con tarjeta"
    mock_loc.get_attribute.return_value = None

    with patch("app.agent.trace_executor.LocatorResolver.find_element_by_text", return_value=mock_loc), \
         patch("app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight") as mock_vh, \
         patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False):
        mock_vh.return_value = (b"fake", None)

        guard = ActionGuard()
        executor = TraceExecutor(browser_manager=mock_browser_manager, action_guard=guard)
        report = await executor.execute_trace(dangerous_trace, sample_client_config)

        assert report.status == ExplorationStatus.COMPLETED
        mock_loc.click.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_partial_success_on_step_failure(
    sample_trace: SessionTrace,
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica estado PARTIAL cuando ocurre un error en un paso intermedio."""
    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page()
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    obstacles_patch = patch(
        "app.agent.trace_executor.ObstacleHandler.dismiss_obstacles",
        side_effect=[False, False, RuntimeError("DOM crashed")],
    )
    with patch("app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight") as mock_vh, \
         obstacles_patch, \
         patch("app.agent.trace_executor.LocatorResolver.find_element_by_text", return_value=None):
        mock_vh.return_value = (b"fake", None)

        executor = TraceExecutor(browser_manager=mock_browser_manager)
        report = await executor.execute_trace(sample_trace, sample_client_config)

        assert report.status == ExplorationStatus.PARTIAL
        assert report.completed_steps == 1
        assert report.completed_steps < report.total_steps


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_fatal_context_error(
    sample_trace: SessionTrace,
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica estado FAILED cuando no se puede crear el contexto del navegador."""
    mock_browser_manager = AsyncMock()
    mock_browser_manager.create_context.side_effect = Exception("Falla fatal al lanzar Chromium")

    executor = TraceExecutor(browser_manager=mock_browser_manager)
    report = await executor.execute_trace(sample_trace, sample_client_config)

    assert report.status == ExplorationStatus.FAILED
    assert report.completed_steps == 0


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_auth_failure_continues_public(
    sample_trace: SessionTrace,
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica que si la autenticación falla, se loguee advertencia y continúe."""
    sample_client_config.requires_authentication = True
    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page()
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    with patch("app.agent.trace_executor.AuthHandler.authenticate", return_value=False), \
         patch("app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
               return_value=(b"fake", None)), \
         patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False):

        executor = TraceExecutor(browser_manager=mock_browser_manager)
        report = await executor.execute_trace(sample_trace, sample_client_config)

        assert report.status == ExplorationStatus.COMPLETED


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_failed_on_step_zero(
    sample_trace: SessionTrace,
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica estado FAILED cuando el primer paso falla y además falla la captura de error."""
    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page()
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_page.goto.side_effect = Exception("Falla de red en carga inicial")

    with patch("app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight") as mock_vh, \
         patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False):
        mock_vh.side_effect = Exception("Screenshot error")

        executor = TraceExecutor(browser_manager=mock_browser_manager)
        report = await executor.execute_trace(sample_trace, sample_client_config)

        assert report.status == ExplorationStatus.FAILED
        assert report.completed_steps == 0


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_context_close_exception(
    sample_trace: SessionTrace,
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica que un error al cerrar el contexto del navegador sea manejado limpiamente."""
    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page()
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_context.close.side_effect = Exception("Context closing failed")

    with patch("app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
               return_value=(b"fake", None)), \
         patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False):

        executor = TraceExecutor(browser_manager=mock_browser_manager)
        report = await executor.execute_trace(sample_trace, sample_client_config)

        assert report.status == ExplorationStatus.COMPLETED


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_link_traversal_success(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica la navegación mediante Link Traversal cuando existe un link al destino."""
    trace = SessionTrace(
        id_patron="pat_link",
        id_cliente="client_test_123",
        id_sesion="trace_link",
        events=[TraceEvent(orden=1, nombre_evento="page_view", ruta="/catalogo")],
    )
    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page(initial_url="https://staging.mitienda.com/inicio")
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_link = AsyncMock()
    mock_link.inner_text.return_value = "Ir a catálogo"
    mock_link.get_attribute.return_value = "/catalogo"
    mock_link.click = AsyncMock()

    with patch("app.agent.trace_executor.LocatorResolver.find_link_to_route", return_value=mock_link), \
         patch("app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
               return_value=(b"fake", None)), \
         patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False):

        executor = TraceExecutor(browser_manager=mock_browser_manager)
        report = await executor.execute_trace(trace, sample_client_config)

        assert report.status == ExplorationStatus.COMPLETED
        mock_link.click.assert_awaited_once()
        mock_page.goto.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_link_traversal_click_failure_fallback(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica que si el clic de Link Traversal falla, recurra a goto directo."""
    trace = SessionTrace(
        id_patron="pat_link_fail",
        id_cliente="client_test_123",
        id_sesion="trace_link_fail",
        events=[TraceEvent(orden=1, nombre_evento="page_view", ruta="/catalogo")],
    )
    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page(initial_url="https://staging.mitienda.com/inicio")
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_link = AsyncMock()
    mock_link.inner_text.return_value = "Ir a catálogo"
    mock_link.get_attribute.return_value = "/catalogo"
    mock_link.click.side_effect = Exception("Interception error")

    with patch("app.agent.trace_executor.LocatorResolver.find_link_to_route", return_value=mock_link), \
         patch("app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
               return_value=(b"fake", None)), \
         patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False):

        executor = TraceExecutor(browser_manager=mock_browser_manager)
        report = await executor.execute_trace(trace, sample_client_config)

        assert report.status == ExplorationStatus.COMPLETED
        mock_link.click.assert_awaited_once()
        mock_page.goto.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_interaction_click_failure_handled(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica que si el clic en un elemento interactivo lanza excepción, se capture y continúe."""
    trace = SessionTrace(
        id_patron="pat_click_err",
        id_cliente="client_test_123",
        id_sesion="trace_click_err",
        events=[
            TraceEvent(
                orden=1,
                nombre_evento="click",
                ruta="/inicio",
                click_detail="Boton con fallo",
            )
        ],
    )
    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page()
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_loc = AsyncMock()
    mock_loc.inner_text.return_value = "Boton con fallo"
    mock_loc.get_attribute.return_value = None
    mock_loc.click.side_effect = Exception("Click detached from DOM")

    with patch("app.agent.trace_executor.LocatorResolver.find_element_by_text", return_value=mock_loc), \
         patch("app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
               return_value=(b"fake", None)), \
         patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False):

        executor = TraceExecutor(browser_manager=mock_browser_manager)
        report = await executor.execute_trace(trace, sample_client_config)

        assert report.status == ExplorationStatus.COMPLETED
        mock_loc.click.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_networkidle_timeout_handled(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica que el timeout al esperar networkidle sea tolerado sin abortar la navegación."""
    trace = SessionTrace(
        id_patron="pat_netidle",
        id_cliente="client_test_123",
        id_sesion="trace_networkidle_to",
        events=[TraceEvent(orden=1, nombre_evento="page_view", ruta="/inicio")],
    )
    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page()
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_page.wait_for_load_state.side_effect = [None, Exception("Timeout 2000ms")]

    with patch("app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
               return_value=(b"fake", None)), \
         patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False):

        executor = TraceExecutor(browser_manager=mock_browser_manager)
        report = await executor.execute_trace(trace, sample_client_config)

        assert report.status == ExplorationStatus.COMPLETED


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_with_storage_state(
    sample_trace: SessionTrace,
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica que en paso 0 el contexto arranque anónimo (JIT) sin inyectar storage_state ni AuthHandler."""
    sample_client_config.requires_authentication = True
    sample_state = {"cookies": [{"name": "auth", "value": "pass"}], "origins": []}
    sample_client_config.storage_state = sample_state

    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page()
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    with patch("app.agent.trace_executor.AuthHandler.authenticate") as mock_auth, \
         patch("app.agent.trace_executor.AuthHandler.inject_storage_state_jit") as mock_jit, \
         patch("app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
               return_value=(b"fake", None)), \
         patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False):

        executor = TraceExecutor(browser_manager=mock_browser_manager)
        report = await executor.execute_trace(sample_trace, sample_client_config)

        assert report.status == ExplorationStatus.COMPLETED
        mock_browser_manager.create_context.assert_awaited_once_with(
            device_info=sample_trace.device_info,
            custom_headers=sample_client_config.custom_headers,
            storage_state=None,
        )
        mock_auth.assert_not_called()
        mock_jit.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_ecommerce_actions_and_items_fallback(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica la resolución inteligente para add_to_cart, checkout, view_cart, view_login y select_item."""
    trace = SessionTrace(
        id_patron="p_ecom",
        id_cliente="client_ecom",
        id_sesion="trace_ecom_1",
        usuarios=15,
        sesiones_perdidas=20.0,
        events=[
            TraceEvent(orden=1, nombre_evento="add_to_cart", ruta="/product/1"),
            TraceEvent(orden=2, nombre_evento="add_shipping_info", ruta="/checkout"),
            TraceEvent(orden=3, nombre_evento="view_cart", ruta="/cart"),
            TraceEvent(orden=4, nombre_evento="view_login", ruta="/checkout"),
            TraceEvent(
                orden=5,
                nombre_evento="select_item",
                ruta="/shop",
                items="Buzo Negro Google",
                es_paso_friccion=True,
            ),
        ],
    )

    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page(initial_url="https://staging.mitienda.com/product/1")
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_loc = AsyncMock()
    mock_loc.is_visible.return_value = True
    mock_loc.bounding_box.return_value = {"x": 0, "y": 0, "width": 10, "height": 10}
    mock_loc.inner_text.return_value = "Agregar"
    mock_loc.get_attribute.return_value = None

    p_cart = patch("app.agent.trace_executor.LocatorResolver.find_add_to_cart_button", return_value=mock_loc)
    p_ship = patch(
        "app.agent.trace_executor.LocatorResolver.find_checkout_or_continue_button",
        return_value=mock_loc,
    )
    p_view_cart = patch("app.agent.trace_executor.LocatorResolver.find_cart_button", return_value=mock_loc)
    p_login = patch("app.agent.trace_executor.LocatorResolver.find_login_button", return_value=mock_loc)
    p_text = patch("app.agent.trace_executor.LocatorResolver.find_element_by_text", return_value=mock_loc)
    p_high = patch(
        "app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
        return_value=(b"webp", None),
    )
    p_obst = patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False)

    with p_cart as m_cart, p_ship as m_ship, p_view_cart as m_view_cart, \
         p_login as m_login, p_text as m_text, p_high, p_obst:

        executor = TraceExecutor(browser_manager=mock_browser_manager)
        report = await executor.execute_trace(trace, sample_client_config)

        assert report.status == ExplorationStatus.COMPLETED
        assert report.usuarios == 15
        assert report.sesiones_perdidas == 20.0
        m_cart.assert_awaited_once()
        m_ship.assert_awaited_once()
        m_view_cart.assert_awaited_once()
        m_login.assert_awaited_once()
        m_text.assert_awaited_with(mock_page, "Buzo Negro Google")

        assert report.evidences[4].es_paso_friccion is True
        assert report.evidences[4].screenshot_url != ""


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_interaction_element_not_found_captures_evidence(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica que si un elemento interactivo no se encuentra en el DOM, se capture evidencia visual."""
    trace = SessionTrace(
        id_patron="pat_missing",
        id_cliente="client_test_missing",
        id_sesion="trace_missing_elem",
        events=[
            TraceEvent(
                orden=1,
                nombre_evento="select_item",
                ruta="/clearance",
                items="Remera Inexistente 2020",
            )
        ],
    )

    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page()
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    with patch("app.agent.trace_executor.LocatorResolver.find_element_by_text", return_value=None), \
         patch("app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
               return_value=(b"fake_not_found", None)) as mock_vh, \
         patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False):

        executor = TraceExecutor(browser_manager=mock_browser_manager)
        report = await executor.execute_trace(trace, sample_client_config)

        assert report.status == ExplorationStatus.COMPLETED
        assert len(report.evidences) == 1
        assert report.evidences[0].screenshot_url != ""
        assert mock_vh.call_args.kwargs["context_type"] == "interaction_element_not_found"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_search_input_not_found_captures_evidence(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica que si el input de búsqueda no existe en el DOM, se capture evidencia de elemento no encontrado."""
    trace = SessionTrace(
        id_patron="pat_no_search",
        id_cliente="client_test_missing_search",
        id_sesion="trace_missing_search",
        events=[
            TraceEvent(
                orden=1,
                nombre_evento="search",
                ruta="/shop",
                search_term="pantalon deportivo",
            )
        ],
    )

    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page()
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    with patch("app.agent.trace_executor.LocatorResolver.find_search_input", return_value=None), \
         patch("app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
               return_value=(b"fake_search_missing", None)) as mock_vh, \
         patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False):

        executor = TraceExecutor(browser_manager=mock_browser_manager)
        report = await executor.execute_trace(trace, sample_client_config)

        assert report.status == ExplorationStatus.COMPLETED
        assert len(report.evidences) == 1
        assert report.evidences[0].screenshot_url != ""
        assert mock_vh.call_args.kwargs["context_type"] == "search_input_not_found"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_captures_all_steps_including_non_pattern_steps(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica que se recorran y capturen visualmente todos los pasos, dentro y fuera del patrón."""
    trace = SessionTrace(
        id_patron="pat_all_captures",
        id_cliente="client_all_captures",
        id_sesion="trace_all_captures",
        events=[
            TraceEvent(orden=1, nombre_evento="page_view", ruta="/home", en_patron=False, scroll=True),
            TraceEvent(orden=2, nombre_evento="select_item", ruta="/clearance", items="Item Antiguo", en_patron=False),
            TraceEvent(orden=3, nombre_evento="page_view", ruta="/checkout", en_patron=True),
        ],
    )

    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page()
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_loc = AsyncMock()
    mock_loc.inner_text.return_value = "Item Antiguo"
    mock_loc.get_attribute.return_value = None

    with patch("app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
               return_value=(b"fake_checkout", None)) as mock_vh, \
         patch("app.agent.trace_executor.LocatorResolver.find_quick_view_for_item", return_value=None), \
         patch("app.agent.trace_executor.LocatorResolver.find_element_by_text", return_value=mock_loc), \
         patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False):

        executor = TraceExecutor(browser_manager=mock_browser_manager, page_settle_seconds=0.0)
        report = await executor.execute_trace(trace, sample_client_config)

        assert report.status == ExplorationStatus.COMPLETED
        assert report.total_steps == 3
        assert report.completed_steps == 3
        assert len(report.evidences) == 3

        assert report.evidences[0].orden == 1
        assert report.evidences[0].en_patron is False
        assert report.evidences[0].screenshot_url != ""
        assert report.evidences[0].scroll is True

        assert report.evidences[1].orden == 2
        assert report.evidences[1].en_patron is False
        assert report.evidences[1].screenshot_url != ""

        assert report.evidences[2].orden == 3
        assert report.evidences[2].en_patron is True
        assert report.evidences[2].screenshot_url != ""
        assert mock_vh.call_count == 3
        assert [c.kwargs["context_type"] for c in mock_vh.call_args_list] == [
            "page_view_loaded",
            "interaction_click",
            "page_view_loaded",
        ]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_page_settle_configuration() -> None:
    """Verifica la inicialización configurable de page_settle_seconds."""
    ex_custom = TraceExecutor(page_settle_seconds=3.5)
    assert ex_custom.page_settle_seconds == 3.5

    with patch.dict("os.environ", {"PAGE_SETTLE_SECONDS": "7.2"}):
        ex_env = TraceExecutor()
        assert ex_env.page_settle_seconds == 7.2

    with patch.dict("os.environ", {"PAGE_SETTLE_SECONDS": "invalid_num"}):
        ex_invalid = TraceExecutor()
        assert ex_invalid.page_settle_seconds == 5.0


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_one_evidence_per_step_across_non_pattern_boundary(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica que un paso previo al patrón con link traversal genere exactamente 1 evidencia con captura."""
    trace = SessionTrace(
        id_patron="pat_dedup",
        id_cliente="client_dedup",
        id_sesion="trace_dedup",
        events=[
            TraceEvent(orden=1, nombre_evento="page_view", ruta="/clearance", en_patron=False),
            TraceEvent(orden=2, nombre_evento="page_view", ruta="/cart", en_patron=True),
        ],
    )

    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page(initial_url="https://staging.mitienda.com/clearance")
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_link = AsyncMock()
    mock_link.is_visible.return_value = True
    mock_link.inner_text.return_value = "Ir a carrito"
    mock_link.get_attribute.return_value = None

    with patch("app.agent.trace_executor.LocatorResolver.find_link_to_route", return_value=mock_link), \
         patch("app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
               return_value=(b"cart_bytes", None)) as mock_vh, \
         patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False):

        executor = TraceExecutor(browser_manager=mock_browser_manager, page_settle_seconds=0.0)
        report = await executor.execute_trace(trace, sample_client_config)

        assert report.completed_steps == 2
        step_1_evidences = [ev for ev in report.evidences if ev.orden == 1]
        assert len(step_1_evidences) == 1
        assert step_1_evidences[0].screenshot_url != ""
        assert mock_vh.call_args_list[0].kwargs["context_type"] == "link_traversal_click"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_error_in_preliminary_step_forces_capture(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica que si ocurre un error en un paso preliminar, se fuerce la captura visual de la falla."""
    trace = SessionTrace(
        id_patron="pat_prelim_err",
        id_cliente="client_prelim_err",
        id_sesion="trace_prelim_err",
        events=[
            TraceEvent(orden=1, nombre_evento="page_view", ruta="/home", en_patron=False),
            TraceEvent(orden=2, nombre_evento="page_view", ruta="/checkout", en_patron=True),
        ],
    )

    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page()
    mock_page.goto.side_effect = RuntimeError("Navigation failed")
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    with patch("app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
               return_value=(b"error_bytes", None)) as mock_vh, \
         patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False):

        executor = TraceExecutor(browser_manager=mock_browser_manager, page_settle_seconds=0.0)
        report = await executor.execute_trace(trace, sample_client_config)

        assert report.status == ExplorationStatus.FAILED
        assert report.completed_steps == 0
        mock_vh.assert_called_once()
        assert len(report.evidences) == 1
        assert mock_vh.call_args.kwargs["context_type"] == "error_step_1"
        assert report.evidences[0].screenshot_url != ""


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_initial_step_interaction_about_blank(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica que si el primer paso es una interacción con page.url == about:blank, navegue a ruta."""
    trace = SessionTrace(
        id_patron="pat_int_first",
        id_cliente="client_interact_first",
        id_sesion="trace_interact_first",
        events=[
            TraceEvent(
                orden=1,
                nombre_evento="select_item",
                ruta="/product/123",
                items="Mi Producto",
                en_patron=True,
            )
        ],
    )

    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page(initial_url="about:blank")
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_loc = AsyncMock()
    mock_loc.inner_text.return_value = "Mi Producto"
    mock_loc.get_attribute.return_value = None

    with patch("app.agent.trace_executor.LocatorResolver.find_element_by_text", return_value=mock_loc), \
         patch("app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
               return_value=(b"fake_prod", None)), \
         patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False):

        executor = TraceExecutor(browser_manager=mock_browser_manager)
        report = await executor.execute_trace(trace, sample_client_config)

        assert report.status == ExplorationStatus.COMPLETED
        mock_page.goto.assert_awaited_once_with(
            "https://staging.mitienda.com/product/123",
            wait_until="domcontentloaded",
        )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_closes_page_and_context_in_finally(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica cierre explícito de page (incluso si falla) y context en el bloque finally."""
    trace = SessionTrace(
        id_patron="pat_close",
        id_cliente="cli_close",
        id_sesion="trace_close",
        events=[TraceEvent(orden=1, nombre_evento="page_view", ruta="/inicio")],
    )

    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page()
    mock_page.close = AsyncMock(side_effect=RuntimeError("page close error"))
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    with patch(
        "app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
        return_value=(b"fake_webp", None),
    ), patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False):
        executor = TraceExecutor(browser_manager=mock_browser_manager, page_settle_seconds=0.0)
        report = await executor.execute_trace(trace, sample_client_config)

    assert report.status == ExplorationStatus.COMPLETED
    mock_page.close.assert_awaited_once()
    mock_context.close.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_propagates_storage_upload_error(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica que fallos de evidence_saver lancen StorageUploadError sin ser silenciados."""
    trace = SessionTrace(
        id_patron="pat_upload",
        id_cliente="cli_upload",
        id_sesion="trace_upload_err",
        events=[TraceEvent(orden=1, nombre_evento="page_view", ruta="/inicio")],
    )

    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page()
    mock_page.close = AsyncMock()
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    async def failing_saver(data: bytes, filename: str, step: int) -> str:
        raise RuntimeError("GCS bucket unreachable")

    with patch(
        "app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
        return_value=(b"fake_webp", None),
    ), patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False):
        executor = TraceExecutor(
            browser_manager=mock_browser_manager,
            evidence_saver=failing_saver,
            page_settle_seconds=0.0,
        )
        with pytest.raises(StorageUploadError, match="Error al persistir evidencia"):
            await executor.execute_trace(trace, sample_client_config)

    mock_page.close.assert_awaited_once()
    mock_context.close.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_step_failure_logs_warning_and_propagates_error_capture_upload_error(
    sample_client_config: ClientInterfaceConfig,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verifica log WARNING en fallo de paso y propagación de StorageUploadError en captura de error."""
    trace = SessionTrace(
        id_patron="pat_warn",
        id_cliente="cli_warn",
        id_sesion="trace_step_warn",
        events=[TraceEvent(orden=1, nombre_evento="custom_other", ruta="/inicio")],
    )

    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page()
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    async def direct_storage_error(data: bytes, filename: str, step: int) -> str:
        raise StorageUploadError("Fatal GCS write failure")

    with patch(
        "app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
        return_value=(b"error_bytes", None),
    ), patch(
        "app.agent.trace_executor.ObstacleHandler.dismiss_obstacles",
        side_effect=RuntimeError("Step failure"),
    ):
        executor = TraceExecutor(
            browser_manager=mock_browser_manager,
            evidence_saver=direct_storage_error,
            page_settle_seconds=0.0,
        )
        with caplog.at_level(logging.WARNING, logger="app.agent.trace_executor"):
            with pytest.raises(StorageUploadError, match="Fatal GCS write failure"):
                await executor.execute_trace(trace, sample_client_config)

    warn_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warn_records) == 1
    assert getattr(warn_records[0], "id_patron") == "pat_warn"
    assert getattr(warn_records[0], "paso") == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_settle_positive_and_fallback_to_text_when_ecom_controls_missing(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Cubre ramas con page_settle_seconds > 0 y fallbacks cuando botones e-commerce no se hallan."""
    trace = SessionTrace(
        id_patron="pat_fallbacks",
        id_cliente="cli_fb",
        id_sesion="ses_fb",
        events=[
            TraceEvent(orden=1, nombre_evento="add_to_cart", ruta="/prod"),
            TraceEvent(orden=2, nombre_evento="add_billing_info", ruta="/checkout"),
            TraceEvent(orden=3, nombre_evento="view_cart", ruta="/cart"),
            TraceEvent(orden=4, nombre_evento="login", ruta="/login"),
        ],
    )

    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page(initial_url="about:blank")
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_page.wait_for_load_state.side_effect = Exception("networkidle timeout")

    with patch("app.agent.trace_executor.LocatorResolver.find_add_to_cart_button", return_value=None), \
         patch("app.agent.trace_executor.LocatorResolver.find_checkout_or_continue_button", return_value=None), \
         patch("app.agent.trace_executor.LocatorResolver.find_cart_button", return_value=None), \
         patch("app.agent.trace_executor.LocatorResolver.find_login_button", return_value=None), \
         patch("app.agent.trace_executor.LocatorResolver.find_element_by_text", return_value=None), \
         patch("app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
               return_value=(b"fb", None)), \
         patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False), \
         patch("app.agent.trace_executor.asyncio.sleep", new_callable=AsyncMock):

        executor = TraceExecutor(browser_manager=mock_browser_manager, page_settle_seconds=0.5)
        report = await executor.execute_trace(trace, sample_client_config)

        assert report.status == ExplorationStatus.COMPLETED
        assert report.completed_steps == 4


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_lookahead_captures_one_evidence_per_page_view(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica 1 evidencia por paso: el paso N resalta el link hacia N+1 y N+1 captura el destino."""
    trace = SessionTrace(
        id_patron="pat_lookahead",
        id_cliente="cli_la",
        id_sesion="ses_la",
        events=[
            TraceEvent(orden=1, nombre_evento="page_view", ruta="/", en_patron=True),
            TraceEvent(orden=2, nombre_evento="page_view", ruta="/shop/socks", en_patron=True),
            TraceEvent(
                orden=3,
                nombre_evento="page_view",
                ruta="/shop/collections",
                en_patron=True,
                es_paso_friccion=True,
            ),
        ],
    )

    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page(initial_url="about:blank")
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    async def _goto_side_effect(url: str, wait_until: str = "domcontentloaded") -> None:
        del wait_until
        mock_page.url = url

    async def _wait_load_state(state: str = "load", timeout: int = 2000) -> None:
        del timeout
        if state == "networkidle":
            raise TimeoutError("networkidle timeout")

    mock_page.goto = AsyncMock(side_effect=_goto_side_effect)
    mock_page.wait_for_load_state = AsyncMock(side_effect=_wait_load_state)

    mock_link_to_socks = AsyncMock()

    async def _click_socks(timeout: int = 3000) -> None:
        del timeout
        mock_page.url = "https://staging.mitienda.com/shop/socks"

    mock_link_to_socks.click = AsyncMock(side_effect=_click_socks)

    async def _find_link_side_effect(page: MagicMock, route_path: str) -> object:
        del page
        if route_path == "/shop/socks":
            return mock_link_to_socks
        return None

    with (
        patch("app.agent.trace_executor.LocatorResolver.find_link_to_route", side_effect=_find_link_side_effect),
        patch.object(ActionGuard, "inspect_locator", return_value=(True, "")),
        patch(
            "app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
            return_value=(b"img", None),
        ) as mock_highlight,
        patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False),
        patch("app.agent.trace_executor.asyncio.sleep", new_callable=AsyncMock),
    ):

        executor = TraceExecutor(browser_manager=mock_browser_manager, page_settle_seconds=0.2)
        report = await executor.execute_trace(trace, sample_client_config)

    assert report.status == ExplorationStatus.COMPLETED
    assert report.completed_steps == 3
    assert len(report.evidences) == 3

    ev1, ev2, ev3 = report.evidences
    assert ev1.orden == 1
    assert ev1.ruta == "https://staging.mitienda.com/"

    assert ev2.orden == 2
    assert ev2.ruta == "https://staging.mitienda.com/shop/socks"

    assert ev3.orden == 3
    assert ev3.es_paso_friccion is True
    assert ev3.ruta == "https://staging.mitienda.com/shop/collections"

    # Paso 1 resaltó mock_link_to_socks; pasos 2 y 3 capturaron sin locator
    assert mock_highlight.call_count == 3
    assert mock_highlight.call_args_list[0].kwargs["locator"] is mock_link_to_socks
    assert mock_highlight.call_args_list[0].kwargs["context_type"] == "link_traversal_click"
    assert mock_highlight.call_args_list[1].kwargs["locator"] is None
    assert mock_highlight.call_args_list[1].kwargs["context_type"] == "page_view_loaded"
    assert mock_highlight.call_args_list[2].kwargs["locator"] is None
    assert mock_highlight.call_args_list[2].kwargs["context_type"] == "page_view_loaded"
    mock_link_to_socks.click.assert_awaited_once()
    assert mock_page.goto.await_count == 2


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_lookahead_supports_strict_root_navigation(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica lookahead y Link Traversal cuando un paso vuelve estrictamente a la raíz '/'."""
    trace = SessionTrace(
        id_patron="pat_la_root",
        id_cliente="cli_la_root",
        id_sesion="ses_la_root",
        events=[
            TraceEvent(orden=1, nombre_evento="page_view", ruta="/cart", en_patron=True),
            TraceEvent(orden=2, nombre_evento="page_view", ruta="/", en_patron=True),
        ],
    )

    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page(initial_url="about:blank")
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    async def _goto_side_effect(url: str, wait_until: str = "domcontentloaded") -> None:
        del wait_until
        mock_page.url = url

    mock_page.goto = AsyncMock(side_effect=_goto_side_effect)
    mock_home_link = AsyncMock()

    async def _click_home(timeout: int = 3000) -> None:
        del timeout
        mock_page.url = "https://staging.mitienda.com/"

    mock_home_link.click = AsyncMock(side_effect=_click_home)

    async def _find_link_side_effect(page: MagicMock, route_path: str) -> object:
        del page
        if route_path == "/":
            return mock_home_link
        return None

    with (
        patch("app.agent.trace_executor.LocatorResolver.find_link_to_route", side_effect=_find_link_side_effect),
        patch.object(ActionGuard, "inspect_locator", return_value=(True, "")),
        patch(
            "app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
            return_value=(b"img", None),
        ) as mock_highlight,
        patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False),
    ):
        executor = TraceExecutor(browser_manager=mock_browser_manager, page_settle_seconds=0.0)
        report = await executor.execute_trace(trace, sample_client_config)

    assert report.status == ExplorationStatus.COMPLETED
    assert len(report.evidences) == 2
    assert mock_highlight.call_args_list[0].kwargs["locator"] is mock_home_link
    assert mock_highlight.call_args_list[0].kwargs["context_type"] == "link_traversal_click"
    assert mock_highlight.call_args_list[1].kwargs["context_type"] == "page_view_loaded"
    mock_home_link.click.assert_awaited_once()
    assert mock_page.goto.await_count == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_lookahead_skips_same_route_and_unsafe_links(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica que el lookahead ignore misma ruta consecutiva y enlaces bloqueados por ActionGuard."""
    trace = SessionTrace(
        id_patron="pat_la_edge",
        id_cliente="cli_la_edge",
        id_sesion="ses_la_edge",
        events=[
            TraceEvent(orden=1, nombre_evento="page_view", ruta="/cart", en_patron=True),
            TraceEvent(orden=2, nombre_evento="page_view", ruta="/cart", en_patron=True),
            TraceEvent(orden=3, nombre_evento="page_view", ruta="/", en_patron=True),
            TraceEvent(orden=4, nombre_evento="page_view", ruta="/checkout", en_patron=True),
        ],
    )

    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page(initial_url="about:blank")
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    async def _goto_side_effect(url: str, wait_until: str = "domcontentloaded") -> None:
        del wait_until
        mock_page.url = url

    mock_page.goto = AsyncMock(side_effect=_goto_side_effect)
    mock_unsafe_link = AsyncMock()

    with (
        patch("app.agent.trace_executor.LocatorResolver.find_link_to_route", return_value=mock_unsafe_link),
        patch.object(ActionGuard, "inspect_locator", return_value=(False, "unsafe_payment_link")),
        patch(
            "app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
            return_value=(b"img", None),
        ) as mock_highlight,
        patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False),
    ):

        executor = TraceExecutor(browser_manager=mock_browser_manager, page_settle_seconds=0.0)
        report = await executor.execute_trace(trace, sample_client_config)

    assert report.status == ExplorationStatus.COMPLETED
    assert len(report.evidences) == 4
    assert all(call.kwargs["context_type"] == "page_view_loaded" for call in mock_highlight.call_args_list)
    assert all(call.kwargs["locator"] is None for call in mock_highlight.call_args_list)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_captures_before_during_and_after_pattern_steps(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica que todos los pasos (previos, del patrón y posteriores) capturen screenshot y metadata."""
    trace = SessionTrace(
        id_patron="pat_post_label",
        id_cliente="cli_post",
        id_sesion="ses_post",
        events=[
            TraceEvent(orden=1, nombre_evento="page_view", ruta="/", en_patron=False),
            TraceEvent(orden=2, nombre_evento="page_view", ruta="/socks", en_patron=True, es_paso_friccion=True),
            TraceEvent(orden=3, nombre_evento="page_view", ruta="/product", en_patron=False),
        ],
    )

    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page(initial_url="about:blank")
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    with (
        patch("app.agent.trace_executor.LocatorResolver.find_link_to_route", return_value=None),
        patch(
            "app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
            return_value=(b"img", None),
        ) as mock_highlight,
        patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False),
    ):
        executor = TraceExecutor(browser_manager=mock_browser_manager, page_settle_seconds=0.0)
        report = await executor.execute_trace(trace, sample_client_config)

    assert report.status == ExplorationStatus.COMPLETED
    assert len(report.evidences) == 3
    assert report.evidences[0].en_patron is False
    assert report.evidences[0].es_paso_friccion is False
    assert report.evidences[0].screenshot_url != ""
    assert report.evidences[1].en_patron is True
    assert report.evidences[1].es_paso_friccion is True
    assert report.evidences[1].screenshot_url != ""
    assert report.evidences[2].en_patron is False
    assert report.evidences[2].es_paso_friccion is False
    assert report.evidences[2].screenshot_url != ""
    assert mock_highlight.call_count == 3


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_select_item_prefers_quick_view_when_next_route_differs(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica Opción 2: page_view previo resalta Quick View y select_item captura el modal desplegado."""
    trace = SessionTrace(
        id_patron="pat_qv",
        id_cliente="cli_qv",
        id_sesion="ses_qv",
        events=[
            TraceEvent(
                orden=1,
                nombre_evento="page_view",
                ruta="/shop/collections/view-all-campus-collection",
            ),
            TraceEvent(
                orden=2,
                nombre_evento="select_item",
                ruta="/shop/collections/view-all-campus-collection",
                items="Google Grey Organic NYC Tee",
            ),
            TraceEvent(
                orden=3,
                nombre_evento="page_view",
                ruta="/product/google-bike-party-bottle-gmssgdhl121799",
            ),
        ],
    )

    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page(initial_url="about:blank")
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    async def _goto_side(url: str, wait_until: str = "domcontentloaded") -> None:
        del wait_until
        mock_page.url = url

    mock_page.goto = AsyncMock(side_effect=_goto_side)

    mock_qv_btn = AsyncMock()
    mock_qv_btn.is_visible.return_value = True
    mock_qv_btn.inner_text.return_value = "Quick View"
    mock_qv_btn.get_attribute.return_value = None

    with (
        patch("app.agent.trace_executor.LocatorResolver.find_quick_view_for_item", return_value=mock_qv_btn) as mock_qv,
        patch("app.agent.trace_executor.LocatorResolver.find_element_by_text") as mock_text,
        patch("app.agent.trace_executor.LocatorResolver.find_link_to_route", return_value=None),
        patch(
            "app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
            return_value=(b"img", None),
        ) as mock_highlight,
        patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False),
    ):
        executor = TraceExecutor(browser_manager=mock_browser_manager, page_settle_seconds=0.0)
        report = await executor.execute_trace(trace, sample_client_config)

    assert report.status == ExplorationStatus.COMPLETED
    assert mock_qv.await_count == 2
    mock_text.assert_not_called()
    # Paso 1 (page_view) resalta el ojo sin clickear; paso 2 (select_item) clickea y captura el modal abierto
    assert mock_highlight.call_args_list[0].kwargs["locator"] is mock_qv_btn
    assert mock_highlight.call_args_list[0].kwargs["context_type"] == "quick_view_click"
    assert mock_highlight.call_args_list[1].kwargs["locator"] is None
    assert mock_highlight.call_args_list[1].kwargs["context_type"] == "quick_view_opened"
    assert mock_highlight.call_args_list[2].kwargs["context_type"] == "page_view_loaded"
    mock_qv_btn.click.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_quick_view_preserves_modal_for_add_to_cart_and_handles_errors(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica que add_to_cart tras Quick View preserve el modal abierto y tolere errores al abrir."""
    trace = SessionTrace(
        id_patron="pat_qv_cart",
        id_cliente="cli_qv_cart",
        id_sesion="ses_qv_cart",
        events=[
            TraceEvent(
                orden=1,
                nombre_evento="select_item",
                ruta="/shop/collections",
                items="Google Grey Organic NYC Tee",
            ),
            TraceEvent(
                orden=2,
                nombre_evento="add_to_cart",
                ruta="/shop/collections",
            ),
        ],
    )

    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page(initial_url="https://staging.mitienda.com/shop/collections")
    mock_page.wait_for_load_state.side_effect = Exception("networkidle timeout")
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_qv_btn = AsyncMock()
    mock_cart_btn = AsyncMock()

    with (
        patch("app.agent.trace_executor.LocatorResolver.find_quick_view_for_item", return_value=mock_qv_btn),
        patch("app.agent.trace_executor.LocatorResolver.find_add_to_cart_button", return_value=mock_cart_btn),
        patch.object(ActionGuard, "inspect_locator", return_value=(True, "")),
        patch("app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight", return_value=(b"img", None)),
        patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False) as mock_dismiss,
    ):
        executor = TraceExecutor(browser_manager=mock_browser_manager, page_settle_seconds=0.05)
        report = await executor.execute_trace(trace, sample_client_config)

    assert report.status == ExplorationStatus.COMPLETED
    # Solo se llama dismiss_obstacles en el paso 1; se omite en paso 2 (add_to_cart) para no cerrar el modal
    assert mock_dismiss.await_count == 1
    mock_qv_btn.click.assert_awaited_once()
    mock_cart_btn.click.assert_awaited_once()

    # También cubre el caso donde clickear Quick View lanza excepción
    mock_qv_err = AsyncMock()
    mock_qv_err.click.side_effect = RuntimeError("Click interceptado")
    trace_err = SessionTrace(
        id_patron="pat_qv_err",
        id_cliente="cli_qv_err",
        id_sesion="ses_qv_err",
        events=[trace.events[0], trace.events[1]],
    )
    with (
        patch("app.agent.trace_executor.LocatorResolver.find_quick_view_for_item", return_value=mock_qv_err),
        patch("app.agent.trace_executor.LocatorResolver.find_add_to_cart_button", return_value=mock_cart_btn),
        patch.object(ActionGuard, "inspect_locator", return_value=(True, "")),
        patch("app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight", return_value=(b"img", None)),
        patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False) as mock_dismiss2,
    ):
        executor2 = TraceExecutor(browser_manager=mock_browser_manager, page_settle_seconds=0.0)
        report2 = await executor2.execute_trace(trace_err, sample_client_config)

    assert report2.status == ExplorationStatus.COMPLETED
    # Como falló la apertura, dismiss_obstacles vuelve a ejecutarse en ambos pasos
    assert mock_dismiss2.await_count == 2


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_select_item_quick_view_heuristics_and_fallback(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Cubre las heurísticas de _should_prefer_quick_view y fallback cuando no hay botón Quick View."""
    sel_tee = TraceEvent(
        orden=1,
        nombre_evento="select_item",
        ruta="/shop/collections",
        items="Google Grey Organic NYC Tee",
    )
    pv_same_tee = TraceEvent(
        orden=2,
        nombre_evento="page_view",
        ruta="/product/google-grey-organic-nyc-tee-gmssgxxx1112",
    )
    pv_same_route = TraceEvent(orden=2, nombre_evento="page_view", ruta="/shop/collections")
    ev_add_cart = TraceEvent(orden=2, nombre_evento="add_to_cart", ruta="/shop/collections")
    sel_short = TraceEvent(orden=1, nombre_evento="select_item", ruta="/shop", items="Tee")
    pv_other = TraceEvent(orden=2, nombre_evento="page_view", ruta="/product/other")

    assert TraceExecutor._should_prefer_quick_view(sel_tee, pv_same_tee) is False
    assert TraceExecutor._should_prefer_quick_view(sel_tee, pv_same_route) is True
    assert TraceExecutor._should_prefer_quick_view(sel_tee, ev_add_cart) is True
    assert TraceExecutor._should_prefer_quick_view(sel_short, pv_other) is False

    # Si find_quick_view_for_item retorna None en select_item -> add_to_cart, cae a find_element_by_text
    trace = SessionTrace(
        id_patron="pat_qv_fb",
        id_cliente="cli_qv_fb",
        id_sesion="ses_qv_fb",
        events=[sel_tee, ev_add_cart],
    )
    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page(initial_url="https://staging.mitienda.com/shop/collections")
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_item_link = AsyncMock()
    mock_cart_btn = AsyncMock()

    with (
        patch("app.agent.trace_executor.LocatorResolver.find_quick_view_for_item", return_value=None) as mock_qv,
        patch("app.agent.trace_executor.LocatorResolver.find_element_by_text", return_value=mock_item_link) as mock_txt,
        patch("app.agent.trace_executor.LocatorResolver.find_add_to_cart_button", return_value=mock_cart_btn),
        patch.object(ActionGuard, "inspect_locator", return_value=(True, "")),
        patch("app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight", return_value=(b"img", None)),
        patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False),
    ):
        executor = TraceExecutor(browser_manager=mock_browser_manager, page_settle_seconds=0.0)
        report = await executor.execute_trace(trace, sample_client_config)

    assert report.status == ExplorationStatus.COMPLETED
    mock_qv.assert_awaited_once()
    mock_txt.assert_awaited_once_with(mock_page, "Google Grey Organic NYC Tee")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_find_safe_link_to_route_mobile_menu_fallback_and_unsafe_close():
    """Verifica el fallback a menú mobile en _find_safe_link_to_route y cierre si ActionGuard lo bloquea."""
    executor = TraceExecutor(browser_manager=AsyncMock(), page_settle_seconds=0.0)
    mock_page = _create_mock_page()
    mock_menu_link = AsyncMock()

    # Caso 1: enlace seguro encontrado en menú mobile
    with (
        patch("app.agent.trace_executor.LocatorResolver.find_link_to_route", return_value=None),
        patch(
            "app.agent.trace_executor.LocatorResolver.find_link_in_mobile_menu",
            return_value=mock_menu_link,
        ) as mock_menu_find,
        patch.object(executor.action_guard, "inspect_locator", return_value=(True, "")),
    ):
        found, origin = await executor._find_safe_link_to_route(mock_page, "/shop/clearance")

    assert found is mock_menu_link
    assert origin == "mobile_menu"
    mock_menu_find.assert_awaited_once_with(mock_page, "/shop/clearance")

    # Caso 2: enlace encontrado en menú mobile pero bloqueado por ActionGuard -> cierra el menú
    with (
        patch("app.agent.trace_executor.LocatorResolver.find_link_to_route", return_value=None),
        patch("app.agent.trace_executor.LocatorResolver.find_link_in_mobile_menu", return_value=mock_menu_link),
        patch("app.agent.trace_executor.LocatorResolver.close_mobile_menu", new_callable=AsyncMock) as mock_close,
        patch.object(executor.action_guard, "inspect_locator", return_value=(False, "blocked_link")),
    ):
        blocked, blocked_origin = await executor._find_safe_link_to_route(mock_page, "/logout")

    assert blocked is None
    assert blocked_origin == "none"
    mock_close.assert_awaited_once_with(mock_page)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_records_context_notes_and_keeps_lookahead_off_mobile_menu(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica notas contextuales de cookies, diálogos y menú mobile sin abrir el menú en lookahead."""
    trace = SessionTrace(
        id_patron="pat_ctx",
        id_cliente="cli_ctx",
        id_sesion="ses_ctx",
        events=[
            TraceEvent(orden=1, nombre_evento="page_view", ruta="/"),
            TraceEvent(orden=2, nombre_evento="page_view", ruta="/shop/clearance"),
            TraceEvent(orden=3, nombre_evento="page_view", ruta="/shop/apparel/mens"),
        ],
    )

    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page(initial_url="about:blank")
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    async def _goto_side(url: str, wait_until: str = "domcontentloaded") -> None:
        del wait_until
        mock_page.url = url

    mock_page.goto = AsyncMock(side_effect=_goto_side)

    mock_menu_sale = AsyncMock()
    mock_menu_sale.inner_text = AsyncMock(return_value="Sale")
    mock_menu_mens = AsyncMock()
    mock_menu_mens.inner_text = AsyncMock(side_effect=RuntimeError("Detached"))

    async def _dismiss_side(page, timeout_ms=600, dismissed_descriptions=None):
        del page, timeout_ms
        if dismissed_descriptions is not None and len(report_calls) == 0:
            dismissed_descriptions.append("Cookies: Accept all")
            report_calls.append("cookies")
            return True
        return False

    report_calls: list[str] = []

    def _dialog_side(page, dialog_notes=None):
        del page
        if dialog_notes is not None:
            dialog_notes.append("Se cerró automáticamente un diálogo nativo del navegador (alert): 'Aviso'.")

    with (
        patch("app.agent.trace_executor.LocatorResolver.find_link_to_route", return_value=None),
        patch(
            "app.agent.trace_executor.LocatorResolver.find_link_in_mobile_menu",
            side_effect=[mock_menu_sale, mock_menu_mens],
        ) as mock_mobile_menu,
        patch.object(ActionGuard, "inspect_locator", return_value=(True, "")),
        patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", side_effect=_dismiss_side),
        patch("app.agent.trace_executor.ObstacleHandler.setup_dialog_dismissal", side_effect=_dialog_side),
        patch(
            "app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
            return_value=(b"img", None),
        ) as mock_highlight,
    ):
        executor = TraceExecutor(browser_manager=mock_browser_manager, page_settle_seconds=0.0)
        report = await executor.execute_trace(trace, sample_client_config)

    assert report.status == ExplorationStatus.COMPLETED
    # Solo 2 llamadas a menú mobile (navegación paso 2 y paso 3), nunca en lookahead
    assert mock_mobile_menu.await_count == 2
    assert all(call.kwargs["locator"] is None for call in mock_highlight.call_args_list)

    assert report.evidences[0].context_notes == [
        "Se cerró un obstáculo o pop-up emergente al cargar la vista (Cookies: Accept all).",
        "Se cerró automáticamente un diálogo nativo del navegador (alert): 'Aviso'.",
    ]
    assert report.evidences[1].context_notes == [
        "El usuario pudo haber accedido a esta página desde el menú hamburguesa mobile (enlace 'Sale')."
    ]
    assert report.evidences[2].context_notes == [
        "El usuario pudo haber accedido a esta página desde el menú hamburguesa mobile."
    ]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_execute_trace_resets_mouse_hover_after_clicks(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica que tras navegar o clickear se mueva el cursor a (0, 0) para cerrar menús :hover."""
    trace = SessionTrace(
        id_patron="pat_hover_reset",
        id_cliente="cli_hover_reset",
        id_sesion="ses_hover_reset",
        objetivo="add_to_cart",
        events=[
            TraceEvent(orden=1, nombre_evento="page_view", ruta="/"),
            TraceEvent(orden=2, nombre_evento="page_view", ruta="/shop/apparel"),
            TraceEvent(
                orden=3,
                nombre_evento="add_to_cart",
                ruta="/shop/apparel",
                click_detail="Add to Cart",
            ),
        ],
    )

    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page(initial_url="about:blank")
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    async def _goto_side(url: str, wait_until: str = "domcontentloaded") -> None:
        del wait_until
        mock_page.url = url

    mock_page.goto = AsyncMock(side_effect=_goto_side)

    mock_apparel_link = AsyncMock()
    mock_add_btn = AsyncMock()
    # Inyectar un fallo transitorio en mouse.move en el último llamado para validar tolerancia a errores
    mock_page.mouse.move = AsyncMock(side_effect=[None, None, RuntimeError("Mouse closed")])

    with (
        patch(
            "app.agent.trace_executor.LocatorResolver.find_link_to_route",
            side_effect=[mock_apparel_link, mock_apparel_link],
        ),
        patch(
            "app.agent.trace_executor.LocatorResolver.find_add_to_cart_button",
            return_value=mock_add_btn,
        ),
        patch.object(ActionGuard, "inspect_locator", return_value=(True, "")),
        patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False),
        patch(
            "app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
            return_value=(b"img", None),
        ),
    ):
        executor = TraceExecutor(browser_manager=mock_browser_manager, page_settle_seconds=0.0)
        report = await executor.execute_trace(trace, sample_client_config)

    assert report.status == ExplorationStatus.COMPLETED
    mock_apparel_link.click.assert_awaited_once()
    mock_add_btn.click.assert_awaited_once()
    assert mock_page.mouse.move.await_count == 3
    mock_page.mouse.move.assert_any_await(0, 0)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_desktop_menu_submenu_lookahead_and_context(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica notas contextuales de menú desktop/submenú y bbox sobre submenú en lookahead."""
    trace = SessionTrace(
        id_patron="pat_desktop_menu",
        id_cliente="cli_desktop_menu",
        id_sesion="ses_desktop_menu",
        objetivo="add_to_cart",
        events=[
            TraceEvent(orden=1, nombre_evento="page_view", ruta="/"),
            TraceEvent(orden=2, nombre_evento="page_view", ruta="/shop/apparel"),
            TraceEvent(orden=3, nombre_evento="page_view", ruta="/shop/apparel/womens"),
        ],
    )

    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page(initial_url="about:blank")
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    async def _goto_side(url: str, wait_until: str = "domcontentloaded") -> None:
        del wait_until
        mock_page.url = url

    mock_page.goto = AsyncMock(side_effect=_goto_side)

    mock_apparel = AsyncMock()
    mock_womens_sub = AsyncMock()

    async def _desktop_ctx_side(locator):
        if locator is mock_apparel:
            return True, "Apparel", ""
        if locator is mock_womens_sub:
            return True, "Women's", "Apparel"
        return False, "", ""

    with (
        patch(
            "app.agent.trace_executor.LocatorResolver.find_link_to_route",
            side_effect=[mock_apparel, mock_apparel, None, None],
        ),
        patch(
            "app.agent.trace_executor.LocatorResolver.find_link_in_desktop_submenu",
            side_effect=[mock_womens_sub, mock_womens_sub],
        ),
        patch(
            "app.agent.trace_executor.LocatorResolver.get_desktop_menu_context",
            side_effect=_desktop_ctx_side,
        ),
        patch.object(ActionGuard, "inspect_locator", return_value=(True, "")),
        patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False),
        patch(
            "app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
            return_value=(b"img", None),
        ) as mock_highlight,
    ):
        executor = TraceExecutor(browser_manager=mock_browser_manager, page_settle_seconds=0.0)
        report = await executor.execute_trace(trace, sample_client_config)

    assert report.status == ExplorationStatus.COMPLETED
    # Paso 1 destaca 'Apparel', paso 2 destaca submenú 'Women's', paso 3 sin lookahead
    highlighted = [call.kwargs["locator"] for call in mock_highlight.call_args_list]
    assert highlighted == [mock_apparel, mock_womens_sub, None]
    # Paso 2 debe haber limpiado hover tanto tras navegar como después de capturar el submenú en lookahead
    assert mock_page.mouse.move.await_count >= 4

    assert report.evidences[0].context_notes == []
    assert report.evidences[1].context_notes == [
        "El usuario pudo haber accedido a esta página desde el menú de navegación desktop (enlace 'Apparel')."
    ]
    assert report.evidences[2].context_notes == [
        "El usuario pudo haber accedido a esta página desde el submenú desplegable desktop de 'Apparel' "
        "(enlace 'Women's')."
    ]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_find_safe_link_to_route_resets_hover_when_desktop_submenu_blocked(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica que si ActionGuard bloquea un enlace en submenú desktop se limpie el hover."""
    del sample_client_config
    mock_page = _create_mock_page()
    mock_blocked_sub = AsyncMock()
    executor = TraceExecutor(browser_manager=AsyncMock(), page_settle_seconds=0.0)

    with (
        patch("app.agent.trace_executor.LocatorResolver.find_link_to_route", return_value=None),
        patch(
            "app.agent.trace_executor.LocatorResolver.find_link_in_desktop_submenu",
            return_value=mock_blocked_sub,
        ),
        patch.object(ActionGuard, "inspect_locator", return_value=(False, "Blocked")),
        patch("app.agent.trace_executor.LocatorResolver.reset_mouse_hover", new_callable=AsyncMock) as mock_reset,
    ):
        found, origin = await executor._find_safe_link_to_route(
            mock_page, "/checkout", allow_mobile_menu=False, allow_desktop_submenu=True
        )

    assert found is None
    assert origin == "none"
    mock_reset.assert_awaited_once_with(mock_page)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_records_context_notes_when_interaction_element_missing(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica notas contextuales neutrales cuando un ítem o botón interactivo no existe en el DOM actual."""
    trace = SessionTrace(
        id_patron="pat_missing_item",
        id_cliente="cli_missing_item",
        id_sesion="ses_missing_item",
        objetivo="begin_checkout",
        events=[
            TraceEvent(
                orden=1,
                nombre_evento="select_item",
                ruta="/shop/lifestyle/bags",
                items="Google Recycled Drawstring Bag",
            ),
            TraceEvent(
                orden=2,
                nombre_evento="add_to_cart",
                ruta="/shop/lifestyle/bags",
                items="Google Recycled Drawstring Bag",
            ),
            TraceEvent(
                orden=3,
                nombre_evento="view_cart",
                ruta="/shop/lifestyle/bags",
            ),
        ],
    )

    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page(initial_url="https://staging.mitienda.com/shop/lifestyle/bags")
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    with (
        patch("app.agent.trace_executor.LocatorResolver.find_element_by_text", return_value=None),
        patch("app.agent.trace_executor.LocatorResolver.find_add_to_cart_button", return_value=None),
        patch("app.agent.trace_executor.LocatorResolver.find_cart_button", return_value=None),
        patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False),
        patch(
            "app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
            return_value=(b"img", None),
        ),
    ):
        executor = TraceExecutor(browser_manager=mock_browser_manager, page_settle_seconds=0.0)
        report = await executor.execute_trace(trace, sample_client_config)

    assert report.status == ExplorationStatus.COMPLETED
    assert len(report.evidences) == 3
    assert (
        "No se localizó el ítem 'Google Recycled Drawstring Bag' en el DOM actual durante la reproducción"
        in report.evidences[0].context_notes[0]
    )
    assert (
        "No se encontró un botón visible de agregar al carrito para 'Google Recycled Drawstring Bag'"
        in report.evidences[1].context_notes[0]
    )
    assert (
        report.evidences[2].context_notes
        == ["No se localizó el elemento interactivo 'view_cart' en el DOM actual durante la reproducción."]
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_begin_checkout_scroll_disabled_and_state_summary(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica begin_checkout, búsqueda con scroll, control disabled y resumen de estado genérico."""
    trace = SessionTrace(
        id_patron="pat_enhancements",
        id_cliente="cli_enh",
        id_sesion="ses_enh",
        objetivo="purchase",
        events=[
            TraceEvent(
                orden=1,
                nombre_evento="select_item",
                ruta="/shop/apparel",
                items="Google Nara Hoodie",
            ),
            TraceEvent(
                orden=2,
                nombre_evento="add_to_cart",
                ruta="/product/google-nara-hoodie",
                items="Google Nara Hoodie",
            ),
            TraceEvent(
                orden=3,
                nombre_evento="begin_checkout",
                ruta="/checkout?show=basket",
                items="Google Nara Hoodie",
            ),
            TraceEvent(
                orden=4,
                nombre_evento="add_billing_info",
                ruta="/checkout?show=multibillto",
            ),
        ],
    )

    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page(initial_url="https://staging.mitienda.com/shop/apparel")
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_item_after_scroll = AsyncMock()
    mock_disabled_cart_btn = AsyncMock()

    with (
        patch("app.agent.trace_executor.LocatorResolver.find_quick_view_for_item", return_value=None),
        patch("app.agent.trace_executor.LocatorResolver.find_element_by_text", return_value=None) as mock_txt,
        patch(
            "app.agent.trace_executor.LocatorResolver.scroll_and_find_element_by_text",
            return_value=mock_item_after_scroll,
        ) as mock_scroll_find,
        patch(
            "app.agent.trace_executor.LocatorResolver.find_add_to_cart_button",
            return_value=mock_disabled_cart_btn,
        ),
        patch("app.agent.trace_executor.LocatorResolver.find_begin_checkout_button", return_value=None),
        patch("app.agent.trace_executor.LocatorResolver.find_checkout_or_continue_button", return_value=None),
        patch(
            "app.agent.trace_executor.LocatorResolver.is_locator_disabled",
            side_effect=[False, True],
        ),
        patch(
            "app.agent.trace_executor.LocatorResolver.extract_page_state_summary",
            side_effect=["Your cart is currently empty.", None],
        ),
        patch.object(ActionGuard, "inspect_locator", return_value=(True, "")),
        patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False),
        patch(
            "app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
            return_value=(b"img", None),
        ) as mock_capture,
    ):
        executor = TraceExecutor(browser_manager=mock_browser_manager, page_settle_seconds=0.0)
        report = await executor.execute_trace(trace, sample_client_config)

    assert report.status == ExplorationStatus.COMPLETED
    assert len(report.evidences) == 4
    # Paso 1: select_item encontró el ítem tras scrollear y lo clickeó
    mock_scroll_find.assert_awaited_once_with(mock_page, "Google Nara Hoodie")
    mock_item_after_scroll.click.assert_awaited_once()
    # Paso 2: add_to_cart encontró botón disabled -> capturó bbox con nota sin clickear
    assert "deshabilitado (disabled)" in report.evidences[1].context_notes[0]
    mock_disabled_cart_btn.click.assert_not_awaited()
    assert mock_capture.call_args_list[1].kwargs["locator"] is mock_disabled_cart_btn
    # Paso 3: begin_checkout no buscó event.items como texto y adjuntó resumen visible de pantalla
    mock_txt.assert_awaited_once_with(mock_page, "Google Nara Hoodie")
    assert (
        "No se localizó el elemento interactivo 'begin_checkout' en el DOM actual durante la reproducción."
        in report.evidences[2].context_notes[0]
    )
    assert "Estado visible en pantalla: «Your cart is currently empty.»" in report.evidences[2].context_notes[0]
    # Paso 4: sin estado resumido conserva nota base limpia
    assert report.evidences[3].context_notes == [
        "No se localizó el elemento interactivo 'add_billing_info' en el DOM actual durante la reproducción."
    ]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_wait_for_spinner_to_clear_and_missing_note_with_summary() -> None:
    """Verifica espera ante spinner activo y notas con state_summary en add_to_cart y select_item."""
    executor = TraceExecutor(browser_manager=AsyncMock(), page_settle_seconds=0.5)
    mock_page = _create_mock_page()
    spinner_loc = AsyncMock()
    spinner_loc.is_visible.side_effect = [True, False]
    wrapper = MagicMock()
    wrapper.first = spinner_loc
    mock_page.locator.return_value = wrapper

    with patch("app.agent.trace_executor.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await executor._wait_for_spinner_to_clear(mock_page, max_wait_seconds=1.0)
    mock_sleep.assert_awaited_once_with(0.25)

    ev_add = TraceEvent(orden=1, nombre_evento="add_to_cart", items="Hoodie")
    note_add = TraceExecutor._build_missing_interaction_note(ev_add, "Hoodie", state_summary="Sold out for now")
    assert "Estado visible en pantalla: «Sold out for now»." in note_add

    ev_sel = TraceEvent(orden=2, nombre_evento="select_item", items="Tee")
    note_sel = TraceExecutor._build_missing_interaction_note(ev_sel, "Tee", state_summary="Not available")
    assert "Estado visible en pantalla: «Not available»." in note_sel


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_add_to_cart_records_note_when_quantity_adjusted(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica que add_to_cart pre-seleccione cantidad 1 si estaba en 0 y registre la nota."""
    trace = SessionTrace(
        id_patron="pat_qty_zero",
        id_cliente="cli_qty",
        id_sesion="ses_qty",
        events=[
            TraceEvent(
                orden=1,
                nombre_evento="add_to_cart",
                ruta="/product/google-nara-hoodie",
                items="Google Nara Hoodie",
            ),
        ],
    )
    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page(initial_url="https://staging.mitienda.com/product/google-nara-hoodie")
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_atc = AsyncMock()
    with (
        patch("app.agent.trace_executor.LocatorResolver.find_add_to_cart_button", return_value=mock_atc),
        patch("app.agent.trace_executor.LocatorResolver.is_locator_disabled", return_value=False),
        patch(
            "app.agent.trace_executor.LocatorResolver.ensure_required_option_selected",
            return_value=("Choose Size", "SM"),
        ),
        patch("app.agent.trace_executor.LocatorResolver.ensure_positive_quantity_selected", return_value=True),
        patch.object(ActionGuard, "inspect_locator", return_value=(True, "")),
        patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False),
        patch("app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight", return_value=(b"img", None)),
    ):
        executor = TraceExecutor(browser_manager=mock_browser_manager, page_settle_seconds=0.0)
        report = await executor.execute_trace(trace, sample_client_config)

    assert report.status == ExplorationStatus.COMPLETED
    mock_atc.click.assert_awaited_once()
    assert (
        "El selector de variante/opción iniciaba sin selección ('Choose Size'); "
        "se seleccionó 'SM' antes de agregar al carrito."
        in report.evidences[0].context_notes
    )
    assert (
        "El selector de cantidad iniciaba en 0; se seleccionó 1 unidad antes de agregar al carrito."
        in report.evidences[0].context_notes
    )

    # También verifica re-resolución y espera de loader cuando page_settle_seconds > 0 tras elegir variante
    mock_atc_initial = AsyncMock()
    mock_atc_refreshed = AsyncMock()
    mock_page_settle = _create_mock_page(initial_url="https://staging.mitienda.com/product/google-nara-hoodie")
    mock_context.new_page = AsyncMock(return_value=mock_page_settle)
    with (
        patch(
            "app.agent.trace_executor.LocatorResolver.find_add_to_cart_button",
            side_effect=[mock_atc_initial, mock_atc_refreshed],
        ),
        patch("app.agent.trace_executor.LocatorResolver.is_locator_disabled", return_value=False),
        patch(
            "app.agent.trace_executor.LocatorResolver.ensure_required_option_selected",
            return_value=("Choose Size", "SM"),
        ),
        patch("app.agent.trace_executor.LocatorResolver.ensure_positive_quantity_selected", return_value=False),
        patch.object(ActionGuard, "inspect_locator", return_value=(True, "")),
        patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False),
        patch(
            "app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
            return_value=(b"img", None),
        ) as mock_cap,
        patch("app.agent.trace_executor.asyncio.sleep", new_callable=AsyncMock),
    ):
        executor_settle = TraceExecutor(browser_manager=mock_browser_manager, page_settle_seconds=0.5)
        await executor_settle.execute_trace(trace, sample_client_config)
    assert mock_cap.call_args.kwargs["locator"] is mock_atc_refreshed
    mock_atc_refreshed.click.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_blocking_overlay_diagnostic_on_missing_interaction(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica nota factual y context_type cuando un modal/drawer superpuesto bloquea la interacción."""
    trace = SessionTrace(
        id_patron="pat_overlay_block",
        id_cliente="cli_overlay",
        id_sesion="ses_overlay",
        events=[
            TraceEvent(
                orden=1,
                nombre_evento="add_billing_info",
                ruta="/checkout?show=multibillto",
            )
        ],
    )

    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page(initial_url="https://staging.mitienda.com/checkout?show=multibillto")
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    with (
        patch("app.agent.trace_executor.LocatorResolver.find_checkout_or_continue_button", return_value=None),
        patch(
            "app.agent.trace_executor.LocatorResolver.detect_blocking_overlay",
            return_value="Login — Click the button below to sign in with Google or create an account",
        ),
        patch(
            "app.agent.trace_executor.LocatorResolver.extract_page_state_summary",
            return_value="Should not be queried",
        ) as mock_summary,
        patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False),
        patch(
            "app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
            return_value=(b"img", None),
        ) as mock_cap,
    ):
        executor = TraceExecutor(browser_manager=mock_browser_manager, page_settle_seconds=0.0)
        report = await executor.execute_trace(trace, sample_client_config)

    assert report.status == ExplorationStatus.COMPLETED
    assert len(report.evidences) == 1
    mock_summary.assert_not_awaited()
    assert mock_cap.call_args.kwargs["context_type"] == "interaction_blocked_by_overlay"
    assert report.evidences[0].context_notes == [
        "La vista actual quedó bloqueada por un modal/panel superpuesto en primer plano "
        "(«Login — Click the button below to sign in with Google or create an account»), "
        "impidiendo localizar o interactuar con 'add_billing_info'."
    ]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_jit_auth_and_expired_session_and_cleanup(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica disparo JIT en barrera de login, nota ante sesión expirada y limpieza en finally."""
    sample_client_config.storage_state = {"cookies": [{"name": "sid", "value": "123"}], "origins": []}
    trace = SessionTrace(
        id_patron="pat_jit_checkout",
        id_cliente="cli_jit",
        id_sesion="ses_jit",
        events=[
            TraceEvent(orden=1, nombre_evento="add_billing_info", ruta="/checkout?show=multibillto"),
        ],
    )

    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page(initial_url="https://staging.mitienda.com/checkout?show=multibillto")
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_billing_btn = AsyncMock()
    # Caso A: bloqueado por login -> inyecta JIT -> aparece botón y lo clickea + limpia carrito en finally
    with (
        patch(
            "app.agent.trace_executor.LocatorResolver.find_checkout_or_continue_button",
            side_effect=[None, mock_billing_btn],
        ),
        patch(
            "app.agent.trace_executor.LocatorResolver.detect_blocking_overlay",
            return_value="Login — Sign in with Google",
        ),
        patch("app.agent.trace_executor.LocatorResolver.is_login_barrier", return_value=True),
        patch("app.agent.trace_executor.AuthHandler.inject_storage_state_jit", return_value=True) as mock_jit,
        patch("app.agent.trace_executor.LocatorResolver.is_locator_disabled", return_value=False),
        patch("app.agent.trace_executor.LocatorResolver.clear_cart_items", return_value=1) as mock_clear,
        patch.object(ActionGuard, "inspect_locator", return_value=(True, "")),
        patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False),
        patch(
            "app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
            return_value=(b"img", None),
        ),
    ):
        executor = TraceExecutor(browser_manager=mock_browser_manager, page_settle_seconds=0.0)
        report = await executor.execute_trace(trace, sample_client_config, allow_session_auth=True)

    assert report.status == ExplorationStatus.COMPLETED
    mock_jit.assert_awaited_once()
    mock_billing_btn.click.assert_awaited_once()
    mock_clear.assert_awaited_once()
    assert any("Se aplicó la sesión autenticada del cliente" in n for n in report.evidences[0].context_notes)

    # Caso B: tras aplicar JIT la pantalla sigue bloqueada por login -> nota de sesión expirada/rechazada
    with (
        patch("app.agent.trace_executor.LocatorResolver.find_checkout_or_continue_button", return_value=None),
        patch(
            "app.agent.trace_executor.LocatorResolver.detect_blocking_overlay",
            return_value="Login — Sign in with Google",
        ),
        patch("app.agent.trace_executor.LocatorResolver.is_login_barrier", return_value=True),
        patch("app.agent.trace_executor.AuthHandler.inject_storage_state_jit", return_value=True),
        patch("app.agent.trace_executor.LocatorResolver.clear_cart_items", return_value=0),
        patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False),
        patch(
            "app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
            return_value=(b"img", None),
        ),
    ):
        report_exp = await executor.execute_trace(trace, sample_client_config, allow_session_auth=True)

    assert "expiraron o fueron rechazadas por el sitio" in report_exp.evidences[0].context_notes[0]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_pre_cart_jit_and_already_authenticated_login_step(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica JIT previo a add_to_cart en Familia B y nota limpia en login posterior ya autenticado."""
    sample_client_config.storage_state = {"cookies": [{"name": "sid", "value": "123"}], "origins": []}
    trace = SessionTrace(
        id_patron="pat_fam_b",
        id_cliente="cli_fb",
        id_sesion="ses_fb",
        events=[
            TraceEvent(orden=1, nombre_evento="add_to_cart", ruta="/product/tshirt"),
            TraceEvent(orden=2, nombre_evento="login", ruta="/checkout?show=basket"),
        ],
    )

    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page(initial_url="https://staging.mitienda.com/product/tshirt")
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_atc_initial = AsyncMock()
    mock_atc_reloaded = AsyncMock()

    with (
        patch(
            "app.agent.trace_executor.LocatorResolver.find_add_to_cart_button",
            side_effect=[mock_atc_initial, mock_atc_reloaded],
        ),
        patch("app.agent.trace_executor.LocatorResolver.find_login_button", return_value=None),
        patch("app.agent.trace_executor.LocatorResolver.detect_blocking_overlay", return_value=None),
        patch("app.agent.trace_executor.AuthHandler.inject_storage_state_jit", return_value=True) as mock_jit,
        patch("app.agent.trace_executor.LocatorResolver.ensure_required_option_selected", return_value=None),
        patch("app.agent.trace_executor.LocatorResolver.ensure_positive_quantity_selected", return_value=False),
        patch("app.agent.trace_executor.LocatorResolver.is_locator_disabled", return_value=False),
        patch("app.agent.trace_executor.LocatorResolver.clear_cart_items", return_value=1) as mock_clear,
        patch.object(ActionGuard, "inspect_locator", return_value=(True, "")),
        patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False),
        patch(
            "app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
            return_value=(b"img", None),
        ) as mock_cap,
    ):
        executor = TraceExecutor(browser_manager=mock_browser_manager, page_settle_seconds=0.0)
        report = await executor.execute_trace(trace, sample_client_config, allow_session_auth=True)

    assert report.status == ExplorationStatus.COMPLETED
    mock_jit.assert_awaited_once()
    mock_atc_reloaded.click.assert_awaited_once()
    mock_clear.assert_awaited_once()
    assert any(
        "antes de agregar al carrito para preservar los ítems en el checkout" in n
        for n in report.evidences[0].context_notes
    )
    assert mock_cap.call_args_list[1].kwargs["context_type"] == "session_already_authenticated"
    assert any("ya se encontraba activa" in n for n in report.evidences[1].context_notes)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_cleanup_client_session_state_and_explicit_login_jit(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Cubre cleanup_client_session_state, JIT por credenciales tradicionales y Disparo A en `login`."""
    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page(initial_url="https://staging.mitienda.com/")
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    executor = TraceExecutor(browser_manager=mock_browser_manager, page_settle_seconds=0.0)

    # 1. Cliente sin auth -> cleanup_client_session_state sale sin crear contexto
    await executor.cleanup_client_session_state(sample_client_config)
    mock_browser_manager.create_context.assert_not_awaited()

    # 2. Cliente con credenciales tradicionales -> navega base_url, autentica (fallback login_url), limpia y cierra
    sample_client_config.requires_authentication = True
    sample_client_config.login_url = "/login"
    with (
        patch("app.agent.trace_executor.AuthHandler.authenticate", side_effect=[False, True]) as mock_auth,
        patch("app.agent.trace_executor.LocatorResolver.clear_cart_items", return_value=2) as mock_clear,
        patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False),
    ):
        await executor.cleanup_client_session_state(sample_client_config)

    assert mock_auth.await_count == 2
    mock_clear.assert_awaited_once()
    mock_page.close.assert_called_once()
    mock_context.close.assert_awaited_once()

    # 3. Disparo A en evento `login` (caso A: botón login encontrado; caso B: formulario sin botón)
    trace_login = SessionTrace(
        id_patron="pat_login_explicit",
        id_cliente="cli_le",
        id_sesion="ses_le",
        events=[TraceEvent(orden=1, nombre_evento="login", ruta="/")],
    )
    mock_login_btn = AsyncMock()
    with (
        patch("app.agent.trace_executor.LocatorResolver.find_login_button", return_value=mock_login_btn),
        patch("app.agent.trace_executor.AuthHandler.authenticate", return_value=False),
        patch.object(ActionGuard, "inspect_locator", return_value=(True, "")),
        patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False),
        patch(
            "app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
            return_value=(b"img", None),
        ) as mock_cap_btn,
    ):
        report_a = await executor.execute_trace(trace_login, sample_client_config)
    assert report_a.status == ExplorationStatus.COMPLETED
    mock_login_btn.click.assert_not_awaited()
    assert mock_cap_btn.call_args.kwargs["context_type"] == "interaction_click"

    with (
        patch("app.agent.trace_executor.LocatorResolver.find_login_button", return_value=None),
        patch("app.agent.trace_executor.AuthHandler.authenticate", return_value=True),
        patch("app.agent.trace_executor.LocatorResolver.clear_cart_items", return_value=0),
        patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False),
        patch(
            "app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
            return_value=(b"img", None),
        ) as mock_cap_form,
    ):
        report_b = await executor.execute_trace(trace_login, sample_client_config)
    assert report_b.status == ExplorationStatus.COMPLETED
    assert mock_cap_form.call_args.kwargs["context_type"] == "login_form_detected"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_begin_checkout_inside_active_checkout_omits_missing_note(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica que begin_checkout sin botón Checkout pero con Continue activo no registre nota de faltante."""
    trace = SessionTrace(
        id_patron="pat_checkout_active",
        id_cliente="cli_ca",
        id_sesion="ses_ca",
        events=[
            TraceEvent(orden=1, nombre_evento="begin_checkout", ruta="/checkout?show=multibillto"),
        ],
    )

    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page(initial_url="https://staging.mitienda.com/checkout?show=multibillto")
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    with (
        patch("app.agent.trace_executor.LocatorResolver.find_begin_checkout_button", return_value=None),
        patch("app.agent.trace_executor.LocatorResolver.detect_blocking_overlay", return_value=None),
        patch(
            "app.agent.trace_executor.LocatorResolver.find_checkout_or_continue_button",
            return_value=AsyncMock(),
        ),
        patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False),
        patch(
            "app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
            return_value=(b"img", None),
        ) as mock_cap,
    ):
        executor = TraceExecutor(browser_manager=mock_browser_manager, page_settle_seconds=0.0)
        report = await executor.execute_trace(trace, sample_client_config)

    assert report.status == ExplorationStatus.COMPLETED
    assert len(report.evidences) == 1
    assert mock_cap.call_args.kwargs["context_type"] == "checkout_stage_active"
    assert report.evidences[0].context_notes == []


@pytest.mark.asyncio
@pytest.mark.unit
async def test_trace_executor_preserves_pdp_when_select_item_navigates_away_from_catalog(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Si select_item abre el PDP y add_to_cart conserva ruta de catálogo, no debe retroceder."""
    trace = SessionTrace(
        id_patron="pat_pdp_preserve",
        id_cliente="cli_pdp",
        id_sesion="ses_pdp",
        events=[
            TraceEvent(orden=1, nombre_evento="select_item", ruta="/shop/new", items="Google Mug"),
            TraceEvent(orden=2, nombre_evento="add_to_cart", ruta="/shop/new", items="Google Mug"),
        ],
    )

    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    mock_page = _create_mock_page(initial_url="https://staging.mitienda.com/shop/new")
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_item_link = AsyncMock()

    async def _nav_to_pdp(*_args: object, **_kwargs: object) -> None:
        mock_page.url = "https://staging.mitienda.com/product/google-mug"

    mock_item_link.click = AsyncMock(side_effect=_nav_to_pdp)
    mock_atc_btn = AsyncMock()

    with (
        patch("app.agent.trace_executor.LocatorResolver.find_quick_view_for_item", return_value=None),
        patch("app.agent.trace_executor.LocatorResolver.find_element_by_text", return_value=mock_item_link),
        patch("app.agent.trace_executor.LocatorResolver.find_add_to_cart_button", return_value=mock_atc_btn),
        patch.object(ActionGuard, "inspect_locator", return_value=(True, "")),
        patch("app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight", return_value=(b"img", None)),
        patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False),
    ):
        executor = TraceExecutor(browser_manager=mock_browser_manager, page_settle_seconds=0.0)
        report = await executor.execute_trace(trace, sample_client_config)

    assert report.status == ExplorationStatus.COMPLETED
    assert mock_page.url == "https://staging.mitienda.com/product/google-mug"
    # El sitio ya estaba en /shop/new; add_to_cart no retrocedió desde el PDP al catálogo
    mock_page.goto.assert_not_awaited()
    mock_atc_btn.click.assert_awaited_once()

    # Verificar también ramas negativas de _should_skip_stale_route_sync
    ev_add = TraceEvent(orden=2, nombre_evento="add_to_cart", ruta="/shop/new")
    assert await executor._should_skip_stale_route_sync(mock_page, ev_add, None) is False
    ev_no_route = TraceEvent(orden=2, nombre_evento="add_to_cart", ruta="")
    assert await executor._should_skip_stale_route_sync(mock_page, ev_no_route, trace.events[0]) is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_wait_after_interaction_click_and_occluded_cart_drawer(
    sample_client_config: ClientInterfaceConfig,
) -> None:
    """Verifica espera post-clic de mutaciones/navegaciones y captura limpia ante drawer de carrito abierto."""
    executor = TraceExecutor(browser_manager=AsyncMock(), page_settle_seconds=1.0)
    mock_page = _create_mock_page()
    mock_page.wait_for_load_state = AsyncMock(side_effect=[Exception("net busy"), Exception("dom busy")])

    with (
        patch("app.agent.trace_executor.asyncio.sleep", new_callable=AsyncMock),
        patch.object(executor, "_wait_for_spinner_to_clear", new_callable=AsyncMock) as mock_wait_spin,
    ):
        await executor._wait_after_interaction_click(mock_page, "add_to_cart")
        await executor._wait_after_interaction_click(mock_page, "select_item")
    mock_wait_spin.assert_awaited_once_with(mock_page, max_wait_seconds=2.5)

    # view_cart cuando el ícono de Basket en header quedó tapado por un drawer ya abierto
    trace = SessionTrace(
        id_patron="pat_cart_drawer",
        id_cliente="cli_cd",
        id_sesion="ses_cd",
        events=[TraceEvent(orden=1, nombre_evento="view_cart", ruta="/shop")],
    )
    mock_browser_manager = AsyncMock()
    mock_context = AsyncMock()
    drawer_page = _create_mock_page(initial_url="https://staging.mitienda.com/shop")
    mock_browser_manager.create_context.return_value = mock_context
    mock_context.new_page = AsyncMock(return_value=drawer_page)
    mock_cart_link = AsyncMock()

    with (
        patch("app.agent.trace_executor.LocatorResolver.find_cart_button", return_value=mock_cart_link),
        patch.object(ActionGuard, "inspect_locator", return_value=(True, "")),
        patch("app.agent.trace_executor.VisualHighlighter.is_locator_unoccluded", return_value=False),
        patch(
            "app.agent.trace_executor.VisualHighlighter.capture_element_with_highlight",
            return_value=(b"img", None),
        ) as mock_cap,
        patch("app.agent.trace_executor.ObstacleHandler.dismiss_obstacles", return_value=False),
    ):
        ex_drawer = TraceExecutor(browser_manager=mock_browser_manager, page_settle_seconds=0.0)
        rep_drawer = await ex_drawer.execute_trace(trace, sample_client_config)

    assert rep_drawer.status == ExplorationStatus.COMPLETED
    mock_cart_link.click.assert_not_awaited()
    assert mock_cap.call_args.kwargs["context_type"] == "cart_drawer_active"
