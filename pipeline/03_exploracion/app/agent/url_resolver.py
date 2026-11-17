"""Módulo para resolución y normalización de URLs relativas y absolutas sobre el dominio base."""

from typing import List
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

# Parámetros de rastreo analítico que deben descartarse para evitar ruido en navegación
TRACKING_PARAMS: List[str] = [
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "_ga",
    "_gl",
]


class UrlResolver:
    """
    Resuelve dinámicamente rutas relativas de eventos GA4 sobre la URL base del cliente.

    Garantiza una configuración sin fricción (zero-friction), aislando la navegación
    estrictamente al entorno configurado (ej. staging o preproducción) incluso si los
    eventos GA4 contienen nombres de dominio de producción.
    """

    @classmethod
    def resolve_url(cls, base_url: str, route_or_url: str = "") -> str:
        """
        Calcula la URL de destino completa apuntando exclusivamente al host de base_url.

        :param base_url: URL base configurada para el cliente (ej. 'https://staging.tienda.com').
        :param route_or_url: Ruta relativa ('/carrito') o URL completa registrada en GA4.
        :return: URL absoluta normalizada sobre el host de base_url.
        """
        if not base_url:
            raise ValueError("base_url no puede estar vacía.")

        base_clean = base_url.strip()
        if not base_clean.startswith(("http://", "https://")):
            base_clean = f"https://{base_clean}"

        base_parsed = urlparse(base_clean)
        route_clean = (route_or_url or "").strip()

        if not route_clean or route_clean == "/":
            return urlunparse((base_parsed.scheme, base_parsed.netloc, "/", "", "", ""))

        # Si la ruta contiene un esquema http/https completo (procedente de producción)
        if route_clean.startswith(("http://", "https://")):
            target_parsed = urlparse(route_clean)
            filtered_query = cls._filter_tracking_params(target_parsed.query)
            # Reemplazar esquema y netloc con los de la base_url
            return urlunparse(
                (
                    base_parsed.scheme,
                    base_parsed.netloc,
                    target_parsed.path or "/",
                    "",
                    filtered_query,
                    target_parsed.fragment,
                )
            )

        # Si es una ruta relativa
        joined = urljoin(f"{base_clean.rstrip('/')}/", route_clean.lstrip("/"))
        joined_parsed = urlparse(joined)
        filtered_query = cls._filter_tracking_params(joined_parsed.query)

        return urlunparse(
            (
                joined_parsed.scheme,
                joined_parsed.netloc,
                joined_parsed.path or "/",
                "",
                filtered_query,
                joined_parsed.fragment,
            )
        )

    @classmethod
    def extract_route_path(cls, url_or_route: str) -> str:
        """
        Extrae el camino ('/path') limpio sin host, query params ni fragmentos.

        :param url_or_route: URL o ruta relativa.
        :return: Path normalizado que siempre inicia con '/'.
        """
        if not url_or_route or not url_or_route.strip():
            return "/"

        parsed = urlparse(url_or_route.strip())
        path = parsed.path.strip()

        if not path:
            return "/"

        if not path.startswith("/"):
            path = f"/{path}"

        # Eliminar barra final excepto si es la raíz
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]

        return path

    @staticmethod
    def _filter_tracking_params(query_string: str) -> str:
        """Elimina parámetros UTM y rastreadores de analítica de la query string."""
        if not query_string:
            return ""

        pairs = parse_qsl(query_string, keep_blank_values=True)
        filtered = [(k, v) for k, v in pairs if k.lower() not in TRACKING_PARAMS]
        return urlencode(filtered)
