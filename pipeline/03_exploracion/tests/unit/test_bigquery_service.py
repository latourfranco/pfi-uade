"""Pruebas unitarias para BigQueryService sobre el dataset centralizado `friccion_resultados`."""

import logging
from unittest.mock import MagicMock, patch
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
import pytest
from app.models.exploration_report import (
    BoundingBox,
    BoundingBoxContext,
    ExplorationReport,
    ExplorationStatus,
    VisualEvidence,
)
from app.models.session_trace import DeviceInfo
from app.services.bigquery_service import EXPLORATION_REPORT_SCHEMA, BigQueryService


@pytest.fixture
def sample_report() -> ExplorationReport:
    """Fixture de un reporte representativo con evidencia visual y métricas del patrón."""
    bbox = BoundingBox(x=10.0, y=20.0, width=100.0, height=40.0)
    bbox_ctx = BoundingBoxContext(
        box=bbox,
        tag_name="button",
        element_text="Comprar",
        role="button",
        aria_label="Boton comprar",
        context_type="interacted_element",
        surrounding_text="Total $100",
    )
    evidence1 = VisualEvidence(
        orden=0,
        nombre_evento="page_view",
        ruta="/inicio",
        items=None,
        scroll=False,
        en_patron=True,
        es_paso_friccion=False,
        screenshot_url="gs://bucket/step_0.webp",
        timestamp="2026-10-17T15:00:00Z",
        bounding_box_context=bbox_ctx,
        context_notes=["Se cerró un obstáculo o pop-up emergente al cargar la vista (Cookies: Accept all)."],
    )
    evidence2 = VisualEvidence(
        orden=1,
        nombre_evento="select_item",
        ruta="/catalogo",
        items="SKU-123",
        scroll=True,
        en_patron=True,
        es_paso_friccion=True,
        screenshot_url="gs://bucket/step_1.webp",
        timestamp="2026-10-17T15:00:05Z",
        bounding_box_context=None,
    )
    return ExplorationReport(
        id_patron="pat_friction_99",
        id_cliente="cliente_demo",
        id_sesion="sesion_demo_1",
        fecha_exploracion="2026-10-28",
        status=ExplorationStatus.COMPLETED,
        total_steps=2,
        completed_steps=2,
        started_at="2026-10-17T15:00:00Z",
        finished_at="2026-10-17T15:00:10Z",
        objetivo="purchase",
        secuencia=["page_view", "select_item"],
        sesiones=120,
        usuarios=95,
        llegada_grupo=0.15,
        llegada_referencia=0.45,
        sesiones_perdidas=36.0,
        id_modelo="mod_v1",
        primera_deteccion="2026-10-20",
        ultima_deteccion="2026-10-28",
        device_info=DeviceInfo(
            tipo_dispositivo="mobile",
            navegador="Chrome",
            sistema_operativo="Android",
        ),
        evidences=[evidence1, evidence2],
        error_message=None,
    )


@pytest.mark.unit
def test_bigquery_service_init_failure_handled():
    """Verifica que si no hay credenciales de BigQuery, se capture la excepción y quede desconectado."""
    with patch("google.cloud.bigquery.Client", side_effect=Exception("No ADC credentials found")):
        service = BigQueryService(project_id="test-proj")
        assert service.is_connected() is False


@pytest.mark.unit
def test_bigquery_service_get_dataset_id():
    """Verifica que get_dataset_id retorne el dataset centralizado configurado."""
    service = BigQueryService(client=MagicMock())
    assert service.get_dataset_id() == service.settings.BIGQUERY_DATASET
    assert service.get_dataset_id() == "friccion_resultados"


