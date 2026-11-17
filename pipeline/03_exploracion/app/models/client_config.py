"""Modelos de configuración para la interfaz del cliente."""

import logging
from typing import Any, Dict, Optional
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class ClientInterfaceConfig(BaseModel):
    """Contexto operativo y de conexión de la interfaz web del cliente."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    client_id: str = Field(
        ...,
        validation_alias=AliasChoices("client_id", "cliente_id"),
        description="Identificador único del cliente.",
    )
    base_url: str = Field(
        ...,
        validation_alias=AliasChoices("base_url", "url_base"),
        description="URL base del entorno a auditar (staging, pre-producción o producción).",
    )
    requires_authentication: bool = Field(
        default=False,
        description="Indica si la exploración requiere iniciar sesión previamente.",
    )
    login_url: Optional[str] = Field(
        default=None,
        description="URL o ruta relativa específica para el inicio de sesión si difiere de la principal.",
    )
    test_username: Optional[str] = Field(
        default=None,
        description="Nombre de usuario o email para autenticación de prueba.",
    )
    test_password_encrypted: Optional[str] = Field(
        default=None,
        description="Contraseña cifrada en reposo.",
    )
    custom_headers: Dict[str, str] = Field(
        default_factory=dict,
        description="Cabeceras HTTP personalizadas para saltar WAFs, Basic Auth o entornos protegidos.",
    )
    default_timeout_ms: int = Field(
        default=15000,
        description="Tiempo máximo de espera por defecto en milisegundos para operaciones de red.",
    )
    gcp_region: Optional[str] = Field(
        default=None,
        description="Región del dataset en BigQuery (ej. 'us', 'southamerica-east1').",
    )
    storage_state_encrypted: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("storage_state_encrypted", "estado_sesion_cifrado"),
        description="Estado de sesión (cookies y localStorage) serializado en JSON y cifrado con AES-256-GCM.",
    )
    storage_state: Optional[Dict[str, Any]] = Field(
        default=None,
        validation_alias=AliasChoices("storage_state", "estado_sesion"),
        description="Estado de sesión en formato dict de Playwright.",
    )

    def resolve_storage_state(self, encryption_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Retorna el estado de sesión deserializado como diccionario para Playwright.

        Si ya fue provisto directamente en `storage_state`, lo retorna.
        Si está presente `storage_state_encrypted`, lo descifra con AES-256-GCM y deserializa el JSON.
        """
        if self.storage_state is not None:
            return self.storage_state

        if not self.storage_state_encrypted:
            return None

        from app.config import get_settings
        from app.security.encryption import decrypt_json

        key = encryption_key or get_settings().AES_ENCRYPTION_KEY
        try:
            state = decrypt_json(self.storage_state_encrypted, key)
            if isinstance(state, dict):
                return state
            logger.warning(
                f"[ClientInterfaceConfig] storage_state descifrado para cliente '{self.client_id}' "
                "no es un diccionario."
            )
            return None
        except Exception as exc:
            logger.error(
                f"[ClientInterfaceConfig] Error al descifrar storage_state para cliente '{self.client_id}': {exc}"
            )
            return None


class ClientSourceIntegration(BaseModel):
    """Representa el registro de un cliente en la tabla Supabase `clientes_integracion_fuente`."""

    id: Optional[Any] = None
    cliente_id: str = Field(
        ...,
        description="Identificador único del cliente.",
    )
    ga4_property_id: Optional[str] = Field(
        default=None,
        description="ID de propiedad de Google Analytics 4.",
    )
    client_gcp_project_id: str = Field(
        ...,
        description="ID del proyecto de Google Cloud Platform del cliente.",
    )
    gcp_region: str = Field(
        ...,
        description="Región de GCP donde reside el Data Warehouse (ej. 'us', 'southamerica-east1').",
    )
    activo: bool = Field(
        default=True,
        description="Indica si la integración se encuentra activa.",
    )
    ultimo_lote_sincronizado: Optional[str] = Field(
        default=None,
        description="Marca temporal del último lote sincronizado.",
    )
    storage_state_encrypted: Optional[str] = Field(
        default=None,
        description="Estado de sesión serializado y cifrado con AES-256-GCM para navegación autenticada.",
    )
