"""Pruebas unitarias para el Job Runner de Cloud Run Jobs (app.job_runner)."""

from datetime import datetime, timezone
import os
from unittest.mock import AsyncMock, patch
import pytest
from app.job_runner import main_async, parse_args, run_client_job
from app.models.client_config import ClientInterfaceConfig, ClientSourceIntegration
from app.models.exploration_report import ExplorationReport, ExplorationStatus, VisualEvidence
from app.models.session_trace import DeviceInfo, SessionTrace, TraceEvent
from app.storage.base import StorageUploadError


@pytest.fixture
def sample_config() -> ClientInterfaceConfig:
    """Fixture de configuración de interfaz para pruebas."""
    return ClientInterfaceConfig(
        client_id="cliente_test",
        base_url="https://staging.test.com",
        requires_authentication=False,
    )


@pytest.fixture
def sample_patterns() -> list[SessionTrace]:
    """Fixture con dos patrones de fricción simulados."""
    return [
        SessionTrace(
            id_patron="pat_1",
            id_cliente="cliente_test",
            id_sesion="sesion_1",
            device_info=DeviceInfo(tipo_dispositivo="desktop"),
            events=[],
        ),
        SessionTrace(
            id_patron="pat_2",
            id_cliente="cliente_test",
            id_sesion="sesion_2",
            device_info=DeviceInfo(tipo_dispositivo="mobile"),
            events=[],
        ),
    ]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_run_client_job_missing_client_id():
    """Verifica que si no se provee client_id o es cadena vacía, retorne código de salida 1."""
    assert await run_client_job(None) == 1
    assert await run_client_job("   ") == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_run_client_job_supabase_connection_failure(sample_patterns):
    """Verifica que si hay patrones y Supabase lanza excepción fatal, se capture y retorne código 1."""
    mock_sb = AsyncMock()
    mock_sb.get_client_interface_config.side_effect = Exception("Supabase connection timeout")
    mock_sb.get_client_source_integration.return_value = None

    mock_bq = AsyncMock()
    mock_bq.get_friction_patterns_for_client.return_value = sample_patterns

    exit_code = await run_client_job(
        "cliente_1",
        supabase_service=mock_sb,
        bigquery_service=mock_bq,
    )
    assert exit_code == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_run_client_job_config_not_found(sample_patterns):
    """Verifica que si hay patrones pero no existe ClientInterfaceConfig en Supabase, retorne código 1."""
    mock_sb = AsyncMock()
    mock_sb.get_client_interface_config.return_value = None
    mock_sb.get_client_source_integration.return_value = None

    mock_bq = AsyncMock()
    mock_bq.get_friction_patterns_for_client.return_value = sample_patterns

    exit_code = await run_client_job(
        "cliente_1",
        supabase_service=mock_sb,
        bigquery_service=mock_bq,
    )
    assert exit_code == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_run_client_job_integration_error_handled(sample_config):
    """Verifica que fallos al consultar ClientSourceIntegration no detengan la ejecución."""
    mock_sb = AsyncMock()
    mock_sb.get_client_interface_config.return_value = sample_config
    mock_sb.get_client_source_integration.side_effect = Exception("Error no crítico en integraciones")

    mock_bq = AsyncMock()
    mock_bq.get_friction_patterns_for_client.return_value = []

    exit_code = await run_client_job(
        "cliente_test",
        supabase_service=mock_sb,
        bigquery_service=mock_bq,
    )
    assert exit_code == 0
    mock_bq.get_friction_patterns_for_client.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_run_client_job_bigquery_query_failure(sample_config):
    """Verifica que si la consulta a BigQuery falla con excepción fatal, retorne código 1."""
    mock_sb = AsyncMock()
    mock_sb.get_client_interface_config.return_value = sample_config
    mock_sb.get_client_source_integration.return_value = None

    mock_bq = AsyncMock()
    mock_bq.get_friction_patterns_for_client.side_effect = Exception("BigQuery quota exceeded")

    exit_code = await run_client_job(
        "cliente_test",
        supabase_service=mock_sb,
        bigquery_service=mock_bq,
    )
    assert exit_code == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_run_client_job_no_patterns_found(sample_config):
    """Verifica que si no hay patrones para procesar, finalice exitosamente con código 0."""
    mock_sb = AsyncMock()
    mock_sb.get_client_interface_config.return_value = sample_config
    mock_sb.get_client_source_integration.return_value = None

    mock_bq = AsyncMock()
    mock_bq.get_friction_patterns_for_client.return_value = []

    exit_code = await run_client_job(
        "cliente_test",
        batch_date="2026-10-29",
        supabase_service=mock_sb,
        bigquery_service=mock_bq,
    )
    assert exit_code == 0


