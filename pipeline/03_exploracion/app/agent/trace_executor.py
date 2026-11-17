"""Ejecutor principal de trazas de sesión con navegación híbrida, salvaguardas y captura visual."""

import asyncio
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import inspect
import logging
import os
import re
from typing import Any, Callable, Coroutine, List, Optional, Sequence, Tuple
from playwright.async_api import BrowserContext, Page
from app.agent.auth_handler import AuthHandler
from app.agent.locator_resolver import LocatorResolver
from app.agent.url_resolver import UrlResolver
from app.browser.browser_manager import BrowserManager
from app.browser.obstacle_handler import ObstacleHandler
from app.browser.visual_highlighter import VisualHighlighter
from app.models.client_config import ClientInterfaceConfig
from app.models.exploration_report import ExplorationReport, ExplorationStatus, VisualEvidence
from app.models.session_trace import EventType, SessionTrace, TraceEvent
from app.safety.action_guard import ActionGuard
from app.safety.network_guard import NetworkGuard
from app.storage.base import StorageUploadError

logger = logging.getLogger(__name__)

# Tipo para función opcional de persistencia de capturas
EvidenceSaver = Callable[[bytes, str, int], Coroutine[Any, Any, str]]


@dataclass
class _TraceSessionState:
    """Estado mutable de autenticación JIT durante la ejecución de una traza."""

    allow_session_auth: bool = True
    prefer_pre_cart_auth: bool = False
    session_attempted: bool = False
    session_active: bool = False
    auth_rejected_or_expired: bool = False


