import asyncio
import logging
from datetime import date
from typing import Any, Dict, Optional, Set
from google.cloud import bigquery
from google.cloud.exceptions import NotFound

from app.config import Settings
from app.models import ClientSourceIntegration, PlatformBigQueryError

logger = logging.getLogger("bigquery_service")


def sanitize_region(region: str) -> str:
    """
    Sanitiza nombres de regiones de GCP para formar identificadores válidos en BigQuery
    (ej. us-central1 -> us_central1).
    """
    return region.lower().replace("-", "_").strip()


class BigQueryService:
    """Servicio encargado de aprovisionar esquemas regionales y ejecutar las consultas MERGE Cross-Project."""

    def __init__(self, settings: Settings, client: Optional[bigquery.Client] = None):
        self.settings = settings
        self._client = client
        self._verified_tables: Set[str] = set()

    @property
    def client(self) -> bigquery.Client:
        """Inicialización perezosa del cliente de BigQuery."""
        if self._client is None:
            self._client = bigquery.Client(project=self.settings.PLATFORM_GCP_PROJECT_ID)
        return self._client

    def get_dataset_id(self, region: str) -> str:
        """Devuelve el identificador del dataset regional: dw_analytics_<region_sanitizada>."""
        return f"dw_analytics_{sanitize_region(region)}"

    def get_table_full_id(self, region: str) -> str:
        """Devuelve el ID completo de la tabla: proyecto.dw_analytics_<region>.eventos_usuario."""
        dataset_id = self.get_dataset_id(region)
        return f"{self.settings.PLATFORM_GCP_PROJECT_ID}.{dataset_id}.eventos_usuario"

    async def ensure_target_schema(self, region: str) -> None:
        """
        Aprovisiona dinámicamente el dataset regional y la tabla particionada/clusterizada si no existen.
        Utiliza una caché en memoria para evitar llamadas DDL duplicadas en el mismo ciclo del proceso.
        """
        dataset_id = self.get_dataset_id(region)
        table_full_id = self.get_table_full_id(region)

        if table_full_id in self._verified_tables:
            return

        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, self._sync_ensure_target_schema, region, dataset_id, table_full_id)
        except Exception as exc:
            logger.error(
                "Error global aprovisionando esquema destino '%s' en proyecto '%s': %s",
                table_full_id,
                self.settings.PLATFORM_GCP_PROJECT_ID,
                str(exc),
                extra={"region": region, "tabla_destino": table_full_id},
            )
            raise PlatformBigQueryError(
                f"Error al operar sobre el proyecto propio de BigQuery ({self.settings.PLATFORM_GCP_PROJECT_ID}): {exc}"
            ) from exc
        self._verified_tables.add(table_full_id)

    def _sync_ensure_target_schema(self, region: str, dataset_id: str, table_full_id: str) -> None:
        """Helper sincrónico para aprovisionamiento de dataset y tabla en BigQuery."""
        project_id = self.settings.PLATFORM_GCP_PROJECT_ID
        dataset_ref = bigquery.DatasetReference(project_id, dataset_id)

        # 1. Asegurar la existencia del Dataset regional
        try:
            self.client.get_dataset(dataset_ref)
            logger.debug("El dataset %s ya existe en la región %s", dataset_id, region)
        except NotFound:
            logger.info("Creando dataset regional %s en ubicación %s...", dataset_id, region)
            new_dataset = bigquery.Dataset(dataset_ref)
            new_dataset.location = region
            self.client.create_dataset(new_dataset, exists_ok=True)
            logger.info("Dataset %s creado exitosamente", dataset_id)

        # 2. Asegurar la existencia de la tabla particionada y clusterizada
        ddl = f"""
        CREATE TABLE IF NOT EXISTS `{table_full_id}` (
            cliente_id STRING NOT NULL,
            fecha_evento DATE NOT NULL,
            id_usuario STRING NOT NULL,
            event_timestamp INT64 NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            nombre_evento STRING NOT NULL,
            tipo_evento STRING NOT NULL,
            ruta STRING,
            detalle_click STRING,
            termino_busqueda STRING,
            porcentaje_scroll INT64,
            tiempo_engagement_ms INT64,
            items STRING,
            promociones STRING,
            pais STRING,
            ciudad STRING,
            tipo_dispositivo STRING,
            navegador STRING,
            sistema_operativo STRING
        )
        PARTITION BY fecha_evento
        CLUSTER BY cliente_id, id_usuario, tipo_evento;
        """
        job_config = bigquery.QueryJobConfig()
        query_job = self.client.query(ddl, job_config=job_config, location=region)
        query_job.result()
        logger.debug("Tabla destino %s verificada/creada", table_full_id)

    def get_source_daily_table_id(self, client_info: ClientSourceIntegration, target_date: date) -> str:
        """Devuelve el ID completo de la tabla diaria exportada de GA4 para la fecha objetivo."""
        date_suffix = target_date.strftime("%Y%m%d")
        return f"{client_info.client_gcp_project_id}.analytics_{client_info.ga4_property_id}.events_{date_suffix}"

    async def get_client_last_event_date(self, client_info: ClientSourceIntegration) -> Optional[date]:
        """
        Consulta MAX(fecha_evento) en el BigQuery analítico propio para determinar si es la
        primera extracción del cliente (None) o desde qué fecha continuar de forma incremental.
        """
        await self.ensure_target_schema(client_info.gcp_region)
        table_full_id = self.get_table_full_id(client_info.gcp_region)
        sql = f"""
        SELECT MAX(fecha_evento) AS ultima_fecha
        FROM `{table_full_id}`
        WHERE cliente_id = @cliente_id
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("cliente_id", "STRING", client_info.cliente_id),
            ]
        )
        loop = asyncio.get_running_loop()

        def _query_max_date() -> Optional[date]:
            query_job = self.client.query(
                sql,
                job_config=job_config,
                location=client_info.gcp_region,
            )
            rows = list(query_job.result())
            if not rows:
                return None
            ultima_fecha = rows[0]["ultima_fecha"]
            return ultima_fecha if isinstance(ultima_fecha, date) else None

        try:
            return await loop.run_in_executor(None, _query_max_date)
        except Exception as exc:
            logger.error(
                "Error consultando MAX(fecha_evento) para cliente '%s' en '%s': %s",
                client_info.cliente_id,
                table_full_id,
                str(exc),
                extra={"id_cliente": client_info.cliente_id, "region": client_info.gcp_region},
            )
            raise PlatformBigQueryError(
                f"Error consultando BigQuery propio ({self.settings.PLATFORM_GCP_PROJECT_ID}): {exc}"
            ) from exc

    async def check_ga4_data_available(
        self,
        client_info: ClientSourceIntegration,
        start_date: date,
        end_date: Optional[date] = None,
    ) -> bool:
        """
        Verifica si existen tablas diarias GA4 disponibles dentro del rango [start_date, end_date].
        - Para un único día (start_date == end_date): valida que exista events_YYYYMMDD con filas > 0.
        - Para un rango multi-día (ej. backfill inicial de 60 días o catch-up): valida que exista
          al menos una tabla diaria events_YYYYMMDD dentro del rango.
        """
        effective_end = end_date or start_date
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = effective_end.strftime("%Y-%m-%d")
        loop = asyncio.get_running_loop()

        if start_date == effective_end:
            source_daily_table = self.get_source_daily_table_id(client_info, start_date)

            def _check_single_table() -> bool:
                try:
                    table = self.client.get_table(source_daily_table)
                except NotFound:
                    logger.info(
                        "Datos GA4 aún no disponibles para cliente '%s' (tabla '%s' inexistente).",
                        client_info.cliente_id,
                        source_daily_table,
                        extra={
                            "id_cliente": client_info.cliente_id,
                            "fecha_inicio_datos_ga4": start_str,
                            "fecha_fin_datos_ga4": end_str,
                        },
                    )
                    return False

                if table.num_rows is not None and table.num_rows == 0:
                    logger.info(
                        "Tabla GA4 '%s' para cliente '%s' existe pero tiene 0 filas.",
                        source_daily_table,
                        client_info.cliente_id,
                        extra={
                            "id_cliente": client_info.cliente_id,
                            "fecha_inicio_datos_ga4": start_str,
                            "fecha_fin_datos_ga4": end_str,
                        },
                    )
                    return False

                return True

            return await loop.run_in_executor(None, _check_single_table)

        dataset_ref = bigquery.DatasetReference(
            client_info.client_gcp_project_id,
            f"analytics_{client_info.ga4_property_id}",
        )
        start_suffix = start_date.strftime("%Y%m%d")
        end_suffix = effective_end.strftime("%Y%m%d")

        def _check_range_tables() -> bool:
            try:
                tables = list(self.client.list_tables(dataset_ref))
            except NotFound:
                logger.info(
                    "Dataset GA4 '%s.analytics_%s' inexistente aún para cliente '%s'.",
                    client_info.client_gcp_project_id,
                    client_info.ga4_property_id,
                    client_info.cliente_id,
                    extra={
                        "id_cliente": client_info.cliente_id,
                        "fecha_inicio_datos_ga4": start_str,
                        "fecha_fin_datos_ga4": end_str,
                    },
                )
                return False

            for table_item in tables:
                table_id = table_item.table_id
                if not table_id.startswith("events_"):
                    continue
                suffix = table_id[len("events_"):]
                if len(suffix) == 8 and suffix.isdigit() and start_suffix <= suffix <= end_suffix:
                    return True

            logger.info(
                "Sin tablas diarias GA4 disponibles para cliente '%s' en rango [%s, %s].",
                client_info.cliente_id,
                start_str,
                end_str,
                extra={
                    "id_cliente": client_info.cliente_id,
                    "fecha_inicio_datos_ga4": start_str,
                    "fecha_fin_datos_ga4": end_str,
                },
            )
            return False

        return await loop.run_in_executor(None, _check_range_tables)

    def build_merge_query(self, client_info: ClientSourceIntegration) -> str:
        """
        Construye la sentencia SQL MERGE Cross-Project parametrizada por fecha y cliente_id.
        """
        table_full_id = self.get_table_full_id(client_info.gcp_region)
        source_table = f"{client_info.client_gcp_project_id}.analytics_{client_info.ga4_property_id}.events_*"

        return f"""
        MERGE `{table_full_id}` T
        USING (
          SELECT
            @cliente_id AS cliente_id,
            PARSE_DATE('%Y%m%d', event_date) AS fecha_evento,
            TO_HEX(SHA256(COALESCE(user_id, user_pseudo_id))) AS id_usuario,
            event_timestamp,
            TIMESTAMP_MICROS(event_timestamp) AS timestamp,
            event_name AS nombre_evento,
            CASE
              WHEN event_name = 'page_view' THEN 'visita_pagina'
              WHEN event_name = 'scroll' THEN 'scroll'
              WHEN event_name IN (
                'click', 'add_to_cart', 'purchase', 'view_item',
                'view_item_list', 'select_item', 'view_promotion',
                'select_promotion', 'add_to_wishlist', 'view_cart',
                'begin_checkout', 'add_shipping_info', 'add_payment_info',
                'remove_from_cart', 'refund'
              ) THEN 'interaccion'
              ELSE 'otro'
            END AS tipo_evento,
            (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location') AS ruta,
            (
              SELECT NULLIF(TRIM(CONCAT(
                COALESCE((SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'link_url'), ''),
                CASE
                  WHEN (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'link_url') IS NOT NULL
                   AND (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'link_text') IS NOT NULL
                  THEN ' | ' ELSE ''
                END,
                COALESCE((SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'link_text'), '')
              )), '')
            ) AS detalle_click,
            (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'search_term') AS termino_busqueda,
            (
              SELECT COALESCE(value.int_value, SAFE_CAST(value.string_value AS INT64))
              FROM UNNEST(event_params) WHERE key = 'percent_scrolled'
            ) AS porcentaje_scroll,
            (
              SELECT COALESCE(value.int_value, SAFE_CAST(value.string_value AS INT64))
              FROM UNNEST(event_params) WHERE key = 'engagement_time_msec'
            ) AS tiempo_engagement_ms,
            TO_JSON_STRING(items) AS items,
            (
              SELECT TO_JSON_STRING(ARRAY_AGG(STRUCT(
                (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'promotion_id') AS promotion_id,
                (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'promotion_name') AS promotion_name,
                (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'creative_name') AS creative_name,
                (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'creative_slot') AS creative_slot
              )))
              FROM UNNEST([1])
              WHERE (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'promotion_id') IS NOT NULL
                 OR (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'promotion_name') IS NOT NULL
            ) AS promociones,
            geo.country AS pais,
            geo.city AS ciudad,
            device.category AS tipo_dispositivo,
            device.web_info.browser AS navegador,
            device.operating_system AS sistema_operativo
          FROM `{source_table}`
          WHERE _TABLE_SUFFIX BETWEEN @start_suffix AND @end_suffix
            AND REGEXP_CONTAINS(_TABLE_SUFFIX, r'^\\d{{8}}$')
            AND event_name NOT IN ('first_visit', 'session_start', 'user_engagement')
        ) S
        ON T.fecha_evento = S.fecha_evento
          AND T.cliente_id = S.cliente_id
          AND T.event_timestamp = S.event_timestamp
          AND T.id_usuario = S.id_usuario
          AND T.nombre_evento = S.nombre_evento
        WHEN NOT MATCHED THEN
          INSERT ROW;
        """

    async def execute_client_merge(
        self,
        client_info: ClientSourceIntegration,
        start_date: date,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Ejecuta la consulta MERGE Cross-Project en BigQuery para el rango [start_date, end_date]
        forzando la región del cliente.

        Retorna:
            Diccionario con filas afectadas, bytes procesados, job_id, etc.
        """
        effective_end = end_date or start_date

        # 1. Asegurar que el dataset y la tabla destino existan en la región del cliente
        await self.ensure_target_schema(client_info.gcp_region)

        # 2. Preparar consulta y parámetros
        sql = self.build_merge_query(client_info)
        start_suffix = start_date.strftime("%Y%m%d")
        end_suffix = effective_end.strftime("%Y%m%d")

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("cliente_id", "STRING", client_info.cliente_id),
                bigquery.ScalarQueryParameter("start_suffix", "STRING", start_suffix),
                bigquery.ScalarQueryParameter("end_suffix", "STRING", end_suffix),
            ]
        )

        start_str = start_date.strftime("%Y-%m-%d")
        end_str = effective_end.strftime("%Y-%m-%d")
        logger.info(
            "Ejecutando MERGE para cliente '%s' (región: %s, rango datos: %s..%s)...",
            client_info.cliente_id,
            client_info.gcp_region,
            start_suffix,
            end_suffix,
            extra={
                "id_cliente": client_info.cliente_id,
                "fecha_inicio_datos_ga4": start_str,
                "fecha_fin_datos_ga4": end_str,
                "region": client_info.gcp_region,
            },
        )

        loop = asyncio.get_running_loop()

        def _run_query():
            query_job = self.client.query(
                sql,
                job_config=job_config,
                location=client_info.gcp_region
            )
            query_job.result()  # Esperar a que culmine la ejecución del Job en BQ
            return query_job

        query_job = await loop.run_in_executor(None, _run_query)

        rows_affected = query_job.num_dml_affected_rows or 0
        bytes_processed = query_job.total_bytes_processed or 0
        job_id = query_job.job_id

        logger.info(
            "MERGE finalizado para cliente '%s'. Filas afectadas: %d, Bytes procesados: %d (Job ID: %s)",
            client_info.cliente_id,
            rows_affected,
            bytes_processed,
            job_id,
            extra={
                "id_cliente": client_info.cliente_id,
                "fecha_inicio_datos_ga4": start_str,
                "fecha_fin_datos_ga4": end_str,
                "region": client_info.gcp_region,
                "job_id": job_id,
                "filas_afectadas": rows_affected,
                "bytes_procesados": bytes_processed,
            },
        )

        return {
            "rows_affected": rows_affected,
            "bytes_processed": bytes_processed,
            "job_id": job_id,
        }
