"""Runner de ejecución por lotes (Batch) para Google Cloud Run Jobs.

Ejecuta de forma aislada la exploración agéntica de los patrones de fricción
detectados para un cliente específico y una fecha de lote (batch_date).
Retorna código de salida 0 en caso de éxito y 1 ante errores fatales de infraestructura.
"""

import argparse
import asyncio
from datetime import datetime, timezone
import logging
import os
import sys
from typing import Dict, List, Optional, Set, Tuple
from app.agent.trace_executor import TraceExecutor
from app.browser.browser_manager import BrowserManager
from app.config import get_settings
from app.logging_config import configure_logging, fecha_ejecucion_ctx, id_cliente_ctx
from app.models.client_config import ClientInterfaceConfig, ClientSourceIntegration
from app.models.exploration_report import ExplorationReport, ExplorationStatus
from app.models.session_trace import SessionTrace
from app.services.bigquery_service import BigQueryService
from app.services.supabase_service import SupabaseService
from app.storage import get_storage_provider
from app.storage.base import StorageUploadError

logger = logging.getLogger("eureka_job_runner")


async def run_client_job(
    client_id: Optional[str],
    batch_date: Optional[str] = None,
    region: Optional[str] = None,
    max_concurrency: Optional[int] = None,
    storage_provider: Optional[str] = None,
    supabase_service: Optional[SupabaseService] = None,
    bigquery_service: Optional[BigQueryService] = None,
    browser_manager: Optional[BrowserManager] = None,
    task_attempt: int = 0,
    target_pattern_ids: Optional[Set[str]] = None,
) -> int:
    """
    Ejecuta el ciclo de exploración agéntica completo para un cliente y fecha de lote.

    :param client_id: Identificador del cliente objetivo.
    :param batch_date: Fecha del lote (formato YYYY-MM-DD); por defecto la fecha actual en UTC.
    :param region: Región de GCP donde reside el Data Warehouse (opcional).
    :param max_concurrency: Cantidad máxima de patrones a explorar en simultáneo (máximo 3).
    :param storage_provider: Proveedor de almacenamiento ('gcs' o 'local', opcional).
    :param supabase_service: Servicio Supabase inyectable para pruebas.
    :param bigquery_service: Servicio BigQuery inyectable para pruebas.
    :param browser_manager: Gestor de navegador inyectable para pruebas.
    :param task_attempt: Número de reintento actual en Cloud Run Jobs.
    :return: 0 si la ejecución concluyó correctamente, 1 si falló de forma irrecuperable.
    """
    if not client_id or not client_id.strip():
        logger.error(
            "[JobRunner] Se requiere un client_id válido para ejecutar el trabajo.",
            extra={"etapa": "EXPLORACION", "intento": task_attempt},
        )
        return 1

    clean_client_id = client_id.strip()
    target_date = (
        batch_date.strip()
        if batch_date and batch_date.strip()
        else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    )

    id_cliente_ctx.set(clean_client_id)
    fecha_ejecucion_ctx.set(target_date)

    logger.info(
        f"[JobRunner] Iniciando Cloud Run Job para client_id='{clean_client_id}', "
        f"batch_date='{target_date}'",
        extra={"etapa": "EXPLORACION", "intento": task_attempt},
    )

    # 1. Resolución ligera de región y Cláusula de Guarda Inicial en BigQuery
    sb = supabase_service or SupabaseService()
    config: Optional[ClientInterfaceConfig] = None
    supabase_error: Optional[Exception] = None
    client_integration: Optional[ClientSourceIntegration] = None

    try:
        config = await sb.get_client_interface_config(clean_client_id)
    except Exception as exc:
        supabase_error = exc
        logger.warning(
            f"[JobRunner] Error al precargar ClientInterfaceConfig para '{clean_client_id}': {exc}",
            extra={"etapa": "EXPLORACION", "intento": task_attempt},
        )

    if not region and (not config or not config.gcp_region):
        try:
            client_integration = await sb.get_client_source_integration(clean_client_id)
        except Exception as exc:
            logger.warning(
                f"[JobRunner] No se pudo obtener ClientSourceIntegration: {exc}",
                extra={"etapa": "EXPLORACION", "intento": task_attempt},
            )

    resolved_region = (
        region
        or (config.gcp_region if config else None)
        or (client_integration.gcp_region if client_integration else None)
        or get_settings().DEFAULT_BIGQUERY_REGION
    )

    bq = bigquery_service or BigQueryService()
    try:
        patterns: List[SessionTrace] = await bq.get_friction_patterns_for_client(
            client_id=clean_client_id,
            batch_date=target_date,
            region=resolved_region,
        )
    except Exception:
        logger.exception(
            f"[JobRunner] Falló consulta de patrones en BigQuery para '{clean_client_id}'.",
            extra={"etapa": "EXPLORACION", "intento": task_attempt},
        )
        return 1

    active_target_ids = (
        target_pattern_ids
        if target_pattern_ids is not None
        else get_settings().get_target_pattern_ids()
    )
    if active_target_ids:
        patterns = [p for p in patterns if p.id_patron in active_target_ids]
        logger.info(
            f"[JobRunner] Filtro TARGET_PATTERN_IDS activo ({len(patterns)} patrones seleccionados).",
            extra={"etapa": "EXPLORACION", "intento": task_attempt},
        )

    if not patterns:
        logger.info(
            "Sin patrones de fricción registrados para este cliente y fecha. Omitiendo exploración.",
            extra={"etapa": "EXPLORACION", "intento": task_attempt},
        )
        return 0

    logger.info(
        f"[JobRunner] Se procesarán {len(patterns)} patrones de fricción.",
        extra={"etapa": "EXPLORACION", "intento": task_attempt},
    )

    # 2. Exigir ClientInterfaceConfig de Supabase solo cuando hay patrones por explorar
    if supabase_error is not None:
        logger.critical(
            f"[JobRunner] Error al conectar con Supabase para client_id='{clean_client_id}': {supabase_error}",
            extra={"etapa": "EXPLORACION", "intento": task_attempt},
        )
        return 1

    if not config:
        logger.error(
            f"[JobRunner] No se encontró ClientInterfaceConfig en Supabase para '{clean_client_id}'.",
            extra={"etapa": "EXPLORACION", "intento": task_attempt},
        )
        return 1

    # 3. Asegurar tabla en BigQuery, preparar almacenamiento e iniciar navegador dentro de try/finally
    if not await bq.ensure_exploration_table_exists(region=resolved_region):
        logger.error(
            f"[JobRunner] No se pudo verificar o crear la tabla de reportes en BigQuery (region='{resolved_region}').",
            extra={"etapa": "EXPLORACION", "intento": task_attempt},
        )
        return 1

    storage = get_storage_provider(provider_type=storage_provider)

    async def _save_evidence(data: bytes, filename: str, step: int) -> str:
        return await storage.save_evidence(data, filename)

    mgr = browser_manager or BrowserManager()
    manage_lifecycle = browser_manager is None
    results: List[Optional[ExplorationReport]] = []

    try:
        if manage_lifecycle:
            await mgr.start()

        executor = TraceExecutor(
            browser_manager=mgr,
            evidence_saver=_save_evidence,
        )

        has_client_session = bool(
            config.resolve_storage_state() is not None or config.requires_authentication
        )
        indexed_patterns: List[Tuple[int, SessionTrace]] = list(enumerate(patterns, start=1))
        if has_client_session:
            anon_batch = [
                (idx, trace)
                for idx, trace in indexed_patterns
                if not trace.requires_authenticated_session()
            ]
            auth_batch = [
                (idx, trace)
                for idx, trace in indexed_patterns
                if trace.requires_authenticated_session()
            ]
        else:
            anon_batch = indexed_patterns
            auth_batch = []

        concurrency_limit = (
            max_concurrency
            if max_concurrency is not None and max_concurrency > 0
            else get_settings().MAX_CONCURRENCY_PER_CLIENT
        )
        semaphore = asyncio.Semaphore(concurrency_limit)
        logger.info(
            f"[JobRunner] Concurrencia configurada: máximo {concurrency_limit} patrones simultáneos "
            f"(anónimos={len(anon_batch)}, con_sesión_secuencial={len(auth_batch)}).",
            extra={"etapa": "EXPLORACION", "intento": task_attempt},
        )

        async def _run_and_persist_pattern(
            trace: SessionTrace,
            index: int,
            allow_session_auth: bool,
        ) -> Optional[ExplorationReport]:
            trace.fecha_exploracion = target_date
            logger.info(
                f"[JobRunner] [{index}/{len(patterns)}] Explorando patrón='{trace.id_patron}' "
                f"(id_sesion='{trace.id_sesion}')",
                extra={
                    "etapa": "EXPLORACION",
                    "intento": task_attempt,
                    "id_patron": trace.id_patron,
                },
            )
            try:
                if allow_session_auth:
                    report = await executor.execute_trace(trace, config)
                else:
                    report = await executor.execute_trace(trace, config, allow_session_auth=False)
            except StorageUploadError:
                raise
            except Exception as trace_exc:
                logger.warning(
                    f"[JobRunner] Fallo puntual al explorar patrón '{trace.id_patron}': {trace_exc}",
                    extra={
                        "etapa": "EXPLORACION",
                        "intento": task_attempt,
                        "id_patron": trace.id_patron,
                    },
                )
                return None

            saved = await bq.save_exploration_report(
                report=report,
                region=resolved_region,
                idempotent=True,
            )
            if not saved:
                raise RuntimeError(
                    f"Error al persistir reporte en BigQuery para patrón '{trace.id_patron}'"
                )

            if report.status == ExplorationStatus.FAILED:
                logger.warning(
                    f"[JobRunner] Patrón '{trace.id_patron}' finalizó en estado FAILED "
                    f"(pasos={report.completed_steps}/{report.total_steps}).",
                    extra={
                        "etapa": "EXPLORACION",
                        "intento": task_attempt,
                        "id_patron": trace.id_patron,
                    },
                )
            return report

        async def _explore_concurrent(
            trace: SessionTrace,
            index: int,
        ) -> Tuple[int, Optional[ExplorationReport]]:
            async with semaphore:
                report = await _run_and_persist_pattern(
                    trace=trace,
                    index=index,
                    allow_session_auth=not has_client_session,
                )
                return index, report

        results_by_index: Dict[int, Optional[ExplorationReport]] = {}
        if anon_batch:
            anon_tasks = [_explore_concurrent(trace, idx) for idx, trace in anon_batch]
            for idx, report in await asyncio.gather(*anon_tasks):
                results_by_index[idx] = report

        if auth_batch:
            logger.info(
                f"[JobRunner] Ejecutando {len(auth_batch)} patrones autenticados en modo secuencial "
                "(concurrencia=1) con pre-limpieza defensiva inicial.",
                extra={"etapa": "EXPLORACION", "intento": task_attempt},
            )
            await executor.cleanup_client_session_state(config)
            for idx, trace in auth_batch:
                results_by_index[idx] = await _run_and_persist_pattern(
                    trace=trace,
                    index=idx,
                    allow_session_auth=True,
                )

        results = [results_by_index.get(idx) for idx, _ in indexed_patterns]

    except Exception:
        logger.exception(
            "[JobRunner] Excepción fatal durante la ejecución de las trazas.",
            extra={"etapa": "EXPLORACION", "intento": task_attempt},
        )
        return 1
    finally:
        if manage_lifecycle:
            await mgr.close()

    any_progress = any(
        r is not None and (r.status != ExplorationStatus.FAILED or r.completed_steps > 0)
        for r in results
    )
    if not any_progress:
        logger.error(
            "Fallo general: ningún patrón pudo ser explorado en el sitio del cliente.",
            extra={"etapa": "EXPLORACION", "intento": task_attempt},
        )
        return 1

    # 4. Log estructurado de finalización
    completed_reports = [
        r for r in results if r is not None and r.status != ExplorationStatus.FAILED
    ]
    total_screenshots = sum(
        1
        for r in results
        if r is not None
        for ev in r.evidences
        if ev.screenshot_url
    )
    logger.info(
        f"Exploración finalizada para cliente '{clean_client_id}'.",
        extra={
            "etapa": "EXPLORACION",
            "intento": task_attempt,
            "patrones_explorados": len(completed_reports),
            "capturas_generadas": total_screenshots,
        },
    )
    return 0


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Construye y procesa los argumentos de línea de comandos para el Job Runner."""
    parser = argparse.ArgumentParser(
        prog="eureka-job-runner",
        description="Punto de entrada de Cloud Run Jobs para la exploración agéntica de un cliente.",
    )
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    parser.add_argument(
        "--client-id",
        "-c",
        default=os.getenv("CLIENT_ID"),
        help="Identificador del cliente a procesar (o variable de entorno CLIENT_ID).",
    )
    parser.add_argument(
        "--batch-date",
        "-d",
        default=os.getenv("BATCH_DATE", today_utc),
        help="Fecha del lote a procesar (formato YYYY-MM-DD). Por defecto la fecha actual (hoy) en UTC.",
    )
    parser.add_argument(
        "--region",
        "-r",
        default=os.getenv("GCP_REGION"),
        help="Región de GCP donde reside el Data Warehouse.",
    )
    parser.add_argument(
        "--max-concurrency",
        "-m",
        type=int,
        default=int(os.getenv("MAX_CONCURRENCY", str(get_settings().MAX_CONCURRENCY_PER_CLIENT))),
        help="Cantidad máxima de patrones a explorar en simultáneo (por defecto 3).",
    )
    parser.add_argument(
        "--storage-provider",
        "-s",
        default=os.getenv("STORAGE_PROVIDER", get_settings().STORAGE_PROVIDER),
        help="Proveedor de almacenamiento de evidencias ('gcs' o 'local').",
    )
    return parser.parse_args(args)


async def main_async(args: Optional[List[str]] = None) -> int:
    """Función de arranque asíncrona para la CLI del Job Runner."""
    parsed = parse_args(args)
    return await run_client_job(
        client_id=parsed.client_id,
        batch_date=parsed.batch_date,
        region=parsed.region,
        max_concurrency=parsed.max_concurrency,
        storage_provider=parsed.storage_provider,
    )


def main() -> None:
    """Punto de entrada síncrono para el contenedor de Cloud Run Jobs."""
    configure_logging()
    exit_code = asyncio.run(main_async())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
