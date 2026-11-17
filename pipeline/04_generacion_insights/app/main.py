"""Punto de entrada CLI puro (Cloud Run Job) orquestado por Google Cloud Workflows."""

import asyncio
import json
import logging
import os
import sys
from typing import Optional

from app.config import Settings, get_settings
from app.core.processor import InsightProcessor
from app.logging_config import configure_logging, fecha_ejecucion_ctx, id_cliente_ctx
from app.services.bigquery_service import BigQueryService, BigQueryServiceError
from app.services.llm_client import LLMClientError, LLMResponseValidationError
from app.services.supabase_service import SupabaseServiceError

logger = logging.getLogger("insights_main")

ETAPA_PIPELINE = "GENERACION_DE_INSIGHTS"


async def run_insights_job(
    client_id: str,
    batch_date: str,
    intento: int = 0,
    dry_run: bool = False,
    settings: Optional[Settings] = None,
    bigquery_service: Optional[BigQueryService] = None,
    processor: Optional[InsightProcessor] = None,
) -> int:
    """Ejecuta el ciclo por lotes del Módulo 4 para un cliente y fecha de ejecución.

    Args:
        client_id: UUID del cliente asignado a esta tarea.
        batch_date: Fecha del ciclo en formato YYYY-MM-DD (FECHA_EJECUCION).
        intento: Número de intento de la tarea en Cloud Run (CLOUD_RUN_TASK_ATTEMPT).
        dry_run: Si es True, no consulta ni persiste en Supabase.
        settings: Configuración inyectable.
        bigquery_service: Servicio de BigQuery inyectable.
        processor: Procesador de insights inyectable.

    Returns:
        Código de salida POSIX (0 para éxito/omisión, 1 para fallo fatal).
    """
    active_settings = settings or get_settings()
    bq_svc = bigquery_service or BigQueryService(settings=active_settings)
    insight_proc = processor or InsightProcessor(settings=active_settings)

    try:
        # 1. Cláusula de guarda inicial: consultar patrones explorados en BigQuery
        reports = bq_svc.get_completed_exploration_reports(
            client_id=client_id,
            batch_date=batch_date,
        )

        if not reports:
            logger.info(
                "Sin patrones explorados completados para este cliente y fecha. Omitiendo generación de insights.",
                extra={"etapa": ETAPA_PIPELINE, "intento": intento},
            )
            return 0

        # 2. Consultar estado previo en Supabase para detectar novedades reales por patrón
        existing_states = (
            insight_proc.supabase_service.get_existing_patterns_state(client_id=client_id)
            if not dry_run
            else {}
        )

        needs_llm_flags = []
        for report in reports:
            prev_state = existing_states.get(report.id_patron)
            has_same_steps = (
                prev_state is not None
                and prev_state.get("has_diagnosis") is True
                and prev_state.get("hash_exploracion") == report.compute_exploration_hash()
            )
            needs_llm_flags.append(not has_same_steps)

        llm_candidates_count = sum(1 for flag in needs_llm_flags if flag)

        logger.info(
            "Iniciando generación de insights UX.",
            extra={
                "etapa": ETAPA_PIPELINE,
                "intento": intento,
                "cantidad_patrones": len(reports),
                "patrones_con_novedades": llm_candidates_count,
            },
        )

        # 3. Verificar disponibilidad del modelo en RunPod solo si hay patrones con novedades
        if llm_candidates_count > 0:
            await insight_proc.llm_client.ensure_model_ready()

        generated_count = 0
        skipped_count = 0
        metrics_updated_count = 0
        error_count = 0

        for report, _ in zip(reports, needs_llm_flags):
            prev_state = existing_states.get(report.id_patron)
            try:
                result = await insight_proc.process_report(
                    report=report,
                    persist=not dry_run,
                    existing_state=prev_state,
                )
                if result.skipped_llm:
                    skipped_count += 1
                    if result.metrics_updated:
                        metrics_updated_count += 1
                else:
                    generated_count += 1
            except LLMResponseValidationError as exc:
                logger.warning(
                    "Respuesta inválida del LLM para patrón '%s': %s",
                    report.id_patron,
                    exc,
                    extra={
                        "etapa": ETAPA_PIPELINE,
                        "intento": intento,
                        "id_patron": report.id_patron,
                        "categoria_error": "PERMANENT",
                    },
                )
                error_count += 1
            except LLMClientError as exc:
                logger.warning(
                    "Fallo comunicando con RunPod/vLLM para patrón '%s': %s",
                    report.id_patron,
                    exc,
                    extra={
                        "etapa": ETAPA_PIPELINE,
                        "intento": intento,
                        "id_patron": report.id_patron,
                        "categoria_error": "TRANSIENT",
                    },
                )
                error_count += 1
            except SupabaseServiceError:
                raise
            except Exception as exc:
                logger.exception(
                    "Error inesperado procesando patrón '%s': %s",
                    report.id_patron,
                    exc,
                    extra={
                        "etapa": ETAPA_PIPELINE,
                        "intento": intento,
                        "id_patron": report.id_patron,
                        "categoria_error": "UNKNOWN",
                    },
                )
                error_count += 1

        logger.info(
            "Generación de insights finalizada para el cliente.",
            extra={
                "etapa": ETAPA_PIPELINE,
                "intento": intento,
                "patrones_generados": generated_count,
                "patrones_omitidos": skipped_count,
                "metricas_actualizadas": metrics_updated_count,
                "patrones_fallidos": error_count,
            },
        )

        if llm_candidates_count > 0 and generated_count == 0 and error_count > 0:
            logger.error(
                "Fallaron todos los patrones con novedades del cliente.",
                extra={
                    "etapa": ETAPA_PIPELINE,
                    "intento": intento,
                    "categoria_error": "TRANSIENT",
                },
            )
            return 1

        return 0

    except (BigQueryServiceError, SupabaseServiceError, LLMClientError) as exc:
        logger.error(
            "Fallo crítico de infraestructura durante el job de insights: %s",
            exc,
            extra={
                "etapa": ETAPA_PIPELINE,
                "intento": intento,
                "categoria_error": "TRANSIENT",
            },
        )
        return 1
    except Exception as exc:
        logger.exception(
            "Fallo crítico no controlado durante la ejecución del job: %s",
            exc,
            extra={
                "etapa": ETAPA_PIPELINE,
                "intento": intento,
                "categoria_error": "UNKNOWN",
            },
        )
        return 1


