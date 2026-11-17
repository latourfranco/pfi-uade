from datetime import date
from unittest.mock import MagicMock
import pytest
from google.api_core.exceptions import PermissionDenied
from google.cloud.exceptions import NotFound
from app.config import Settings
from app.models import ClientSourceIntegration, PlatformBigQueryError
from app.services.bigquery_service import BigQueryService, sanitize_region


@pytest.mark.unit
def test_sanitize_region():
    """Prueba la sanitización de nombres de regiones para identificar datasets válidos en BigQuery."""
    assert sanitize_region("us-central1") == "us_central1"
    assert sanitize_region("southamerica-west1") == "southamerica_west1"
    assert sanitize_region("US") == "us"
    assert sanitize_region("EU") == "eu"


@pytest.mark.unit
def test_build_merge_query(mock_settings: Settings, sample_clients: list[ClientSourceIntegration]):
    """Prueba que la consulta SQL generada contenga todas las reglas de negocio e idempotencia."""
    service = BigQueryService(mock_settings)
    client = sample_clients[0]  # us-central1

    sql = service.build_merge_query(client)

    # Verificar tabla destino y origen
    assert "MERGE `test-central-platform.dw_analytics_us_central1.eventos_usuario` T" in sql
    assert "`client-alpha-gcp.analytics_123456789.events_*`" in sql

    # Verificar anonimización irreversible de IDs
    assert "TO_HEX(SHA256(COALESCE(user_id, user_pseudo_id))) AS id_usuario" in sql

    # Verificar clasificación taxonómica de eventos
    assert "WHEN event_name = 'page_view' THEN 'visita_pagina'" in sql
    assert "WHEN event_name = 'scroll' THEN 'scroll'" in sql
    assert "THEN 'interaccion'" in sql

    # Verificar exclusión de eventos base
    assert "event_name NOT IN ('first_visit', 'session_start', 'user_engagement')" in sql

    # Verificar filtro de rango de particiones diarias (excluye intraday)
    assert "_TABLE_SUFFIX BETWEEN @start_suffix AND @end_suffix" in sql
    assert "REGEXP_CONTAINS(_TABLE_SUFFIX, r'^\\d{8}$')" in sql

    # Verificar condiciones de MERGE idempotente
    assert "ON T.fecha_evento = S.fecha_evento" in sql
    assert "AND T.cliente_id = S.cliente_id" in sql
    assert "AND T.event_timestamp = S.event_timestamp" in sql
    assert "AND T.id_usuario = S.id_usuario" in sql
    assert "AND T.nombre_evento = S.nombre_evento" in sql
    assert "WHEN NOT MATCHED THEN" in sql
    assert "INSERT ROW;" in sql


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ensure_target_schema_creates_if_not_found(mock_settings: Settings):
    """Prueba la creación del dataset y tabla destino cuando el dataset no existe previamente."""
    mock_bq_client = MagicMock()
    mock_bq_client.get_dataset.side_effect = NotFound("Dataset inexistente")
    mock_query_job = MagicMock()
    mock_query_job.result.return_value = None
    mock_bq_client.query.return_value = mock_query_job

    service = BigQueryService(mock_settings, client=mock_bq_client)
    await service.ensure_target_schema("southamerica-west1")

    mock_bq_client.create_dataset.assert_called_once()
    mock_bq_client.query.assert_called_once()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_execute_client_merge(mock_settings: Settings, sample_clients: list[ClientSourceIntegration]):
    """Prueba la ejecución de la consulta MERGE y la extracción de estadísticas del Job."""
    mock_bq_client = MagicMock()
    mock_query_job = MagicMock()
    mock_query_job.num_dml_affected_rows = 1500
    mock_query_job.total_bytes_processed = 2048000
    mock_query_job.job_id = "job_12345"
    mock_query_job.result.return_value = None
    mock_bq_client.query.return_value = mock_query_job

    service = BigQueryService(mock_settings, client=mock_bq_client)
    # Pre-marcar esquema como verificado en la caché para no invocar get_dataset
    service._verified_tables.add(service.get_table_full_id(sample_clients[0].gcp_region))

    result = await service.execute_client_merge(sample_clients[0], date(2026, 9, 21))

    assert result["rows_affected"] == 1500
    assert result["bytes_processed"] == 2048000
    assert result["job_id"] == "job_12345"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ensure_target_schema_when_dataset_already_exists(mock_settings: Settings):
    """Prueba que si el dataset ya existe, no se invoque create_dataset pero sí se asegure la tabla."""
    mock_bq_client = MagicMock()
    mock_bq_client.get_dataset.return_value = MagicMock()  # Dataset existe
    mock_query_job = MagicMock()
    mock_query_job.result.return_value = None
    mock_bq_client.query.return_value = mock_query_job

    service = BigQueryService(mock_settings, client=mock_bq_client)
    await service.ensure_target_schema("us-central1")

    mock_bq_client.get_dataset.assert_called_once()
    mock_bq_client.create_dataset.assert_not_called()
    mock_bq_client.query.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_target_schema_cache_hit_short_circuits(mock_settings: Settings):
    """Prueba que invocaciones consecutivas para la misma región utilicen la caché en memoria."""
    mock_bq_client = MagicMock()
    mock_bq_client.get_dataset.return_value = MagicMock()
    mock_query_job = MagicMock()
    mock_query_job.result.return_value = None
    mock_bq_client.query.return_value = mock_query_job

    service = BigQueryService(mock_settings, client=mock_bq_client)
    # Primera llamada: llena caché
    await service.ensure_target_schema("us-central1")
    assert mock_bq_client.query.call_count == 1

    # Segunda llamada: cortocircuita por _verified_tables
    await service.ensure_target_schema("us-central1")
    assert mock_bq_client.query.call_count == 1


