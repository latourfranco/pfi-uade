import asyncio
import logging
from typing import List, Optional
from supabase import Client, create_client

from app.config import Settings
from app.models import ClientSourceIntegration

logger = logging.getLogger("supabase_service")


class SupabaseService:
    """Servicio encargado de interactuar con las tablas administrativas en Supabase."""

    def __init__(self, settings: Settings, client: Optional[Client] = None):
        self.settings = settings
        self._client = client

    @property
    def client(self) -> Client:
        """Inicialización perezosa del cliente de Supabase."""
        if self._client is None:
            if not self.settings.SUPABASE_URL or not self.settings.SUPABASE_SERVICE_ROLE_KEY:
                raise ValueError("SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY deben estar configurados")
            self._client = create_client(
                self.settings.SUPABASE_URL,
                self.settings.SUPABASE_SERVICE_ROLE_KEY
            )
        return self._client

    async def get_active_clients(self, cliente_id: Optional[str] = None) -> List[ClientSourceIntegration]:
        """
        Obtiene los clientes activos desde `clientes_integracion_fuente` con `activo = true`.
        Permite filtrar opcionalmente por un `cliente_id` específico.
        """
        loop = asyncio.get_running_loop()

        def _fetch():
            columns = (
                "id, cliente_id, ga4_property_id, "
                "client_gcp_project_id, gcp_region, activo, ultimo_lote_sincronizado"
            )
            query = (
                self.client.table("clientes_integracion_fuente")
                .select(columns)
                .eq("activo", True)
            )
            if cliente_id:
                query = query.eq("cliente_id", cliente_id)

            response = query.execute()
            return response.data or []

        data = await loop.run_in_executor(None, _fetch)
        clients = [ClientSourceIntegration(**row) for row in data]
        logger.info("Se recuperaron %d clientes activos desde Supabase", len(clients))
        return clients
