"""Pruebas unitarias para el punto de entrada Cloud Run Job en app.main."""

import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.config import Settings
from app.logging_config import fecha_ejecucion_ctx, id_cliente_ctx
from app.main import ejecutar_tarea, run_insights_job
from app.models.exploration_models import ExplorationReport
from app.models.response_models import ProcessClusterResponse
from app.services.bigquery_service import BigQueryServiceError
from app.services.llm_client import LLMClientError, LLMResponseValidationError
from app.services.supabase_service import SupabaseServiceError


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_insights_job_guard_clause_empty_reports(mock_settings: Settings) -> None:
    """Verifica salida 0 inmediata si BigQuery devuelve 0 reportes explorados."""
    mock_bq = MagicMock()
    mock_bq.get_completed_exploration_reports.return_value = []
    mock_proc = MagicMock()

    exit_code = await run_insights_job(
        client_id="cli-1",
        batch_date="2026-11-16",
        settings=mock_settings,
        bigquery_service=mock_bq,
        processor=mock_proc,
    )

    assert exit_code == 0
    mock_proc.supabase_service.get_existing_patterns_state.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_insights_job_all_skipped_no_llm_ready_call(
    mock_settings: Settings,
    sample_exploration_report: ExplorationReport,
) -> None:
    """Verifica que si todos los patrones coinciden en hash no se llama a ensure_model_ready."""
    mock_bq = MagicMock()
    mock_bq.get_completed_exploration_reports.return_value = [sample_exploration_report]

    mock_proc = MagicMock()
    mock_proc.supabase_service.get_existing_patterns_state.return_value = {
        sample_exploration_report.id_patron: {
            "has_diagnosis": True,
            "hash_exploracion": sample_exploration_report.compute_exploration_hash(),
        }
    }
    mock_proc.llm_client = AsyncMock()
    mock_proc.process_report = AsyncMock(
        return_value=ProcessClusterResponse(
            success=True,
            friccion_id=sample_exploration_report.id_patron,
            skipped_llm=True,
            metrics_updated=True,
        )
    )

    exit_code = await run_insights_job(
        client_id="cli-1",
        batch_date="2026-11-16",
        settings=mock_settings,
        bigquery_service=mock_bq,
        processor=mock_proc,
    )

    assert exit_code == 0
    mock_proc.llm_client.ensure_model_ready.assert_not_called()
    mock_proc.process_report.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_insights_job_success_and_isolated_failures(
    mock_settings: Settings,
    sample_exploration_report: ExplorationReport,
) -> None:
    """Verifica éxito completo y aislamiento de fallos por patrón puntual."""
    rep_ok = sample_exploration_report
    rep_val_err = sample_exploration_report.model_copy(update={"id_patron": "pat-val-err"})
    rep_conn_err = sample_exploration_report.model_copy(update={"id_patron": "pat-conn-err"})
    rep_unhandled = sample_exploration_report.model_copy(update={"id_patron": "pat-unhandled"})
    rep_skip = sample_exploration_report.model_copy(update={"id_patron": "pat-skip"})

    mock_bq = MagicMock()
    mock_bq.get_completed_exploration_reports.return_value = [
        rep_ok,
        rep_val_err,
        rep_conn_err,
        rep_unhandled,
        rep_skip,
    ]

    mock_proc = MagicMock()
    mock_proc.supabase_service.get_existing_patterns_state.return_value = {}
    mock_proc.llm_client = AsyncMock()
    mock_proc.process_report = AsyncMock(
        side_effect=[
            ProcessClusterResponse(success=True, friccion_id=rep_ok.id_patron, skipped_llm=False),
            LLMResponseValidationError("JSON inválido"),
            LLMClientError("Timeout de Pod"),
            RuntimeError("Fallo inesperado en patrón"),
            ProcessClusterResponse(success=True, friccion_id=rep_skip.id_patron, skipped_llm=True),
        ]
    )

    exit_code = await run_insights_job(
        client_id="cli-1",
        batch_date="2026-11-16",
        settings=mock_settings,
        bigquery_service=mock_bq,
        processor=mock_proc,
    )

    assert exit_code == 0
    mock_proc.llm_client.ensure_model_ready.assert_called_once()
    assert mock_proc.process_report.call_count == 5


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_insights_job_all_candidates_fail_returns_1(
    mock_settings: Settings,
    sample_exploration_report: ExplorationReport,
) -> None:
    """Verifica código de salida 1 cuando fallan todos los patrones con novedades."""
    mock_bq = MagicMock()
    mock_bq.get_completed_exploration_reports.return_value = [sample_exploration_report]

    mock_proc = MagicMock()
    mock_proc.supabase_service.get_existing_patterns_state.return_value = {}
    mock_proc.llm_client = AsyncMock()
    mock_proc.process_report = AsyncMock(side_effect=LLMClientError("Pod caído"))

    exit_code = await run_insights_job(
        client_id="cli-1",
        batch_date="2026-11-16",
        settings=mock_settings,
        bigquery_service=mock_bq,
        processor=mock_proc,
    )

    assert exit_code == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_insights_job_fatal_infrastructure_errors(
    mock_settings: Settings,
    sample_exploration_report: ExplorationReport,
) -> None:
    """Verifica retorno 1 ante fallos críticos de BigQuery, Supabase o inesperados."""
    # 1. Error en BigQuery
    mock_bq = MagicMock()
    mock_bq.get_completed_exploration_reports.side_effect = BigQueryServiceError("BQ error")
    assert await run_insights_job("c1", "2026-11-16", settings=mock_settings, bigquery_service=mock_bq) == 1

    # 2. Error fatal en Supabase durante process_report
    mock_bq.get_completed_exploration_reports.side_effect = None
    mock_bq.get_completed_exploration_reports.return_value = [sample_exploration_report]
    mock_proc = MagicMock()
    mock_proc.supabase_service.get_existing_patterns_state.return_value = {}
    mock_proc.llm_client = AsyncMock()
    mock_proc.process_report = AsyncMock(side_effect=SupabaseServiceError("Supabase caído"))
    assert (
        await run_insights_job(
            "c1",
            "2026-11-16",
            settings=mock_settings,
            bigquery_service=mock_bq,
            processor=mock_proc,
        )
        == 1
    )

    # 3. Excepción inesperada en nivel superior
    mock_bq.get_completed_exploration_reports.side_effect = RuntimeError("Error imprevisto")
    assert await run_insights_job("c1", "2026-11-16", settings=mock_settings, bigquery_service=mock_bq) == 1


