from typing import Any, List, Optional
from pydantic import BaseModel, Field


class ClientSourceIntegration(BaseModel):
    """Representa el registro de un cliente en la tabla Supabase `clientes_integracion_fuente`."""
    id: Any
    cliente_id: str
    ga4_property_id: str
    client_gcp_project_id: str
    gcp_region: str
    activo: bool = True
    ultimo_lote_sincronizado: Optional[str] = None


class ExtractionRequest(BaseModel):
    """Cuerpo de la petición para invocar el endpoint de extracción batch."""
    fecha_ejecucion: Optional[str] = Field(
        default=None,
        description=(
            "Fecha del ciclo de ejecución (T) en formato YYYY-MM-DD. "
            "Se extraerán los datos GA4 correspondientes a T-1. Por defecto toma la fecha actual en UTC."
        ),
    )
    cliente_id: Optional[str] = Field(
        default=None,
        description="Filtro opcional para ejecutar el pipeline sobre un único cliente específico."
    )


class PlatformBigQueryError(Exception):
    """Error crítico al operar contra el proyecto propio de BigQuery de la plataforma."""


class ClientIngestionResult(BaseModel):
    """Resultado interno de la operación de extracción y MERGE para un cliente individual."""
    cliente_id: str
    exitoso: bool
    omitido: bool = False
    filas_afectadas: int = 0
    bytes_procesados: Optional[int] = None
    job_id: Optional[str] = None
    duracion_ms: float = 0.0
    intentos: int = 1
    error: Optional[str] = None
    tipo_error: Optional[str] = None


class BatchExtractionResponse(BaseModel):
    """Respuesta consolidada con los listados de clientes según el contrato de orquestación."""
    fecha_ejecucion: str
    clientes_exitosos: List[str] = []
    clientes_omitidos: List[str] = []
    clientes_fallidos: List[str] = []


class HealthResponse(BaseModel):
    """Respuesta del endpoint de verificación de salud (/health)."""
    status: str = "ok"
    timestamp: str
    environment: str