@pytest.mark.unit
def test_report_to_row_serialization(sample_report):
    """Verifica la serialización completa de un ExplorationReport a formato fila BigQuery."""
    service = BigQueryService(client=MagicMock())
    row = service.report_to_row(sample_report)

    assert row["id_patron"] == "pat_friction_99"
    assert row["id_cliente"] == "cliente_demo"
    assert row["id_sesion"] == "sesion_demo_1"
    assert row["fecha_exploracion"] == "2026-10-28"
    assert row["status"] == "COMPLETED"
    assert row["objetivo"] == "purchase"
    assert row["secuencia"] == ["page_view", "select_item"]
    assert row["sesiones_perdidas"] == 36.0
    assert row["device_info"] == {
        "tipo_dispositivo": "mobile",
        "navegador": "Chrome",
        "sistema_operativo": "Android",
    }
    assert len(row["evidences"]) == 2
    assert row["evidences"][0]["orden"] == 0
    assert row["evidences"][0]["nombre_evento"] == "page_view"
    assert row["evidences"][0]["bounding_box_context"]["tag_name"] == "button"
    assert row["evidences"][0]["context_notes"] == [
        "Se cerró un obstáculo o pop-up emergente al cargar la vista (Cookies: Accept all)."
    ]
    assert row["evidences"][1]["scroll"] is True
    assert row["evidences"][1]["es_paso_friccion"] is True
    assert row["evidences"][1]["bounding_box_context"] is None
    assert row["evidences"][1]["context_notes"] == []
    evidences_field = next(f for f in EXPLORATION_REPORT_SCHEMA if f.name == "evidences")
    assert any(sf.name == "context_notes" and sf.mode == "REPEATED" for sf in evidences_field.fields)
    assert "created_at" in row

    # Sin device_info
    sample_report.device_info = None
    row_no_device = service.report_to_row(sample_report)
    assert row_no_device["device_info"] is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_exploration_report_success(sample_report):
    """Verifica la inserción exitosa de un reporte en el dataset centralizado."""
    mock_client = MagicMock()
    mock_client.insert_rows_json.return_value = []

    service = BigQueryService(client=mock_client)
    success = await service.save_exploration_report(
        sample_report,
        region="southamerica-east1",
        project_id="pruebas-pfi",
    )

    assert success is True
    mock_client.insert_rows_json.assert_called_once()
    table_ref = mock_client.insert_rows_json.call_args[0][0]
    assert table_ref == f"pruebas-pfi.friccion_resultados.{service.settings.BIGQUERY_TABLE_NAME}"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_exploration_report_not_connected(sample_report):
    """Verifica que si no hay cliente activo retorne False."""
    service = BigQueryService(client=None)
    service.client = None
    assert await service.save_exploration_report(sample_report) is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_exploration_report_no_project_id(sample_report):
    """Verifica que si no se puede resolver el project_id retorne False."""
    mock_client = MagicMock()
    mock_client.project = None

    service = BigQueryService(client=mock_client)
    service.project_id = None
    with patch.object(service.settings, "PLATFORM_GCP_PROJECT_ID", None):
        assert await service.save_exploration_report(sample_report, project_id=None) is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_exploration_report_insert_errors(sample_report):
    """Verifica el manejo de errores retornados por insert_rows_json."""
    mock_client = MagicMock()
    mock_client.insert_rows_json.return_value = [{"index": 0, "errors": [{"message": "type error"}]}]

    service = BigQueryService(client=mock_client)
    assert await service.save_exploration_report(sample_report, project_id="test-proj") is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_exploration_report_table_not_found_creates_table(sample_report):
    """Verifica que si la tabla no existe, cree la tabla con clustering y reintente."""
    mock_client = MagicMock()
    mock_client.insert_rows_json.side_effect = [NotFound("Table not found"), []]

    service = BigQueryService(client=mock_client)
    success = await service.save_exploration_report(sample_report, project_id="test-proj")

    assert success is True
    mock_client.create_table.assert_called_once()
    created_table = mock_client.create_table.call_args[0][0]
    assert created_table.time_partitioning is None
    assert created_table.clustering_fields == ["id_cliente", "id_patron"]
    assert created_table.schema == EXPLORATION_REPORT_SCHEMA
    assert mock_client.insert_rows_json.call_count == 2


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_exploration_report_table_not_found_retry_propagation_sleep(sample_report):
    """Verifica el reintento con sleep si NotFound persiste brevemente tras create_table."""
    mock_client = MagicMock()
    mock_client.insert_rows_json.side_effect = [
        NotFound("Table not found"),
        NotFound("Propagating..."),
        [],
    ]

    service = BigQueryService(client=mock_client)
    with patch("app.services.bigquery_service.time.sleep") as mock_sleep:
        success = await service.save_exploration_report(sample_report, project_id="test-proj")

    assert success is True
    mock_sleep.assert_called_once_with(1.0)
    assert mock_client.insert_rows_json.call_count == 3


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_exploration_report_table_not_found_exhausts_retries(sample_report):
    """Verifica que si el retry agota los 3 intentos por NotFound, capture el error y retorne False."""
    mock_client = MagicMock()
    mock_client.insert_rows_json.side_effect = [
        NotFound("Initial missing"),
        NotFound("Try 1"),
        NotFound("Try 2"),
        NotFound("Try 3"),
    ]

    service = BigQueryService(client=mock_client)
    with patch("app.services.bigquery_service.time.sleep"):
        assert await service.save_exploration_report(sample_report, project_id="test-proj") is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_exploration_report_table_not_found_retry_fails(sample_report):
    """Verifica que si tras crear la tabla el retry devuelve errores, retorne False."""
    mock_client = MagicMock()
    mock_client.insert_rows_json.side_effect = [
        NotFound("Table not found"),
        [{"errors": ["retry failed"]}],
    ]

    service = BigQueryService(client=mock_client)
    assert await service.save_exploration_report(sample_report, project_id="test-proj") is False
    mock_client.create_table.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_exploration_report_table_create_exception(sample_report):
    """Verifica que si la creación de la tabla lanza excepción, retorne False."""
    mock_client = MagicMock()
    mock_client.insert_rows_json.side_effect = NotFound("Table not found")
    mock_client.create_table.side_effect = Exception("Permission denied")

    service = BigQueryService(client=mock_client)
    assert await service.save_exploration_report(sample_report, project_id="test-proj") is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_exploration_report_generic_exception(sample_report):
    """Verifica que una excepción genérica al insertar sea capturada y retorne False."""
    mock_client = MagicMock()
    mock_client.insert_rows_json.side_effect = Exception("Red de BigQuery caída")

    service = BigQueryService(client=mock_client)
    assert await service.save_exploration_report(sample_report, project_id="test-proj") is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_friction_patterns_for_client_success():
    """Verifica la consulta JOIN incremental y deserialización a SessionTrace."""
    mock_client = MagicMock()
    mock_job = MagicMock()

    class MockRow:
        def __init__(self, data):
            self._data = data

        def items(self):
            return self._data.items()

    raw_rows = [
        MockRow({
            "id_patron": "pat_1",
            "id_cliente": "cliente_1",
            "id_sesion": "sesion_1",
            "objetivo": "purchase",
            "secuencia": ["page_view", "add_to_cart"],
            "sesiones": 50,
            "usuarios": 40,
            "llegada_grupo": 0.1,
            "llegada_referencia": 0.4,
            "sesiones_perdidas": 15.0,
            "id_modelo": "m1",
            "primera_deteccion": "2026-10-20",
            "ultima_deteccion": "2026-10-28",
            "pasos": [
                {
                    "orden": 0,
                    "nombre_evento": "page_view",
                    "ruta": "/home",
                    "items": None,
                    "scroll": False,
                    "en_patron": True,
                    "es_paso_friccion": False,
                    "tipo_dispositivo": "desktop",
                    "navegador": "Chrome",
                    "sistema_operativo": "macOS",
                },
                {
                    "orden": 1,
                    "nombre_evento": "add_to_cart",
                    "ruta": "/product/1",
                    "items": "SKU-1",
                    "scroll": True,
                    "en_patron": True,
                    "es_paso_friccion": True,
                    "tipo_dispositivo": "desktop",
                    "navegador": "Chrome",
                    "sistema_operativo": "macOS",
                },
            ],
        }),
        MockRow({
            "id_patron": "pat_2",
            "id_cliente": "cliente_1",
            "id_sesion": "sesion_2",
            "sesiones_perdidas": 5.0,
            "pasos": [
                {
                    "orden": 0,
                    "nombre_evento": "view_cart",
                    "ruta": "/cart",
                    "scroll": False,
                    "en_patron": True,
                    "es_paso_friccion": True,
                    "tipo_dispositivo": "mobile",
                    "navegador": "Safari",
                    "sistema_operativo": "iOS",
                }
            ],
        }),
    ]
    mock_job.job_id = "bq-job-123"
    mock_job.total_bytes_processed = 2048
    mock_job.result.return_value = raw_rows
    mock_client.query.return_value = mock_job

    service = BigQueryService(client=mock_client)
    traces = await service.get_friction_patterns_for_client(
        client_id="cliente_1",
        batch_date="2026-10-28",
        region="us",
        project_id="test-proj",
    )

    assert len(traces) == 2
    assert traces[0].id_patron == "pat_1"
    assert traces[0].id_sesion == "sesion_1"
    assert traces[0].sesiones_perdidas == 15.0
    assert traces[0].device_info.tipo_dispositivo == "desktop"
    assert len(traces[0].events) == 2
    assert traces[0].events[1].scroll is True
    assert traces[1].id_patron == "pat_2"
    assert traces[1].device_info.tipo_dispositivo == "mobile"

    query_str = mock_client.query.call_args[0][0]
    assert "`test-proj.friccion_resultados.patrones`" in query_str
    assert "`test-proj.friccion_resultados.sesion_representativa`" in query_str
    assert "`test-proj.friccion_resultados.patrones_friccion_explorados`" in query_str
    assert "NOT EXISTS" in query_str
    assert "ORDER BY p.sesiones_perdidas DESC" in query_str


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_friction_patterns_fallback_when_explored_table_missing():
    """Verifica que si patrones_friccion_explorados no existe, ejecute el fallback sin NOT EXISTS."""
    mock_client = MagicMock()
    mock_job = MagicMock()

    class MockRow:
        def __init__(self, data):
            self._data = data

        def items(self):
            return self._data.items()

    mock_job.result.return_value = [
        MockRow({
            "id_patron": "pat_fallback",
            "id_cliente": "cliente_1",
            "id_sesion": "sesion_fb",
            "pasos": [
                {
                    "orden": 0,
                    "nombre_evento": "page_view",
                    "ruta": "/inicio",
                    "scroll": False,
                    "en_patron": True,
                    "es_paso_friccion": False,
                }
            ],
        })
    ]
    mock_client.query.side_effect = [
        NotFound("Not found: Table test-proj:friccion_resultados.patrones_friccion_explorados"),
        mock_job,
    ]

    service = BigQueryService(client=mock_client)
    traces = await service.get_friction_patterns_for_client(
        client_id="cliente_1",
        batch_date="2026-10-28",
        project_id="test-proj",
    )

    assert len(traces) == 1
    assert traces[0].id_patron == "pat_fallback"
    assert mock_client.query.call_count == 2
    fallback_sql = mock_client.query.call_args_list[1][0][0]
    assert "NOT EXISTS" not in fallback_sql


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_friction_patterns_for_client_not_connected():
    """Verifica que si no hay cliente BigQuery activo, lance RuntimeError."""
    service = BigQueryService(client=None)
    service.client = None
    with pytest.raises(RuntimeError, match="No hay cliente BigQuery activo"):
        await service.get_friction_patterns_for_client(
            client_id="cliente_1",
            batch_date="2026-10-28",
        )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_friction_patterns_for_client_no_project_id():
    """Verifica que si no hay project_id disponible, lance RuntimeError."""
    mock_client = MagicMock()
    mock_client.project = None

    service = BigQueryService(client=mock_client)
    service.project_id = None
    with patch.object(service.settings, "PLATFORM_GCP_PROJECT_ID", None):
        with pytest.raises(RuntimeError, match="project_id"):
            await service.get_friction_patterns_for_client(
                client_id="cliente_1",
                batch_date="2026-10-28",
                project_id=None,
            )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_friction_patterns_for_client_query_exception(caplog):
    """Verifica que si la consulta SQL lanza una excepción no-NotFound, la propague tras registrar ERROR."""
    mock_client = MagicMock()
    mock_client.query.side_effect = Exception("Query timeout in BigQuery")

    service = BigQueryService(client=mock_client)
    with caplog.at_level(logging.ERROR, logger="app.services.bigquery_service"):
        with pytest.raises(Exception, match="Query timeout in BigQuery"):
            await service.get_friction_patterns_for_client(
                client_id="cliente_1",
                batch_date="2026-10-28",
                region="us",
                project_id="test-proj",
            )

    error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert any(getattr(r, "region", None) == "us" for r in error_records)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_friction_patterns_for_client_not_found_returns_empty():
    """Verifica que si falta la tabla de patrones o sesiones (NotFound), retorne lista vacía."""
    mock_client = MagicMock()
    mock_client.query.side_effect = NotFound("Table patrones not found")

    service = BigQueryService(client=mock_client)
    traces = await service.get_friction_patterns_for_client(
        client_id="cliente_1",
        batch_date="2026-10-28",
        region="us",
        project_id="test-proj",
    )
    assert traces == []


