"""Servicio de persistencia y consulta de configuraciones y reportes en Supabase."""

import logging
from typing import Any, Optional
from supabase import Client, create_client
from app.config import get_settings
from app.models.client_config import ClientInterfaceConfig, ClientSourceIntegration
from app.models.exploration_report import ExplorationReport, VisualEvidence

logger = logging.getLogger(__name__)


class SupabaseService:
    """
    Servicio de integración con la base de datos PostgreSQL de Supabase.

    Permite:
    1. Recuperar la configuración de interfaz del cliente (URL base, credenciales cifradas).
    2. Persistir el reporte de exploración consolidado y sus evidencias fotográficas.
    """

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        client: Optional[Any] = None,
    ) -> None:
        """
        Inicializa el cliente de Supabase.

        :param supabase_url: URL del proyecto Supabase.
        :param supabase_key: Service Role Key o clave API de Supabase.
        :param client: Cliente preexistente para inyección en pruebas unitarias.
        """
        settings = get_settings()
        url = supabase_url if supabase_url is not None else settings.SUPABASE_URL
        key = supabase_key if supabase_key is not None else settings.SUPABASE_SERVICE_ROLE_KEY

        self.client: Optional[Client] = None

        if client is not None:
            self.client = client
        elif url and key:
            try:
                self.client = create_client(url, key)
                logger.info("[SupabaseService] Cliente de Supabase conectado exitosamente.")
            except Exception as exc:
                logger.error(f"[SupabaseService] Error al inicializar cliente de Supabase: {exc}")
        else:
            logger.warning(
                "[SupabaseService] Credenciales de Supabase no configuradas. "
                "Operando en modo sin persistencia remota."
            )

    def is_connected(self) -> bool:
        """Verifica si hay un cliente activo de Supabase configurado."""
        return self.client is not None

    async def get_client_interface_config(self, client_id: str) -> Optional[ClientInterfaceConfig]:
        """
        Consulta la configuración de interfaz de un cliente desde `clientes_integracion_fuente`.

        :param client_id: Identificador único del cliente.
        :return: ClientInterfaceConfig o None si no se encuentra.
        """
        if not self.client:
            logger.warning("[SupabaseService] No hay cliente configurado para consultar client_id.")
            return None

        try:
            response = (
                self.client.table("clientes_integracion_fuente")
                .select("*")
                .eq("cliente_id", client_id)
                .limit(1)
                .execute()
            )
            if response.data and len(response.data) > 0:
                raw_config = response.data[0]
                if isinstance(raw_config, dict):
                    # Si no tiene base_url definida, no se puede explorar
                    if not raw_config.get("base_url") and not raw_config.get("url_base"):
                        logger.warning(
                            f"[SupabaseService] El cliente '{client_id}' "
                            "no tiene 'base_url' en clientes_integracion_fuente."
                        )
                        return None
                    return ClientInterfaceConfig(**raw_config)
            return None
        except Exception as exc:
            logger.error(f"[SupabaseService] Error al consultar configuración del cliente '{client_id}': {exc}")
            return None

    async def get_client_source_integration(self, client_id: str) -> Optional[ClientSourceIntegration]:
        """
        Consulta la información de integración de fuente del cliente desde `clientes_integracion_fuente`.

        :param client_id: Identificador único del cliente (cliente_id).
        :return: ClientSourceIntegration o None si no se encuentra.
        """
        if not self.client:
            logger.warning("[SupabaseService] No hay cliente configurado para consultar integración del cliente.")
            return None

        try:
            response = (
                self.client.table("clientes_integracion_fuente")
                .select("*")
                .eq("cliente_id", client_id)
                .limit(1)
                .execute()
            )
            if response.data and len(response.data) > 0:
                raw_integration = response.data[0]
                if isinstance(raw_integration, dict):
                    return ClientSourceIntegration(**raw_integration)
            return None
        except Exception as exc:
            logger.error(f"[SupabaseService] Error al consultar integracion del cliente '{client_id}': {exc}")
            return None

    async def update_client_storage_state(
        self,
        client_id: str,
        storage_state_encrypted: str,
    ) -> bool:
        """
        Actualiza el estado de sesión cifrado (storage_state_encrypted) para un cliente en Supabase.

        :param client_id: Identificador único del cliente (cliente_id).
        :param storage_state_encrypted: Payload serializado y cifrado con AES-256-GCM.
        :return: True si se actualizó correctamente, False ante fallos.
        """
        if not self.client:
            logger.warning("[SupabaseService] No hay cliente configurado para actualizar storage_state.")
            return False

        try:
            response = (
                self.client.table("clientes_integracion_fuente")
                .update({"storage_state_encrypted": storage_state_encrypted})
                .eq("cliente_id", client_id)
                .execute()
            )
            logger.info(f"[SupabaseService] storage_state_encrypted actualizado para cliente_id='{client_id}'")
            return bool(response.data)
        except Exception as exc:
            logger.error(f"[SupabaseService] Error al actualizar storage_state de cliente '{client_id}': {exc}")
            return False

    async def save_exploration_report(self, report: ExplorationReport) -> bool:
        """
        Persiste el reporte de exploración de una sesión anómala.

        :param report: Reporte estructurado con evidencias y estados.
        :return: True si se insertó correctamente, False ante fallos.
        """
        if not self.client:
            logger.warning("[SupabaseService] No hay cliente configurado para persistir reporte.")
            return False

        try:
            payload = report.model_dump(mode="json")
            response = self.client.table("exploration_reports").upsert(payload).execute()
            logger.info(
                f"[SupabaseService] Reporte de exploración guardado para id_patron='{report.id_patron}' "
                f"(id_sesion='{report.id_sesion}')"
            )
            return bool(response.data)
        except Exception as exc:
            logger.error(f"[SupabaseService] Error al persistir reporte en Supabase: {exc}")
            return False

    async def save_visual_evidence(self, evidence: VisualEvidence, id_sesion: str) -> bool:
        """
        Persiste un registro de evidencia visual individual en Supabase.

        :param evidence: Instancia de VisualEvidence.
        :param id_sesion: Identificador de la sesión asociada.
        :return: True si se insertó con éxito, False en caso contrario.
        """
        if not self.client:
            return False

        try:
            payload = evidence.model_dump(mode="json")
            payload["id_sesion"] = id_sesion
            response = self.client.table("visual_evidences").insert(payload).execute()
            return bool(response.data)
        except Exception as exc:
            logger.error(f"[SupabaseService] Error al persistir evidencia visual: {exc}")
            return False
