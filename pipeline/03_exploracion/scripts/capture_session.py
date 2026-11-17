#!/usr/bin/env python3
"""Utilidad interactiva para capturar una sesión autenticada (ej. Google OAuth) y guardarla cifrada en Supabase."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

from playwright.async_api import Browser, Playwright, async_playwright

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings  # noqa: E402
from app.logging_config import configure_logging  # noqa: E402
from app.security.encryption import decrypt_json, encrypt_json  # noqa: E402
from app.services.supabase_service import SupabaseService  # noqa: E402

logger = logging.getLogger("capture_session")


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Procesa los argumentos CLI para captura interactiva de `storage_state`."""
    parser = argparse.ArgumentParser(
        prog="capture_session",
        description=(
            "Abre el navegador en modo visible para iniciar sesión manualmente (Google/OAuth/SSO), "
            "captura `storage_state`, lo cifra con AES-256-GCM y lo almacena en Supabase."
        ),
    )
    parser.add_argument(
        "--client-id",
        "-c",
        default="00000000-0000-0000-0000-000000000001",
        help="ID del cliente en `clientes_integracion_fuente`.",
    )
    parser.add_argument(
        "--url",
        "-u",
        default=None,
        help="URL inicial opcional; por defecto usa `base_url` del cliente en Supabase.",
    )
    parser.add_argument(
        "--channel",
        default="chrome",
        help="Canal de navegador a intentar primero ('chrome', 'msedge' o '' para Chromium incluido).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Captura y cifra localmente para validar sin escribir en Supabase.",
    )
    return parser.parse_args(args)


async def _launch_interactive_browser(playwright: Playwright, preferred_channel: str) -> Browser:
    """Lanza navegador visible evitando detección básica de automatización para Google OAuth."""
    launch_kwargs: Dict[str, Any] = {
        "headless": False,
        "ignore_default_args": ["--enable-automation"],
        "args": ["--disable-blink-features=AutomationControlled"],
    }
    clean_channel = preferred_channel.strip()
    if clean_channel:
        try:
            return await playwright.chromium.launch(channel=clean_channel, **launch_kwargs)
        except Exception as exc:
            logger.warning(
                f"No se pudo abrir canal '{clean_channel}' ({exc}); usando Chromium de Playwright."
            )
    return await playwright.chromium.launch(**launch_kwargs)


def summarize_storage_state(state: Dict[str, Any]) -> Tuple[int, int]:
    """Retorna cantidad de cookies y claves de localStorage capturadas."""
    cookies = state.get("cookies") or []
    origins = state.get("origins") or []
    cookie_count = len(cookies) if isinstance(cookies, list) else 0
    ls_count = sum(
        len(entry.get("localStorage") or [])
        for entry in origins
        if isinstance(entry, dict) and isinstance(entry.get("localStorage"), list)
    )
    return cookie_count, ls_count


async def capture_and_store_session(
    client_id: str,
    target_url_override: Optional[str] = None,
    preferred_channel: str = "chrome",
    dry_run: bool = False,
) -> int:
    """Flujo principal interactivo de captura, cifrado y persistencia en Supabase."""
    sb = SupabaseService()
    if not sb.client:
        logger.error("No hay conexión activa a Supabase. Revisá SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY.")
        return 1

    config = await sb.get_client_interface_config(client_id)
    if not config:
        logger.error(f"No se encontró ClientInterfaceConfig en Supabase para client_id='{client_id}'.")
        return 1

    target_url = (target_url_override or config.base_url).strip()
    settings = get_settings()

    browser: Optional[Browser] = None
    try:
        async with async_playwright() as p:
            browser = await _launch_interactive_browser(p, preferred_channel=preferred_channel)
            context = await browser.new_context(
                viewport={
                    "width": settings.DESKTOP_VIEWPORT_WIDTH,
                    "height": settings.DESKTOP_VIEWPORT_HEIGHT,
                },
                extra_http_headers=config.custom_headers or None,
            )
            page = await context.new_page()
            logger.info(f"Abriendo '{target_url}' para inicio de sesión manual...")
            await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)

            print("\n" + "=" * 76)
            print(f"Cliente: {client_id}")
            print(f"Sitio:   {target_url}")
            print("-" * 76)
            print("1. Iniciá sesión con Google (u OAuth/usuario) en la ventana del navegador.")
            print("2. Verificá que la sesión quedó iniciada y que el carrito esté vacío.")
            print("3. Volvé aquí y presioná ENTER para capturar, cifrar y guardar la sesión.")
            print("   (Presioná Ctrl+C para cancelar sin guardar cambios)")
            print("=" * 76)

            try:
                await asyncio.to_thread(input, "\nPresioná ENTER cuando hayas completado el login > ")
            except (KeyboardInterrupt, EOFError):
                print("\nCaptura cancelada por el usuario. No se modificó Supabase.")
                return 1

            raw_state = dict(await context.storage_state())
            cookie_count, ls_count = summarize_storage_state(raw_state)
            if cookie_count == 0 and ls_count == 0:
                logger.error("El estado capturado está vacío (0 cookies y 0 entradas en localStorage). Abortando.")
                return 1

            encrypted_payload = encrypt_json(raw_state, settings.AES_ENCRYPTION_KEY)
            verified = decrypt_json(encrypted_payload, settings.AES_ENCRYPTION_KEY)
            if not isinstance(verified, dict):
                logger.error("Falló la verificación local de descifrado AES-256-GCM.")
                return 1

            print(
                f"\nSesión capturada y cifrada correctamente "
                f"(cookies={cookie_count}, localStorage_keys={ls_count}, payload_len={len(encrypted_payload)})."
            )

            if dry_run:
                print("Modo --dry-run activo: no se escribió en Supabase.")
                return 0

            updated = await sb.update_client_storage_state(client_id, encrypted_payload)
            if not updated:
                logger.error(f"No se pudo actualizar `storage_state_encrypted` en Supabase para '{client_id}'.")
                return 1

            print(f"OK: `storage_state_encrypted` actualizado en Supabase para cliente '{client_id}'.\n")
            return 0
    finally:
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                pass


def main() -> None:
    """Punto de entrada CLI."""
    configure_logging()
    args = parse_args()
    exit_code = asyncio.run(
        capture_and_store_session(
            client_id=args.client_id,
            target_url_override=args.url,
            preferred_channel=args.channel,
            dry_run=args.dry_run,
        )
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