@pytest.mark.unit
def test_sync_query_patterns_not_connected():
    """Verifica que _sync_query_patterns lance RuntimeError si el cliente es None."""
    service = BigQueryService(client=None)
    service.client = None
    with pytest.raises(RuntimeError, match="No hay cliente BigQuery activo"):
        service._sync_query_patterns("SELECT 1", bigquery.QueryJobConfig())


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_exploration_report_idempotent_alias(sample_report):
    """Verifica que save_exploration_report_idempotent ejecute DELETE previo y luego inserte."""
    mock_client = MagicMock()
    mock_client.insert_rows_json.return_value = []

    service = BigQueryService(client=mock_client)
    success = await service.save_exploration_report_idempotent(
        report=sample_report,
        project_id="test-proj",
    )
    assert success is True
    mock_client.insert_rows_json.assert_called_once()
    mock_client.query.assert_called_once()
    delete_sql = mock_client.query.call_args[0][0]
    assert "WHERE id_cliente = @id_cliente" in delete_sql
    assert "AND id_patron = @id_patron" in delete_sql
    assert "AND CAST(fecha_exploracion AS STRING) = @fecha_exploracion" in delete_sql


@pytest.mark.unit
def test_sync_delete_existing_edge_cases():
    """Verifica comportamiento de _sync_delete_existing ante NotFound y excepciones."""
    service = BigQueryService(client=None)
    service.client = None
    assert service._sync_delete_existing("tabla", "cli", "pat", "2026-10-28") is False

    mock_client = MagicMock()
    mock_client.query.side_effect = NotFound("Table not found")
    service.client = mock_client
    assert service._sync_delete_existing("tabla", "cli", "pat", "2026-10-28") is True

    mock_client.query.side_effect = Exception("Falla de red")
    assert service._sync_delete_existing("tabla", "cli", "pat", "2026-10-28") is False

    mock_client.query.side_effect = Exception(
        "UPDATE or DELETE statement over table would affect rows in the streaming buffer, which is not supported"
    )
    assert service._sync_delete_existing("tabla", "cli", "pat", "2026-10-28") is True


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_exploration_report_non_idempotent(sample_report):
    """Verifica que save_exploration_report con idempotent=False no ejecute query de borrado."""
    mock_client = MagicMock()
    mock_client.insert_rows_json.return_value = []

    service = BigQueryService(client=mock_client)
    success = await service.save_exploration_report(
        report=sample_report,
        project_id="test-proj",
        idempotent=False,
    )
    assert success is True
    mock_client.insert_rows_json.assert_called_once()
    mock_client.query.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_friction_patterns_deserialization_error_handled():
    """Verifica que si una fila no se puede deserializar, se capture el error y se continúe."""
    mock_client = MagicMock()
    mock_job = MagicMock()

    class MockBadDataRow:
        def items(self):
            return {"sin_id_patron": "bad"}.items()

    mock_job.result.return_value = [MockBadDataRow()]
    mock_client.query.return_value = mock_job

    service = BigQueryService(client=mock_client)
    traces = await service.get_friction_patterns_for_client(
        client_id="cli_err",
        batch_date="2026-10-28",
        project_id="test-proj",
    )
    assert traces == []