@pytest.mark.asyncio
@pytest.mark.unit
async def test_run_client_job_full_success(sample_config, sample_patterns):
    """Verifica la ejecución exitosa de múltiples patrones con persistencia de evidencias y reportes."""
    mock_sb = AsyncMock()
    mock_sb.get_client_interface_config.return_value = sample_config
    mock_sb.get_client_source_integration.return_value = ClientSourceIntegration(
        cliente_id="cliente_test",
        client_gcp_project_id="test-proj",
        gcp_region="southamerica-east1",
    )

    mock_bq = AsyncMock()
    mock_bq.get_friction_patterns_for_client.return_value = sample_patterns
    mock_bq.ensure_exploration_table_exists.return_value = True
    mock_bq.save_exploration_report.return_value = True

    mock_mgr = AsyncMock()
    mock_report = ExplorationReport(
        id_patron="pat_1",
        id_cliente="cliente_test",
        id_sesion="sesion_1",
        fecha_exploracion="2026-10-29",
        status=ExplorationStatus.COMPLETED,
        total_steps=1,
        completed_steps=1,
        started_at="2026-10-29T12:00:00Z",
        finished_at="2026-10-29T12:01:00Z",
    )

    with patch("app.job_runner.TraceExecutor") as MockExecutor, \
         patch("app.job_runner.get_storage_provider") as mock_storage_factory:
        mock_storage = AsyncMock()
        mock_storage.save_evidence.return_value = "gs://bucket/test.webp"
        mock_storage_factory.return_value = mock_storage

        executor_instance = AsyncMock()
        executor_instance.execute_trace.return_value = mock_report
        MockExecutor.return_value = executor_instance

        exit_code = await run_client_job(
            "cliente_test",
            batch_date="2026-10-29",
            supabase_service=mock_sb,
            bigquery_service=mock_bq,
            browser_manager=mock_mgr,
        )

        assert exit_code == 0
        assert executor_instance.execute_trace.await_count == 2
        assert mock_bq.save_exploration_report.await_count == 2
        # Verificar que la función interna de guardado de evidencias funcione
        evidence_saver = MockExecutor.call_args[1]["evidence_saver"]
        saved_url = await evidence_saver(b"data", "test.webp", 0)
        assert saved_url == "gs://bucket/test.webp"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_run_client_job_trace_step_error_non_fatal(sample_config, sample_patterns):
    """Verifica que un fallo individual en una traza se capture como error no fatal y continúe."""
    mock_sb = AsyncMock()
    mock_sb.get_client_interface_config.return_value = sample_config
    mock_sb.get_client_source_integration.return_value = None

    mock_bq = AsyncMock()
    mock_bq.get_friction_patterns_for_client.return_value = sample_patterns
    mock_bq.ensure_exploration_table_exists.return_value = True
    mock_bq.save_exploration_report.return_value = True

    mock_mgr = AsyncMock()

    with patch("app.job_runner.TraceExecutor") as MockExecutor, \
         patch("app.job_runner.get_storage_provider"):
        executor_instance = AsyncMock()
        # Primer traza lanza excepción, segunda tiene éxito
        executor_instance.execute_trace.side_effect = [
            Exception("Navigation error in test site"),
            ExplorationReport(
                id_patron="pat_2",
                id_cliente="cliente_test",
                id_sesion="sesion_2",
                fecha_exploracion="2026-10-29",
                status=ExplorationStatus.COMPLETED,
                total_steps=1,
                completed_steps=1,
                started_at="2026-10-29T12:00:00Z",
                finished_at="2026-10-29T12:01:00Z",
            ),
        ]
        MockExecutor.return_value = executor_instance

        exit_code = await run_client_job(
            "cliente_test",
            batch_date="2026-10-29",
            supabase_service=mock_sb,
            bigquery_service=mock_bq,
            browser_manager=mock_mgr,
        )

        assert exit_code == 0
        assert executor_instance.execute_trace.await_count == 2
        # Solo la segunda traza exitosa debió persistir
        assert mock_bq.save_exploration_report.await_count == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_run_client_job_lifecycle_managed_automatically(sample_config, sample_patterns):
    """Verifica que si no se inyecta BrowserManager, se creen y gestionen start() y close() automáticamente."""
    mock_sb = AsyncMock()
    mock_sb.get_client_interface_config.return_value = sample_config
    mock_sb.get_client_source_integration.return_value = None

    mock_bq = AsyncMock()
    mock_bq.get_friction_patterns_for_client.return_value = sample_patterns
    mock_bq.ensure_exploration_table_exists.return_value = True
    mock_bq.save_exploration_report.return_value = True

    mock_mgr_instance = AsyncMock()

    with patch("app.job_runner.BrowserManager", return_value=mock_mgr_instance), \
         patch("app.job_runner.TraceExecutor") as MockExecutor, \
         patch("app.job_runner.get_storage_provider"):
        executor_instance = AsyncMock()
        executor_instance.execute_trace.return_value = ExplorationReport(
            id_patron="pat_1",
            id_cliente="cliente_test",
            id_sesion="sesion_auto",
            fecha_exploracion="2026-10-29",
            status=ExplorationStatus.COMPLETED,
            total_steps=1,
            completed_steps=1,
            started_at="2026-10-29T12:00:00Z",
            finished_at="2026-10-29T12:01:00Z",
        )
        MockExecutor.return_value = executor_instance

        exit_code = await run_client_job(
            "cliente_test",
            batch_date="2026-10-29",
            supabase_service=mock_sb,
            bigquery_service=mock_bq,
            browser_manager=None,
        )

        assert exit_code == 0
        mock_mgr_instance.start.assert_awaited_once()
        mock_mgr_instance.close.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_run_client_job_fatal_exception_in_loop(sample_config, sample_patterns):
    """Verifica que una excepción fatal no controlada cierre el navegador y retorne código 1."""
    mock_sb = AsyncMock()
    mock_sb.get_client_interface_config.return_value = sample_config
    mock_sb.get_client_source_integration.return_value = None

    mock_bq = AsyncMock()
    mock_bq.get_friction_patterns_for_client.return_value = sample_patterns

    mock_mgr_instance = AsyncMock()

    with patch("app.job_runner.BrowserManager", return_value=mock_mgr_instance), \
         patch("app.job_runner.TraceExecutor", side_effect=RuntimeError("Fatal runtime memory fault")), \
         patch("app.job_runner.get_storage_provider"):
        exit_code = await run_client_job(
            "cliente_test",
            batch_date="2026-10-29",
            supabase_service=mock_sb,
            bigquery_service=mock_bq,
            browser_manager=None,
        )

        assert exit_code == 1
        mock_mgr_instance.start.assert_awaited_once()
        mock_mgr_instance.close.assert_awaited_once()