def ejecutar_tarea() -> None:
    """Punto de entrada principal del Cloud Run Job orquestado por Google Workflows."""
    configure_logging()

    try:
        indice_tarea = int(os.environ.get("CLOUD_RUN_TASK_INDEX", "0"))
        intento = int(os.environ.get("CLOUD_RUN_TASK_ATTEMPT", "0"))
        fecha_ejecucion = os.environ["FECHA_EJECUCION"]
        fecha_ejecucion_ctx.set(fecha_ejecucion)

        ids_clientes = json.loads(os.environ["IDS_CLIENTES"])
        if not isinstance(ids_clientes, list):
            raise ValueError("IDS_CLIENTES debe ser un arreglo JSON válido.")

        if indice_tarea < 0 or indice_tarea >= len(ids_clientes):
            logger.warning(
                "Índice de tarea fuera de rango. Finalizando sin acción.",
                extra={
                    "etapa": ETAPA_PIPELINE,
                    "indice_tarea": indice_tarea,
                    "total_clientes": len(ids_clientes),
                },
            )
            sys.exit(0)

        id_cliente = str(ids_clientes[indice_tarea])
        id_cliente_ctx.set(id_cliente)

        exit_code = asyncio.run(
            run_insights_job(
                client_id=id_cliente,
                batch_date=fecha_ejecucion,
                intento=intento,
            )
        )
        sys.exit(exit_code)
    except Exception as exc:
        logger.exception(
            "Error crítico inicializando la tarea del Cloud Run Job: %s",
            exc,
            extra={"etapa": ETAPA_PIPELINE, "categoria_error": "PERMANENT"},
        )
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    ejecutar_tarea()
