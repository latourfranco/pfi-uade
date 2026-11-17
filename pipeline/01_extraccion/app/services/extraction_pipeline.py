import asyncio
import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple

from google.auth.exceptions import DefaultCredentialsError, RefreshError

from app.config import Settings
from app.logging_config import fecha_ejecucion_ctx, id_cliente_ctx
from app.models import (
    BatchExtractionResponse,
    ClientIngestionResult,
    ClientSourceIntegration,
    PlatformBigQueryError,
)
from app.retry import classify_error, retry_async_operation
from app.services.bigquery_service import BigQueryService
from app.services.supabase_service import SupabaseService

logger = logging.getLogger("extraction_pipeline")


class ExtractionPipeline:
    """Orquesta la extracción batch cross-project con control de concurrencia, reintentos y métricas."""

    def __init__(
        self,
        settings: Settings,
        bigquery_service: BigQueryService,
        supabase_service: SupabaseService,
    ):
        self.settings = settings
        self.bigquery_service = bigquery_service
        self.supabase_service = supabase_service

    def resolve_execution_date(self, execution_date_str: Optional[str] = None) -> date:
        """Resuelve la fecha del ciclo de ejecución (T) en YYYY-MM-DD o toma hoy en UTC por defecto."""
        if execution_date_str:
            try:
                return datetime.strptime(execution_date_str.strip(), "%Y-%m-%d").date()
            except ValueError:
                raise ValueError(
                    f"Formato de fecha inválido '{execution_date_str}'. Se esperaba 'YYYY-MM-DD'."
                )
        return datetime.now(timezone.utc).date()

    def resolve_target_date(self, target_date_str: Optional[str] = None) -> date:
        """Calcula la fecha de datos GA4 a extraer (T-1) a partir de la fecha de ejecución (T)."""
        return self.resolve_execution_date(target_date_str) - timedelta(days=1)

    def resolve_client_date_window(
        self,
        last_event_date: Optional[date],
        target_end_date: date,
    ) -> Tuple[date, date]:
        """
        Determina el rango [fecha_inicio, fecha_fin] a extraer para un cliente:
        - Primera ejecución (last_event_date is None): últimos N días (TTL de 60 días por defecto).
        - Re-ejecución de una fecha ya cargada (last_event_date >= target_end_date): solo target_end_date.
        - Ejecución incremental / catch-up (last_event_date < target_end_date): desde last_event_date + 1
          hasta target_end_date, acotado al límite máximo de TTL de 60 días.
        """
        backfill_days = max(1, self.settings.GA4_INITIAL_BACKFILL_DAYS)
        min_allowed_date = target_end_date - timedelta(days=backfill_days - 1)

        if last_event_date is None:
            return (min_allowed_date, target_end_date)

        if last_event_date >= target_end_date:
            return (target_end_date, target_end_date)

        next_date = last_event_date + timedelta(days=1)
        return (max(next_date, min_allowed_date), target_end_date)

    async def process_single_client(
        self,
        client: ClientSourceIntegration,
        target_date: date,
        semaphore: asyncio.Semaphore,
        execution_date_str: Optional[str] = None,
    ) -> ClientIngestionResult:
        """
        Procesa la extracción para un cliente individual dentro del semáforo de concurrencia.
        Calcula la ventana dinámica (60 días en primera ejecución o incremental desde MAX(fecha_evento))
        y utiliza reintentos in-process con exponential backoff para fallos transitorios.
        """
        start_time = time.perf_counter()
        data_date_str = target_date.strftime("%Y-%m-%d")
        cycle_date_str = execution_date_str or (target_date + timedelta(days=1)).strftime("%Y-%m-%d")
        token_cliente = id_cliente_ctx.set(client.cliente_id)
        async with semaphore:
            try:
                last_event_date = await self.bigquery_service.get_client_last_event_date(client)
                start_date, end_date = self.resolve_client_date_window(last_event_date, target_date)
                start_str = start_date.strftime("%Y-%m-%d")
                end_str = end_date.strftime("%Y-%m-%d")

                logger.info(
                    "Iniciando extracción para cliente '%s' (ventana: %s..%s)...",
                    client.cliente_id,
                    start_str,
                    end_str,
                    extra={
                        "id_cliente": client.cliente_id,
                        "fecha_ejecucion": cycle_date_str,
                        "fecha_inicio_datos_ga4": start_str,
                        "fecha_fin_datos_ga4": end_str,
                        "primera_extraccion": last_event_date is None,
                    },
                )

                async def _operation():
                    disponible = await self.bigquery_service.check_ga4_data_available(
                        client, start_date, end_date
                    )
                    if not disponible:
                        return None
                    return await self.bigquery_service.execute_client_merge(
                        client, start_date, end_date
                    )

                bq_result, attempts = await retry_async_operation(
                    operation=_operation,
                    max_retries=self.settings.MAX_CLIENT_RETRIES,
                    initial_delay=self.settings.RETRY_INITIAL_DELAY,
                    backoff_factor=self.settings.RETRY_BACKOFF_FACTOR,
                    operation_name="BigQueryMERGE",
                    client_id=client.cliente_id,
                )

                elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
                if bq_result is None:
                    logger.info(
                        "Cliente '%s' omitido para fecha_datos_ga4=%s por falta de datos GA4 disponibles.",
                        client.cliente_id,
                        data_date_str,
                        extra={
                            "id_cliente": client.cliente_id,
                            "fecha_ejecucion": cycle_date_str,
                            "fecha_datos_ga4": data_date_str,
                        },
                    )
                    return ClientIngestionResult(
                        cliente_id=client.cliente_id,
                        exitoso=False,
                        omitido=True,
                        filas_afectadas=0,
                        duracion_ms=elapsed_ms,
                        intentos=attempts,
                    )

                return ClientIngestionResult(
                    cliente_id=client.cliente_id,
                    exitoso=True,
                    filas_afectadas=bq_result.get("rows_affected", 0),
                    bytes_procesados=bq_result.get("bytes_procesados"),
                    job_id=bq_result.get("job_id"),
                    duracion_ms=elapsed_ms,
                    intentos=attempts,
                )

            except (PlatformBigQueryError, DefaultCredentialsError, RefreshError):
                # Fallos globales de plataforma/credenciales no deben aislarse por cliente:
                # deben propagarse para responder HTTP 500 y disparar reintentos Nivel 2.
                raise

            except Exception as exc:
                elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
                category, is_retryable = classify_error(exc)
                actual_attempts = 1 if not is_retryable else self.settings.MAX_CLIENT_RETRIES
                logger.error(
                    "Extracción fallida para cliente '%s' tras reintentos (%s): %s",
                    client.cliente_id,
                    category,
                    str(exc),
                    extra={
                        "id_cliente": client.cliente_id,
                        "fecha_ejecucion": cycle_date_str,
                        "fecha_datos_ga4": data_date_str,
                        "tipo_error": category,
                        "intentos": actual_attempts,
                    },
                )
                return ClientIngestionResult(
                    cliente_id=client.cliente_id,
                    exitoso=False,
                    omitido=False,
                    filas_afectadas=0,
                    duracion_ms=elapsed_ms,
                    intentos=actual_attempts,
                    error=str(exc),
                    tipo_error=category,
                )
            finally:
                id_cliente_ctx.reset(token_cliente)

    async def run_batch(
        self,
        target_date_str: Optional[str] = None,
        cliente_id: Optional[str] = None,
    ) -> BatchExtractionResponse:
        """
        Punto de entrada principal para ejecutar el lote de extracción.
        Recibe la fecha de ejecución (T) y extrae los datos GA4 correspondientes al día anterior (T-1).
        Soporta procesamiento de todos los clientes activos o de un cliente específico.
        Incluye una segunda pasada automática (Second-Chance Pass) para fallos transitorios.
        """
        batch_start = time.perf_counter()
        execution_date = self.resolve_execution_date(target_date_str)
        target_date = execution_date - timedelta(days=1)
        execution_date_str = execution_date.strftime("%Y-%m-%d")
        data_date_str = target_date.strftime("%Y-%m-%d")
        token_fecha = fecha_ejecucion_ctx.set(execution_date_str)

        try:
            logger.info(
                "Iniciando extracción batch para fecha_ejecucion=%s (datos GA4=%s, cliente filtrado: %s)",
                execution_date_str,
                data_date_str,
                cliente_id or "TODOS",
                extra={"fecha_ejecucion": execution_date_str, "fecha_datos_ga4": data_date_str},
            )

            # 1. Obtener clientes activos desde Supabase
            active_clients = await self.supabase_service.get_active_clients(cliente_id=cliente_id)
            if not active_clients:
                logger.warning(
                    "No se encontraron clientes activos en Supabase para procesar",
                    extra={"fecha_ejecucion": execution_date_str, "fecha_datos_ga4": data_date_str},
                )
                return BatchExtractionResponse(
                    fecha_ejecucion=execution_date_str,
                    clientes_exitosos=[],
                    clientes_omitidos=[],
                    clientes_fallidos=[],
                )

            # 1b. Pre-aprovisionar esquemas regionales en el BigQuery propio (fallo global -> HTTP 500)
            unique_regions = sorted({c.gcp_region for c in active_clients})
            for region in unique_regions:
                await self.bigquery_service.ensure_target_schema(region)

            semaphore = asyncio.Semaphore(self.settings.MAX_CONCURRENT_CLIENTS)

            # 2. Pasada 1: Ejecutar todos los clientes en paralelo con el semáforo
            tasks = [
                self.process_single_client(
                    client,
                    target_date,
                    semaphore,
                    execution_date_str=execution_date_str,
                )
                for client in active_clients
            ]
            results: List[ClientIngestionResult] = await asyncio.gather(*tasks)

            # Mapear resultados por cliente_id
            results_map = {r.cliente_id: r for r in results}

            # 3. Pasada 2 (Second-Chance Pass): Reintentar clientes con fallos transitorios (excluye omitidos)
            transient_failed_clients = [
                c for c in active_clients
                if not results_map[c.cliente_id].exitoso
                and not results_map[c.cliente_id].omitido
                and results_map[c.cliente_id].tipo_error in ("TRANSIENT", "UNKNOWN")
            ]

            if transient_failed_clients:
                logger.info(
                    "Ejecutando Segunda Pasada para %d cliente(s) con fallos transitorios...",
                    len(transient_failed_clients),
                    extra={"fecha_ejecucion": execution_date_str, "fecha_datos_ga4": data_date_str},
                )
                await asyncio.sleep(3.0)  # Breve pausa antes de la segunda pasada

                retry_tasks = [
                    self.process_single_client(
                        client,
                        target_date,
                        semaphore,
                        execution_date_str=execution_date_str,
                    )
                    for client in transient_failed_clients
                ]
                retry_results = await asyncio.gather(*retry_tasks)
                for r in retry_results:
                    if r.exitoso or r.omitido:
                        logger.info(
                            "¡Segunda Pasada resuelta para cliente '%s'!",
                            r.cliente_id,
                            extra={
                                "id_cliente": r.cliente_id,
                                "fecha_ejecucion": execution_date_str,
                                "fecha_datos_ga4": data_date_str,
                            },
                        )
                        results_map[r.cliente_id] = r

            # 4. Consolidar resumen final
            final_results = list(results_map.values())
            exitosos = [r for r in final_results if r.exitoso]
            omitidos = [r for r in final_results if r.omitido]
            fallidos = [r for r in final_results if not r.exitoso and not r.omitido]
            total_duration = round(time.perf_counter() - batch_start, 2)

            logger.info(
                "Extracción batch finalizada para %s (datos GA4=%s): "
                "%d total, %d exitosos, %d omitidos, %d fallidos en %.2fs",
                execution_date_str,
                data_date_str,
                len(final_results),
                len(exitosos),
                len(omitidos),
                len(fallidos),
                total_duration,
                extra={"fecha_ejecucion": execution_date_str, "fecha_datos_ga4": data_date_str},
            )

            return BatchExtractionResponse(
                fecha_ejecucion=execution_date_str,
                clientes_exitosos=[r.cliente_id for r in exitosos],
                clientes_omitidos=[r.cliente_id for r in omitidos],
                clientes_fallidos=[r.cliente_id for r in fallidos],
            )
        finally:
            fecha_ejecucion_ctx.reset(token_fecha)
