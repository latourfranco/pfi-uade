import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.logging_config import configure_logging
from app.models import BatchExtractionResponse, ExtractionRequest, HealthResponse
from app.services.bigquery_service import BigQueryService
from app.services.extraction_pipeline import ExtractionPipeline
from app.services.supabase_service import SupabaseService

# Configuración de logging JSON estructurado para Google Cloud Logging
configure_logging(logging.INFO)
logger = logging.getLogger("api")

app = FastAPI(
    title="Motor de Ingesta Analítica Batch",
    description="Servicio de extracción batch cross-project de eventos GA4 hacia Data Warehouses regionales",
    version="1.0.0",
)


def get_pipeline(settings: Settings = Depends(get_settings)) -> ExtractionPipeline:
    """Inyector de dependencias para el orquestador del pipeline."""
    bq_service = BigQueryService(settings)
    supabase_service = SupabaseService(settings)
    return ExtractionPipeline(
        settings=settings,
        bigquery_service=bq_service,
        supabase_service=supabase_service,
    )


@app.get("/health", response_model=HealthResponse, tags=["Monitoreo"])
async def health_check(settings: Settings = Depends(get_settings)):
    """Endpoint de comprobación de salud y disponibilidad."""
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
        environment=settings.ENVIRONMENT,
    )


@app.post(
    "/extraer",
    response_model=BatchExtractionResponse,
    status_code=status.HTTP_200_OK,
    tags=["Extracción"],
    summary="Disparar la extracción batch de eventos GA4 cross-project",
)
async def extract_events(
    request: Optional[ExtractionRequest] = None,
    pipeline: ExtractionPipeline = Depends(get_pipeline),
):
    """
    Endpoint principal de extracción invocado por Google Cloud Workflows.

    - La autenticación OIDC es validada por el proxy IAM de Cloud Run (`--no-allow-unauthenticated`).
    - Resuelve `fecha_ejecucion` (T, o fecha actual UTC si se omite) y extrae los datos GA4 de T-1.
    - Consulta los clientes activos en Supabase (`activo = true`) en modo solo lectura.
    - Aprovisiona datasets/tablas regionales (`dw_analytics_<region>`) si no existen.
    - Ejecuta sentencias MERGE idempotentes en BigQuery forzando la región del cliente.
    - Aplica reintentos automáticos ante fallos temporales y ejecuta una segunda pasada.
    """
    fecha_str = request.fecha_ejecucion if request else None
    cliente_id = request.cliente_id if request else None
    try:
        response = await pipeline.run_batch(
            target_date_str=fecha_str,
            cliente_id=cliente_id,
        )
        return response
    except ValueError as e:
        logger.warning(
            "Parámetros de petición inválidos: %s",
            str(e),
            extra={"fecha_ejecucion": fecha_str, "id_cliente": cliente_id},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(
            "Error inesperado durante la extracción batch: %s",
            str(e),
            extra={"fecha_ejecucion": fecha_str, "id_cliente": cliente_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno en la extracción batch: {str(e)}",
        )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Manejador global para formatear excepciones HTTP en respuestas JSON consistentes."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code},
    )
