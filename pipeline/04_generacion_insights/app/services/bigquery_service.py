"""Servicio para consultas analíticas sobre BigQuery y cálculo de distribuciones de audiencia."""

from collections import defaultdict
from datetime import date, datetime
import logging
from typing import Any, Dict, List, Optional

from google.cloud import bigquery
from google.oauth2 import service_account

from app.config import Settings, get_settings
from app.models.exploration_models import (
    AudienceDistributionItem,
    AudienceDistributions,
    BoundingBoxContext,
    BoundingBoxCoordinates,
    DeviceInfo,
    ExplorationEvidence,
    ExplorationReport,
)

logger = logging.getLogger(__name__)


class BigQueryServiceError(Exception):
    """Excepción para errores de ejecución o comunicación con Google BigQuery."""
    pass


class BigQueryService:
    """Gestiona la consulta de patrones explorados, modelos y distribuciones en BigQuery."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        client: Optional[bigquery.Client] = None,
    ) -> None:
        """Inicializa el servicio de BigQuery con inyección de cliente o settings.

        Args:
            settings: Configuración general del módulo.
            client: Instancia preexistente de bigquery.Client (útil para pruebas unitarias).
        """
        self.settings = settings or get_settings()
        self._client = client

    @property
    def client(self) -> bigquery.Client:
        """Obtiene o inicializa el cliente de BigQuery con credenciales ADC o archivo SA."""
        if self._client is None:
            if self.settings.GOOGLE_APPLICATION_CREDENTIALS:
                logger.info(
                    "Inicializando cliente BigQuery con credenciales de archivo: %s",
                    self.settings.GOOGLE_APPLICATION_CREDENTIALS,
                )
                credentials = service_account.Credentials.from_service_account_file(
                    self.settings.GOOGLE_APPLICATION_CREDENTIALS,
                )
                self._client = bigquery.Client(
                    project=self.settings.PLATFORM_GCP_PROJECT_ID,
                    credentials=credentials,
                )
            else:
                logger.info("Inicializando cliente BigQuery con credenciales por defecto (ADC)")
                self._client = bigquery.Client(project=self.settings.PLATFORM_GCP_PROJECT_ID)
        return self._client

    def get_completed_exploration_reports(
        self,
        client_id: str,
        batch_date: str,
        enrich_distributions: bool = True,
    ) -> List[ExplorationReport]:
        """Consulta patrones explorados completados en BigQuery enriquecidos con el modelo.

        Args:
            client_id: UUID del cliente a consultar.
            batch_date: Fecha de exploración en formato YYYY-MM-DD.
            enrich_distributions: Si es True, calcula las distribuciones de audiencia desde eventos_usuario.

        Returns:
            Lista de objetos ExplorationReport deduplicados.

        Raises:
            BigQueryServiceError: Ante fallos en la consulta o comunicación con BigQuery.
        """
        project_id = self.settings.PLATFORM_GCP_PROJECT_ID
        dataset_id = self.settings.BIGQUERY_DATASET_ID
        exploration_table = f"{project_id}.{dataset_id}.{self.settings.BIGQUERY_EXPLORATION_TABLE_NAME}"
        models_table = f"{project_id}.{dataset_id}.{self.settings.BIGQUERY_MODELS_TABLE_NAME}"

        query = f"""
        WITH exploraciones_dedup AS (
          SELECT *,
                 ROW_NUMBER() OVER(
                   PARTITION BY id_cliente, id_patron
                   ORDER BY fecha_exploracion DESC, created_at DESC
                 ) AS rn
          FROM `{exploration_table}`
          WHERE id_cliente = @id_cliente
            AND fecha_exploracion <= CAST(@fecha_ejecucion AS DATE)
            AND status = 'COMPLETED'
        )
        SELECT
          e.* EXCEPT(rn),
          m.sesiones AS total_sesiones_modelo,
          m.objetivo AS objetivo_modelo,
          m.eventos_clave AS eventos_clave_modelo,
          m.nombres_hitos AS nombres_hitos_modelo,
          m.datos_desde AS datos_desde_modelo,
          m.datos_hasta AS datos_hasta_modelo
        FROM exploraciones_dedup e
        LEFT JOIN `{models_table}` m
          ON e.id_modelo = m.id_modelo
        WHERE e.rn = 1
        ORDER BY e.sesiones_perdidas DESC NULLS LAST, e.id_patron ASC;
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("id_cliente", "STRING", client_id),
                bigquery.ScalarQueryParameter("fecha_ejecucion", "STRING", batch_date),
            ]
        )

        try:
            logger.info(
                "Consultando reportes explorados en BigQuery para id_cliente='%s', fecha_exploracion='%s'.",
                client_id,
                batch_date,
                extra={"tabla_origen": exploration_table},
            )
            query_job = self.client.query(query, job_config=job_config)
            rows = query_job.result()

            reports: List[ExplorationReport] = []
            for row in rows:
                row_dict = dict(row.items())
                reports.append(self._parse_row_to_report(row_dict))

            raw_bytes = getattr(query_job, "total_bytes_processed", None)
            bytes_procesados = raw_bytes if isinstance(raw_bytes, int) else 0
            raw_job_id = getattr(query_job, "job_id", None)
            job_id_str = raw_job_id if isinstance(raw_job_id, str) else None

            logger.info(
                "Se recuperaron %d reportes explorados completados de BigQuery.",
                len(reports),
                extra={
                    "job_id": job_id_str,
                    "filas_afectadas": len(reports),
                    "bytes_procesados": bytes_procesados,
                },
            )

            if reports and enrich_distributions:
                self._enrich_audience_distributions(
                    client_id=client_id,
                    batch_date=batch_date,
                    reports=reports,
                )

            return reports

        except Exception as exc:
            logger.error(
                "Error al consultar BigQuery en tabla '%s' para cliente '%s': %s",
                exploration_table,
                client_id,
                exc,
            )
            raise BigQueryServiceError(f"Error en consulta BigQuery: {exc}") from exc

    def _enrich_audience_distributions(
        self,
        client_id: str,
        batch_date: str,
        reports: List[ExplorationReport],
    ) -> None:
        """Calcula distribuciones porcentuales por dispositivo, navegador, SO y país."""
        project_id = self.settings.PLATFORM_GCP_PROJECT_ID
        results_dataset = self.settings.BIGQUERY_DATASET_ID
        exploration_table = f"{project_id}.{results_dataset}.{self.settings.BIGQUERY_EXPLORATION_TABLE_NAME}"
        models_table = f"{project_id}.{results_dataset}.{self.settings.BIGQUERY_MODELS_TABLE_NAME}"
        events_table = (
            f"{project_id}.{self.settings.BIGQUERY_EVENTS_DATASET_ID}.{self.settings.BIGQUERY_EVENTS_TABLE_NAME}"
        )

        query = f"""
        WITH patrones_lote AS (
          SELECT
            e.id_patron,
            e.id_cliente,
            e.secuencia,
            m.datos_desde,
            m.datos_hasta
          FROM (
            SELECT *,
                   ROW_NUMBER() OVER(
                     PARTITION BY id_cliente, id_patron
                     ORDER BY fecha_exploracion DESC, created_at DESC
                   ) AS rn
            FROM `{exploration_table}`
            WHERE id_cliente = @id_cliente
              AND fecha_exploracion <= CAST(@fecha_ejecucion AS DATE)
              AND status = 'COMPLETED'
          ) e
          LEFT JOIN `{models_table}` m
            ON e.id_modelo = m.id_modelo
          WHERE e.rn = 1
        ),
        ventana AS (
          SELECT
            MIN(DATE(datos_desde)) AS min_fecha,
            MAX(DATE(datos_hasta)) AS max_fecha,
            MIN(datos_desde) AS min_ts,
            MAX(datos_hasta) AS max_ts
          FROM patrones_lote
        ),
        eventos_norm AS (
          SELECT
            ev.id_usuario,
            ev.event_timestamp,
            LAG(ev.event_timestamp) OVER (PARTITION BY ev.id_usuario ORDER BY ev.event_timestamp) AS prev_ts,
            ev.nombre_evento,
            IFNULL(REGEXP_EXTRACT(ev.ruta, r'^https?://[^/]+(/.*)$'), '/') AS path_rel,
            IFNULL(NULLIF(ev.tipo_dispositivo, '(not set)'), 'Desconocido') AS tipo_dispositivo,
            IFNULL(NULLIF(ev.navegador, '(not set)'), 'Desconocido') AS navegador,
            IFNULL(NULLIF(ev.sistema_operativo, '(not set)'), 'Desconocido') AS sistema_operativo,
            IFNULL(NULLIF(ev.pais, '(not set)'), 'Desconocido') AS pais
          FROM `{events_table}` ev
          CROSS JOIN ventana v
          WHERE ev.cliente_id = @id_cliente
            AND ev.nombre_evento != 'scroll'
            AND (v.min_fecha IS NULL OR ev.fecha_evento BETWEEN v.min_fecha AND v.max_fecha)
            AND (v.min_ts IS NULL OR ev.timestamp BETWEEN v.min_ts AND v.max_ts)
        ),
        sesiones_cortadas AS (
          SELECT
            *,
            SUM(CASE WHEN prev_ts IS NULL OR (event_timestamp - prev_ts) > 399000000 THEN 1 ELSE 0 END)
              OVER (PARTITION BY id_usuario ORDER BY event_timestamp) AS num_sesion_usuario
          FROM eventos_norm
        ),
        tokens_sesion AS (
          SELECT
            CONCAT(id_usuario, '_', CAST(num_sesion_usuario AS STRING)) AS sesion_id,
            id_usuario,
            ANY_VALUE(tipo_dispositivo) AS tipo_dispositivo,
            ANY_VALUE(navegador) AS navegador,
            ANY_VALUE(sistema_operativo) AS sistema_operativo,
            ANY_VALUE(pais) AS pais,
            CONCAT(
              '|inicio_de_sesion|',
              STRING_AGG(
                CONCAT(
                  nombre_evento, ' ',
                  CASE
                    WHEN STARTS_WITH(path_rel, '/product/') THEN '/product/{{param}}'
                    WHEN STARTS_WITH(path_rel, '/search?keyword=') THEN '/search?keyword={{param}}'
                    WHEN STARTS_WITH(path_rel, '/shop/') AND path_rel != '/shop/shop-by-brand/google-cloud'
                      THEN '/shop/…'
                    WHEN STARTS_WITH(path_rel, '/checkout')
                      AND path_rel NOT IN (
                        '/checkout?show=multibillto&paymentType=StripeCustom&paymentState=',
                        '/checkout?show=payment&paymentType=StripeCustom&paymentState=payment'
                      ) THEN '/checkout/…'
                    ELSE path_rel
                  END
                ),
                '|' ORDER BY event_timestamp
              ),
              '|'
            ) AS seq_tokens
          FROM sesiones_cortadas
          GROUP BY sesion_id, id_usuario
        ),
        usuarios_por_patron AS (
          SELECT
            p.id_patron,
            t.id_usuario,
            ANY_VALUE(t.tipo_dispositivo) AS tipo_dispositivo,
            ANY_VALUE(t.navegador) AS navegador,
            ANY_VALUE(t.sistema_operativo) AS sistema_operativo,
            ANY_VALUE(t.pais) AS pais
          FROM patrones_lote p
          JOIN tokens_sesion t
            ON STRPOS(
                 t.seq_tokens,
                 CONCAT(
                   '|',
                   ARRAY_TO_STRING(
                     ARRAY(SELECT REGEXP_REPLACE(s, r' \\(la misma página\\)$', '') FROM UNNEST(p.secuencia) s),
                     '|'
                   ),
                   '|'
                 )
               ) > 0
          GROUP BY p.id_patron, t.id_usuario
        )
        SELECT
          id_patron,
          tipo_dispositivo,
          navegador,
          sistema_operativo,
          pais,
          COUNT(DISTINCT id_usuario) AS usuarios_cnt
        FROM usuarios_por_patron
        GROUP BY id_patron, tipo_dispositivo, navegador, sistema_operativo, pais;
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("id_cliente", "STRING", client_id),
                bigquery.ScalarQueryParameter("fecha_ejecucion", "STRING", batch_date),
            ]
        )

        try:
            query_job = self.client.query(query, job_config=job_config)
            rows = [dict(row.items()) for row in query_job.result()]
            distributions_by_pattern = self._build_distributions_map(rows)

            for report in reports:
                if report.id_patron in distributions_by_pattern:
                    report.audience_distributions = distributions_by_pattern[report.id_patron]

            raw_bytes = getattr(query_job, "total_bytes_processed", None)
            bytes_procesados = raw_bytes if isinstance(raw_bytes, int) else 0
            logger.info(
                "Distribuciones porcentuales de audiencia calculadas para %d patrones.",
                len(distributions_by_pattern),
                extra={"bytes_procesados": bytes_procesados},
            )
        except Exception as exc:
            logger.warning(
                "No se pudieron calcular las distribuciones de audiencia en BigQuery (se continúa sin ellas): %s",
                exc,
            )

    def _build_distributions_map(self, rows: List[Dict[str, Any]]) -> Dict[str, AudienceDistributions]:
        """Agrupa filas agregadas de usuarios y calcula porcentajes por las 4 dimensiones."""
        counts: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(
            lambda: {
                "tipo_dispositivo": defaultdict(int),
                "navegador": defaultdict(int),
                "sistema_operativo": defaultdict(int),
                "pais": defaultdict(int),
            }
        )

        for row in rows:
            pattern_id = row.get("id_patron")
            if not pattern_id:
                continue
            raw_cnt = row.get("usuarios_cnt")
            cnt = int(raw_cnt) if raw_cnt is not None else 0
            if cnt <= 0:
                continue

            pid = str(pattern_id)
            for dim in ("tipo_dispositivo", "navegador", "sistema_operativo", "pais"):
                label_val = row.get(dim)
                label = str(label_val).strip() if label_val else "Desconocido"
                if not label:
                    label = "Desconocido"
                counts[pid][dim][label] += cnt

        result: Dict[str, AudienceDistributions] = {}
        for pid, dims in counts.items():
            result[pid] = AudienceDistributions(
                dispositivos=self._to_distribution_items(dims["tipo_dispositivo"]),
                navegadores=self._to_distribution_items(dims["navegador"]),
                sistemas_operativos=self._to_distribution_items(dims["sistema_operativo"]),
                paises=self._to_distribution_items(dims["pais"]),
            )
        return result

    @staticmethod
    def _to_distribution_items(counter: Dict[str, int]) -> List[AudienceDistributionItem]:
        """Convierte conteos absolutos en porcentajes ordenados descendentemente."""
        total = sum(counter.values())
        if total <= 0:
            return []
        items = [
            AudienceDistributionItem(
                label=label,
                percentage=round((cnt / total) * 100.0, 1),
            )
            for label, cnt in counter.items()
        ]
        return sorted(items, key=lambda item: (-item.percentage, item.label))

    @staticmethod
    def _normalize_date(value: Any) -> Optional[str]:
        """Normaliza valores DATE/DATETIME de BigQuery a cadena YYYY-MM-DD."""
        if value is None:
            return None
        if isinstance(value, (datetime, date)):
            return value.strftime("%Y-%m-%d")
        text = str(value).strip()
        return text or None

    @staticmethod
    def _parse_device_info(raw: Any) -> Optional[DeviceInfo]:
        """Convierte el registro device_info de BigQuery en DeviceInfo."""
        if not isinstance(raw, dict):
            return None
        return DeviceInfo(
            tipo_dispositivo=raw.get("tipo_dispositivo"),
            navegador=raw.get("navegador"),
            sistema_operativo=raw.get("sistema_operativo"),
        )

    @staticmethod
    def _parse_evidence(ev: Any) -> Optional[ExplorationEvidence]:
        """Convierte un elemento del arreglo evidences de BigQuery en ExplorationEvidence."""
        if not isinstance(ev, dict):
            return None

        bbox_data = ev.get("bounding_box_context")
        bbox_context: Optional[BoundingBoxContext] = None

        if isinstance(bbox_data, dict):
            coords_data = bbox_data.get("box")
            coords = (
                BoundingBoxCoordinates(
                    x=float(coords_data.get("x", 0.0)),
                    y=float(coords_data.get("y", 0.0)),
                    width=float(coords_data.get("width", 0.0)),
                    height=float(coords_data.get("height", 0.0)),
                )
                if isinstance(coords_data, dict)
                else None
            )
            bbox_context = BoundingBoxContext(
                box=coords,
                tag_name=bbox_data.get("tag_name"),
                element_text=bbox_data.get("element_text"),
                role=bbox_data.get("role"),
                aria_label=bbox_data.get("aria_label"),
                context_type=bbox_data.get("context_type"),
                surrounding_text=bbox_data.get("surrounding_text"),
            )

        raw_orden = ev.get("orden")
        orden_val = int(raw_orden) if raw_orden is not None and int(raw_orden) >= 1 else 1

        return ExplorationEvidence(
            orden=orden_val,
            nombre_evento=str(ev.get("nombre_evento") or "page_view"),
            ruta=str(ev.get("ruta") or ""),
            items=ev.get("items"),
            scroll=bool(ev.get("scroll", False)),
            en_patron=bool(ev["en_patron"]) if ev.get("en_patron") is not None else True,
            es_paso_friccion=bool(ev.get("es_paso_friccion", False)),
            screenshot_url=str(ev.get("screenshot_url") or ""),
            timestamp=ev.get("timestamp"),
            bounding_box_context=bbox_context,
            context_notes=list(ev.get("context_notes") or []),
        )

    def _parse_row_to_report(self, row: Dict[str, Any]) -> ExplorationReport:
        """Transforma una fila cruda de BigQuery en un modelo ExplorationReport tipado.

        Args:
            row: Diccionario con los campos de la fila.

        Returns:
            Instancia validada de ExplorationReport.
        """
        raw_evidences = row.get("evidences") or []
        parsed_evidences: List[ExplorationEvidence] = []
        for ev in raw_evidences:
            parsed_ev = self._parse_evidence(ev)
            if parsed_ev is not None:
                parsed_evidences.append(parsed_ev)

        fecha_exp = self._normalize_date(row.get("fecha_exploracion")) or ""

        return ExplorationReport(
            id_patron=str(row.get("id_patron") or ""),
            id_cliente=str(row.get("id_cliente") or ""),
            id_sesion=str(row.get("id_sesion") or ""),
            fecha_exploracion=fecha_exp,
            status=str(row.get("status") or "COMPLETED"),
            total_steps=int(row.get("total_steps") or 0),
            completed_steps=int(row.get("completed_steps") or 0),
            started_at=row.get("started_at"),
            finished_at=row.get("finished_at"),
            objetivo=row.get("objetivo"),
            secuencia=list(row.get("secuencia") or []),
            sesiones=int(row["sesiones"]) if row.get("sesiones") is not None else None,
            usuarios=int(row["usuarios"]) if row.get("usuarios") is not None else None,
            llegada_grupo=float(row["llegada_grupo"]) if row.get("llegada_grupo") is not None else None,
            llegada_referencia=(
                float(row["llegada_referencia"]) if row.get("llegada_referencia") is not None else None
            ),
            sesiones_perdidas=(
                float(row["sesiones_perdidas"]) if row.get("sesiones_perdidas") is not None else None
            ),
            id_modelo=row.get("id_modelo"),
            primera_deteccion=self._normalize_date(row.get("primera_deteccion")),
            ultima_deteccion=self._normalize_date(row.get("ultima_deteccion")),
            total_sesiones_modelo=(
                int(row["total_sesiones_modelo"]) if row.get("total_sesiones_modelo") is not None else None
            ),
            objetivo_modelo=row.get("objetivo_modelo"),
            eventos_clave_modelo=list(row.get("eventos_clave_modelo") or []),
            nombres_hitos_modelo=list(row.get("nombres_hitos_modelo") or []),
            datos_desde_modelo=row.get("datos_desde_modelo"),
            datos_hasta_modelo=row.get("datos_hasta_modelo"),
            device_info=self._parse_device_info(row.get("device_info")),
            evidences=parsed_evidences,
            error_message=row.get("error_message"),
            created_at=row.get("created_at"),
        )
