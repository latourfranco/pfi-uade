from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from google.api_core.exceptions import PermissionDenied, ServiceUnavailable
from google.auth.exceptions import DefaultCredentialsError, RefreshError, TransportError

from app.config import Settings
from app.models import ClientSourceIntegration
from app.retry import classify_error, retry_async_operation
from app.services.extraction_pipeline import ExtractionPipeline


@pytest.mark.unit
def test_iam_credential_errors_fast_fail_classification():
    """
    Verifica que fallos de credenciales IAM/OAuth de GCP (RefreshError y DefaultCredentialsError)
    se clasifiquen de forma estricta como PERMANENT para evitar bucles de reintentos inutiles.
    """
    cat_refresh, retryable_refresh = classify_error(RefreshError("The credentials could not be refreshed."))
    assert cat_refresh == "PERMANENT"
    assert retryable_refresh is False

    cat_default, retryable_default = classify_error(DefaultCredentialsError("Could not determine credentials."))
    assert cat_default == "PERMANENT"
    assert retryable_default is False

    cat_perm, retryable_perm = classify_error(PermissionDenied("Missing bigquery.jobs.create IAM permission"))
    assert cat_perm == "PERMANENT"
    assert retryable_perm is False


@pytest.mark.unit
def test_transient_transport_error_classification():
    """Verifica que fallos de transporte de red en Google Auth sean reintentables."""
    cat, retryable = classify_error(TransportError("Connection reset by peer"))
    assert cat == "TRANSIENT"
    assert retryable is True


@pytest.mark.unit
def test_classify_error_string_patterns_and_fallback():
    """Verifica la clasificacion basada en coincidencia de subcadenas y fallback desconocido."""
    # Coincidencia con keywords transitorias
    assert classify_error(Exception("HTTP 503 backend error")) == ("TRANSIENT", True)
    assert classify_error(Exception("rate limit exceeded on BigQuery query job")) == ("TRANSIENT", True)
    assert classify_error(Exception("temporary connection reset")) == ("TRANSIENT", True)

    # Coincidencia con keywords permanentes
    assert classify_error(Exception("404 table not found in dataset")) == ("PERMANENT", False)
    assert classify_error(Exception("403 Forbidden: client lacks IAM access")) == ("PERMANENT", False)
    assert classify_error(Exception("syntax error in SQL query")) == ("PERMANENT", False)

    # Error completamente desconocido (default UNKNOWN, reintentable)
    assert classify_error(Exception("Unexpected mathematical anomaly")) == ("UNKNOWN", True)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_iam_refresh_error_fast_fails_without_retrying():
    """
    Verifica que si una llamada falla con RefreshError, retry_async_operation
    cancele de inmediato los intentos (intento = 1) y lance la excepcion original.
    """
    calls = 0

    async def _operation_with_expired_token():
        nonlocal calls
        calls += 1
        raise RefreshError("invalid_grant: Token has been revoked or expired")

    with pytest.raises(RefreshError):
        await retry_async_operation(
            operation=_operation_with_expired_token,
            max_retries=3,
            initial_delay=0.01,
            client_id="cliente_con_token_expirado"
        )
    assert calls == 1  # Fast-fail


