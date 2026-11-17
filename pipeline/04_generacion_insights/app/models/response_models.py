"""Modelos Pydantic para los resultados estructurados del procesamiento de reportes."""

from typing import Optional
from pydantic import BaseModel, Field

from app.models.llm_schemas import UxDiagnosticsOutput


class ProcessClusterResponse(BaseModel):
    """Respuesta tras procesar y persistir el diagnóstico de un patrón de fricción."""

    success: bool = Field(..., description="Indica si el proceso culminó satisfactoriamente.")
    friccion_id: str = Field(..., description="Identificador del patrón de fricción procesado.")
    diagnostico_id: Optional[str] = Field(
        None,
        description="UUID asignado al registro en fricciones_diagnosticos.",
    )
    diagnostico: Optional[UxDiagnosticsOutput] = Field(
        None,
        description="Diagnóstico cualitativo completo retornado por el LLM.",
    )
    notas_count: int = Field(0, description="Cantidad de notas de pasos persistidas en friccion_recorrido_notas.")
    prompt_tokens: int = Field(0, description="Cantidad de tokens utilizados en el prompt.")
    completion_tokens: int = Field(0, description="Cantidad de tokens generados en la respuesta.")
    skipped_llm: bool = Field(
        False,
        description="Indica si se omitió la inferencia LLM por no haber novedades en los pasos explorados.",
    )
    metrics_updated: bool = Field(
        False,
        description="Indica si se actualizaron únicamente métricas cuantitativas en Supabase.",
    )
    message: str = Field("Diagnóstico generado y persistido con éxito.", description="Mensaje explicativo.")
