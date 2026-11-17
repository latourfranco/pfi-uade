"""Orquestador central del flujo de análisis multimodal, filtrado incremental y persistencia."""

import logging
from typing import Any, Dict, Optional

from app.config import Settings, get_settings
from app.core.prompt_builder import PromptBuilder
from app.models.exploration_models import ExplorationReport
from app.models.response_models import ProcessClusterResponse
from app.services.gcs_service import GCSService
from app.services.llm_client import LLMClient
from app.services.supabase_service import SupabaseService

logger = logging.getLogger(__name__)


class InsightProcessor:
    """Orquesta la detección de novedades, descarga de evidencias, inferencia LLM y persistencia."""

    def __init__(
        self,
        gcs_service: Optional[GCSService] = None,
        llm_client: Optional[LLMClient] = None,
        prompt_builder: Optional[PromptBuilder] = None,
        supabase_service: Optional[SupabaseService] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        """Inicializa el procesador inyectando servicios o utilizando implementaciones por defecto.

        Args:
            gcs_service: Servicio de descarga Base64 desde GCS.
            llm_client: Cliente de inferencia vLLM en RunPod.
            prompt_builder: Ensamblador de payloads multimodales.
            supabase_service: Servicio de persistencia relacional e incremental.
            settings: Configuración general.
        """
        self.settings = settings or get_settings()
        self.gcs_service = gcs_service or GCSService(settings=self.settings)
        self.llm_client = llm_client or LLMClient(settings=self.settings)
        self.prompt_builder = prompt_builder or PromptBuilder(settings=self.settings)
        self.supabase_service = supabase_service or SupabaseService(settings=self.settings)

    async def process_report(
        self,
        report: ExplorationReport,
        persist: bool = True,
        existing_state: Optional[Dict[str, Any]] = None,
    ) -> ProcessClusterResponse:
        """Ejecuta el ciclo de análisis para un ExplorationReport con control incremental.

        Args:
            report: Reporte de exploración agéntica desde BigQuery.
            persist: Booleano para definir si se guardan los resultados en base de datos.
            existing_state: Estado previo opcional del patrón en Supabase (para omitir LLM sin novedades).

        Returns:
            ProcessClusterResponse con resultado, métricas de tokens y estado de omisión.
        """
        friccion_id = report.id_patron
        exploration_hash = report.compute_exploration_hash()

        if (
            existing_state is not None
            and existing_state.get("has_diagnosis") is True
            and existing_state.get("hash_exploracion") == exploration_hash
        ):
            metrics_changed = self.supabase_service.has_quantitative_changes(report, existing_state)
            if metrics_changed and persist:
                logger.info(
                    "Patrón '%s' sin cambios en pasos explorados; actualizando solo métricas en Supabase.",
                    friccion_id,
                    extra={"id_patron": friccion_id},
                )
                self.supabase_service.update_pattern_metrics_only(
                    report=report,
                    exploration_hash=exploration_hash,
                )
                return ProcessClusterResponse(
                    success=True,
                    friccion_id=friccion_id,
                    diagnostico_id=existing_state.get("diagnostico_id"),
                    skipped_llm=True,
                    metrics_updated=True,
                    message="Sin novedades en pasos explorados; métricas cuantitativas actualizadas.",
                )

            logger.info(
                "Patrón '%s' sin novedades en pasos ni métricas. Omitiendo inferencia LLM.",
                friccion_id,
                extra={"id_patron": friccion_id},
            )
            return ProcessClusterResponse(
                success=True,
                friccion_id=friccion_id,
                diagnostico_id=existing_state.get("diagnostico_id"),
                skipped_llm=True,
                metrics_updated=False,
                message="Sin novedades en pasos ni métricas respecto al diagnóstico existente.",
            )

        logger.info(
            "Iniciando generación de diagnóstico para id_patron='%s' (id_sesion='%s').",
            friccion_id,
            report.id_sesion,
            extra={"id_patron": friccion_id},
        )

        # 1. Descargar y codificar en Base64 las capturas WebP desde GCS
        images_map = self.gcs_service.resolve_step_images_base64(report.evidences)
        logger.info(
            "Resueltas %d capturas WebP en Base64 para id_patron '%s'.",
            len(images_map),
            friccion_id,
            extra={"id_patron": friccion_id},
        )

        # 2. Construir payload multimodal para RunPod vLLM
        payload = self.prompt_builder.build_payload_from_report(report, images_map)

        # 3. Invocar inferencia con razonamiento activo en RunPod
        generation_result = await self.llm_client.generate_diagnostics(payload)
        diagnostico = generation_result.output

        # Conservar únicamente notas correspondientes a pasos pertenecientes al patrón
        pattern_step_numbers = {ev.orden for ev in report.evidences if ev.en_patron}
        if pattern_step_numbers and any(not ev.en_patron for ev in report.evidences):
            diagnostico.journey_step_notes = [
                note for note in diagnostico.journey_step_notes if note.step_number in pattern_step_numbers
            ]

        diagnostico_id: Optional[str] = None
        notas_count = 0

        # 4. Persistir en Supabase si está habilitado
        if persist:
            logger.info(
                "Guardando patrón, diagnóstico, pasos y notas en Supabase para id_patron '%s'.",
                friccion_id,
                extra={"id_patron": friccion_id},
            )
            save_result = self.supabase_service.save_diagnostics(
                report=report,
                diagnostico=diagnostico,
                prompt_tokens=generation_result.prompt_tokens,
                completion_tokens=generation_result.completion_tokens,
                model_name=generation_result.model_name,
                exploration_hash=exploration_hash,
            )
            diagnostico_id = save_result.get("diagnostico_id")
            notas_count = save_result.get("notas_count", 0)

        message = (
            "Diagnóstico de exploración generado y persistido con éxito."
            if persist
            else "Diagnóstico de exploración generado con éxito (modo dry-run sin persistencia)."
        )

        return ProcessClusterResponse(
            success=True,
            friccion_id=friccion_id,
            diagnostico_id=diagnostico_id,
            diagnostico=diagnostico,
            notas_count=notas_count,
            prompt_tokens=generation_result.prompt_tokens,
            completion_tokens=generation_result.completion_tokens,
            skipped_llm=False,
            metrics_updated=False,
            message=message,
        )
