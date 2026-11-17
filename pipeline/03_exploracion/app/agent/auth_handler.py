"""Módulo para autenticación automatizada (credenciales AES e inyección JIT de sesión)."""

import asyncio
import inspect
import json
import logging
from typing import Any, Dict, Optional, Sequence
from playwright.async_api import BrowserContext, Locator, Page
from app.agent.url_resolver import UrlResolver
from app.config import get_settings
from app.models.client_config import ClientInterfaceConfig
from app.security.encryption import decrypt_text

logger = logging.getLogger(__name__)

# Heurísticas de selectores para campos de usuario/email
USERNAME_SELECTORS = [
    'input[type="email"]',
    'input[name*="email" i]',
    'input[name*="user" i]',
    'input[id*="email" i]',
    'input[id*="user" i]',
    'input[placeholder*="usuario" i]',
    'input[placeholder*="correo" i]',
    'input[placeholder*="email" i]',
    'input[placeholder*="username" i]',
]

# Heurísticas de selectores para campos de contraseña
PASSWORD_SELECTORS = [
    'input[type="password"]',
    'input[name*="pass" i]',
    'input[id*="pass" i]',
    'input[placeholder*="contrase" i]',
    'input[placeholder*="pass" i]',
]

# Botones intermedios en flujos de login en 2 pasos (email -> siguiente -> password)
NEXT_STEP_SELECTORS = [
    'button:has-text("Siguiente")',
    'button:has-text("Continuar")',
    'button:has-text("Next")',
    'button:has-text("Continue")',
    'input[type="button"][value*="Next" i]',
    'input[type="button"][value*="Continue" i]',
]

# Heurísticas de selectores para botones de envío de login
SUBMIT_SELECTORS = [
    'button[type="submit"]',
    'input[type="submit"]',
    'button:has-text("Iniciar sesión")',
    'button:has-text("Ingresar")',
    'button:has-text("Iniciar")',
    'button:has-text("Log in")',
    'button:has-text("Sign in")',
    'button:has-text("Entrar")',
]

ERROR_ALERT_SELECTORS = [
    '[role="alert"]',
    '.error',
    '[class*="error" i]',
]


