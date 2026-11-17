"""Servicio de integración y persistencia de reportes de exploración en Google BigQuery."""

import asyncio
from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from app.config import get_settings
from app.models.exploration_report import ExplorationReport
from app.models.session_trace import SessionTrace

logger = logging.getLogger(__name__)

# Esquema estandarizado de la tabla de salida patrones_friccion_explorados en friccion_resultados
EXPLORATION_REPORT_SCHEMA: List[bigquery.SchemaField] = [
    bigquery.SchemaField("id_patron", "STRING", mode="REQUIRED", description="ID del patrón de fricción"),
    bigquery.SchemaField("id_cliente", "STRING", mode="REQUIRED", description="Identificador único del cliente"),
    bigquery.SchemaField("id_sesion", "STRING", mode="REQUIRED", description="ID de la sesión representativa"),
    bigquery.SchemaField(
        "fecha_exploracion",
        "DATE",
        mode="REQUIRED",
        description="Fecha de ejecución de la exploración (YYYY-MM-DD)",
    ),
    bigquery.SchemaField("status", "STRING", mode="REQUIRED", description="Estado final (COMPLETED/PARTIAL/FAILED)"),
    bigquery.SchemaField("total_steps", "INTEGER", mode="REQUIRED", description="Total de pasos de la sesión"),
    bigquery.SchemaField("completed_steps", "INTEGER", mode="REQUIRED", description="Pasos reproducidos con éxito"),
    bigquery.SchemaField("started_at", "TIMESTAMP", mode="REQUIRED", description="Inicio de la reproducción"),
    bigquery.SchemaField("finished_at", "TIMESTAMP", mode="REQUIRED", description="Fin de la reproducción"),
    bigquery.SchemaField("objetivo", "STRING", mode="NULLABLE", description="Objetivo de conversión evaluado"),
    bigquery.SchemaField("secuencia", "STRING", mode="REPEATED", description="Secuencia de eventos del patrón"),
    bigquery.SchemaField("sesiones", "INTEGER", mode="NULLABLE", description="Cantidad de sesiones del patrón"),
    bigquery.SchemaField("usuarios", "INTEGER", mode="NULLABLE", description="Cantidad de usuarios en el patrón"),
    bigquery.SchemaField("llegada_grupo", "FLOAT", mode="NULLABLE", description="Tasa de llegada del grupo anómalo"),
    bigquery.SchemaField("llegada_referencia", "FLOAT", mode="NULLABLE", description="Tasa de llegada de referencia"),
    bigquery.SchemaField("sesiones_perdidas", "FLOAT", mode="NULLABLE", description="Impacto en sesiones perdidas"),
    bigquery.SchemaField("id_modelo", "STRING", mode="NULLABLE", description="ID del modelo de detección"),
    bigquery.SchemaField("primera_deteccion", "DATE", mode="NULLABLE", description="Primera fecha de detección"),
    bigquery.SchemaField("ultima_deteccion", "DATE", mode="NULLABLE", description="Última fecha de detección"),
    bigquery.SchemaField(
        "device_info",
        "RECORD",
        mode="NULLABLE",
        description="Contexto del dispositivo de la sesión representativa",
        fields=[
            bigquery.SchemaField("tipo_dispositivo", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("navegador", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("sistema_operativo", "STRING", mode="NULLABLE"),
        ],
    ),
    bigquery.SchemaField(
        "evidences",
        "RECORD",
        mode="REPEATED",
        description="Evidencias visuales y contexto de interacción por paso",
        fields=[
            bigquery.SchemaField("orden", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("nombre_evento", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("ruta", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("items", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("scroll", "BOOLEAN", mode="REQUIRED"),
            bigquery.SchemaField("en_patron", "BOOLEAN", mode="REQUIRED"),
            bigquery.SchemaField("es_paso_friccion", "BOOLEAN", mode="REQUIRED"),
            bigquery.SchemaField("screenshot_url", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField(
                "bounding_box_context",
                "RECORD",
                mode="NULLABLE",
                fields=[
                    bigquery.SchemaField(
                        "box",
                        "RECORD",
                        mode="REQUIRED",
                        fields=[
                            bigquery.SchemaField("x", "FLOAT", mode="REQUIRED"),
                            bigquery.SchemaField("y", "FLOAT", mode="REQUIRED"),
                            bigquery.SchemaField("width", "FLOAT", mode="REQUIRED"),
                            bigquery.SchemaField("height", "FLOAT", mode="REQUIRED"),
                        ],
                    ),
                    bigquery.SchemaField("tag_name", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("element_text", "STRING", mode="NULLABLE"),
                    bigquery.SchemaField("role", "STRING", mode="NULLABLE"),
                    bigquery.SchemaField("aria_label", "STRING", mode="NULLABLE"),
                    bigquery.SchemaField("context_type", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("surrounding_text", "STRING", mode="NULLABLE"),
                ],
            ),
            bigquery.SchemaField("context_notes", "STRING", mode="REPEATED"),
        ],
    ),
    bigquery.SchemaField("error_message", "STRING", mode="NULLABLE", description="Detalle del error fatal si hubo"),
    bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED", description="Momento de inserción en BigQuery"),
]


class BigQueryService:
    """
    Servicio de integración con Google BigQuery sobre el dataset centralizado
    de resultados de fricción (`friccion_resultados`).
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        client: Optional[Any] = None,
    ) -> None:
        """
        Inicializa el cliente de BigQuery.

        :param project_id: ID del proyecto de GCP por defecto (opcional).
        :param client: Cliente preexistente para inyección en pruebas unitarias.
        """
        self.settings = get_settings()
        self.project_id = project_id or self.settings.PLATFORM_GCP_PROJECT_ID
        self.client: Optional[bigquery.Client] = None

        if client is not None:
            self.client = client
        else:
            try:
                self.client = bigquery.Client(project=self.project_id)
                logger.info("[BigQueryService] Cliente de BigQuery inicializado exitosamente.")
            except Exception as exc:
                logger.warning(
                    f"[BigQueryService] No fue posible inicializar cliente BigQuery automáticamente: {exc}. "
                    "Operando en modo sin persistencia analítica directa."
                )

    def is_connected(self) -> bool:
        """Verifica si hay un cliente activo de BigQuery configurado."""
        return self.client is not None

    def get_dataset_id(self) -> str:
        """Retorna el nombre del dataset centralizado configurado."""
        return self.settings.BIGQUERY_DATASET

    def report_to_row(self, report: ExplorationReport) -> Dict[str, Any]:
        """
        Convierte una instancia de ExplorationReport en un diccionario serializable para BigQuery.
        """
        evidences_data: List[Dict[str, Any]] = []
        for ev in report.evidences:
            bbox_dict: Optional[Dict[str, Any]] = None
            if ev.bounding_box_context:
                bbox_dict = {
                    "box": {
                        "x": ev.bounding_box_context.box.x,
                        "y": ev.bounding_box_context.box.y,
                        "width": ev.bounding_box_context.box.width,
                        "height": ev.bounding_box_context.box.height,
                    },
                    "tag_name": ev.bounding_box_context.tag_name,
                    "element_text": ev.bounding_box_context.element_text,
                    "role": ev.bounding_box_context.role,
                    "aria_label": ev.bounding_box_context.aria_label,
                    "context_type": ev.bounding_box_context.context_type,
                    "surrounding_text": ev.bounding_box_context.surrounding_text,
                }

            evidences_data.append(
                {
                    "orden": ev.orden,
                    "nombre_evento": ev.nombre_evento,
                    "ruta": ev.ruta,
                    "items": ev.items,
                    "scroll": ev.scroll,
                    "en_patron": ev.en_patron,
                    "es_paso_friccion": ev.es_paso_friccion,
                    "screenshot_url": ev.screenshot_url,
                    "timestamp": ev.timestamp,
                    "bounding_box_context": bbox_dict,
                    "context_notes": list(ev.context_notes),
                }
            )

        device_info_dict: Optional[Dict[str, Any]] = None
        if report.device_info:
            device_info_dict = {
                "tipo_dispositivo": report.device_info.tipo_dispositivo,
                "navegador": report.device_info.navegador,
                "sistema_operativo": report.device_info.sistema_operativo,
            }

        return {
            "id_patron": report.id_patron,
            "id_cliente": report.id_cliente,
            "id_sesion": report.id_sesion,
            "fecha_exploracion": report.fecha_exploracion,
            "status": report.status.value,
            "total_steps": report.total_steps,
            "completed_steps": report.completed_steps,
            "started_at": report.started_at,
            "finished_at": report.finished_at,
            "objetivo": report.objetivo,
            "secuencia": report.secuencia,
            "sesiones": report.sesiones,
            "usuarios": report.usuarios,
            "llegada_grupo": report.llegada_grupo,
            "llegada_referencia": report.llegada_referencia,
            "sesiones_perdidas": report.sesiones_perdidas,
            "id_modelo": report.id_modelo,
            "primera_deteccion": report.primera_deteccion,
            "ultima_deteccion": report.ultima_deteccion,
            "device_info": device_info_dict,
            "evidences": evidences_data,
            "error_message": report.error_message,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def _build_patterns_query(
        self,
        patrones_ref: str,
        sesiones_ref: str,
        explorados_ref: Optional[str] = None,
    ) -> str:
        """Construye la consulta SQL de patrones JOIN sesiones representativas."""
        exclusion_clause = ""
        if explorados_ref:
            exclusion_clause = f"""
              AND NOT EXISTS (
                  SELECT 1
                  FROM {explorados_ref} e
                  WHERE e.id_patron = p.id_patron
                    AND e.id_cliente = p.id_cliente
                    AND e.status IN ('COMPLETED', 'PARTIAL')
              )"""

        return f"""
            SELECT
                p.id_patron,
                p.id_cliente,
                p.objetivo,
                p.secuencia,
                p.sesiones,
                p.usuarios,
                p.llegada_grupo,
                p.llegada_referencia,
                p.sesiones_perdidas,
                p.id_modelo,
                p.primera_deteccion,
                p.ultima_deteccion,
                ANY_VALUE(sr.id_sesion) AS id_sesion,
                ARRAY_AGG(
                    STRUCT(
                        sr.orden,
                        sr.nombre_evento,
                        sr.ruta,
                        sr.items,
                        sr.scroll,
                        sr.en_patron,
                        sr.es_paso_friccion,
                        sr.tipo_dispositivo,
                        sr.navegador,
                        sr.sistema_operativo
                    )
                    ORDER BY sr.orden ASC
                ) AS pasos
            FROM {patrones_ref} p
            INNER JOIN {sesiones_ref} sr
                ON p.id_patron = sr.id_patron
            WHERE p.id_cliente = @client_id
              AND p.ultima_deteccion <= CAST(@fecha_ejecucion AS DATE){exclusion_clause}
            GROUP BY
                p.id_patron,
                p.id_cliente,
                p.objetivo,
                p.secuencia,
                p.sesiones,
                p.usuarios,
                p.llegada_grupo,
                p.llegada_referencia,
                p.sesiones_perdidas,
                p.id_modelo,
                p.primera_deteccion,
                p.ultima_deteccion
            ORDER BY p.sesiones_perdidas DESC
        """

    def _sync_query_patterns(
        self,
        query: str,
        job_config: bigquery.QueryJobConfig,
        region: Optional[str] = None,
        fallback_query: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Ejecuta sincrónicamente una consulta para recuperar patrones de fricción."""
        if not self.client:
            raise RuntimeError("No hay cliente BigQuery activo para consultar patrones.")
        resolved_region = (region or self.settings.DEFAULT_BIGQUERY_REGION).strip().lower()
        try:
            query_job = self.client.query(query, job_config=job_config)
            results = query_job.result()
            rows = [dict(row.items()) for row in results]
            logger.info(
                f"[BigQueryService] Consulta de patrones completada ({len(rows)} filas).",
                extra={
                    "region": resolved_region,
                    "job_id": getattr(query_job, "job_id", None),
                    "filas_afectadas": len(rows),
                    "bytes_procesados": getattr(query_job, "total_bytes_processed", None),
                },
            )
            return rows
        except NotFound as exc:
            if fallback_query and self.settings.BIGQUERY_TABLE_NAME in str(exc):
                logger.info(
                    "[BigQueryService] Tabla de reportes explorados aún no existe; "
                    "consultando todos los patrones pendientes sin exclusión previa.",
                    extra={"region": resolved_region},
                )
                return self._sync_query_patterns(
                    fallback_query,
                    job_config,
                    region=resolved_region,
                    fallback_query=None,
                )
            logger.info(
                "[BigQueryService] Tabla de patrones o sesiones aún no existe en BigQuery; "
                "retornando lista vacía.",
                extra={"region": resolved_region},
            )
            return []
        except Exception as exc:
            logger.error(
                f"[BigQueryService] Error al consultar patrones de fricción: {exc}",
                extra={"region": resolved_region},
            )
            raise

    async def get_friction_patterns_for_client(
        self,
        client_id: str,
        batch_date: str,
        region: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> List[SessionTrace]:
        """
        Consulta de forma incremental los patrones de fricción pendientes de explorar para un cliente.

        Combina `patrones` y `sesion_representativa` en el dataset centralizado `friccion_resultados`,
        filtrando por `ultima_deteccion <= fecha_ejecucion`, excluyendo patrones ya explorados en
        estado COMPLETED o PARTIAL, y priorizando por mayor impacto (`sesiones_perdidas DESC`).

        :param client_id: Identificador único del cliente (`id_cliente`).
        :param batch_date: Fecha de corte de ejecución (formato YYYY-MM-DD).
        :param region: Región GCP informativa para trazabilidad en logs (opcional).
        :param project_id: ID del proyecto GCP central (opcional).
        :return: Lista de instancias SessionTrace reconstruidas listas para explorar.
        """
        resolved_region = (region or self.settings.DEFAULT_BIGQUERY_REGION).strip().lower()
        if not self.client:
            logger.error(
                "[BigQueryService] No hay cliente BigQuery activo para consultar patrones.",
                extra={"region": resolved_region},
            )
            raise RuntimeError("No hay cliente BigQuery activo para consultar patrones.")

        target_project = project_id or self.project_id or getattr(self.client, "project", None)
        if not target_project:
            logger.error(
                "[BigQueryService] No se pudo determinar el project_id de GCP para BigQuery.",
                extra={"region": resolved_region},
            )
            raise RuntimeError("No se pudo determinar el project_id de GCP para BigQuery.")

        dataset_id = self.get_dataset_id()
        patrones_ref = f"`{target_project}.{dataset_id}.{self.settings.BIGQUERY_PATTERNS_TABLE_NAME}`"
        sesiones_ref = f"`{target_project}.{dataset_id}.{self.settings.BIGQUERY_SESSIONS_TABLE_NAME}`"
        explorados_ref = f"`{target_project}.{dataset_id}.{self.settings.BIGQUERY_TABLE_NAME}`"

        query = self._build_patterns_query(patrones_ref, sesiones_ref, explorados_ref=explorados_ref)
        fallback_query = self._build_patterns_query(patrones_ref, sesiones_ref, explorados_ref=None)

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("client_id", "STRING", client_id),
                bigquery.ScalarQueryParameter("fecha_ejecucion", "STRING", str(batch_date)),
            ]
        )

        rows = await asyncio.to_thread(
            self._sync_query_patterns,
            query,
            job_config,
            resolved_region,
            fallback_query,
        )
        traces: List[SessionTrace] = []
        for row in rows:
            try:
                raw_pasos = row.get("pasos")
                session_rows = [dict(p) for p in raw_pasos] if isinstance(raw_pasos, list) else None
                traces.append(SessionTrace.from_friction_pattern(row, session_rows=session_rows))
            except Exception as exc:
                logger.error(
                    f"[BigQueryService] Error al deserializar patrón de fricción: {exc}",
                    extra={"region": resolved_region},
                )

        logger.info(
            f"[BigQueryService] Se obtuvieron {len(traces)} patrones pendientes de explorar "
            f"para cliente='{client_id}', corte='{batch_date}'",
            extra={"region": resolved_region, "filas_afectadas": len(traces)},
        )
        return traces

    def _sync_delete_existing(
        self,
        table_ref: str,
        id_cliente: str,
        id_patron: str,
        fecha_exploracion: str,
    ) -> bool:
        """Elimina registros previos con la clave (id_cliente, id_patron, fecha_exploracion) para idempotencia."""
        if not self.client:
            return False

        delete_query = f"""
            DELETE FROM `{table_ref}`
            WHERE id_cliente = @id_cliente
              AND id_patron = @id_patron
              AND CAST(fecha_exploracion AS STRING) = @fecha_exploracion
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("id_cliente", "STRING", id_cliente),
                bigquery.ScalarQueryParameter("id_patron", "STRING", id_patron),
                bigquery.ScalarQueryParameter("fecha_exploracion", "STRING", str(fecha_exploracion)),
            ]
        )
        try:
            query_job = self.client.query(delete_query, job_config=job_config)
            query_job.result()
            logger.info(
                f"[BigQueryService] Registros previos eliminados para id_patron='{id_patron}' en '{table_ref}'",
                extra={
                    "job_id": getattr(query_job, "job_id", None),
                    "filas_afectadas": getattr(query_job, "num_dml_affected_rows", None),
                    "bytes_procesados": getattr(query_job, "total_bytes_processed", None),
                },
            )
            return True
        except NotFound:
            return True
        except Exception as exc:
            if "streaming buffer" in str(exc).lower():
                logger.info(
                    f"[BigQueryService] Registros en streaming buffer de BigQuery para id_patron='{id_patron}'; "
                    "omitiendo borrado físico inmediato (se resolverá analíticamente por created_at)."
                )
                return True
            logger.warning(f"[BigQueryService] No se pudo ejecutar borrado previo idempotente: {exc}")
            return False

    def _sync_insert(self, table_ref: Any, row: Dict[str, Any], idempotent: bool = True) -> bool:
        """Operación síncrona de inserción en BigQuery con soporte idempotente."""
        if not self.client:
            return False

        if idempotent:
            self._sync_delete_existing(
                str(table_ref),
                row.get("id_cliente", ""),
                row.get("id_patron", ""),
                row.get("fecha_exploracion", ""),
            )

        try:
            errors = self.client.insert_rows_json(table_ref, [row])
            if errors:
                logger.error(f"[BigQueryService] Errores al insertar fila en BigQuery: {errors}")
                return False
            logger.info(f"[BigQueryService] Fila persistida exitosamente en '{table_ref}'")
            return True
        except NotFound:
            logger.info(f"[BigQueryService] Tabla '{table_ref}' no encontrada; creándola con esquema...")
            try:
                table = bigquery.Table(table_ref, schema=EXPLORATION_REPORT_SCHEMA)
                table.clustering_fields = ["id_cliente", "id_patron"]
                self.client.create_table(table, exists_ok=True)
                retry_errors = None
                for attempt in range(1, 4):
                    try:
                        retry_errors = self.client.insert_rows_json(table_ref, [row])
                        break
                    except NotFound:
                        if attempt == 3:
                            raise
                        time.sleep(1.0 * attempt)

                if retry_errors:
                    logger.error(f"[BigQueryService] Errores en retry tras crear tabla: {retry_errors}")
                    return False
                logger.info(f"[BigQueryService] Fila persistida exitosamente tras crear tabla '{table_ref}'")
                return True
            except Exception as create_exc:
                logger.error(f"[BigQueryService] Falló creación o reintento de tabla '{table_ref}': {create_exc}")
                return False
        except Exception as exc:
            logger.error(f"[BigQueryService] Excepción al insertar en BigQuery: {exc}")
            return False

    def _sync_ensure_exploration_table_exists(self, table_ref: str) -> bool:
        """Verifica síncronamente que la tabla de reportes exista en BigQuery; si no, la crea con clustering."""
        if not self.client:
            return False
        try:
            self.client.get_table(table_ref)
            logger.info(f"[BigQueryService] Tabla de reportes verificada: '{table_ref}'")
            return True
        except NotFound:
            logger.info(
                f"[BigQueryService] Tabla '{table_ref}' no existe; creándola con clustering (id_cliente, id_patron)..."
            )
            try:
                table = bigquery.Table(table_ref, schema=EXPLORATION_REPORT_SCHEMA)
                table.clustering_fields = ["id_cliente", "id_patron"]
                self.client.create_table(table, exists_ok=True)
                logger.info(f"[BigQueryService] Tabla '{table_ref}' creada exitosamente.")
                return True
            except Exception as exc:
                logger.error(f"[BigQueryService] Error al crear tabla de reportes '{table_ref}': {exc}")
                return False
        except Exception as exc:
            logger.warning(f"[BigQueryService] Error al verificar tabla '{table_ref}': {exc}")
            return False

    async def ensure_exploration_table_exists(
        self,
        region: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> bool:
        """
        Verifica proactivamente que la tabla de reportes de exploración exista en `friccion_resultados`.
        Si no existe, la crea con su esquema completo y clustering por (`id_cliente`, `id_patron`).
        """
        if not self.client:
            logger.warning("[BigQueryService] No hay cliente BigQuery activo para verificar/crear tabla.")
            return False

        target_project = project_id or self.project_id or getattr(self.client, "project", None)
        if not target_project:
            logger.error("[BigQueryService] No se pudo determinar el project_id de GCP para BigQuery.")
            return False

        dataset_id = self.get_dataset_id()
        table_name = self.settings.BIGQUERY_TABLE_NAME
        table_ref = f"{target_project}.{dataset_id}.{table_name}"
        return await asyncio.to_thread(self._sync_ensure_exploration_table_exists, table_ref)

    async def save_exploration_report(
        self,
        report: ExplorationReport,
        region: Optional[str] = None,
        project_id: Optional[str] = None,
        idempotent: bool = True,
    ) -> bool:
        """
        Persiste el reporte de exploración en `friccion_resultados.patrones_friccion_explorados`.

        Garantiza idempotencia eliminando previamente registros duplicados de la misma clave
        (`id_cliente`, `id_patron`, `fecha_exploracion`).
        """
        if not self.client:
            logger.warning("[BigQueryService] No hay cliente BigQuery activo para persistir reporte.")
            return False

        target_project = project_id or self.project_id or getattr(self.client, "project", None)
        if not target_project:
            logger.error("[BigQueryService] No se pudo determinar el project_id de GCP para BigQuery.")
            return False

        dataset_id = self.get_dataset_id()
        table_name = self.settings.BIGQUERY_TABLE_NAME
        table_ref = f"{target_project}.{dataset_id}.{table_name}"

        row_payload = self.report_to_row(report)
        return await asyncio.to_thread(self._sync_insert, table_ref, row_payload, idempotent)

    async def save_exploration_report_idempotent(
        self,
        report: ExplorationReport,
        region: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> bool:
        """Alias explícito para persistir un reporte garantizando idempotencia."""
        return await self.save_exploration_report(
            report=report,
            region=region,
            project_id=project_id,
            idempotent=True,
        )