@pytest.mark.unit
def test_sync_insert_not_connected():
    """Verifica que _sync_insert retorne False si el cliente es None."""
    service = BigQueryService(client=None)
    service.client = None
    assert service._sync_insert("table_ref", {}, idempotent=False) is False


@pytest.mark.unit
def test_sync_ensure_exploration_table_exists_not_connected():
    """Verifica que _sync_ensure_exploration_table_exists retorne False sin cliente."""
    service = BigQueryService(client=None)
    service.client = None
    assert service._sync_ensure_exploration_table_exists("proj.ds.tbl") is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_ensure_exploration_table_exists_already_exists():
    """Verifica que si la tabla ya existe, no se invoque create_table y retorne True."""
    mock_client = MagicMock()
    mock_client.get_table.return_value = MagicMock()

    service = BigQueryService(client=mock_client)
    assert await service.ensure_exploration_table_exists(project_id="pruebas-pfi") is True
    mock_client.get_table.assert_called_once_with(
        f"pruebas-pfi.friccion_resultados.{service.settings.BIGQUERY_TABLE_NAME}"
    )
    mock_client.create_table.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_ensure_exploration_table_exists_creates_when_not_found():
    """Verifica que si no existe la tabla (NotFound), se cree con clustering (id_cliente, id_patron)."""
    mock_client = MagicMock()
    mock_client.get_table.side_effect = NotFound("Table not found")

    service = BigQueryService(client=mock_client)
    assert await service.ensure_exploration_table_exists(project_id="pruebas-pfi") is True
    mock_client.create_table.assert_called_once()
    table_arg = mock_client.create_table.call_args[0][0]
    assert table_arg.time_partitioning is None
    assert table_arg.clustering_fields == ["id_cliente", "id_patron"]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_ensure_exploration_table_exists_handles_errors_and_edge_cases():
    """Verifica manejo de errores y bordes en ensure_exploration_table_exists."""
    mock_client = MagicMock()
    mock_client.get_table.side_effect = NotFound("Table not found")
    mock_client.create_table.side_effect = RuntimeError("Permission denied")
    assert await BigQueryService(client=mock_client).ensure_exploration_table_exists() is False

    mock_client_err = MagicMock()
    mock_client_err.get_table.side_effect = RuntimeError("Connection dropped")
    assert await BigQueryService(client=mock_client_err).ensure_exploration_table_exists() is False

    service_none = BigQueryService(client=None)
    service_none.client = None
    assert await service_none.ensure_exploration_table_exists() is False

    mock_client_noproj = MagicMock()
    mock_client_noproj.project = None
    service_no_proj = BigQueryService(client=mock_client_noproj)
    service_no_proj.project_id = None
    with patch.object(service_no_proj.settings, "PLATFORM_GCP_PROJECT_ID", None):
        assert await service_no_proj.ensure_exploration_table_exists(project_id=None) is False