@pytest.mark.integration
@pytest.mark.asyncio
async def test_second_chance_pass_recovers_transient_failed_clients(
    mock_settings: Settings, sample_clients: list[ClientSourceIntegration]
):
    """
    Verifica la activacion de la segunda pasada:
    - Cliente Alpha falla en la primera pasada por un error 503 transitorio.
    - Cliente Beta es exitoso en la primera pasada.
    - En la segunda pasada, Cliente Alpha se recupera y finaliza exitoso.
    - Metricas finales: total_exitosos = 2, total_fallidos = 0.
    """
    mock_sb = MagicMock()
    mock_sb.get_active_clients = AsyncMock(return_value=sample_clients)

    client_alpha_attempts = 0

    async def _mock_merge(client: ClientSourceIntegration, start_date, end_date=None):
        nonlocal client_alpha_attempts
        if client.cliente_id == "cliente_alpha":
            client_alpha_attempts += 1
            # Falla en las llamadas de la Pasada 1 (hasta agotar max_retries de ese intento)
            if client_alpha_attempts <= mock_settings.MAX_CLIENT_RETRIES:
                raise ServiceUnavailable("BigQuery 503 Backend Temporarily Unavailable")
            # En la Segunda Pasada (Second-Chance), se recupera exitosamente
            return {"rows_affected": 320, "bytes_procesados": 12000, "job_id": "job_alpha_recuperado"}
        return {"rows_affected": 150, "bytes_procesados": 8000, "job_id": "job_beta"}

    mock_bq = MagicMock()
    mock_bq.ensure_target_schema = AsyncMock()
    mock_bq.get_client_last_event_date = AsyncMock(return_value=None)
    mock_bq.check_ga4_data_available = AsyncMock(return_value=True)
    mock_bq.execute_client_merge = AsyncMock(side_effect=_mock_merge)

    pipeline = ExtractionPipeline(mock_settings, mock_bq, mock_sb)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        response = await pipeline.run_batch("2026-09-20")

    assert response.clientes_exitosos == ["cliente_alpha", "cliente_beta"]
    assert response.clientes_omitidos == []
    assert response.clientes_fallidos == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_second_chance_pass_persists_failure_if_error_continues(
    mock_settings: Settings, sample_clients: list[ClientSourceIntegration]
):
    """
    Verifica que si el error transitorio persiste incluso en la segunda pasada,
    el cliente permanezca registrado en la lista de fallidos.
    """
    mock_sb = MagicMock()
    mock_sb.get_active_clients = AsyncMock(return_value=[sample_clients[0]])

    mock_bq = MagicMock()
    mock_bq.ensure_target_schema = AsyncMock()
    mock_bq.get_client_last_event_date = AsyncMock(return_value=None)
    mock_bq.check_ga4_data_available = AsyncMock(return_value=True)
    # Falla persistentemente con ServiceUnavailable
    mock_bq.execute_client_merge = AsyncMock(side_effect=ServiceUnavailable("BigQuery outage"))

    pipeline = ExtractionPipeline(mock_settings, mock_bq, mock_sb)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        response = await pipeline.run_batch("2026-09-20")

    assert response.clientes_exitosos == []
    assert response.clientes_omitidos == []
    assert response.clientes_fallidos == ["cliente_alpha"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_second_chance_pass_does_not_retry_omitted_clients(
    mock_settings: Settings, sample_clients: list[ClientSourceIntegration]
):
    """Verifica que los clientes omitidos no se reintenten en la segunda pasada."""
    mock_sb = MagicMock()
    mock_sb.get_active_clients = AsyncMock(return_value=sample_clients)

    mock_bq = MagicMock()
    mock_bq.ensure_target_schema = AsyncMock()
    mock_bq.get_client_last_event_date = AsyncMock(return_value=None)

    async def _mock_available(client, start_date, end_date=None):
        return client.cliente_id != "cliente_alpha"

    mock_bq.check_ga4_data_available = AsyncMock(side_effect=_mock_available)
    mock_bq.execute_client_merge = AsyncMock(side_effect=ServiceUnavailable("BigQuery 503"))

    pipeline = ExtractionPipeline(mock_settings, mock_bq, mock_sb)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        response = await pipeline.run_batch("2026-11-14")

    assert response.clientes_exitosos == []
    assert response.clientes_omitidos == ["cliente_alpha"]
    assert response.clientes_fallidos == ["cliente_beta"]
    # cliente_alpha solo debe haberse verificado una vez (no en segunda pasada)
    alpha_checks = [
        call for call in mock_bq.check_ga4_data_available.call_args_list
        if call.args[0].cliente_id == "cliente_alpha"
    ]
    assert len(alpha_checks) == 1
