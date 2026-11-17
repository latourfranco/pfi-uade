"""Pruebas unitarias para el orquestador InsightProcessor en app.core.processor."""

from unittest.mock import AsyncMock, MagicMock
import pytest

from app.config import Settings
from app.core.processor import InsightProcessor
from app.core.prompt_builder import PromptBuilder
from app.models.exploration_models import ExplorationEvidence, ExplorationReport
from app.models.llm_schemas import UxDiagnosticsOutput
from app.services.gcs_service import GCSService
from app.services.llm_client import LLMClient, LLMGenerationResult
from app.services.supabase_service import SupabaseService


@pytest.mark.unit
def test_processor_default_instantiation() -> None:
    """Verifica que InsightProcessor pueda instanciarse con defaults sin errores."""
    processor = InsightProcessor()
    assert processor.settings is not None
    assert processor.gcs_service is not None
    assert processor.llm_client is not None
    assert processor.prompt_builder is not None
    assert processor.supabase_service is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_processor_process_report_success_and_filter_non_pattern_notes(
    mock_settings: Settings,
    sample_exploration_report: ExplorationReport,
    sample_ux_diagnostics: UxDiagnosticsOutput,
) -> None:
    """Verifica el flujo completo y el filtrado de notas de pasos fuera del patrón."""
    # Agregamos un paso 3 de contexto (en_patron=False) y verificamos que se filtre del output
    ev_context = ExplorationEvidence(
        orden=3,
        nombre_evento="page_view",
        ruta="https://shop.merch.google/",
        en_patron=False,
        screenshot_url="gs://b/3.webp",
    )
    report_with_ctx = sample_exploration_report.model_copy(
        update={"evidences": [*sample_exploration_report.evidences, ev_context]}
    )

    extra_note = sample_ux_diagnostics.journey_step_notes[0].model_copy(update={"step_number": 3})
    diag_with_extra = sample_ux_diagnostics.model_copy(
        update={"journey_step_notes": [*sample_ux_diagnostics.journey_step_notes, extra_note]}
    )

    mock_gcs = MagicMock(spec=GCSService)
    mock_gcs.resolve_step_images_base64.return_value = {1: "data:image/webp;base64,AAAA"}

    mock_prompt_builder = MagicMock(spec=PromptBuilder)
    mock_prompt_builder.build_payload_from_report.return_value = {"messages": []}

    mock_llm = AsyncMock(spec=LLMClient)
    mock_llm.generate_diagnostics.return_value = LLMGenerationResult(
        output=diag_with_extra,
        prompt_tokens=210,
        completion_tokens=520,
        model_name="cyankiwi/Qwen3.5-27B-AWQ-4bit",
    )

    mock_supabase = MagicMock(spec=SupabaseService)
    mock_supabase.save_diagnostics.return_value = {"diagnostico_id": "report-diag-uuid", "notas_count": 2}

    processor = InsightProcessor(
        gcs_service=mock_gcs,
        llm_client=mock_llm,
        prompt_builder=mock_prompt_builder,
        supabase_service=mock_supabase,
        settings=mock_settings,
    )

    response = await processor.process_report(report_with_ctx, persist=True, existing_state=None)

    assert response.success is True
    assert response.friccion_id == report_with_ctx.id_patron
    assert response.diagnostico_id == "report-diag-uuid"
    assert response.notas_count == 2
    assert response.skipped_llm is False
    assert response.metrics_updated is False
    assert response.diagnostico is not None
    assert [n.step_number for n in response.diagnostico.journey_step_notes] == [1, 2]

    mock_supabase.save_diagnostics.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_processor_process_report_dry_run_and_changed_hash(
    mock_settings: Settings,
    sample_exploration_report: ExplorationReport,
    sample_ux_diagnostics: UxDiagnosticsOutput,
) -> None:
    """Verifica dry-run y re-procesamiento cuando cambia el hash de exploración."""
    mock_gcs = MagicMock(spec=GCSService)
    mock_gcs.resolve_step_images_base64.return_value = {}
    mock_prompt_builder = MagicMock(spec=PromptBuilder)
    mock_prompt_builder.build_payload_from_report.return_value = {}
    mock_llm = AsyncMock(spec=LLMClient)
    mock_llm.generate_diagnostics.return_value = LLMGenerationResult(
        output=sample_ux_diagnostics,
        prompt_tokens=50,
        completion_tokens=100,
        model_name="model-x",
    )
    mock_supabase = MagicMock(spec=SupabaseService)

    processor = InsightProcessor(
        gcs_service=mock_gcs,
        llm_client=mock_llm,
        prompt_builder=mock_prompt_builder,
        supabase_service=mock_supabase,
        settings=mock_settings,
    )

    stale_state = {"has_diagnosis": True, "hash_exploracion": "old_different_hash"}
    response = await processor.process_report(
        sample_exploration_report,
        persist=False,
        existing_state=stale_state,
    )

    assert response.success is True
    assert response.diagnostico_id is None
    assert response.skipped_llm is False
    assert "dry-run" in response.message
    mock_llm.generate_diagnostics.assert_called_once()
    mock_supabase.save_diagnostics.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_processor_incremental_skip_and_metrics_update(
    mock_settings: Settings,
    sample_exploration_report: ExplorationReport,
) -> None:
    """Verifica omisión del LLM cuando no hay novedades en pasos y actualización solo de métricas."""
    mock_gcs = MagicMock(spec=GCSService)
    mock_prompt_builder = MagicMock(spec=PromptBuilder)
    mock_llm = AsyncMock(spec=LLMClient)
    mock_supabase = MagicMock(spec=SupabaseService)

    processor = InsightProcessor(
        gcs_service=mock_gcs,
        llm_client=mock_llm,
        prompt_builder=mock_prompt_builder,
        supabase_service=mock_supabase,
        settings=mock_settings,
    )

    current_hash = sample_exploration_report.compute_exploration_hash()
    matching_state = {
        "has_diagnosis": True,
        "hash_exploracion": current_hash,
        "diagnostico_id": "diag-existing-1",
    }

    # Caso 1: Cambiaron métricas cuantitativas -> actualiza solo public.fricciones sin LLM
    mock_supabase.has_quantitative_changes.return_value = True
    res_metrics = await processor.process_report(
        sample_exploration_report,
        persist=True,
        existing_state=matching_state,
    )
    assert res_metrics.skipped_llm is True
    assert res_metrics.metrics_updated is True
    assert res_metrics.diagnostico_id == "diag-existing-1"
    mock_supabase.update_pattern_metrics_only.assert_called_once()
    mock_gcs.resolve_step_images_base64.assert_not_called()
    mock_llm.generate_diagnostics.assert_not_called()

    # Caso 2: Sin cambios ni en pasos ni en métricas -> omisión total
    mock_supabase.has_quantitative_changes.return_value = False
    res_skip = await processor.process_report(
        sample_exploration_report,
        persist=True,
        existing_state=matching_state,
    )
    assert res_skip.skipped_llm is True
    assert res_skip.metrics_updated is False
    assert res_skip.diagnostico_id == "diag-existing-1"