class TraceExecutor:
    """
    Ejecutor autónomo de trazas de navegación anómalas.

    Reproduce de extremo a extremo la secuencia de interacción del usuario mediante Playwright:
    1. Aplica salvaguardas preventivas de red (NetworkGuard) y de acciones destructivas (ActionGuard).
    2. Utiliza navegación híbrida (Link Traversal preferente sobre direct goto).
    3. Descarta obstáculos de UI (cookies/modales) de manera desatendida.
    4. Captura evidencia visual de cada estado con recuadros semánticos para el LLM multimodal.
    5. Propaga el campo contextual `scroll` sin ejecutar desplazamiento en el navegador.
    """

    def __init__(
        self,
        browser_manager: Optional[BrowserManager] = None,
        action_guard: Optional[ActionGuard] = None,
        network_guard: Optional[NetworkGuard] = None,
        evidence_saver: Optional[EvidenceSaver] = None,
        page_settle_seconds: Optional[float] = None,
    ) -> None:
        """
        Inicializa el ejecutor de trazas.

        :param browser_manager: Gestor de navegador existente; crea uno nuevo si es None.
        :param action_guard: Guardia de acciones; inicializa uno por defecto si es None.
        :param network_guard: Guardia de red; inicializa uno por defecto si es None.
        :param evidence_saver: Corrutina para persistir imágenes (bytes, filename, step) -> url.
        :param page_settle_seconds: Tiempo en segundos de espera adaptativa antes de capturar página.
        """
        self.browser_manager = browser_manager or BrowserManager()
        self.action_guard = action_guard or ActionGuard()
        self.network_guard = network_guard or NetworkGuard()
        self.evidence_saver = evidence_saver
        if page_settle_seconds is not None:
            self.page_settle_seconds = float(page_settle_seconds)
        else:
            try:
                self.page_settle_seconds = float(os.getenv("PAGE_SETTLE_SECONDS", "5.0"))
            except ValueError:
                self.page_settle_seconds = 5.0

    async def execute_trace(
        self,
        trace: SessionTrace,
        client_config: ClientInterfaceConfig,
        allow_session_auth: bool = True,
    ) -> ExplorationReport:
        """
        Ejecuta la reproducción completa de la sesión y genera el reporte de exploración.

        :param trace: Secuencia de eventos de la sesión representativa del patrón.
        :param client_config: Parámetros del cliente y entorno de navegación.
        :param allow_session_auth: Permite autenticación JIT si la traza requiere sesión.
        :return: ExplorationReport consolidado con estado, evidencias y errores.
        """
        start_iso = datetime.now(timezone.utc).isoformat()
        logger.info(
            f"[TraceExecutor] Iniciando exploración para id_patron='{trace.id_patron}' "
            f"(id_sesion='{trace.id_sesion}')..."
        )

        evidences: List[VisualEvidence] = []
        completed_steps = 0
        total_steps = len(trace.events)
        status = ExplorationStatus.COMPLETED
        error_msg: Optional[str] = None

        context: Optional[BrowserContext] = None
        page: Optional[Page] = None
        session_state = _TraceSessionState(
            allow_session_auth=allow_session_auth,
            prefer_pre_cart_auth=trace.prefers_pre_cart_auth_jit(),
        )

        try:
            # 1. Crear contexto siempre anónimo en paso 0 (autenticación JIT en pasos posteriores)
            context = await self.browser_manager.create_context(
                device_info=trace.device_info,
                custom_headers=client_config.custom_headers,
                storage_state=None,
            )
            await self.network_guard.attach_to_context(context)

            # 2. Inicializar página y manejador de diálogos
            page = await context.new_page()
            dialog_notes: List[str] = []
            ObstacleHandler.setup_dialog_dismissal(page, dialog_notes=dialog_notes)

            # 3. Iterar sobre eventos ordenados por `orden` recorriendo todos los pasos
            sorted_events = sorted(trace.events, key=lambda e: e.orden)
            prev_opened_quick_view = False

            for idx, event in enumerate(sorted_events):
                prev_event = sorted_events[idx - 1] if idx > 0 else None
                next_event = sorted_events[idx + 1] if idx + 1 < len(sorted_events) else None
                after_next_event = sorted_events[idx + 2] if idx + 2 < len(sorted_events) else None
                try:
                    prev_opened_quick_view = await self._execute_step(
                        page=page,
                        event=event,
                        trace=trace,
                        client_config=client_config,
                        evidences=evidences,
                        prev_event=prev_event,
                        next_event=next_event,
                        after_next_event=after_next_event,
                        preserve_active_modal=prev_opened_quick_view,
                        dialog_notes=dialog_notes,
                        context=context,
                        session_state=session_state,
                    )
                    completed_steps += 1
                except StorageUploadError:
                    raise
                except Exception as step_exc:
                    error_msg = f"Error en paso {event.orden} ({event.nombre_evento}): {step_exc}"
                    logger.warning(
                        f"[TraceExecutor] {error_msg}",
                        extra={"id_patron": trace.id_patron, "paso": event.orden},
                    )
                    # Registrar captura de falla si la página sigue abierta
                    try:
                        await self._capture_evidence(
                            page=page,
                            event=event,
                            trace=trace,
                            reason=f"error_step_{event.orden}",
                            evidences=evidences,
                            dialog_notes=dialog_notes,
                        )
                    except StorageUploadError:
                        raise
                    except Exception:
                        pass
                    break

            if completed_steps == 0 and total_steps > 0:
                status = ExplorationStatus.FAILED
            elif completed_steps < total_steps:
                status = ExplorationStatus.PARTIAL
            else:
                status = ExplorationStatus.COMPLETED

        except StorageUploadError:
            raise
        except Exception as fatal_exc:
            error_msg = f"Excepción fatal durante la exploración: {fatal_exc}"
            logger.critical(
                f"[TraceExecutor] {error_msg}",
                extra={"id_patron": trace.id_patron},
            )
            status = ExplorationStatus.FAILED

        finally:
            if session_state.session_active and page is not None:
                try:
                    removed = await LocatorResolver.clear_cart_items(
                        page=page,
                        base_url=client_config.base_url,
                        action_guard=self.action_guard,
                    )
                    logger.info(
                        f"[TraceExecutor] Limpieza post-patrón completada (ítems removidos={removed}).",
                        extra={"id_patron": trace.id_patron},
                    )
                except Exception as clean_exc:
                    logger.debug(f"[TraceExecutor] Error no crítico en limpieza post-patrón: {clean_exc}")

            if page is not None:
                try:
                    close_res = page.close()
                    if inspect.isawaitable(close_res):
                        await close_res
                except Exception as page_close_exc:
                    logger.debug(f"[TraceExecutor] Error menor al cerrar página: {page_close_exc}")

            if context is not None:
                try:
                    close_ctx_res = context.close()
                    if inspect.isawaitable(close_ctx_res):
                        await close_ctx_res
                except Exception as close_exc:
                    logger.debug(f"[TraceExecutor] Error menor al cerrar contexto: {close_exc}")

        finish_iso = datetime.now(timezone.utc).isoformat()

        report = ExplorationReport(
            id_patron=trace.id_patron,
            id_cliente=trace.id_cliente,
            id_sesion=trace.id_sesion,
            fecha_exploracion=trace.fecha_exploracion or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            status=status,
            total_steps=total_steps,
            completed_steps=completed_steps,
            started_at=start_iso,
            finished_at=finish_iso,
            objetivo=trace.objetivo,
            secuencia=trace.secuencia,
            sesiones=trace.sesiones,
            usuarios=trace.usuarios,
            llegada_grupo=trace.llegada_grupo,
            llegada_referencia=trace.llegada_referencia,
            sesiones_perdidas=trace.sesiones_perdidas,
            id_modelo=trace.id_modelo,
            primera_deteccion=trace.primera_deteccion,
            ultima_deteccion=trace.ultima_deteccion,
            device_info=trace.device_info,
            evidences=evidences,
            error_message=error_msg,
        )

        logger.info(
            f"[TraceExecutor] Exploración finalizada: status={status.value}, "
            f"pasos={completed_steps}/{total_steps}",
            extra={"id_patron": trace.id_patron, "capturas_generadas": len(evidences)},
        )
        return report

    _SPINNER_SELECTORS: Tuple[str, ...] = (
        "[role='progressbar']",
        "[aria-busy='true']",
        ".spinner",
        ".loader",
        "[class*='spinner' i]",
        "[class*='loading' i][class*='overlay' i]",
        "[class*='loading-overlay' i]",
        "[data-testid='overlay'][class*='loading' i]",
    )

    async def _wait_for_spinner_to_clear(
        self,
        page: Page,
        max_wait_seconds: float = 1.5,
        extra_selectors: Sequence[str] = (),
    ) -> None:
        """Espera brevemente si hay un indicador de carga visible antes de capturar evidencia."""
        if self.page_settle_seconds <= 0:
            return
        selectors = tuple(self._SPINNER_SELECTORS) + tuple(extra_selectors)
        attempts = max(1, int(max_wait_seconds / 0.25))
        for _ in range(attempts):
            spinner_active = False
            for selector in selectors:
                try:
                    visible = await page.locator(selector).first.is_visible(timeout=200)
                    if isinstance(visible, bool) and visible:
                        spinner_active = True
                        break
                except Exception:
                    continue
            if not spinner_active:
                return
            await asyncio.sleep(0.25)

    _ASYNC_MUTATION_INTERACTIONS = frozenset({
        "add_to_cart",
        "begin_checkout",
        "add_shipping_info",
        "add_billing_info",
        "add_payment_info",
    })

    async def _wait_after_interaction_click(self, page: Page, event_name: str) -> None:
        """Espera estabilización tras un clic, aguardando red y spinners en mutaciones/navegaciones."""
        if self.page_settle_seconds <= 0:
            await asyncio.sleep(0.1)
            return

        if event_name in self._ASYNC_MUTATION_INTERACTIONS:
            try:
                await page.wait_for_load_state("networkidle", timeout=1500)
            except Exception:
                pass
            await asyncio.sleep(min(self.page_settle_seconds, 1.0))
            await self._wait_for_spinner_to_clear(page, max_wait_seconds=2.5)
            return

        if event_name == "select_item":
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=1500)
            except Exception:
                pass

        await asyncio.sleep(min(self.page_settle_seconds, 1.0))

    async def _wait_for_page_settle(self, page: Page, target_path: str, log_settle: bool = False) -> None:
        """Espera estabilización de red, tiempo configurado y desaparición de loaders activos."""
        try:
            await page.wait_for_load_state("networkidle", timeout=2000)
        except Exception:
            pass

        if self.page_settle_seconds > 0:
            if log_settle:
                logger.info(
                    f"[TraceExecutor] Esperando {self.page_settle_seconds:.1f}s para estabilización "
                    f"y carga dinámica de la página ({target_path})..."
                )
            await asyncio.sleep(self.page_settle_seconds)
            await self._wait_for_spinner_to_clear(page)
        elif not log_settle:
            await asyncio.sleep(0.1)

    async def _navigate_for_event_route(
        self,
        page: Page,
        ruta: str,
        client_config: ClientInterfaceConfig,
    ) -> None:
        """Navega a la ruta del evento si la página aún está en blanco o en otra ruta."""
        if not ruta:
            return

        current_url = page.url or "about:blank"
        target_path = UrlResolver.extract_route_path(ruta)
        needs_navigation = current_url == "about:blank" or (
            UrlResolver.extract_route_path(current_url) != target_path
        )
        if not needs_navigation:
            return

        init_url = UrlResolver.resolve_url(client_config.base_url, ruta)
        logger.info(f"[TraceExecutor] Sincronizando ruta del paso: {init_url}")
        await page.goto(init_url, wait_until="domcontentloaded")
        await self._wait_for_page_settle(page, target_path, log_settle=False)

    @staticmethod
    def _append_dismissed_obstacle_notes(
        dismissed_descriptions: List[str],
        step_notes: List[str],
    ) -> None:
        """Convierte descripciones de obstáculos cerrados en notas contextuales legibles."""
        for desc in dismissed_descriptions:
            step_notes.append(f"Se cerró un obstáculo o pop-up emergente al cargar la vista ({desc}).")

    @staticmethod
    def _has_client_auth_config(client_config: Optional[ClientInterfaceConfig]) -> bool:
        """Indica si el cliente posee configuración de sesión (storage_state o credenciales)."""
        if client_config is None:
            return False
        return client_config.resolve_storage_state() is not None or bool(client_config.requires_authentication)

    async def _try_jit_authentication(
        self,
        page: Page,
        context: Optional[BrowserContext],
        client_config: ClientInterfaceConfig,
        session_state: _TraceSessionState,
        target_route: Optional[str] = None,
    ) -> bool:
        """Aplica autenticación Just-In-Time (storage_state o formulario tradicional)."""
        session_state.session_attempted = True
        storage_state = client_config.resolve_storage_state()
        auth_ok = False

        if storage_state is not None:
            active_ctx = context or getattr(page, "context", None)
            if active_ctx is not None:
                auth_ok = await AuthHandler.inject_storage_state_jit(active_ctx, page, storage_state)
        elif client_config.requires_authentication:
            auth_ok = await AuthHandler.authenticate(page, client_config, navigate_to_login_url=False)
            if not auth_ok and client_config.login_url:
                auth_ok = await AuthHandler.authenticate(page, client_config, navigate_to_login_url=True)

        if auth_ok:
            session_state.session_active = True
            if target_route:
                await self._navigate_for_event_route(page, target_route, client_config)
            route_path = UrlResolver.extract_route_path(target_route or getattr(page, "url", "") or "/")
            await self._wait_for_page_settle(page, route_path, log_settle=False)
            await ObstacleHandler.dismiss_obstacles(page)
        else:
            session_state.auth_rejected_or_expired = True
            logger.warning("[TraceExecutor] La autenticación JIT no pudo completarse o fue rechazada.")
        return auth_ok

    async def cleanup_client_session_state(self, client_config: ClientInterfaceConfig) -> None:
        """Pre-limpieza defensiva del carrito en un contexto aislado para evitar residuos de corridas previas."""
        if not self._has_client_auth_config(client_config):
            return

        context: Optional[BrowserContext] = None
        page: Optional[Page] = None
        session_state = _TraceSessionState(allow_session_auth=True)
        try:
            context = await self.browser_manager.create_context(
                custom_headers=client_config.custom_headers,
                storage_state=None,
            )
            await self.network_guard.attach_to_context(context)
            page = await context.new_page()
            await page.goto(client_config.base_url, wait_until="domcontentloaded")
            auth_ok = await self._try_jit_authentication(
                page=page,
                context=context,
                client_config=client_config,
                session_state=session_state,
                target_route=client_config.base_url,
            )
            if auth_ok:
                removed = await LocatorResolver.clear_cart_items(
                    page=page,
                    base_url=client_config.base_url,
                    action_guard=self.action_guard,
                )
                logger.info(f"[TraceExecutor] Pre-limpieza defensiva completada (ítems removidos={removed}).")
        except Exception as exc:
            logger.debug(f"[TraceExecutor] Error no crítico en pre-limpieza defensiva: {exc}")
        finally:
            if page is not None:
                try:
                    close_res = page.close()
                    if inspect.isawaitable(close_res):
                        await close_res
                except Exception:
                    pass
            if context is not None:
                try:
                    close_ctx_res = context.close()
                    if inspect.isawaitable(close_ctx_res):
                        await close_ctx_res
                except Exception:
                    pass

    async def _should_skip_stale_route_sync(
        self,
        page: Page,
        event: TraceEvent,
        prev_event: Optional[TraceEvent],
    ) -> bool:
        """Evita retroceder al catálogo si `select_item` navegó a una ficha con botón `add_to_cart` activo."""
        if event.nombre_evento.strip().lower() != "add_to_cart":
            return False
        if prev_event is None or prev_event.nombre_evento.strip().lower() != "select_item":
            return False
        if not event.ruta or not prev_event.ruta:
            return False

        target_path = UrlResolver.extract_route_path(event.ruta)
        prev_path = UrlResolver.extract_route_path(prev_event.ruta)
        current_path = UrlResolver.extract_route_path(page.url or "")
        if not target_path or target_path != prev_path or current_path == target_path:
            return False

        return await LocatorResolver.find_add_to_cart_button(page, timeout_ms=800) is not None

    async def _execute_step(
        self,
        page: Page,
        event: TraceEvent,
        trace: SessionTrace,
        client_config: ClientInterfaceConfig,
        evidences: List[VisualEvidence],
        prev_event: Optional[TraceEvent] = None,
        next_event: Optional[TraceEvent] = None,
        after_next_event: Optional[TraceEvent] = None,
        preserve_active_modal: bool = False,
        dialog_notes: Optional[List[str]] = None,
        context: Optional[BrowserContext] = None,
        session_state: Optional[_TraceSessionState] = None,
    ) -> bool:
        """Ejecuta un evento particular de la traza según su tipo operativo.

        Retorna True si el paso dejó un modal de Quick View abierto para el paso siguiente.
        """
        step_notes: List[str] = []

        if event.event_type != EventType.PAGE_VIEW and event.ruta:
            if not await self._should_skip_stale_route_sync(page, event, prev_event):
                await self._navigate_for_event_route(page, event.ruta, client_config)

        # Descartar obstáculos antes de la acción (salvo si el paso previo abrió Quick View para interactuar)
        if not (preserve_active_modal and event.event_type == EventType.INTERACTION):
            pre_dismissed: List[str] = []
            await ObstacleHandler.dismiss_obstacles(page, dismissed_descriptions=pre_dismissed)
            self._append_dismissed_obstacle_notes(pre_dismissed, step_notes)

        if event.event_type == EventType.PAGE_VIEW:
            await self._handle_page_view(
                page=page,
                event=event,
                trace=trace,
                client_config=client_config,
                evidences=evidences,
                next_event=next_event,
                after_next_event=after_next_event,
                step_notes=step_notes,
                dialog_notes=dialog_notes,
            )
            return False
        if event.event_type == EventType.INTERACTION:
            return await self._handle_interaction(
                page=page,
                event=event,
                trace=trace,
                evidences=evidences,
                next_event=next_event,
                step_notes=step_notes,
                dialog_notes=dialog_notes,
                client_config=client_config,
                context=context,
                session_state=session_state,
            )
        await self._capture_evidence(
            page=page,
            event=event,
            trace=trace,
            reason="event_other",
            evidences=evidences,
            context_notes=step_notes,
            dialog_notes=dialog_notes,
        )
        return False

    async def _find_safe_link_to_route(
        self,
        page: Page,
        route_path: str,
        allow_mobile_menu: bool = True,
        allow_desktop_submenu: bool = True,
    ) -> Tuple[Any, str]:
        """Busca un enlace visible y seguro hacia `route_path`, incluyendo menú desktop y mobile."""
        link_loc = await LocatorResolver.find_link_to_route(page, route_path)
        origin = "none"
        if link_loc is not None:
            in_desktop_menu, _, _ = await LocatorResolver.get_desktop_menu_context(link_loc)
            origin = "desktop_menu" if in_desktop_menu else "direct"
        elif allow_desktop_submenu:
            link_loc = await LocatorResolver.find_link_in_desktop_submenu(page, route_path)
            if link_loc is not None:
                origin = "desktop_submenu"

        if link_loc is None and allow_mobile_menu:
            link_loc = await LocatorResolver.find_link_in_mobile_menu(page, route_path)
            if link_loc is not None:
                origin = "mobile_menu"
        if not link_loc:
            return None, "none"
        is_safe, _ = await self.action_guard.inspect_locator(link_loc)
        if not is_safe:
            if origin == "mobile_menu":
                await LocatorResolver.close_mobile_menu(page)
            elif origin == "desktop_submenu":
                await LocatorResolver.reset_mouse_hover(page)
            return None, "none"
        return link_loc, origin

    @staticmethod
    async def _read_navigation_labels(link_loc: Any, link_origin: str) -> Tuple[str, str]:
        """Extrae la etiqueta del enlace y del padre antes de navegar fuera del DOM actual."""
        if link_origin == "mobile_menu":
            try:
                return (await link_loc.inner_text(timeout=500) or "").strip(), ""
            except Exception:
                return "", ""
        if link_origin in ("desktop_menu", "desktop_submenu"):
            _, link_label, parent_label = await LocatorResolver.get_desktop_menu_context(link_loc)
            if not link_label:
                try:
                    link_label = (await link_loc.inner_text(timeout=500) or "").strip()
                except Exception:
                    link_label = ""
            return link_label, parent_label
        return "", ""

    @staticmethod
    def _append_navigation_origin_note(
        link_origin: str,
        link_label: str,
        parent_label: str,
        notes: List[str],
    ) -> None:
        """Agrega nota contextual cuando la navegación partió desde un menú desktop o mobile."""
        if link_origin == "mobile_menu":
            suffix = f" (enlace '{link_label}')" if link_label else ""
            notes.append(f"El usuario pudo haber accedido a esta página desde el menú hamburguesa mobile{suffix}.")
        elif link_origin == "desktop_menu":
            suffix = f" (enlace '{link_label}')" if link_label else ""
            notes.append(f"El usuario pudo haber accedido a esta página desde el menú de navegación desktop{suffix}.")
        elif link_origin == "desktop_submenu":
            parent_suffix = f" de '{parent_label}'" if parent_label else ""
            link_suffix = f" (enlace '{link_label}')" if link_label else ""
            notes.append(
                f"El usuario pudo haber accedido a esta página desde el submenú desplegable desktop"
                f"{parent_suffix}{link_suffix}."
            )

    async def _handle_page_view(
        self,
        page: Page,
        event: TraceEvent,
        trace: SessionTrace,
        client_config: ClientInterfaceConfig,
        evidences: List[VisualEvidence],
        next_event: Optional[TraceEvent] = None,
        after_next_event: Optional[TraceEvent] = None,
        step_notes: Optional[List[str]] = None,
        dialog_notes: Optional[List[str]] = None,
    ) -> None:
        """Maneja la navegación a una página combinando Link Traversal con fallback a URL directa."""
        target_url = UrlResolver.resolve_url(client_config.base_url, event.ruta)
        target_path = UrlResolver.extract_route_path(event.ruta)
        collected_notes = list(step_notes or [])

        # 1. Estrategia Link Traversal: si ya estamos en un documento y existe enlace al destino
        navigated_via_link = False
        if page.url and page.url != "about:blank":
            link_loc, link_origin = await self._find_safe_link_to_route(
                page, target_path, allow_mobile_menu=True, allow_desktop_submenu=True
            )
            if link_loc:
                link_label, parent_label = await self._read_navigation_labels(link_loc, link_origin)

                logger.info(f"[TraceExecutor] Navegando vía Link Traversal hacia '{target_path}'")
                try:
                    await link_loc.click(timeout=3000)
                    await page.wait_for_load_state("domcontentloaded", timeout=5000)
                    navigated_via_link = True
                    self._append_navigation_origin_note(link_origin, link_label, parent_label, collected_notes)
                except Exception as exc:
                    logger.warning(f"[TraceExecutor] Falló Link Traversal, recurriendo a navegación directa: {exc}")

        # 2. Fallback: navegación directa por URL
        if not navigated_via_link:
            logger.info(f"[TraceExecutor] Navegando directamente a: {target_url}")
            await page.goto(target_url, wait_until="domcontentloaded")

        # Mover el cursor fuera de barras/menús de navegación para evitar :hover pegados en capturas
        await self._clear_pointer_hover(page)

        # 3. Estabilización adaptativa (red inactiva con timeout breve + buffer de renderizado)
        await self._wait_for_page_settle(page, target_path, log_settle=True)

        # Descartar banners que surjan al cargar la nueva página
        post_dismissed: List[str] = []
        await ObstacleHandler.dismiss_obstacles(page, dismissed_descriptions=post_dismissed)
        self._append_dismissed_obstacle_notes(post_dismissed, collected_notes)

        # 4. Captura visual única del paso actual (sin abrir menú hamburguesa para no tapar la pantalla)
        next_highlight_loc = None
        next_highlight_origin = "none"
        context_type = "page_view_loaded"

        if next_event is not None:
            if next_event.event_type == EventType.PAGE_VIEW and next_event.ruta:
                next_path = UrlResolver.extract_route_path(next_event.ruta)
                if next_path != target_path:
                    next_highlight_loc, next_highlight_origin = await self._find_safe_link_to_route(
                        page,
                        next_path,
                        allow_mobile_menu=False,
                        allow_desktop_submenu=True,
                    )
                    if next_highlight_loc is not None:
                        context_type = "link_traversal_click"
            elif self._should_prefer_quick_view(next_event, after_next_event) and next_event.items:
                next_item_path = UrlResolver.extract_route_path(next_event.ruta or target_path)
                if next_item_path == target_path:
                    qv_loc = await LocatorResolver.find_quick_view_for_item(page, next_event.items.strip())
                    if qv_loc is not None:
                        is_safe, _ = await self.action_guard.inspect_locator(qv_loc)
                        if is_safe:
                            next_highlight_loc = qv_loc
                            context_type = "quick_view_click"

        try:
            await self._capture_evidence(
                page=page,
                event=event,
                trace=trace,
                reason=context_type,
                locator=next_highlight_loc,
                evidences=evidences,
                context_notes=collected_notes,
                dialog_notes=dialog_notes,
            )
        finally:
            if next_highlight_origin == "desktop_submenu":
                await self._clear_pointer_hover(page)

    @staticmethod
    def _should_prefer_quick_view(
        event: TraceEvent,
        next_event: Optional[TraceEvent],
    ) -> bool:
        """Determina si un `select_item` probablemente abrió Quick View sin navegar a la ficha del ítem."""
        if event.nombre_evento.strip().lower() != "select_item":
            return False
        item_name = (event.items or "").strip()
        if not item_name or next_event is None:
            return False

        if next_event.event_type != EventType.PAGE_VIEW:
            return True

        current_path = UrlResolver.extract_route_path(event.ruta or "")
        next_path = UrlResolver.extract_route_path(next_event.ruta or "")
        if not next_path or next_path == current_path:
            return True

        tokens = [tok for tok in re.findall(r"[a-z0-9]+", item_name.lower()) if len(tok) >= 3]
        if len(tokens) < 2:
            return False

        next_lower = next_path.lower()
        matched_tokens = sum(1 for tok in tokens if tok in next_lower)
        return (matched_tokens / len(tokens)) < 0.5

    _FLOW_CONTROL_INTERACTIONS = frozenset({
        "add_to_cart",
        "begin_checkout",
        "view_cart",
        "view_login",
        "login",
        "add_shipping_info",
        "add_billing_info",
        "add_payment_info",
    })

    async def _resolve_interaction_locator(
        self,
        page: Page,
        event: TraceEvent,
        next_event: Optional[TraceEvent] = None,
    ) -> Tuple[Any, bool]:
        """Resuelve el localizador objetivo e indica si corresponde a un botón de Quick View."""
        nombre = event.nombre_evento.strip().lower()
        if nombre == "add_to_cart":
            loc = await LocatorResolver.find_add_to_cart_button(page)
            if loc is not None:
                return loc, False
        elif nombre == "begin_checkout":
            loc = await LocatorResolver.find_begin_checkout_button(page)
            if loc is not None:
                return loc, False
        elif nombre in ("add_shipping_info", "add_billing_info", "add_payment_info"):
            loc = await LocatorResolver.find_checkout_or_continue_button(page)
            if loc is not None:
                return loc, False
        elif nombre == "view_cart":
            loc = await LocatorResolver.find_cart_button(page)
            if loc is not None:
                return loc, False
        elif nombre in ("view_login", "login"):
            loc = await LocatorResolver.find_login_button(page)
            if loc is not None:
                return loc, False

        # En eventos de flujo (ej. begin_checkout/add_to_cart), `items` es metadato de producto,
        # no el texto del botón objetivo salvo que exista `click_detail` explícito.
        if nombre in self._FLOW_CONTROL_INTERACTIONS and not event.click_detail:
            return None, False

        if self._should_prefer_quick_view(event, next_event) and event.items:
            qv_loc = await LocatorResolver.find_quick_view_for_item(page, event.items.strip())
            if qv_loc is not None:
                return qv_loc, True

        click_target = event.click_detail
        if not click_target and event.items and event.items.strip():
            click_target = event.items.strip()
        if not click_target:
            click_target = event.nombre_evento

        loc = await LocatorResolver.find_element_by_text(page, click_target)
        if loc is None and (nombre == "select_item" or event.scroll or (event.items and event.items.strip())):
            loc = await LocatorResolver.scroll_and_find_element_by_text(page, click_target)
        return loc, False

    async def _handle_interaction(
        self,
        page: Page,
        event: TraceEvent,
        trace: SessionTrace,
        evidences: List[VisualEvidence],
        next_event: Optional[TraceEvent] = None,
        step_notes: Optional[List[str]] = None,
        dialog_notes: Optional[List[str]] = None,
        client_config: Optional[ClientInterfaceConfig] = None,
        context: Optional[BrowserContext] = None,
        session_state: Optional[_TraceSessionState] = None,
    ) -> bool:
        """Maneja clics interactivos o búsquedas. Retorna True si dejó Quick View abierto."""
        # Caso A: búsqueda de texto
        if event.search_term:
            search_input = await LocatorResolver.find_search_input(page)
            if search_input:
                logger.info(f"[TraceExecutor] Ingresando término de búsqueda: '{event.search_term}'")
                await search_input.fill(event.search_term)
                await page.keyboard.press("Enter")
                submit_settle = min(self.page_settle_seconds, 1.0) if self.page_settle_seconds > 0 else 0.0
                await asyncio.sleep(submit_settle if submit_settle > 0 else 0.1)
                await self._capture_evidence(
                    page=page,
                    event=event,
                    trace=trace,
                    reason="search_submitted",
                    evidences=evidences,
                    context_notes=step_notes,
                    dialog_notes=dialog_notes,
                )
                return False

            logger.info(f"[TraceExecutor] Campo de búsqueda para '{event.search_term}' no localizado en DOM.")
            await self._capture_evidence(
                page=page,
                event=event,
                trace=trace,
                reason="search_input_not_found",
                evidences=evidences,
                context_notes=step_notes,
                dialog_notes=dialog_notes,
            )
            return False

        # Caso B: resolución del elemento interactivo
        nombre = event.nombre_evento.strip().lower()
        if nombre in self._FLOW_CONTROL_INTERACTIONS:
            click_target = event.click_detail or event.nombre_evento
        else:
            click_target = (
                event.click_detail
                or (event.items.strip() if event.items and event.items.strip() else None)
                or event.nombre_evento
            )
        element_loc, is_quick_view = await self._resolve_interaction_locator(
            page, event, next_event=next_event
        )
        active_notes = list(step_notes or [])
        blocking_overlay: Optional[str] = None
        is_login_wall = False
        can_try_jit = bool(
            session_state is not None
            and session_state.allow_session_auth
            and not session_state.session_attempted
            and client_config is not None
            and self._has_client_auth_config(client_config)
        )

        if (
            nombre == "add_to_cart"
            and can_try_jit
            and client_config is not None
            and session_state is not None
            and session_state.prefer_pre_cart_auth
        ):
            jit_ok = await self._try_jit_authentication(
                page=page,
                context=context,
                client_config=client_config,
                session_state=session_state,
                target_route=event.ruta,
            )
            can_try_jit = False
            if jit_ok:
                refreshed_loc, refreshed_qv = await self._resolve_interaction_locator(
                    page, event, next_event=next_event
                )
                if refreshed_loc is not None:
                    element_loc = refreshed_loc
                    is_quick_view = refreshed_qv
                active_notes.append(
                    "Se aplicó la sesión autenticada del cliente antes de agregar al carrito "
                    "para preservar los ítems en el checkout."
                )

        if (
            element_loc is None
            and nombre == "login"
            and can_try_jit
            and client_config is not None
            and session_state is not None
        ):
            await self._capture_evidence(
                page=page,
                event=event,
                trace=trace,
                reason="login_form_detected",
                locator=None,
                evidences=evidences,
                context_notes=active_notes,
                dialog_notes=dialog_notes,
            )
            await self._try_jit_authentication(
                page=page,
                context=context,
                client_config=client_config,
                session_state=session_state,
                target_route=event.ruta,
            )
            return False

        if element_loc is None:
            blocking_overlay = await LocatorResolver.detect_blocking_overlay(page)
            if can_try_jit and client_config is not None and session_state is not None:
                is_login_wall = await LocatorResolver.is_login_barrier(page, blocking_overlay)
                if is_login_wall:
                    jit_ok = await self._try_jit_authentication(
                        page=page,
                        context=context,
                        client_config=client_config,
                        session_state=session_state,
                        target_route=event.ruta,
                    )
                    if jit_ok:
                        element_loc, is_quick_view = await self._resolve_interaction_locator(
                            page, event, next_event=next_event
                        )
                        if element_loc is not None:
                            active_notes.append(
                                "Se aplicó la sesión autenticada del cliente al detectarse "
                                "solicitud de login en este paso."
                            )
                        else:
                            blocking_overlay = await LocatorResolver.detect_blocking_overlay(page)
                            is_login_wall = await LocatorResolver.is_login_barrier(page, blocking_overlay)
                            if is_login_wall:
                                session_state.auth_rejected_or_expired = True

        if element_loc:
            is_safe, block_reason = await self.action_guard.inspect_locator(element_loc)
            if not is_safe:
                logger.warning(f"[TraceExecutor] Clic omitido por guardia de seguridad: {block_reason}")
                return False

            if nombre == "view_cart" and not await VisualHighlighter.is_locator_unoccluded(element_loc):
                await self._capture_evidence(
                    page=page,
                    event=event,
                    trace=trace,
                    reason="cart_drawer_active",
                    locator=None,
                    evidences=evidences,
                    context_notes=active_notes,
                    dialog_notes=dialog_notes,
                )
                return False

            if is_quick_view:
                opened = False
                try:
                    await element_loc.click(timeout=3000)
                    try:
                        await page.wait_for_load_state("networkidle", timeout=2000)
                    except Exception:
                        pass
                    qv_settle = min(self.page_settle_seconds, 2.0) if self.page_settle_seconds > 0 else 0.0
                    await asyncio.sleep(qv_settle if qv_settle > 0 else 0.1)
                    opened = True
                except Exception as exc:
                    logger.warning(f"[TraceExecutor] Error al abrir Quick View para '{click_target}': {exc}")

                await self._capture_evidence(
                    page=page,
                    event=event,
                    trace=trace,
                    reason="quick_view_opened",
                    locator=None,
                    evidences=evidences,
                    context_notes=active_notes,
                    dialog_notes=dialog_notes,
                )
                return opened

            if await LocatorResolver.is_locator_disabled(element_loc):
                logger.info(f"[TraceExecutor] Control interactivo '{click_target}' deshabilitado en DOM.")
                disabled_notes = list(active_notes)
                disabled_notes.append(
                    f"El control interactivo '{click_target}' figura visible en la vista actual pero "
                    "deshabilitado (disabled), por lo que requiere completar requisitos previos o no está "
                    "disponible para avanzar."
                )
                await self._capture_evidence(
                    page=page,
                    event=event,
                    trace=trace,
                    reason="interaction_disabled",
                    locator=element_loc,
                    evidences=evidences,
                    context_notes=disabled_notes,
                    dialog_notes=dialog_notes,
                )
                return False

            interaction_notes = list(active_notes)
            if nombre == "add_to_cart":
                selected_opt = await LocatorResolver.ensure_required_option_selected(page)
                if selected_opt:
                    placeholder_label, chosen_label = selected_opt
                    interaction_notes.append(
                        f"El selector de variante/opción iniciaba sin selección ('{placeholder_label}'); "
                        f"se seleccionó '{chosen_label}' antes de agregar al carrito."
                    )
                    if self.page_settle_seconds > 0:
                        await asyncio.sleep(0.35)
                        await self._wait_for_spinner_to_clear(
                            page,
                            max_wait_seconds=2.0,
                            extra_selectors=(":text-is('Loading')", ":text-is('Cargando')"),
                        )
                    refreshed_loc, _ = await self._resolve_interaction_locator(
                        page, event, next_event=next_event
                    )
                    if refreshed_loc is not None:
                        element_loc = refreshed_loc
                if await LocatorResolver.ensure_positive_quantity_selected(page):
                    interaction_notes.append(
                        "El selector de cantidad iniciaba en 0; se seleccionó 1 unidad antes de agregar al carrito."
                    )

            await self._capture_evidence(
                page=page,
                event=event,
                trace=trace,
                reason="interaction_click",
                locator=element_loc,
                evidences=evidences,
                context_notes=interaction_notes,
                dialog_notes=dialog_notes,
            )

            if (
                nombre == "login"
                and can_try_jit
                and client_config is not None
                and session_state is not None
            ):
                await self._try_jit_authentication(
                    page=page,
                    context=context,
                    client_config=client_config,
                    session_state=session_state,
                    target_route=event.ruta,
                )
                return False

            try:
                await element_loc.click(timeout=3000)
                await self._clear_pointer_hover(page)
                await self._wait_after_interaction_click(page, nombre)
            except Exception as exc:
                logger.warning(f"[TraceExecutor] Error al clickear '{click_target}': {exc}")
            return False

        logger.info(f"[TraceExecutor] Elemento interactivo '{click_target}' no localizado en DOM.")
        if nombre == "begin_checkout" and not blocking_overlay:
            progress_btn = await LocatorResolver.find_checkout_or_continue_button(page, timeout_ms=400)
            if progress_btn is not None:
                await self._capture_evidence(
                    page=page,
                    event=event,
                    trace=trace,
                    reason="checkout_stage_active",
                    evidences=evidences,
                    context_notes=active_notes,
                    dialog_notes=dialog_notes,
                )
                return False

        if (
            nombre in ("view_login", "login")
            and session_state is not None
            and session_state.session_active
            and not blocking_overlay
        ):
            already_notes = list(active_notes)
            already_notes.append(
                "La sesión autenticada del cliente ya se encontraba activa en este flujo para preservar "
                "el carrito, por lo que la opción de inicio de sesión ya no figura en pantalla."
            )
            await self._capture_evidence(
                page=page,
                event=event,
                trace=trace,
                reason="session_already_authenticated",
                evidences=evidences,
                context_notes=already_notes,
                dialog_notes=dialog_notes,
            )
            return False

        if blocking_overlay and not is_login_wall and session_state is not None and session_state.session_attempted:
            is_login_wall = await LocatorResolver.is_login_barrier(page, blocking_overlay)
        auth_expired = bool(session_state is not None and session_state.session_attempted and is_login_wall)
        state_summary = None if blocking_overlay else await LocatorResolver.extract_page_state_summary(page)
        missing_notes = list(active_notes)
        missing_notes.append(
            self._build_missing_interaction_note(
                event,
                click_target,
                state_summary=state_summary,
                blocking_overlay=blocking_overlay,
                auth_expired=auth_expired,
            )
        )
        await self._capture_evidence(
            page=page,
            event=event,
            trace=trace,
            reason="interaction_blocked_by_overlay" if blocking_overlay else "interaction_element_not_found",
            evidences=evidences,
            context_notes=missing_notes,
            dialog_notes=dialog_notes,
        )
        return False

    @classmethod
    def _build_missing_interaction_note(
        cls,
        event: TraceEvent,
        click_target: str,
        state_summary: Optional[str] = None,
        blocking_overlay: Optional[str] = None,
        auth_expired: bool = False,
    ) -> str:
        """Genera una nota contextual factual cuando un elemento interactivo no aparece o está bloqueado."""
        if blocking_overlay:
            if auth_expired:
                return (
                    f"Se aplicó la sesión autenticada configurada para el cliente, pero la vista continuó "
                    f"bloqueada por el requerimiento de inicio de sesión («{blocking_overlay}»), impidiendo "
                    f"interactuar con '{click_target}'. Esto indica que la sesión guardada o las credenciales "
                    "de prueba expiraron o fueron rechazadas por el sitio."
                )
            return (
                f"La vista actual quedó bloqueada por un modal/panel superpuesto en primer plano "
                f"(«{blocking_overlay}»), impidiendo localizar o interactuar con '{click_target}'."
            )
        nombre = event.nombre_evento.strip().lower()
        item_name = (event.items or "").strip()
        summary_suffix = f" Estado visible en pantalla: «{state_summary}»." if state_summary else ""
        if nombre == "add_to_cart":
            item_suffix = f" para '{item_name}'" if item_name else ""
            if state_summary:
                return (
                    f"No se encontró un botón visible de agregar al carrito{item_suffix} en la vista actual."
                    f"{summary_suffix}"
                )
            return (
                f"No se encontró un botón visible de agregar al carrito{item_suffix} en la vista actual "
                "(posiblemente porque el producto previo no pudo abrirse o no está disponible actualmente)."
            )
        if nombre not in cls._FLOW_CONTROL_INTERACTIONS and (
            nombre == "select_item" or (item_name and click_target == item_name)
        ):
            return (
                f"No se localizó el ítem '{click_target}' en el DOM actual durante la reproducción "
                "(posible cambio de catálogo/nombre respecto a la traza histórica o ubicación fuera de la vista cargada)."  # noqa: E501
                f"{summary_suffix}"
            )
        return (
            f"No se localizó el elemento interactivo '{click_target}' en el DOM actual durante la reproducción."
            f"{summary_suffix}"
        )

    @staticmethod
    async def _clear_pointer_hover(page: Page) -> None:
        """Mueve el cursor fuera de elementos interactivos para cerrar menús activados por :hover."""
        await LocatorResolver.reset_mouse_hover(page)

    async def _capture_evidence(
        self,
        page: Page,
        event: TraceEvent,
        trace: SessionTrace,
        reason: str,
        evidences: List[VisualEvidence],
        locator: Any = None,
        context_notes: Optional[List[str]] = None,
        dialog_notes: Optional[List[str]] = None,
    ) -> None:
        """Captura y persiste la evidencia visual en formato WebP con su contexto semántico."""
        now_iso = datetime.now(timezone.utc).isoformat()
        current_route = page.url or event.ruta or "/"

        raw_notes: List[str] = list(context_notes or [])
        if dialog_notes:
            raw_notes.extend(dialog_notes)
            dialog_notes.clear()
        deduped_notes = list(dict.fromkeys(note for note in raw_notes if note))

        screenshot_bytes, bbox_ctx = await VisualHighlighter.capture_element_with_highlight(
            page=page,
            locator=locator,
            context_type=reason,
        )

        target_date = trace.fecha_exploracion or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filename = f"capturas/{trace.id_cliente}/{target_date}/{trace.id_patron}_{event.orden}.webp"

        if self.evidence_saver:
            try:
                screenshot_url = await self.evidence_saver(screenshot_bytes, filename, event.orden)
            except StorageUploadError:
                raise
            except Exception as upload_exc:
                raise StorageUploadError(
                    f"Error al persistir evidencia '{filename}' en almacenamiento: {upload_exc}"
                ) from upload_exc
        else:
            b64_str = base64.b64encode(screenshot_bytes).decode("utf-8")
            screenshot_url = f"data:image/webp;base64,{b64_str[:60]}...[len:{len(screenshot_bytes)}]"

        evidence = VisualEvidence(
            orden=event.orden,
            nombre_evento=event.nombre_evento,
            ruta=current_route,
            items=event.items,
            scroll=event.scroll,
            en_patron=event.en_patron,
            es_paso_friccion=event.es_paso_friccion,
            screenshot_url=screenshot_url,
            timestamp=now_iso,
            bounding_box_context=bbox_ctx,
            context_notes=deduped_notes,
        )
        evidences.append(evidence)