@pytest.mark.unit
def test_ejecutar_tarea_env_resolution_and_exit_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica ejecutar_tarea con variables de Cloud Run Jobs, fuera de rango y error de entorno."""
    # 1. Ejecución exitosa para task index 1
    monkeypatch.setenv("FECHA_EJECUCION", "2026-11-16")
    monkeypatch.setenv("IDS_CLIENTES", json.dumps(["cli-0", "cli-1"]))
    monkeypatch.setenv("CLOUD_RUN_TASK_INDEX", "1")
    monkeypatch.setenv("CLOUD_RUN_TASK_ATTEMPT", "2")

    async def fake_run(client_id: str, batch_date: str, intento: int) -> int:
        assert client_id == "cli-1"
        assert batch_date == "2026-11-16"
        assert intento == 2
        assert fecha_ejecucion_ctx.get() == "2026-11-16"
        assert id_cliente_ctx.get() == "cli-1"
        return 0

    with patch("app.main.run_insights_job", side_effect=fake_run):
        with pytest.raises(SystemExit) as exc_info:
            ejecutar_tarea()
        assert exc_info.value.code == 0

    # 2. Índice fuera de rango -> exit(0)
    monkeypatch.setenv("CLOUD_RUN_TASK_INDEX", "5")
    with pytest.raises(SystemExit) as exc_out:
        ejecutar_tarea()
    assert exc_out.value.code == 0

    # 3. IDS_CLIENTES no es una lista -> exit(1)
    monkeypatch.setenv("CLOUD_RUN_TASK_INDEX", "0")
    monkeypatch.setenv("IDS_CLIENTES", json.dumps({"not": "a_list"}))
    with pytest.raises(SystemExit) as exc_bad_type:
        ejecutar_tarea()
    assert exc_bad_type.value.code == 1

    # 4. Variable FECHA_EJECUCION faltante -> exit(1)
    monkeypatch.delenv("FECHA_EJECUCION", raising=False)
    with pytest.raises(SystemExit) as exc_missing:
        ejecutar_tarea()
    assert exc_missing.value.code == 1
