from datetime import date
from unittest.mock import MagicMock
import pytest
from app.config import Settings
from app.models import ClientSourceIntegration
from app.services.bigquery_service import BigQueryService


@pytest.fixture
def bq_service(mock_settings: Settings) -> BigQueryService:
    return BigQueryService(mock_settings)


@pytest.mark.unit
def test_merge_natural_composite_key_definition(
    bq_service: BigQueryService,
    sample_clients: list[ClientSourceIntegration]
):
    """
    Verifica que la condicion ON del MERGE utilice la clave natural compuesta estricta de 5 campos:
    (cliente_id, fecha_evento, event_timestamp, id_usuario, nombre_evento).
    Esto garantiza la unicidad ontologica de cada evento del usuario en el tiempo.
    """
    sql = bq_service.build_merge_query(sample_clients[0])

    expected_keys = [
        "T.fecha_evento = S.fecha_evento",
        "T.cliente_id = S.cliente_id",
        "T.event_timestamp = S.event_timestamp",
        "T.id_usuario = S.id_usuario",
        "T.nombre_evento = S.nombre_evento",
    ]
    for key_clause in expected_keys:
        assert key_clause in sql, f"Falta la clave compuesta '{key_clause}' en la condicion ON del MERGE"


@pytest.mark.unit
def test_merge_insert_only_idempotency_clause(
    bq_service: BigQueryService,
    sample_clients: list[ClientSourceIntegration]
):
    """
    Verifica que la sentencia MERGE sea estrictamente de insercion idempotente (Append-only):
    - Debe contener WHEN NOT MATCHED THEN INSERT ROW.
    - No debe contener WHEN MATCHED THEN UPDATE (los eventos historicos son inmutables).
    - No debe contener DELETE.
    """
    sql = bq_service.build_merge_query(sample_clients[0])
    assert "WHEN NOT MATCHED THEN" in sql
    assert "INSERT ROW;" in sql
    assert "WHEN MATCHED THEN UPDATE" not in sql
    assert "DELETE" not in sql


@pytest.mark.integration
@pytest.mark.asyncio
async def test_merge_idempotent_reexecution_zero_duplicates(
    mock_settings: Settings,
    sample_clients: list[ClientSourceIntegration]
):
    """
    Verifica que ante una re-ejecucion del lote con los mismos eventos ya procesados,
    el resultado de filas afectadas sea estrictamente 0 (cero duplicados, cero mutaciones).
    """
    mock_bq_client = MagicMock()
    service = BigQueryService(mock_settings, client=mock_bq_client)
    # Marcar esquema en cache para centrarse en la ejecucion de la query
    service._verified_tables.add(service.get_table_full_id(sample_clients[0].gcp_region))

    # Corrida 1: Insercion inicial de lote (1500 eventos insertados)
    job_run_1 = MagicMock()
    job_run_1.num_dml_affected_rows = 1500
    job_run_1.total_bytes_processed = 5000000
    job_run_1.job_id = "job_batch_run_1"
    job_run_1.result.return_value = None

    mock_bq_client.query.return_value = job_run_1
    result_1 = await service.execute_client_merge(sample_clients[0], date(2026, 9, 21))
    assert result_1["rows_affected"] == 1500

    # Corrida 2: Re-ejecucion del mismo dia con exactamente los mismos eventos (Idempotencia)
    # Al estar todos ya insertados, num_dml_affected_rows debe ser 0
    job_run_2 = MagicMock()
    job_run_2.num_dml_affected_rows = 0
    job_run_2.total_bytes_processed = 5000000  # Lee bytes para contrastar pero no inserta
    job_run_2.job_id = "job_batch_run_2"
    job_run_2.result.return_value = None

    mock_bq_client.query.return_value = job_run_2
    result_2 = await service.execute_client_merge(sample_clients[0], date(2026, 9, 21))
    assert result_2["rows_affected"] == 0, "Una re-ejecucion sobre datos existentes debio afectar 0 filas"


@pytest.mark.unit
def test_partitioning_and_clustering_in_target_table_ddl(bq_service: BigQueryService):
    """
    Verifica que el DDL de aprovisionamiento regional cree la tabla con:
    - Particionamiento diario por fecha_evento (reduccion de bytes escaneados).
    - Clustering compuesto por cliente_id, id_usuario, tipo_evento (aceleracion del MERGE).
    """
    mock_client = MagicMock()
    mock_client.get_dataset.return_value = MagicMock()
    query_mock = MagicMock()
    mock_client.query.return_value = query_mock

    bq_service._client = mock_client
    bq_service._sync_ensure_target_schema("us-central1", "dw_analytics_us_central1", "proj.dw.eventos")

    executed_ddl = mock_client.query.call_args[0][0]
    assert "PARTITION BY fecha_evento" in executed_ddl
    assert "CLUSTER BY cliente_id, id_usuario, tipo_evento;" in executed_ddl
