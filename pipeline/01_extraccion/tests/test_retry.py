import pytest
from google.api_core.exceptions import (
    Forbidden,
    NotFound,
    PermissionDenied,
    ResourceExhausted,
    ServiceUnavailable,
    TooManyRequests,
)
from app.retry import classify_error, retry_async_operation

pytestmark = pytest.mark.unit


def test_classify_error():
    """Prueba la clasificación exacta de excepciones permanentes vs transitorias."""
    # Permanentes (Fast-fail)
    assert classify_error(NotFound("Dataset no encontrado")) == ("PERMANENT", False)
    assert classify_error(Forbidden("Acceso denegado")) == ("PERMANENT", False)
    assert classify_error(PermissionDenied("El usuario carece de permisos")) == ("PERMANENT", False)

    # Transitorias (Reintentables)
    assert classify_error(TooManyRequests("Límite de tasa alcanzado")) == ("TRANSIENT", True)
    assert classify_error(ResourceExhausted("Cuota excedida")) == ("TRANSIENT", True)
    assert classify_error(ServiceUnavailable("Error backend 503 en BQ")) == ("TRANSIENT", True)
    assert classify_error(TimeoutError("Timeout de conexión")) == ("TRANSIENT", True)


@pytest.mark.asyncio
async def test_retry_successful_first_try():
    """Prueba que una operación exitosa en el primer intento no ejecute reintentos."""
    call_count = 0

    async def _op():
        nonlocal call_count
        call_count += 1
        return "exito"

    result, attempts = await retry_async_operation(
        _op,
        max_retries=3,
        initial_delay=0.01,
        client_id="cliente_prueba",
    )
    assert result == "exito"
    assert attempts == 1
    assert call_count == 1


@pytest.mark.asyncio
async def test_retry_transient_error_then_success():
    """Prueba que una operación con fallo transitorio inicial se recupere en el siguiente intento."""
    call_count = 0

    async def _op():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ServiceUnavailable("Error temporal 503 en BigQuery")
        return "recuperado"

    result, attempts = await retry_async_operation(
        _op,
        max_retries=3,
        initial_delay=0.01,
        client_id="cliente_prueba",
    )
    assert result == "recuperado"
    assert attempts == 2
    assert call_count == 2


@pytest.mark.asyncio
async def test_retry_permanent_error_fast_fails():
    """Prueba que un error permanente (Fast-fail) falle de inmediato en el intento 1 sin reintentar."""
    call_count = 0

    async def _op():
        nonlocal call_count
        call_count += 1
        raise PermissionDenied("El usuario no tiene el permiso bigquery.tables.getData")

    with pytest.raises(PermissionDenied):
        await retry_async_operation(
            _op,
            max_retries=3,
            initial_delay=0.01,
            client_id="cliente_prueba",
        )
    assert call_count == 1  # Fast-fail: no reintentó


@pytest.mark.asyncio
async def test_retry_exhaustion_raises_last_exception():
    """Prueba que ante un error transitorio persistente se agoten los intentos y se lance la excepción."""
    call_count = 0

    async def _op():
        nonlocal call_count
        call_count += 1
        raise TooManyRequests("Cuota 429")

    with pytest.raises(TooManyRequests):
        await retry_async_operation(
            _op,
            max_retries=2,
            initial_delay=0.01,
            client_id="cliente_prueba",
        )
    assert call_count == 2
