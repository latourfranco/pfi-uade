from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest
from google.api_core.exceptions import PermissionDenied
from google.auth.exceptions import DefaultCredentialsError, RefreshError
from app.config import Settings
from app.models import ClientSourceIntegration, PlatformBigQueryError
from app.services.extraction_pipeline import ExtractionPipeline


@pytest.mark.unit
def test_resolve_target_date(mock_settings: Settings):
    """Prueba la resolución de fecha_ejecucion (T) y fecha de datos GA4 (T-1)."""
    pipeline = ExtractionPipeline(mock_settings, MagicMock(), MagicMock())

    # Si fecha_ejecucion = 2026-09-15 (T), extrae datos de 2026-09-14 (T-1)
    assert pipeline.resolve_execution_date("2026-09-15") == date(2026, 9, 15)
    assert pipeline.resolve_target_date("2026-09-15") == date(2026, 9, 14)

    # Formato inválido lanza ValueError
    with pytest.raises(ValueError):
        pipeline.resolve_target_date("15/09/2026")

    # Por defecto T = hoy UTC y T-1 = ayer UTC
    expected_today = datetime.now(timezone.utc).date()
    expected_yesterday = expected_today - timedelta(days=1)
    assert pipeline.resolve_execution_date(None) == expected_today
    assert pipeline.resolve_target_date(None) == expected_yesterday


@pytest.mark.integration
@pytest.mark.asyncio
async def test_run_batch_empty_clients(mock_settings: Settings):
    """Prueba la ejecución del lote cuando no hay clientes activos en Supabase."""
    mock_sb = MagicMock()
    mock_sb.get_active_clients = AsyncMock(return_value=[])
    mock_bq = MagicMock()

    pipeline = ExtractionPipeline(mock_settings, mock_bq, mock_sb)
    response = await pipeline.run_batch()

    assert response.clientes_exitosos == []
    assert response.clientes_omitidos == []
    assert response.clientes_fallidos == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_run_batch_all_success(mock_settings: Settings, sample_clients: list[ClientSourceIntegration]):
    """Prueba la ejecución exitosa de todos los clientes en el lote sin escrituras en Supabase."""
    mock_sb = MagicMock()
    mock_sb.get_active_clients = AsyncMock(return_value=sample_clients)

    mock_bq = MagicMock()
    mock_bq.ensure_target_schema = AsyncMock()
    mock_bq.get_client_last_event_date = AsyncMock(return_value=date(2026, 9, 18))
    mock_bq.check_ga4_data_available = AsyncMock(return_value=True)
    mock_bq.execute_client_merge = AsyncMock(return_value={
        "rows_affected": 100,
        "bytes_procesados": 50000,
        "job_id": "job_xyz",
    })

    pipeline = ExtractionPipeline(mock_settings, mock_bq, mock_sb)
    response = await pipeline.run_batch("2026-09-20")

    assert response.fecha_ejecucion == "2026-09-20"
    assert response.clientes_exitosos == ["cliente_alpha", "cliente_beta"]
    assert response.clientes_omitidos == []
    assert response.clientes_fallidos == []
    # Verifica que con fecha_ejecucion=2026-09-20 (T) y MAX=2026-09-18 se extrajo 2026-09-19..2026-09-19
    for call in mock_bq.check_ga4_data_available.call_args_list:
        assert call.args[1] == date(2026, 9, 19)
        assert call.args[2] == date(2026, 9, 19)
    for call in mock_bq.execute_client_merge.call_args_list:
        assert call.args[1] == date(2026, 9, 19)
        assert call.args[2] == date(2026, 9, 19)


