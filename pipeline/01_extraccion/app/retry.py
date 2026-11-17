import asyncio
import logging
import random
from typing import Any, Callable, Coroutine, Tuple, TypeVar

from google.api_core.exceptions import (
    BadRequest,
    DeadlineExceeded,
    Forbidden,
    GatewayTimeout,
    InternalServerError,
    InvalidArgument,
    NotFound,
    PermissionDenied,
    ResourceExhausted,
    ServiceUnavailable,
    TooManyRequests,
    Unauthenticated,
)

from google.auth.exceptions import DefaultCredentialsError, RefreshError, TransportError

from app.models import PlatformBigQueryError

logger = logging.getLogger("retry")

T = TypeVar("T")

# Excepciones permanentes que NO deben reintentarse (Fast-fail)
PERMANENT_EXCEPTIONS = (
    NotFound,
    Forbidden,
    PermissionDenied,
    BadRequest,
    InvalidArgument,
    Unauthenticated,
    DefaultCredentialsError,
    RefreshError,
    PlatformBigQueryError,
)

# Excepciones transitorias que es seguro reintentar
TRANSIENT_EXCEPTIONS = (
    ResourceExhausted,
    TooManyRequests,
    ServiceUnavailable,
    InternalServerError,
    DeadlineExceeded,
    GatewayTimeout,
    TransportError,
    asyncio.TimeoutError,
    TimeoutError,
    ConnectionError,
)


def classify_error(exc: Exception) -> Tuple[str, bool]:
    """
    Clasifica una excepción en una categoría y determina si es reintentable.

    Retorna:
        (nombre_categoria, es_reintentable)
    """
    if isinstance(exc, PERMANENT_EXCEPTIONS):
        return ("PERMANENT", False)
    if isinstance(exc, TRANSIENT_EXCEPTIONS):
        return ("TRANSIENT", True)

    # Evaluar patrones de texto para identificar fallos transitorios
    msg = str(exc).lower()
    transient_keywords = [
        "rate limit", "quota", "timeout", "timed out", "503", "500",
        "backend error", "transient", "connection reset"
    ]
    if any(k in msg for k in transient_keywords):
        return ("TRANSIENT", True)
    if any(k in msg for k in ["permission denied", "not found", "404", "403", "syntax error", "invalid"]):
        return ("PERMANENT", False)

    # Por defecto para errores desconocidos se permite reintentar
    return ("UNKNOWN", True)


async def retry_async_operation(
    operation: Callable[[], Coroutine[Any, Any, T]],
    max_retries: int = 3,
    initial_delay: float = 2.0,
    backoff_factor: float = 2.0,
    operation_name: str = "Operacion",
    client_id: str = "desconocido",
) -> Tuple[T, int]:
    """
    Ejecuta una operación asíncrona aplicando Exponential Backoff con Jitter ante errores transitorios.

    Retorna:
        (resultado, cantidad_de_intentos)

    Lanza:
        Exception: La última excepción ocurrida si se agotan los reintentos o ante un error permanente.
    """
    attempt = 0
    while attempt < max_retries:
        attempt += 1
        try:
            result = await operation()
            return result, attempt
        except Exception as exc:
            category, is_retryable = classify_error(exc)
            logger.warning(
                "[%s] Intento %d/%d falló para cliente '%s': %s (Categoría: %s, Reintentable: %s)",
                operation_name,
                attempt,
                max_retries,
                client_id,
                str(exc),
                category,
                is_retryable,
                extra={
                    "id_cliente": client_id,
                    "intento": attempt,
                    "categoria_error": category,
                },
            )

            if not is_retryable or attempt >= max_retries:
                logger.error(
                    "[%s] Cancelando reintentos para cliente '%s' en intento %d: %s",
                    operation_name,
                    client_id,
                    attempt,
                    str(exc),
                    extra={
                        "id_cliente": client_id,
                        "intento": attempt,
                        "categoria_error": category,
                    },
                )
                raise exc

            # Calcular retraso exponencial con jitter aleatorio
            delay = (initial_delay * (backoff_factor ** (attempt - 1))) + random.uniform(0.1, 0.5)
            logger.info(
                "[%s] Esperando %.2fs antes del intento %d para cliente '%s'...",
                operation_name,
                delay,
                attempt + 1,
                client_id,
                extra={"id_cliente": client_id, "intento": attempt},
            )
            await asyncio.sleep(delay)

    raise RuntimeError(f"Fin inesperado del bucle de reintentos para el cliente {client_id}")
