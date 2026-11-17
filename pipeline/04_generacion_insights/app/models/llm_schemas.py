"""Esquemas de datos Pydantic para la respuesta estructurada del LLM vía guided_json."""

from typing import List, Literal
from pydantic import BaseModel, Field

SeverityLevel = Literal["alta", "media", "baja"]
StepStatus = Literal["success", "warning", "error"]
ClusterMatchLevel = Literal["baja", "media", "alta", "muy alta", "crítica"]


class JourneyStepNote(BaseModel):
    """Observación cualitativa y enriquecida para un paso específico del journey."""

    step_number: int = Field(description="Identificador secuencial del paso (1-indexed).")
    note_title: str = Field(description="Título formal de la observación en este paso.")
    note_description: str = Field(description="Detalle técnico de lo que ocurre en la pantalla.")
    badges: List[str] = Field(description="1 a 3 etiquetas de diagnóstico rápido.", max_length=3)
    status: StepStatus = Field(description="Estado de la interacción en la pantalla.")
    cluster_match: ClusterMatchLevel = Field(description="Correlación del paso con la causa raíz del cluster.")


class UxDiagnosticsOutput(BaseModel):
    """Estructura canónica de salida del diagnóstico UX devuelto por vLLM."""

    name: str = Field(description="Nombre conciso para badges y radar.", max_length=60)
    title: str = Field(description="Título descriptivo formal.", max_length=100)
    subtitle: str = Field(description="Bajada ejecutiva de 1 a 2 oraciones.")
    severity: SeverityLevel = Field(description="Nivel de criticidad evaluado.")
    impact_summary: str = Field(description="Etiqueta breve de impacto comercial (ej: -34% Add-to-Cart).")
    diagnosis_short: str = Field(description="Diagnóstico ejecutivo de un párrafo.")
    diagnosis_paragraphs: List[str] = Field(
        description="Tres párrafos: 1. Manifestación en UI, 2. Causa raíz técnica, 3. Impacto conductual.",
        min_length=3,
        max_length=3,
    )
    evidence: List[str] = Field(
        description="Afirmaciones empíricas que correlacionan interacción y métricas.",
        min_length=2,
        max_length=5,
    )
    audience_summary: str = Field(description="Síntesis narrativa del segmento más impactado.")
    recommendations: List[str] = Field(
        description="Recomendaciones prioritarias y accionables.",
        min_length=1,
        max_length=4,
    )
    journey_step_notes: List[JourneyStepNote] = Field(
        description="Enriquecimiento cualitativo de cada paso analizado."
    )