@pytest.mark.unit
def test_resolve_client_date_window(mock_settings: Settings):
    """Prueba las reglas de ventana de 60 días inicial, incremental, catch-up e idempotencia."""
    pipeline = ExtractionPipeline(mock_settings, MagicMock(), MagicMock())
    target_end = date(2026, 11, 14)  # T - 1 cuando T = 2026-11-15

    # 1. Primera ejecución (None): últimos 60 días [T-60, T-1] = [2026-09-16, 2026-11-14]
    assert pipeline.resolve_client_date_window(None, target_end) == (
        date(2026, 9, 16),
        date(2026, 11, 14),
    )

    # 2. Ejecución diaria normal (MAX = T - 2): extrae solo T - 1
    assert pipeline.resolve_client_date_window(date(2026, 11, 13), target_end) == (
        date(2026, 11, 14),
        date(2026, 11, 14),
    )

    # 3. Catch-up tras días caídos (MAX = 2026-11-10): recupera [2026-11-11, 2026-11-14]
    assert pipeline.resolve_client_date_window(date(2026, 11, 10), target_end) == (
        date(2026, 11, 11),
        date(2026, 11, 14),
    )

    # 4. Catch-up con último evento más antiguo que el TTL de 60 días: acota a T - 60
    assert pipeline.resolve_client_date_window(date(2026, 8, 1), target_end) == (
        date(2026, 9, 16),
        date(2026, 11, 14),
    )

    # 5. Re-ejecución de una fecha ya cargada (MAX >= T - 1): extrae idempotente [T-1, T-1]
    assert pipeline.resolve_client_date_window(date(2026, 11, 14), target_end) == (
        date(2026, 11, 14),
        date(2026, 11, 14),
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_run_batch_first_execution_backfills_60_days_and_second_uses_max_date(
    mock_settings: Settings, sample_clients: list[ClientSourceIntegration]
):
    """Prueba en lote que un cliente nuevo use ventana de 60 días y uno existente use MAX(fecha_evento)."""
    mock_sb = MagicMock()
    mock_sb.get_active_clients = AsyncMock(return_value=sample_clients)

    mock_bq = MagicMock()
    mock_bq.ensure_target_schema = AsyncMock()

    async def _mock_last_date(client):
        # cliente_alpha es nuevo (None), cliente_beta ya tiene datos hasta 2026-11-12
        return None if client.cliente_id == "cliente_alpha" else date(2026, 11, 12)

    mock_bq.get_client_last_event_date = AsyncMock(side_effect=_mock_last_date)
    mock_bq.check_ga4_data_available = AsyncMock(return_value=True)
    mock_bq.execute_client_merge = AsyncMock(return_value={"rows_affected": 100, "job_id": "job_1"})

    pipeline = ExtractionPipeline(mock_settings, mock_bq, mock_sb)
    response = await pipeline.run_batch("2026-11-15")  # T=2026-11-15 -> target_end=2026-11-14

    assert response.clientes_exitosos == ["cliente_alpha", "cliente_beta"]

    merges_by_client = {
        call.args[0].cliente_id: (call.args[1], call.args[2])
        for call in mock_bq.execute_client_merge.call_args_list
    }
    assert merges_by_client["cliente_alpha"] == (date(2026, 9, 16), date(2026, 11, 14))
    assert merges_by_client["cliente_beta"] == (date(2026, 11, 13), date(2026, 11, 14))


@pytest.mark.integration
@pytest.mark.asyncio
async def test_run_batch_error_isolation(mock_settings: Settings, sample_clients: list[ClientSourceIntegration]):
    """Prueba que el fallo en un cliente (ej. 403) no impida que los demás clientes procesen con éxito."""
    mock_sb = MagicMock()
    mock_sb.get_active_clients = AsyncMock(return_value=sample_clients)

    mock_bq = MagicMock()
    mock_bq.ensure_target_schema = AsyncMock()
    mock_bq.get_client_last_event_date = AsyncMock(return_value=date(2026, 9, 18))
    mock_bq.check_ga4_data_available = AsyncMock(return_value=True)

    async def _mock_merge(client, start_date, end_date=None):
        if client.cliente_id == "cliente_alpha":
            raise PermissionDenied("Acceso denegado a tablas BigQuery de cliente alpha")
        return {"rows_affected": 50, "job_id": "job_beta"}

    mock_bq.execute_client_merge = AsyncMock(side_effect=_mock_merge)

    pipeline = ExtractionPipeline(mock_settings, mock_bq, mock_sb)
    response = await pipeline.run_batch("2026-09-20")

    assert response.clientes_exitosos == ["cliente_beta"]
    assert response.clientes_omitidos == []
    assert response.clientes_fallidos == ["cliente_alpha"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_run_batch_omits_client_when_ga4_data_unavailable(
    mock_settings: Settings, sample_clients: list[ClientSourceIntegration]
):
    """Prueba que un cliente sin tabla diaria GA4 disponible vaya a clientes_omitidos sin ejecutar MERGE."""
    mock_sb = MagicMock()
    mock_sb.get_active_clients = AsyncMock(return_value=sample_clients)

    mock_bq = MagicMock()
    mock_bq.ensure_target_schema = AsyncMock()
    mock_bq.get_client_last_event_date = AsyncMock(return_value=None)

    async def _mock_available(client, start_date, end_date=None):
        return client.cliente_id != "cliente_alpha"

    mock_bq.check_ga4_data_available = AsyncMock(side_effect=_mock_available)
    mock_bq.execute_client_merge = AsyncMock(return_value={"rows_affected": 80, "job_id": "job_beta"})

    pipeline = ExtractionPipeline(mock_settings, mock_bq, mock_sb)
    response = await pipeline.run_batch("2026-11-14")

    assert response.fecha_ejecucion == "2026-11-14"
    assert response.clientes_exitosos == ["cliente_beta"]
    assert response.clientes_omitidos == ["cliente_alpha"]
    assert response.clientes_fallidos == []
    assert mock_bq.execute_client_merge.call_count == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_run_batch_propagates_platform_bigquery_error(
    mock_settings: Settings, sample_clients: list[ClientSourceIntegration]
):
    """Prueba que un fallo en el proyecto propio de BigQuery se propague para responder HTTP 500."""
    mock_sb = MagicMock()
    mock_sb.get_active_clients = AsyncMock(return_value=sample_clients)

    mock_bq = MagicMock()
    mock_bq.ensure_target_schema = AsyncMock(
        side_effect=PlatformBigQueryError("Proyecto propio BigQuery inaccesible")
    )

    pipeline = ExtractionPipeline(mock_settings, mock_bq, mock_sb)
    with pytest.raises(PlatformBigQueryError):
        await pipeline.run_batch("2026-11-14")


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "global_exc",
    [
        DefaultCredentialsError("Sin credenciales ADC"),
        RefreshError("Token de servicio expirado o revocado"),
        PlatformBigQueryError("Fallo al acceder al proyecto propio"),
    ],
)
async def test_run_batch_propagates_global_errors_from_client_task(
    mock_settings: Settings, sample_clients: list[ClientSourceIntegration], global_exc: Exception
):
    """Prueba que fallos globales de credenciales o plataforma no se aíslen en clientes_fallidos."""
    mock_sb = MagicMock()
    mock_sb.get_active_clients = AsyncMock(return_value=[sample_clients[0]])

    mock_bq = MagicMock()
    mock_bq.ensure_target_schema = AsyncMock()
    mock_bq.get_client_last_event_date = AsyncMock(return_value=None)
    mock_bq.check_ga4_data_available = AsyncMock(side_effect=global_exc)

    pipeline = ExtractionPipeline(mock_settings, mock_bq, mock_sb)
    with pytest.raises(type(global_exc)):
        await pipeline.run_batch("2026-11-14")