@pytest.mark.unit
def test_bigquery_client_lazy_initialization(mock_settings: Settings):
    """Prueba la inicialización perezosa de bigquery.Client."""
    from unittest.mock import patch
    with patch("google.cloud.bigquery.Client") as mock_client_cls:
        service = BigQueryService(mock_settings)
        assert service._client is None
        client = service.client
        assert client is not None
        mock_client_cls.assert_called_once_with(project=mock_settings.PLATFORM_GCP_PROJECT_ID)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_ga4_data_available_returns_true_when_table_has_rows(
    mock_settings: Settings, sample_clients: list[ClientSourceIntegration]
):
    """Prueba que check_ga4_data_available retorne True cuando la tabla diaria existe y tiene filas."""
    mock_bq_client = MagicMock()
    mock_table = MagicMock()
    mock_table.num_rows = 250
    mock_bq_client.get_table.return_value = mock_table

    service = BigQueryService(mock_settings, client=mock_bq_client)
    available = await service.check_ga4_data_available(sample_clients[0], date(2026, 11, 14))

    assert available is True
    mock_bq_client.get_table.assert_called_once_with("client-alpha-gcp.analytics_123456789.events_20261114")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_ga4_data_available_returns_false_on_not_found(
    mock_settings: Settings, sample_clients: list[ClientSourceIntegration]
):
    """Prueba que si la tabla diaria events_YYYYMMDD no existe aún, retorne False sin lanzar error."""
    mock_bq_client = MagicMock()
    mock_bq_client.get_table.side_effect = NotFound("Tabla no exportada aún")

    service = BigQueryService(mock_settings, client=mock_bq_client)
    available = await service.check_ga4_data_available(sample_clients[0], date(2026, 11, 14))

    assert available is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_ga4_data_available_returns_false_when_table_empty(
    mock_settings: Settings, sample_clients: list[ClientSourceIntegration]
):
    """Prueba que si la tabla diaria existe pero tiene 0 filas, retorne False."""
    mock_bq_client = MagicMock()
    mock_table = MagicMock()
    mock_table.num_rows = 0
    mock_bq_client.get_table.return_value = mock_table

    service = BigQueryService(mock_settings, client=mock_bq_client)
    available = await service.check_ga4_data_available(sample_clients[0], date(2026, 11, 14))

    assert available is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_ga4_data_available_propagates_permission_denied(
    mock_settings: Settings, sample_clients: list[ClientSourceIntegration]
):
    """Prueba que errores de permisos sobre el proyecto del cliente se propaguen para ir a clientes_fallidos."""
    mock_bq_client = MagicMock()
    mock_bq_client.get_table.side_effect = PermissionDenied("Sin acceso a BigQuery del cliente")

    service = BigQueryService(mock_settings, client=mock_bq_client)
    with pytest.raises(PermissionDenied):
        await service.check_ga4_data_available(sample_clients[0], date(2026, 11, 14))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_target_schema_raises_platform_bigquery_error_on_failure(mock_settings: Settings):
    """Prueba que un fallo al aprovisionar el proyecto propio de BigQuery lance PlatformBigQueryError."""
    mock_bq_client = MagicMock()
    mock_bq_client.get_dataset.side_effect = PermissionDenied("Sin permisos en proyecto de plataforma")

    service = BigQueryService(mock_settings, client=mock_bq_client)
    with pytest.raises(PlatformBigQueryError):
        await service.ensure_target_schema("us-central1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_client_last_event_date_returns_none_when_empty(
    mock_settings: Settings, sample_clients: list[ClientSourceIntegration]
):
    """Prueba que get_client_last_event_date retorne None si el cliente no tiene filas previas."""
    mock_bq_client = MagicMock()
    mock_query_job = MagicMock()
    mock_query_job.result.return_value = [{"ultima_fecha": None}]
    mock_bq_client.query.return_value = mock_query_job

    service = BigQueryService(mock_settings, client=mock_bq_client)
    service._verified_tables.add(service.get_table_full_id(sample_clients[0].gcp_region))

    last_date = await service.get_client_last_event_date(sample_clients[0])
    assert last_date is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_client_last_event_date_returns_max_date(
    mock_settings: Settings, sample_clients: list[ClientSourceIntegration]
):
    """Prueba que get_client_last_event_date retorne la fecha máxima existente del cliente."""
    mock_bq_client = MagicMock()
    mock_query_job = MagicMock()
    mock_query_job.result.return_value = [{"ultima_fecha": date(2026, 11, 10)}]
    mock_bq_client.query.return_value = mock_query_job

    service = BigQueryService(mock_settings, client=mock_bq_client)
    service._verified_tables.add(service.get_table_full_id(sample_clients[0].gcp_region))

    last_date = await service.get_client_last_event_date(sample_clients[0])
    assert last_date == date(2026, 11, 10)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_client_last_event_date_empty_rows_returns_none(
    mock_settings: Settings, sample_clients: list[ClientSourceIntegration]
):
    """Prueba que si result() retorna lista vacía, get_client_last_event_date retorne None."""
    mock_bq_client = MagicMock()
    mock_query_job = MagicMock()
    mock_query_job.result.return_value = []
    mock_bq_client.query.return_value = mock_query_job

    service = BigQueryService(mock_settings, client=mock_bq_client)
    service._verified_tables.add(service.get_table_full_id(sample_clients[0].gcp_region))

    last_date = await service.get_client_last_event_date(sample_clients[0])
    assert last_date is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_client_last_event_date_raises_platform_bigquery_error(
    mock_settings: Settings, sample_clients: list[ClientSourceIntegration]
):
    """Prueba que un error al consultar el BigQuery propio lance PlatformBigQueryError."""
    mock_bq_client = MagicMock()
    mock_bq_client.query.side_effect = PermissionDenied("Sin acceso a tabla propia")

    service = BigQueryService(mock_settings, client=mock_bq_client)
    service._verified_tables.add(service.get_table_full_id(sample_clients[0].gcp_region))

    with pytest.raises(PlatformBigQueryError):
        await service.get_client_last_event_date(sample_clients[0])


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_ga4_data_available_range_returns_true_if_any_table_in_range(
    mock_settings: Settings, sample_clients: list[ClientSourceIntegration]
):
    """Prueba que en ventana multi-día retorne True si al menos 1 tabla events_YYYYMMDD cae en el rango."""
    t_intraday = MagicMock(table_id="events_intraday_20261114")
    t_old = MagicMock(table_id="events_20260801")
    t_valid = MagicMock(table_id="events_20261105")
    t_other = MagicMock(table_id="pseudonymous_users_20261105")

    mock_bq_client = MagicMock()
    mock_bq_client.list_tables.return_value = [t_intraday, t_old, t_other, t_valid]

    service = BigQueryService(mock_settings, client=mock_bq_client)
    available = await service.check_ga4_data_available(
        sample_clients[0], date(2026, 9, 16), date(2026, 11, 14)
    )
    assert available is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_ga4_data_available_range_returns_false_when_only_intraday_or_out_of_range(
    mock_settings: Settings, sample_clients: list[ClientSourceIntegration]
):
    """Prueba que en ventana multi-día ignore tablas intraday o fuera de rango y retorne False."""
    t_intraday = MagicMock(table_id="events_intraday_20261114")
    t_old = MagicMock(table_id="events_20260801")

    mock_bq_client = MagicMock()
    mock_bq_client.list_tables.return_value = [t_intraday, t_old]

    service = BigQueryService(mock_settings, client=mock_bq_client)
    available = await service.check_ga4_data_available(
        sample_clients[0], date(2026, 9, 16), date(2026, 11, 14)
    )
    assert available is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_ga4_data_available_range_returns_false_on_missing_dataset(
    mock_settings: Settings, sample_clients: list[ClientSourceIntegration]
):
    """Prueba que si el dataset analytics_<property_id> aún no existe, retorne False."""
    mock_bq_client = MagicMock()
    mock_bq_client.list_tables.side_effect = NotFound("Dataset no encontrado")

    service = BigQueryService(mock_settings, client=mock_bq_client)
    available = await service.check_ga4_data_available(
        sample_clients[0], date(2026, 9, 16), date(2026, 11, 14)
    )
    assert available is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_execute_client_merge_with_date_range_passes_start_and_end_suffix(
    mock_settings: Settings, sample_clients: list[ClientSourceIntegration]
):
    """Prueba que execute_client_merge pase @start_suffix y @end_suffix en QueryJobConfig."""
    mock_bq_client = MagicMock()
    mock_query_job = MagicMock()
    mock_query_job.num_dml_affected_rows = 4200
    mock_query_job.total_bytes_processed = 10240000
    mock_query_job.job_id = "job_range_60d"
    mock_query_job.result.return_value = None
    mock_bq_client.query.return_value = mock_query_job

    service = BigQueryService(mock_settings, client=mock_bq_client)
    service._verified_tables.add(service.get_table_full_id(sample_clients[0].gcp_region))

    result = await service.execute_client_merge(
        sample_clients[0], date(2026, 9, 16), date(2026, 11, 14)
    )
    assert result["rows_affected"] == 4200
    job_config = mock_bq_client.query.call_args.kwargs["job_config"]
    params = {p.name: p.value for p in job_config.query_parameters}
    assert params["start_suffix"] == "20260916"
    assert params["end_suffix"] == "20261114"
    assert params["cliente_id"] == "cliente_alpha"
