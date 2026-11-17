"""Servicio de persistencia relacional e incremental en Supabase (sin cascada)."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from supabase import Client, create_client

from app.config import Settings, get_settings
from app.models.exploration_models import ExplorationReport
from app.models.llm_schemas import UxDiagnosticsOutput

logger = logging.getLogger(__name__)


def resolve_milestone_label(
    event_name: Optional[str],
    milestone_labels: Dict[str, str],
) -> Optional[str]:
    """Obtiene el nombre legible del evento desde el mapa de nombres_hitos de BigQuery."""
    if not event_name or not event_name.strip():
        return None
    token = event_name.strip().split()[0].lower()
    return milestone_labels.get(token)


class SupabaseServiceError(Exception):
    """Excepción base para fallos de persistencia en Supabase."""
    pass


class SupabaseService:
    """Gestiona consulta de estado incremental y upsert idempotente en las 4 tablas de Supabase."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        client: Optional[Client] = None,
    ) -> None:
        """Inicializa SupabaseService.

        Args:
            settings: Configuración del módulo.
            client: Cliente Supabase preexistente (inyección en tests o mocks).
        """
        self.settings = settings or get_settings()
        self._client = client

    @property
    def client(self) -> Client:
        """Obtiene o inicializa el cliente de Supabase usando el Service Role Key."""
        if self._client is None:
            if not self.settings.SUPABASE_URL or not self.settings.SUPABASE_SERVICE_ROLE_KEY:
                raise SupabaseServiceError(
                    "SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY deben estar configurados para operar en la base de datos."
                )
            logger.info("Inicializando cliente Supabase en %s", self.settings.SUPABASE_URL)
            self._client = create_client(
                self.settings.SUPABASE_URL,
                self.settings.SUPABASE_SERVICE_ROLE_KEY,
            )
        return self._client

    def get_existing_patterns_state(self, client_id: str) -> Dict[str, Dict[str, Any]]:
        """Consulta el estado persistido de patrones y diagnósticos previos del cliente."""
        try:
            fricciones_res = (
                self.client.table("fricciones")
                .select("id, hash_exploracion, ultima_deteccion, sesiones, usuarios, sesiones_perdidas")
                .eq("client_id", client_id)
                .execute()
            )
            state: Dict[str, Dict[str, Any]] = {}
            rows = fricciones_res.data
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict) and row.get("id"):
                        pid = str(row["id"])
                        state[pid] = {
                            "hash_exploracion": row.get("hash_exploracion"),
                            "ultima_deteccion": (
                                str(row["ultima_deteccion"]) if row.get("ultima_deteccion") is not None else None
                            ),
                            "sesiones": row.get("sesiones"),
                            "usuarios": row.get("usuarios"),
                            "sesiones_perdidas": (
                                float(row["sesiones_perdidas"])
                                if row.get("sesiones_perdidas") is not None
                                else None
                            ),
                            "has_diagnosis": False,
                            "diagnostico_id": None,
                        }

            if state:
                diag_res = (
                    self.client.table("fricciones_diagnosticos")
                    .select("id, friccion_id")
                    .in_("friccion_id", list(state.keys()))
                    .execute()
                )
                diag_rows = diag_res.data
                if isinstance(diag_rows, list):
                    for d_row in diag_rows:
                        if isinstance(d_row, dict) and d_row.get("friccion_id"):
                            pid = str(d_row["friccion_id"])
                            if pid in state:
                                state[pid]["has_diagnosis"] = True
                                state[pid]["diagnostico_id"] = str(d_row["id"]) if d_row.get("id") else None

            return state
        except Exception as exc:
            logger.error("Error consultando estado previo en Supabase para client_id %s: %s", client_id, exc)
            raise SupabaseServiceError(f"Error consultando estado previo en Supabase: {exc}") from exc

    @staticmethod
    def has_quantitative_changes(report: ExplorationReport, existing_state: Dict[str, Any]) -> bool:
        """Determina si cambiaron las métricas o fecha de detección respecto a Supabase."""
        if report.ultima_deteccion != existing_state.get("ultima_deteccion"):
            return True
        if report.sesiones != existing_state.get("sesiones"):
            return True
        if report.usuarios != existing_state.get("usuarios"):
            return True

        prev_lost = existing_state.get("sesiones_perdidas")
        curr_lost = report.sesiones_perdidas
        if (prev_lost is None) != (curr_lost is None):
            return True
        if prev_lost is not None and curr_lost is not None:
            if round(float(prev_lost), 4) != round(float(curr_lost), 4):
                return True
        return False

    @staticmethod
    def _build_fricciones_payload(
        report: ExplorationReport,
        nombre: Optional[str],
        exploration_hash: str,
    ) -> Dict[str, Any]:
        """Construye el diccionario de columnas para la tabla public.fricciones."""
        tasa_abandono = (
            round((1.0 - report.llegada_grupo) * 100.0, 2)
            if report.llegada_grupo is not None
            else None
        )
        dist = report.audience_distributions
        milestone_labels = report.get_milestone_labels_map()
        payload: Dict[str, Any] = {
            "id": report.id_patron,
            "client_id": report.id_cliente,
            "evento_clave": report.objetivo,
            "evento_clave_nombre": resolve_milestone_label(report.objetivo, milestone_labels),
            "tasa_abandono": tasa_abandono,
            "secuencia": report.secuencia,
            "secuencia_nombres": [
                resolve_milestone_label(step, milestone_labels) or step for step in report.secuencia
            ],
            "sesiones": report.sesiones,
            "usuarios": report.usuarios,
            "llegada_grupo": report.llegada_grupo,
            "llegada_referencia": report.llegada_referencia,
            "sesiones_perdidas": report.sesiones_perdidas,
            "total_sesiones_modelo": report.total_sesiones_modelo,
            "id_modelo": report.id_modelo,
            "id_sesion": report.id_sesion,
            "primera_deteccion": report.primera_deteccion,
            "ultima_deteccion": report.ultima_deteccion,
            "fecha_exploracion": report.fecha_exploracion or None,
            "hash_exploracion": exploration_hash,
            "tipo_dispositivo": report.device_info.tipo_dispositivo if report.device_info else None,
            "navegador": report.device_info.navegador if report.device_info else None,
            "sistema_operativo": report.device_info.sistema_operativo if report.device_info else None,
            "distribucion_dispositivos": [item.model_dump() for item in dist.dispositivos],
            "distribucion_navegadores": [item.model_dump() for item in dist.navegadores],
            "distribucion_sistemas": [item.model_dump() for item in dist.sistemas_operativos],
            "distribucion_paises": [item.model_dump() for item in dist.paises],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if nombre is not None:
            payload["nombre"] = nombre
        return payload

    def update_pattern_metrics_only(
        self,
        report: ExplorationReport,
        exploration_hash: Optional[str] = None,
    ) -> None:
        """Actualiza únicamente métricas y distribuciones en public.fricciones sin re-ejecutar LLM."""
        hash_val = exploration_hash or report.compute_exploration_hash()
        payload = self._build_fricciones_payload(report=report, nombre=None, exploration_hash=hash_val)
        payload.pop("id", None)
        payload.pop("client_id", None)

        try:
            self.client.table("fricciones").update(payload).eq("id", report.id_patron).execute()
        except Exception as exc:
            logger.error("Error actualizando métricas en 'fricciones' para %s: %s", report.id_patron, exc)
            raise SupabaseServiceError(f"Error actualizando métricas en Supabase: {exc}") from exc

    def _fetch_step_id_mapping(self, friccion_id: str) -> Dict[int, str]:
        """Obtiene la asociación entre numero_paso y paso_id desde friccion_recorrido_pasos."""
        try:
            response = (
                self.client.table("friccion_recorrido_pasos")
                .select("id, numero_paso")
                .eq("friccion_id", friccion_id)
                .execute()
            )
            step_map: Dict[int, str] = {}
            data = response.data
            if isinstance(data, list):
                for row in data:
                    if isinstance(row, dict):
                        num = row.get("numero_paso")
                        step_id = row.get("id")
                        if num is not None and step_id is not None:
                            step_map[int(str(num))] = str(step_id)
            return step_map
        except Exception as exc:
            logger.warning(
                "No se pudo consultar el mapeo de pasos en friccion_recorrido_pasos para friccion_id %s: %s",
                friccion_id,
                exc,
            )
            return {}

    def save_diagnostics(
        self,
        report: ExplorationReport,
        diagnostico: UxDiagnosticsOutput,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        model_name: Optional[str] = None,
        exploration_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Persiste en forma idempotente y sin cascada el patrón, diagnóstico, pasos y notas."""
        friccion_id = report.id_patron
        model = model_name or self.settings.LLM_MODEL_NAME
        hash_val = exploration_hash or report.compute_exploration_hash()
        now_iso = datetime.now(timezone.utc).isoformat()

        fricciones_row = self._build_fricciones_payload(
            report=report,
            nombre=diagnostico.name,
            exploration_hash=hash_val,
        )

        diagnostico_row: Dict[str, Any] = {
            "friccion_id": friccion_id,
            "nombre_corto": diagnostico.name,
            "titulo": diagnostico.title,
            "subtitulo": diagnostico.subtitle,
            "severidad": diagnostico.severity,
            "impacto_resumen": diagnostico.impact_summary,
            "diagnostico_corto": diagnostico.diagnosis_short,
            "diagnostico_parrafos": diagnostico.diagnosis_paragraphs,
            "evidencias": diagnostico.evidence,
            "recomendaciones": diagnostico.recommendations,
            "audiencia_resumen": diagnostico.audience_summary,
            "modelo_llm": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "fecha_ejecucion": report.fecha_exploracion or None,
            "updated_at": now_iso,
        }

        try:
            # 1. Upsert del patrón padre en public.fricciones
            logger.info("Ejecutando upsert del patrón '%s' en 'fricciones'.", friccion_id)
            self.client.table("fricciones").upsert(fricciones_row, on_conflict="id").execute()

            # 2. Upsert 1:1 del diagnóstico en public.fricciones_diagnosticos
            logger.info("Ejecutando upsert del diagnóstico para '%s' en 'fricciones_diagnosticos'.", friccion_id)
            diag_res = (
                self.client.table("fricciones_diagnosticos")
                .upsert(diagnostico_row, on_conflict="friccion_id")
                .execute()
            )

            diagnostico_id: Optional[str] = None
            diag_data = diag_res.data
            if isinstance(diag_data, list) and len(diag_data) > 0:
                first_row = diag_data[0]
                if isinstance(first_row, dict) and "id" in first_row:
                    diagnostico_id = str(first_row["id"])

            # 3. Limpieza ordenada sin CASCADE (primero hijos: notas, luego pasos)
            self.client.table("friccion_recorrido_notas").delete().eq("friccion_id", friccion_id).execute()
            self.client.table("friccion_recorrido_pasos").delete().eq("friccion_id", friccion_id).execute()

            # 4. Upsert de pasos en public.friccion_recorrido_pasos
            step_id_map: Dict[int, str] = {}
            milestone_labels = report.get_milestone_labels_map()
            pasos_rows: List[Dict[str, Any]] = [
                {
                    "friccion_id": friccion_id,
                    "numero_paso": ev.orden,
                    "ruta_pagina": ev.ruta,
                    "captura_gcs_url": ev.screenshot_url,
                    "friccion_detectada": ev.es_paso_friccion,
                    "nombre_evento": ev.nombre_evento,
                    "evento_nombre": resolve_milestone_label(ev.nombre_evento, milestone_labels),
                    "items": ev.items,
                    "scroll": ev.scroll,
                    "en_patron": ev.en_patron,
                    "notas_contexto": ev.context_notes,
                }
                for ev in sorted(report.evidences, key=lambda item: item.orden)
            ]

            if pasos_rows:
                pasos_res = (
                    self.client.table("friccion_recorrido_pasos")
                    .upsert(pasos_rows, on_conflict="friccion_id,numero_paso")
                    .execute()
                )
                if isinstance(pasos_res.data, list):
                    for p_row in pasos_res.data:
                        if isinstance(p_row, dict) and p_row.get("id") and p_row.get("numero_paso") is not None:
                            step_id_map[int(str(p_row["numero_paso"]))] = str(p_row["id"])

            if not step_id_map and pasos_rows:
                step_id_map = self._fetch_step_id_mapping(friccion_id)

            # 5. Upsert de notas paso a paso en public.friccion_recorrido_notas
            notas_rows: List[Dict[str, Any]] = []
            for step_note in diagnostico.journey_step_notes:
                paso_id = step_id_map.get(step_note.step_number)
                nota_data: Dict[str, Any] = {
                    "friccion_id": friccion_id,
                    "numero_paso": step_note.step_number,
                    "nota_titulo": step_note.note_title,
                    "nota_descripcion": step_note.note_description,
                    "insignias": step_note.badges,
                    "estado": step_note.status,
                    "coincidencia_cluster": step_note.cluster_match,
                }
                if paso_id:
                    nota_data["paso_id"] = paso_id
                notas_rows.append(nota_data)

            inserted_notas_count = 0
            if notas_rows:
                logger.info(
                    "Insertando %d notas paso a paso en 'friccion_recorrido_notas' para friccion_id: %s",
                    len(notas_rows),
                    friccion_id,
                )
                notas_res = (
                    self.client.table("friccion_recorrido_notas")
                    .upsert(notas_rows, on_conflict="friccion_id,numero_paso")
                    .execute()
                )
                if isinstance(notas_res.data, list):
                    inserted_notas_count = len(notas_res.data)

            return {
                "diagnostico_id": diagnostico_id,
                "notas_count": inserted_notas_count,
            }

        except Exception as exc:
            logger.error("Error al persistir diagnóstico en Supabase para friccion_id %s: %s", friccion_id, exc)
            raise SupabaseServiceError(f"Error persistiendo datos en Supabase: {exc}") from exc
