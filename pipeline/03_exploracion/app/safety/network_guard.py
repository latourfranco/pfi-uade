"""Módulo de protección de red para evitar cobros reales y llamadas mutables a pasarelas de pago."""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse
from playwright.async_api import BrowserContext, Page, Route

logger = logging.getLogger(__name__)

# Dominios estándar de pasarelas de pago y procesadores financieros
DEFAULT_PAYMENT_DOMAINS: Set[str] = {
    # Mercado Pago
    "mercadopago.com",
    "mercadopago.com.ar",
    "mpago.la",
    "mpago.li",
    # Stripe
    "stripe.com",
    "api.stripe.com",
    "checkout.stripe.com",
    # PayPal
    "paypal.com",
    "paypalobjects.com",
    # Argentina locales
    "pagofacil.com.ar",
    "rapipago.com.ar",
    "todopago.com.ar",
    "decidir.com.ar",
    "prismamediosdepago.com",
    # Internacionales
    "authorize.net",
    "braintreegateway.com",
    "braintree-api.com",
    "adyen.com",
    "square.com",
    "squareup.com",
    "klarna.com",
    "worldpay.com",
    "payu.com",
    "2checkout.com",
}

# Métodos HTTP que mutan estado o ejecutan transacciones
MUTABLE_HTTP_METHODS: Set[str] = {"POST", "PUT", "DELETE", "PATCH"}


class NetworkGuard:
    """
    Guardia de seguridad de red para Playwright.

    Intercepta tráfico HTTP/HTTPS y aborta automáticamente cualquier solicitud mutable
    o intento de pago dirigido a pasarelas de pago y procesadores de cobro conocidos,
    evitando transacciones monetarias reales durante la exploración agentica.
    """

    def __init__(
        self,
        blocked_domains: Optional[Set[str]] = None,
        block_all_methods_for_payment: bool = False,
    ) -> None:
        """
        Inicializa el guardia de red.

        :param blocked_domains: Conjunto opcional de dominios a bloquear en lugar de los por defecto.
        :param block_all_methods_for_payment: Si es True, bloquea incluso GET a pasarelas de pago.
        """
        self.blocked_domains: Set[str] = (
            {d.lower().strip() for d in blocked_domains}
            if blocked_domains is not None
            else set(DEFAULT_PAYMENT_DOMAINS)
        )
        self.block_all_methods: bool = block_all_methods_for_payment
        self.blocked_requests: List[Dict[str, Any]] = []

    def is_blocked(self, url: str, method: str) -> Tuple[bool, Optional[str]]:
        """
        Determina si una solicitud HTTP debe ser interceptada y bloqueada por seguridad.

        :param url: URL completa de la solicitud.
        :param method: Método HTTP (GET, POST, etc.).
        :return: Tupla (debe_bloquearse, razon_del_bloqueo).
        """
        if not url:
            return False, None

        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower().strip()
        method_upper = method.upper().strip()

        # Comprobar si el hostname coincide exactamente o es un subdominio de alguno bloqueado
        is_payment_domain = any(
            hostname == domain or hostname.endswith(f".{domain}")
            for domain in self.blocked_domains
        )

        if not is_payment_domain:
            return False, None

        # Si coincide con pasarela de pago, evaluar método
        if self.block_all_methods:
            return True, f"Tráfico bloqueado hacia pasarela de pago ({hostname})"

        if method_upper in MUTABLE_HTTP_METHODS:
            return (
                True,
                f"Solicitud mutable ({method_upper}) bloqueada hacia pasarela de pago ({hostname})",
            )

        return False, None

    async def handle_route(self, route: Route) -> None:
        """
        Manejador de rutas para Playwright.
        Evalúa la solicitud y la aborta si viola las políticas de seguridad.
        """
        request = route.request
        url = request.url
        method = request.method

        should_block, reason = self.is_blocked(url, method)

        if should_block:
            log_msg = f"[NetworkGuard] {reason}: {url}"
            logger.warning(log_msg)
            self.blocked_requests.append(
                {
                    "url": url,
                    "method": method,
                    "reason": reason,
                }
            )
            try:
                await route.abort("blockedbyclient")
            except Exception as exc:
                logger.error(f"[NetworkGuard] Error al abortar ruta de Playwright: {exc}")
        else:
            try:
                await route.continue_()
            except Exception as exc:
                logger.debug(f"[NetworkGuard] Error menor al continuar ruta: {exc}")

    async def attach_to_page(self, page: Page) -> None:
        """
        Asocia la intercepción de rutas a una página de Playwright específica.
        """
        await page.route("**/*", self.handle_route)
        logger.info("[NetworkGuard] Intercepción de red activada exitosamente en la página.")

    async def attach_to_context(self, context: BrowserContext) -> None:
        """
        Asocia la intercepción de rutas a nivel de BrowserContext de Playwright.
        """
        await context.route("**/*", self.handle_route)
        logger.info("[NetworkGuard] Intercepción de red activada exitosamente en el contexto del navegador.")