class AuthHandler:
    """
    Gestiona la autenticación del agente mediante inyección JIT o credenciales seguras.

    Soporta inyección Just-In-Time de `storage_state` (cookies y localStorage) y
    autenticación tradicional de 1 o 2 pasos con contraseña cifrada AES-256-GCM.
    """

    @classmethod
    async def _find_first_visible_element(
        cls,
        page: Page,
        selectors: Sequence[str],
        timeout_ms: int,
    ) -> Optional[Locator]:
        """Localiza el primer elemento visible entre múltiples selectores y coincidencias."""
        per_check = max(150, timeout_ms)
        for selector in selectors:
            try:
                group = page.locator(selector)
                count = None
                try:
                    count_res = group.count()
                    if inspect.isawaitable(count_res):
                        count = await count_res
                except Exception:
                    count = None

                if isinstance(count, int) and count > 0:
                    for idx in range(min(count, 6)):
                        candidate = group.nth(idx)
                        visible = await candidate.is_visible(timeout=per_check)
                        if isinstance(visible, bool) and visible:
                            return candidate
                else:
                    first_loc = group.first
                    visible = await first_loc.is_visible(timeout=per_check)
                    if isinstance(visible, bool) and visible:
                        return first_loc
            except Exception:
                continue
        return None

    @classmethod
    async def inject_storage_state_jit(
        cls,
        context: BrowserContext,
        page: Page,
        storage_state: Dict[str, Any],
    ) -> bool:
        """Inyecta cookies y localStorage de `storage_state` en una sesión activa y recarga."""
        try:
            cookies = storage_state.get("cookies") or []
            if isinstance(cookies, list) and cookies:
                await context.add_cookies(cookies)

            origins = storage_state.get("origins") or []
            if isinstance(origins, list):
                for entry in origins:
                    if not isinstance(entry, dict):
                        continue
                    origin = entry.get("origin")
                    items = entry.get("localStorage") or []
                    if not isinstance(origin, str) or not origin or not isinstance(items, list) or not items:
                        continue
                    pairs = [
                        (str(item["name"]), str(item["value"]))
                        for item in items
                        if isinstance(item, dict) and "name" in item and "value" in item
                    ]
                    if not pairs:
                        continue
                    pairs_json = json.dumps(pairs)
                    origin_json = json.dumps(origin)
                    await context.add_init_script(
                        f"if (window.location.origin === {origin_json}) {{"
                        f"  for (const [k, v] of {pairs_json}) {{ window.localStorage.setItem(k, v); }}"
                        f"}}"
                    )
                    try:
                        await page.evaluate(
                            """([targetOrigin, entries]) => {
                                if (window.location.origin === targetOrigin) {
                                    for (const [k, v] of entries) {
                                        window.localStorage.setItem(k, v);
                                    }
                                }
                            }""",
                            [origin, pairs],
                        )
                    except Exception:
                        pass

            current_url = getattr(page, "url", "") or ""
            if current_url and current_url != "about:blank":
                await page.reload(wait_until="domcontentloaded")
            logger.info("[AuthHandler] Estado de sesión (storage_state) inyectado en modo JIT.")
            return True
        except Exception as exc:
            logger.warning(f"[AuthHandler] Error al inyectar storage_state en modo JIT: {exc}")
            return False

    @classmethod
    async def authenticate(
        cls,
        page: Page,
        client_config: ClientInterfaceConfig,
        encryption_key: Optional[str] = None,
        timeout_ms: int = 4000,
        navigate_to_login_url: bool = True,
    ) -> bool:
        """
        Ejecuta el inicio de sesión si el cliente requiere autenticación.

        Detecta formularios ya abiertos en la vista/modal actual antes de navegar a `login_url`,
        soporta flujos en 1 o 2 pasos y verifica si hubo rechazo explícito tras enviar.
        """
        if not client_config.requires_authentication:
            logger.info("[AuthHandler] El cliente no requiere autenticación previa.")
            return True

        if not client_config.test_username or not client_config.test_password_encrypted:
            logger.warning("[AuthHandler] Requiere autenticación pero faltan credenciales configuradas.")
            return False

        key = encryption_key or get_settings().AES_ENCRYPTION_KEY
        try:
            password = decrypt_text(client_config.test_password_encrypted, key)
        except Exception as exc:
            logger.error(f"[AuthHandler] Error al descifrar la contraseña con AES: {exc}")
            return False

        current_url = getattr(page, "url", "") or ""
        on_login_url = bool(
            client_config.login_url
            and isinstance(current_url, str)
            and client_config.login_url.strip("/") in current_url
        )

        if navigate_to_login_url and client_config.login_url and not on_login_url:
            resolved_login_url = UrlResolver.resolve_url(client_config.base_url, client_config.login_url)
            logger.info(f"[AuthHandler] Navegando a la pantalla de login: {resolved_login_url}")
            try:
                await page.goto(resolved_login_url, wait_until="domcontentloaded", timeout=timeout_ms * 2)
            except Exception as exc:
                logger.warning(f"[AuthHandler] Error al navegar a login_url: {exc}")

        user_loc = await cls._find_first_visible_element(page, USERNAME_SELECTORS, timeout_ms=timeout_ms // 2)

        if user_loc is None:
            logger.warning("[AuthHandler] No se pudo localizar el campo de usuario o email.")
            return False

        await user_loc.fill(client_config.test_username)

        # 2. Localizar contraseña (si no está visible aún, intentar paso intermedio de 2 pasos)
        pass_loc = await cls._find_first_visible_element(page, PASSWORD_SELECTORS, timeout_ms=timeout_ms // 2)
        if pass_loc is None:
            next_btn = await cls._find_first_visible_element(
                page, NEXT_STEP_SELECTORS + SUBMIT_SELECTORS, timeout_ms=timeout_ms // 3
            )
            if next_btn is not None:
                try:
                    await next_btn.click()
                except Exception:
                    pass
            else:
                try:
                    await page.keyboard.press("Enter")
                except Exception:
                    pass
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
            except Exception:
                pass
            await asyncio.sleep(0.4)
            pass_loc = await cls._find_first_visible_element(page, PASSWORD_SELECTORS, timeout_ms=timeout_ms // 2)

        if pass_loc is None:
            logger.warning("[AuthHandler] No se pudo localizar el campo de contraseña.")
            return False

        await pass_loc.fill(password)

        # 3. Localizar y clickear botón de submit
        btn_loc = await cls._find_first_visible_element(page, SUBMIT_SELECTORS, timeout_ms=timeout_ms // 2)
        if btn_loc is not None:
            await btn_loc.click()
        else:
            try:
                await page.keyboard.press("Enter")
            except Exception as exc:
                logger.error(f"[AuthHandler] Error al enviar formulario con Enter: {exc}")
                return False

        # Esperar estabilización posterior al login y validar que no haya error explícito
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
            await asyncio.sleep(0.5)
        except Exception:
            pass

        still_on_password = False
        try:
            vis = await pass_loc.is_visible(timeout=300)
            still_on_password = isinstance(vis, bool) and vis
        except Exception:
            still_on_password = False

        if still_on_password:
            err_loc = await cls._find_first_visible_element(page, ERROR_ALERT_SELECTORS, timeout_ms=300)
            if err_loc is not None:
                try:
                    raw_err = await err_loc.inner_text()
                    err_text = raw_err.strip() if isinstance(raw_err, str) else ""
                except Exception:
                    err_text = ""
                if err_text:
                    logger.warning(f"[AuthHandler] El sitio rechazó el inicio de sesión: '{err_text[:120]}'")
                    return False

        logger.info("[AuthHandler] Formulario de autenticación completado y enviado exitosamente.")
        return True
