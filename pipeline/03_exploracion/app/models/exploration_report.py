"""Modelos de datos para el reporte de exploración y evidencias visuales generadas."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from app.models.session_trace import DeviceInfo


class ExplorationStatus(str, Enum):
    """Estados finales de ejecución de una traza de exploración."""

    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class BoundingBox(BaseModel):
    """Coordenadas y dimensiones de un recuadro visual en píxeles."""

    x: float = Field(..., description="Posición horizontal en píxeles desde el borde izquierdo.")
    y: float = Field(..., description="Posición vertical en píxeles desde el borde superior.")
    width: float = Field(..., description="Ancho del elemento en píxeles.")
    height: float = Field(..., description="Alto del elemento en píxeles.")


class BoundingBoxContext(BaseModel):
    """Grounding visual y semántico del elemento señalado para el LLM multimodal."""

    box: BoundingBox = Field(
        ...,
        description="Coordenadas espaciales del recuadro visual en la captura.",
    )
    tag_name: str = Field(
        ...,
        description="Etiqueta HTML del elemento (ej: button, a, input, div).",
    )
    element_text: Optional[str] = Field(
        default=None,
        description="Texto visible o valor interactivo del elemento.",
    )
    role: Optional[str] = Field(
        default=None,
        description="Rol accesible ARIA (ej: button, link, alert, dialog).",
    )
    aria_label: Optional[str] = Field(
        default=None,
        description="Etiqueta accesible de accesibilidad si está presente.",
    )
    context_type: str = Field(
        default="interacted_element",
        description="Motivo del resaltado: interacted_element, error_message, dead_click, blocking_modal.",
    )
    surrounding_text: Optional[str] = Field(
        default=None,
        description="Fragmento de texto circundante en el DOM para aportar contexto contextual.",
    )


class VisualEvidence(BaseModel):
    """Evidencia fotográfica documentando el estado de la interfaz en un paso específico."""

    orden: int = Field(
        ...,
        description="Número de paso dentro de la sesión representativa.",
    )
    nombre_evento: str = Field(
        ...,
        description="Nombre del evento GA4 ejecutado en el paso.",
    )
    ruta: str = Field(
        ...,
        description="Ruta URL activa en el navegador al tomar la captura.",
    )
    items: Optional[str] = Field(
        default=None,
        description="Producto asociado al paso (si aplica).",
    )
    scroll: bool = Field(
        default=False,
        description="Señal contextual heredada indicando si el usuario llegó al fondo de la página.",
    )
    en_patron: bool = Field(
        default=False,
        description="Indica si el paso pertenece a la secuencia central del patrón anómalo.",
    )
    es_paso_friccion: bool = Field(
        default=False,
        description="Indica si este paso representa el punto crítico de fricción analítica.",
    )
    screenshot_url: str = Field(
        ...,
        description="Ruta de acceso a la imagen (URI gs://... en Cloud Storage o ruta local).",
    )
    timestamp: str = Field(
        ...,
        description="Marca temporal ISO-8601 del momento exacto de la captura.",
    )
    bounding_box_context: Optional[BoundingBoxContext] = Field(
        default=None,
        description="Metadatos semánticos del elemento resaltado en la captura (si aplica).",
    )
    context_notes: List[str] = Field(
        default_factory=list,
        description=(
            "Notas contextuales de la interfaz observadas durante el paso "
            "(ej. banners cerrados o navegación mediante menú mobile)."
        ),
    )


class ExplorationReport(BaseModel):
    """Reporte estructurado consolidando los resultados de la exploración de un patrón."""

    id_patron: str = Field(
        ...,
        description="Identificador único del patrón de fricción.",
    )
    id_cliente: str = Field(
        ...,
        description="Identificador del cliente analizado.",
    )
    id_sesion: str = Field(
        ...,
        description="Identificador de la sesión representativa explorada.",
    )
    fecha_exploracion: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        description="Fecha de ejecución de la exploración (formato ISO YYYY-MM-DD).",
    )
    status: ExplorationStatus = Field(
        ...,
        description="Resultado final del recorrido de exploración.",
    )
    total_steps: int = Field(
        ...,
        description="Cantidad total de pasos programados en la traza.",
    )
    completed_steps: int = Field(
        ...,
        description="Cantidad de pasos ejecutados con éxito.",
    )
    started_at: str = Field(
        ...,
        description="Marca temporal ISO-8601 del inicio de la emulación.",
    )
    finished_at: str = Field(
        ...,
        description="Marca temporal ISO-8601 de finalización de la emulación.",
    )
    objetivo: Optional[str] = Field(
        default=None,
        description="Escalón del embudo que faltaba alcanzar.",
    )
    secuencia: List[str] = Field(
        default_factory=list,
        description="Pasos del patrón en el vocabulario del modelo.",
    )
    sesiones: Optional[int] = Field(
        default=None,
        description="Cantidad total de sesiones del patrón.",
    )
    usuarios: Optional[int] = Field(
        default=None,
        description="Cantidad total de usuarios afectados por el patrón.",
    )
    llegada_grupo: Optional[float] = Field(
        default=None,
        description="Proporción del grupo que llega al objetivo.",
    )
    llegada_referencia: Optional[float] = Field(
        default=None,
        description="Proporción de referencia que llega al objetivo.",
    )
    sesiones_perdidas: Optional[float] = Field(
        default=None,
        description="Impacto estimado en sesiones perdidas.",
    )
    id_modelo: Optional[str] = Field(
        default=None,
        description="Identificador del entrenamiento del modelo detector.",
    )
    primera_deteccion: Optional[str] = Field(
        default=None,
        description="Fecha de primera detección del patrón (YYYY-MM-DD).",
    )
    ultima_deteccion: Optional[str] = Field(
        default=None,
        description="Fecha de última detección del patrón (YYYY-MM-DD).",
    )
    device_info: Optional[DeviceInfo] = Field(
        default=None,
        description="Metadatos del dispositivo emulado en la sesión.",
    )
    evidences: List[VisualEvidence] = Field(
        default_factory=list,
        description="Listado cronológico de evidencias visuales capturadas.",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Detalle del error fatal si la exploración terminó en estado FAILED o BLOCKED.",
    )