@pytest.mark.unit
def test_parse_args_defaults():
    """Verifica los valores por defecto del parser CLI (batch_date es hoy en UTC)."""
    with patch.dict(os.environ, {}, clear=True):
        args = parse_args([])
        today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert args.batch_date == today_utc
        assert args.client_id is None
        assert args.region is None


@pytest.mark.unit
def test_parse_args_explicit_flags():
    """Verifica que los flags explícitos sobreescriban los valores por defecto."""
    args = parse_args([
        "--client-id", "cliente_xyz",
        "--batch-date", "2026-10-29",
        "--region", "us-central1",
        "--storage-provider", "gcs",
    ])
    assert args.client_id == "cliente_xyz"
    assert args.batch_date == "2026-10-29"
    assert args.region == "us-central1"
    assert args.storage_provider == "gcs"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_main_async():
    """Verifica que main_async conecte los argumentos procesados con run_client_job."""
    with patch("app.job_runner.run_client_job", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = 0
        code = await main_async([
            "--client-id", "cliente_cli",
            "--batch-date", "2026-10-29",
            "--max-concurrency", "2",
            "--storage-provider", "gcs",
        ])
        assert code == 0
        mock_run.assert_awaited_once_with(
            client_id="cliente_cli",
            batch_date="2026-10-29",
            region=None,
            max_concurrency=2,
            storage_provider="gcs",
        )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_run_client_job_concurrency_bounded_to_max_3(sample_config):
    """Verifica que nunca se ejecuten más de 3 patrones en simultáneo."""
    import asyncio

    patterns = [
        SessionTrace(id_patron=f"p_{i}", id_cliente="cliente_test", id_sesion=f"s_{i}", events=[])
        for i in range(6)
    ]

    mock_sb = AsyncMock()
    mock_sb.get_client_interface_config.return_value = sample_config
    mock_sb.get_client_source_integration.return_value = None

    mock_bq = AsyncMock()
    mock_bq.get_friction_patterns_for_client.return_value = patterns
    mock_bq.save_exploration_report.return_value = True

    mock_mgr = AsyncMock()

    active_executions = 0
    max_observed_concurrency = 0

    async def fake_execute_trace(trace, config):
        nonlocal active_executions, max_observed_concurrency
        active_executions += 1
        if active_executions > max_observed_concurrency:
            max_observed_concurrency = active_executions
        await asyncio.sleep(0.01)
        active_executions -= 1
        return ExplorationReport(
            id_patron=trace.id_patron,
            id_cliente="cliente_test",
            id_sesion=trace.id_sesion,
            fecha_exploracion="2026-10-29",
            status=ExplorationStatus.COMPLETED,
            total_steps=1,
            completed_steps=1,
            started_at="2026-10-29T12:00:00Z",
            finished_at="2026-10-29T12:00:01Z",
        )

    with patch("app.job_runner.TraceExecutor") as MockExecutor, \
         patch("app.job_runner.get_storage_provider"):
        executor_instance = AsyncMock()
        executor_instance.execute_trace.side_effect = fake_execute_trace
        MockExecutor.return_value = executor_instance

        exit_code = await run_client_job(
            "cliente_test",
            batch_date="2026-10-29",
            max_concurrency=3,
            supabase_service=mock_sb,
            bigquery_service=mock_bq,
            browser_manager=mock_mgr,
        )

        assert exit_code == 0
        assert max_observed_concurrency <= 3
        assert executor_instance.execute_trace.await_count == 6


@pytest.mark.unit
def test_main_entrypoint():
    """Verifica que main() invoque asyncio.run y sys.exit con el código retornado."""
    def fake_run(coro):
        coro.close()
        return 0

    with patch("app.job_runner.asyncio.run", side_effect=fake_run) as mock_async_run, \
         patch("app.job_runner.sys.exit") as mock_exit, \
         patch("app.job_runner.configure_logging") as mock_cfg_log:
        from app.job_runner import main
        main()
        mock_cfg_log.assert_called_once()
        mock_async_run.assert_called_once()
        mock_exit.assert_called_once_with(0)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_run_client_job_zero_patterns_guard_without_config_or_browser():
    """Verifica la cláusula de guarda: 0 patrones retorna 0 sin config en Supabase ni BrowserManager."""
    mock_sb = AsyncMock()
    mock_sb.get_client_interface_config.return_value = None
    mock_sb.get_client_source_integration.return_value = None

    mock_bq = AsyncMock()
    mock_bq.get_friction_patterns_for_client.return_value = []

    with patch("app.job_runner.BrowserManager") as mock_mgr_cls:
        exit_code = await run_client_job(
            "cliente_sin_patrones",
            batch_date="2026-11-15",
            supabase_service=mock_sb,
            bigquery_service=mock_bq,
        )

    assert exit_code == 0
    mock_mgr_cls.assert_not_called()
    mock_bq.ensure_exploration_table_exists.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_run_client_job_ensure_table_fails_returns_1(sample_config, sample_patterns):
    """Verifica que si ensure_exploration_table_exists retorna False, aborte con código 1."""
    mock_sb = AsyncMock()
    mock_sb.get_client_interface_config.return_value = sample_config
    mock_sb.get_client_source_integration.return_value = None

    mock_bq = AsyncMock()
    mock_bq.get_friction_patterns_for_client.return_value = sample_patterns
    mock_bq.ensure_exploration_table_exists.return_value = False

    with patch("app.job_runner.BrowserManager") as mock_mgr_cls:
        exit_code = await run_client_job(
            "cliente_test",
            batch_date="2026-11-15",
            supabase_service=mock_sb,
            bigquery_service=mock_bq,
        )

    assert exit_code == 1
    mock_mgr_cls.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_run_client_job_save_report_false_returns_1(sample_config, sample_patterns):
    """Verifica que si save_exploration_report retorna False, cierre el navegador y retorne 1."""
    mock_sb = AsyncMock()
    mock_sb.get_client_interface_config.return_value = sample_config
    mock_sb.get_client_source_integration.return_value = None

    mock_bq = AsyncMock()
    mock_bq.get_friction_patterns_for_client.return_value = sample_patterns
    mock_bq.ensure_exploration_table_exists.return_value = True
    mock_bq.save_exploration_report.return_value = False

    mock_mgr_instance = AsyncMock()
    mock_report = ExplorationReport(
        id_patron="pat_1",
        id_cliente="cliente_test",
        id_sesion="sesion_1",
        fecha_exploracion="2026-11-15",
        status=ExplorationStatus.COMPLETED,
        total_steps=1,
        completed_steps=1,
        started_at="2026-11-15T12:00:00Z",
        finished_at="2026-11-15T12:01:00Z",
    )

    with patch("app.job_runner.BrowserManager", return_value=mock_mgr_instance), \
         patch("app.job_runner.TraceExecutor") as MockExecutor, \
         patch("app.job_runner.get_storage_provider"):
        executor_instance = AsyncMock()
        executor_instance.execute_trace.return_value = mock_report
        MockExecutor.return_value = executor_instance

        exit_code = await run_client_job(
            "cliente_test",
            batch_date="2026-11-15",
            supabase_service=mock_sb,
            bigquery_service=mock_bq,
        )

    assert exit_code == 1
    mock_mgr_instance.close.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_run_client_job_storage_upload_error_returns_1(sample_config, sample_patterns):
    """Verifica que StorageUploadError en execute_trace aborte el job con código 1."""
    mock_sb = AsyncMock()
    mock_sb.get_client_interface_config.return_value = sample_config
    mock_sb.get_client_source_integration.return_value = None

    mock_bq = AsyncMock()
    mock_bq.get_friction_patterns_for_client.return_value = sample_patterns
    mock_bq.ensure_exploration_table_exists.return_value = True

    mock_mgr_instance = AsyncMock()

    with patch("app.job_runner.BrowserManager", return_value=mock_mgr_instance), \
         patch("app.job_runner.TraceExecutor") as MockExecutor, \
         patch("app.job_runner.get_storage_provider"):
        executor_instance = AsyncMock()
        executor_instance.execute_trace.side_effect = StorageUploadError("GCS write failed")
        MockExecutor.return_value = executor_instance

        exit_code = await run_client_job(
            "cliente_test",
            batch_date="2026-11-15",
            supabase_service=mock_sb,
            bigquery_service=mock_bq,
        )

    assert exit_code == 1
    mock_mgr_instance.close.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_run_client_job_all_patterns_failed_step_zero_returns_1(sample_config, sample_patterns):
    """Verifica que si todos los patrones fallan en el paso 0, el job retorne 1 (caída general)."""
    mock_sb = AsyncMock()
    mock_sb.get_client_interface_config.return_value = sample_config
    mock_sb.get_client_source_integration.return_value = None

    mock_bq = AsyncMock()
    mock_bq.get_friction_patterns_for_client.return_value = sample_patterns
    mock_bq.ensure_exploration_table_exists.return_value = True
    mock_bq.save_exploration_report.return_value = True

    failed_reports = [
        ExplorationReport(
            id_patron=f"pat_{i}",
            id_cliente="cliente_test",
            id_sesion=f"sesion_{i}",
            fecha_exploracion="2026-11-15",
            status=ExplorationStatus.FAILED,
            total_steps=2,
            completed_steps=0,
            started_at="2026-11-15T12:00:00Z",
            finished_at="2026-11-15T12:01:00Z",
        )
        for i in (1, 2)
    ]

    with patch("app.job_runner.TraceExecutor") as MockExecutor, \
         patch("app.job_runner.get_storage_provider"):
        executor_instance = AsyncMock()
        executor_instance.execute_trace.side_effect = failed_reports
        MockExecutor.return_value = executor_instance

        exit_code = await run_client_job(
            "cliente_test",
            batch_date="2026-11-15",
            supabase_service=mock_sb,
            bigquery_service=mock_bq,
            browser_manager=AsyncMock(),
        )

    assert exit_code == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_run_client_job_mixed_failed_and_completed_logs_warning_and_returns_0(
    sample_config,
    sample_patterns,
    caplog,
):
    """Verifica que si un patrón falla pero otro avanza, registre WARNING y retorne 0."""
    import logging

    mock_sb = AsyncMock()
    mock_sb.get_client_interface_config.return_value = sample_config
    mock_sb.get_client_source_integration.return_value = None

    mock_bq = AsyncMock()
    mock_bq.get_friction_patterns_for_client.return_value = sample_patterns
    mock_bq.ensure_exploration_table_exists.return_value = True
    mock_bq.save_exploration_report.return_value = True

    reports = [
        ExplorationReport(
            id_patron="pat_1",
            id_cliente="cliente_test",
            id_sesion="sesion_1",
            fecha_exploracion="2026-11-15",
            status=ExplorationStatus.FAILED,
            total_steps=2,
            completed_steps=0,
            started_at="2026-11-15T12:00:00Z",
            finished_at="2026-11-15T12:01:00Z",
        ),
        ExplorationReport(
            id_patron="pat_2",
            id_cliente="cliente_test",
            id_sesion="sesion_2",
            fecha_exploracion="2026-11-15",
            status=ExplorationStatus.COMPLETED,
            total_steps=1,
            completed_steps=1,
            started_at="2026-11-15T12:00:00Z",
            finished_at="2026-11-15T12:01:00Z",
            evidences=[
                VisualEvidence(
                    orden=0,
                    nombre_evento="page_view",
                    ruta="/inicio",
                    screenshot_url="gs://bucket/capturas/cliente_test/2026-11-15/pat_2_0.webp",
                    timestamp="2026-11-15T12:00:30Z",
                )
            ],
        ),
    ]

    with patch("app.job_runner.TraceExecutor") as MockExecutor, \
         patch("app.job_runner.get_storage_provider"):
        executor_instance = AsyncMock()
        executor_instance.execute_trace.side_effect = reports
        MockExecutor.return_value = executor_instance

        with caplog.at_level(logging.INFO, logger="eureka_job_runner"):
            exit_code = await run_client_job(
                "cliente_test",
                batch_date="2026-11-15",
                supabase_service=mock_sb,
                bigquery_service=mock_bq,
                browser_manager=AsyncMock(),
            )

    assert exit_code == 0
    assert any(r.levelno == logging.WARNING and getattr(r, "id_patron", None) == "pat_1" for r in caplog.records)
    summary_records = [r for r in caplog.records if "Exploración finalizada" in r.getMessage()]
    assert len(summary_records) == 1
    assert summary_records[0].patrones_explorados == 1
    assert summary_records[0].capturas_generadas == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_run_client_job_selective_concurrency_and_precleanup():
    """Verifica ejecución paralela para patrones anónimos y secuencial=1 + pre-limpieza para autenticados."""
    from app.models.session_trace import TraceEvent

    auth_config = ClientInterfaceConfig(
        client_id="cliente_auth",
        base_url="https://staging.test.com",
        storage_state={"cookies": [{"name": "sid", "value": "1"}], "origins": []},
    )
    pat_anon = SessionTrace(
        id_patron="pat_anon",
        id_cliente="cliente_auth",
        id_sesion="ses_anon",
        events=[TraceEvent(orden=1, nombre_evento="view_login", ruta="/checkout?show=basket")],
    )
    pat_auth_1 = SessionTrace(
        id_patron="pat_auth_1",
        id_cliente="cliente_auth",
        id_sesion="ses_a1",
        events=[TraceEvent(orden=1, nombre_evento="login", ruta="/")],
    )
    pat_auth_2 = SessionTrace(
        id_patron="pat_auth_2",
        id_cliente="cliente_auth",
        id_sesion="ses_a2",
        events=[TraceEvent(orden=1, nombre_evento="add_billing_info", ruta="/checkout?show=multibillto")],
    )

    mock_sb = AsyncMock()
    mock_sb.get_client_interface_config.return_value = auth_config
    mock_bq = AsyncMock()
    mock_bq.get_friction_patterns_for_client.return_value = [pat_anon, pat_auth_1, pat_auth_2]
    mock_bq.ensure_exploration_table_exists.return_value = True
    mock_bq.save_exploration_report.return_value = True

    calls = []

    async def _fake_exec(trace: SessionTrace, config: ClientInterfaceConfig, allow_session_auth: bool = True):
        calls.append((trace.id_patron, allow_session_auth))
        return ExplorationReport(
            id_patron=trace.id_patron,
            id_cliente="cliente_auth",
            id_sesion=trace.id_sesion,
            fecha_exploracion="2026-11-16",
            status=ExplorationStatus.COMPLETED,
            total_steps=1,
            completed_steps=1,
            started_at="2026-11-16T12:00:00Z",
            finished_at="2026-11-16T12:00:05Z",
            evidences=[],
        )

    with (
        patch("app.job_runner.TraceExecutor") as MockExecutor,
        patch("app.job_runner.get_storage_provider"),
    ):
        executor_instance = AsyncMock()
        executor_instance.execute_trace.side_effect = _fake_exec
        MockExecutor.return_value = executor_instance

        exit_code = await run_client_job(
            "cliente_auth",
            batch_date="2026-11-16",
            max_concurrency=3,
            supabase_service=mock_sb,
            bigquery_service=mock_bq,
            browser_manager=AsyncMock(),
        )

    assert exit_code == 0
    executor_instance.cleanup_client_session_state.assert_awaited_once_with(auth_config)
    assert calls == [
        ("pat_anon", False),
        ("pat_auth_1", True),
        ("pat_auth_2", True),
    ]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_run_client_job_filters_target_pattern_ids() -> None:
    """Verifica que target_pattern_ids acote la corrida a los IDs especificados."""
    p1 = SessionTrace(
        id_patron="pat_keep",
        id_cliente="cli_f",
        id_sesion="s1",
        events=[TraceEvent(orden=1, nombre_evento="page_view", ruta="/")],
    )
    p2 = SessionTrace(
        id_patron="pat_drop",
        id_cliente="cli_f",
        id_sesion="s2",
        events=[TraceEvent(orden=1, nombre_evento="page_view", ruta="/shop")],
    )

    mock_sb = AsyncMock()
    mock_sb.get_client_interface_config.return_value = ClientInterfaceConfig(
        client_id="cli_f",
        base_url="https://tienda.com",
    )
    mock_bq = AsyncMock()
    mock_bq.get_friction_patterns_for_client.return_value = [p1, p2]
    mock_bq.ensure_exploration_table_exists.return_value = True
    mock_bq.save_exploration_report.return_value = True

    executed = []

    async def _fake_exec(trace: SessionTrace, config: ClientInterfaceConfig, allow_session_auth: bool = True):
        executed.append(trace.id_patron)
        return ExplorationReport(
            id_patron=trace.id_patron,
            id_cliente="cli_f",
            id_sesion=trace.id_sesion,
            fecha_exploracion="2026-11-16",
            status=ExplorationStatus.COMPLETED,
            total_steps=1,
            completed_steps=1,
            started_at="2026-11-16T12:00:00Z",
            finished_at="2026-11-16T12:00:05Z",
            evidences=[],
        )

    with (
        patch("app.job_runner.TraceExecutor") as MockExecutor,
        patch("app.job_runner.get_storage_provider"),
    ):
        ex = AsyncMock()
        ex.execute_trace.side_effect = _fake_exec
        MockExecutor.return_value = ex

        exit_code = await run_client_job(
            "cli_f",
            batch_date="2026-11-16",
            supabase_service=mock_sb,
            bigquery_service=mock_bq,
            browser_manager=AsyncMock(),
            target_pattern_ids={"pat_keep"},
        )

    assert exit_code == 0
    assert executed == ["pat_keep"]
