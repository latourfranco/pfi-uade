"""Modelos Pydantic para los reportes de exploración agéntica consumidos desde BigQuery."""

from datetime import datetime
import hashlib
import json
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class BoundingBoxCoordinates(BaseModel):
    """Coordenadas espaciales del elemento interactuado en pantalla."""

    x: float = Field(0.0, description="Posición horizontal X del elemento.")
    y: float = Field(0.0, description="Posición vertical Y del elemento.")
    width: float = Field(0.0, description="Ancho del elemento en píxeles.")
    height: float = Field(0.0, description="Alto del elemento en píxeles.")


class BoundingBoxContext(BaseModel):
    """Contexto semántico, de accesibilidad y coordenadas del elemento interactuado."""

    box: Optional[BoundingBoxCoordinates] = Field(
        default=None,
        description="Coordenadas espaciales del recuadro.",
    )
    tag_name: Optional[str] = Field(default=None, description="Etiqueta HTML (ej: button, a, input).")
    element_text: Optional[str] = Field(default=None, description="Texto visible dentro del elemento.")
    role: Optional[str] = Field(default=None, description="Rol ARIA del componente (ej: button, link).")
    aria_label: Optional[str] = Field(default=None, description="Atributo aria-label para accesibilidad.")
    context_type: Optional[str] = Field(default=None, description="Categoría contextual (ej: interaction_click).")
    surrounding_text: Optional[str] = Field(
        default=None,
        description="Texto cercano alrededor del componente para contextualizar al LLM.",
    )


class DeviceInfo(BaseModel):
    """Contexto del dispositivo de la sesión representativa explorada."""

    tipo_dispositivo: Optional[str] = Field(default=None, description="Tipo de dispositivo (mobile, desktop, tablet).")
    navegador: Optional[str] = Field(default=None, description="Navegador utilizado en la sesión.")
    sistema_operativo: Optional[str] = Field(default=None, description="Sistema operativo o entorno.")


class AudienceDistributionItem(BaseModel):
    """Elemento individual dentro de una distribución porcentual de audiencia."""

    label: str = Field(..., description="Categoría de la dimensión (ej: mobile, Chrome v87.0, United States).")
    percentage: float = Field(..., description="Porcentaje de usuarios en el patrón (0 a 100).", ge=0.0, le=100.0)


class AudienceDistributions(BaseModel):
    """Distribuciones porcentuales de usuarios del patrón por dispositivo, navegador, SO y país."""

    dispositivos: List[AudienceDistributionItem] = Field(default_factory=list)
    navegadores: List[AudienceDistributionItem] = Field(default_factory=list)
    sistemas_operativos: List[AudienceDistributionItem] = Field(default_factory=list)
    paises: List[AudienceDistributionItem] = Field(default_factory=list)


class ExplorationEvidence(BaseModel):
    """Evidencia contextual, técnica y visual capturada en un paso específico del recorrido."""

    orden: int = Field(..., description="Número secuencial del paso en la sesión (1-indexed).", ge=1)
    nombre_evento: str = Field("page_view", description="Nombre del evento GA4 reproducido.")
    ruta: str = Field("", description="URL completa navegada durante este paso.")
    items: Optional[str] = Field(default=None, description="Producto o promoción asociada al paso.")
    scroll: bool = Field(default=False, description="Indica si llegó al fondo de la página.")
    en_patron: bool = Field(
        default=True,
        description="Indica si este paso forma parte del patrón de fricción.",
    )
    es_paso_friccion: bool = Field(
        default=False,
        description="Indica si este es el paso donde ocurre la fricción.",
    )
    screenshot_url: str = Field(..., description="URI canónica en Google Cloud Storage (gs://...webp).")
    timestamp: Optional[Union[datetime, str]] = Field(default=None, description="Marca temporal del paso.")
    bounding_box_context: Optional[BoundingBoxContext] = Field(
        default=None,
        description="Información semántica y coordenadas del elemento interactuado.",
    )
    context_notes: List[str] = Field(
        default_factory=list,
        description="Notas contextuales de la reproducción en navegador.",
    )


class ExplorationReport(BaseModel):
    """Reporte estructurado de una exploración agéntica persistido en BigQuery."""

    id_patron: str = Field(..., description="Identificador único del patrón de fricción (hash).")
    id_cliente: str = Field(..., description="UUID del cliente en la plataforma.")
    id_sesion: str = Field(..., description="Identificador único de la sesión representativa.")
    fecha_exploracion: str = Field(..., description="Fecha de ejecución de la exploración (YYYY-MM-DD).")
    status: str = Field("COMPLETED", description="Estado final de la exploración: COMPLETED, PARTIAL o FAILED.")
    total_steps: int = Field(0, description="Cantidad total de pasos de la sesión.")
    completed_steps: int = Field(0, description="Cantidad de pasos reproducidos exitosamente.")
    started_at: Optional[Union[datetime, str]] = Field(default=None, description="Inicio de la emulación UTC.")
    finished_at: Optional[Union[datetime, str]] = Field(default=None, description="Fin de la emulación UTC.")
    objetivo: Optional[str] = Field(default=None, description="Objetivo de conversión evaluado en el patrón.")
    secuencia: List[str] = Field(default_factory=list, description="Secuencia abstracta de pasos del patrón.")
    sesiones: Optional[int] = Field(default=None, description="Cantidad de sesiones incluidas en el patrón.")
    usuarios: Optional[int] = Field(default=None, description="Cantidad de usuarios afectados por el patrón.")
    llegada_grupo: Optional[float] = Field(default=None, description="Tasa de llegada al objetivo del grupo anómalo.")
    llegada_referencia: Optional[float] = Field(
        default=None,
        description="Tasa de llegada de referencia para el mismo contexto.",
    )
    sesiones_perdidas: Optional[float] = Field(default=None, description="Impacto estimado en sesiones perdidas.")
    id_modelo: Optional[str] = Field(default=None, description="ID del modelo de detección utilizado.")
    primera_deteccion: Optional[str] = Field(default=None, description="Primera fecha de detección (YYYY-MM-DD).")
    ultima_deteccion: Optional[str] = Field(default=None, description="Última fecha de detección (YYYY-MM-DD).")
    total_sesiones_modelo: Optional[int] = Field(
        default=None,
        description="Total de sesiones analizadas en el entrenamiento del modelo.",
    )
    objetivo_modelo: Optional[str] = Field(default=None, description="Objetivo macro configurado en el modelo.")
    eventos_clave_modelo: List[str] = Field(
        default_factory=list,
        description="Hitos del embudo completo elegidos para el modelo.",
    )
    nombres_hitos_modelo: List[str] = Field(
        default_factory=list,
        description="Nombres legibles de cada hito del modelo en el mismo orden que eventos_clave_modelo.",
    )
    datos_desde_modelo: Optional[Union[datetime, str]] = Field(
        default=None,
        description="Inicio de la ventana de entrenamiento del modelo.",
    )
    datos_hasta_modelo: Optional[Union[datetime, str]] = Field(
        default=None,
        description="Fin de la ventana de entrenamiento del modelo.",
    )
    device_info: Optional[DeviceInfo] = Field(
        default=None,
        description="Contexto del dispositivo de la sesión representativa.",
    )
    audience_distributions: AudienceDistributions = Field(
        default_factory=AudienceDistributions,
        description="Distribuciones porcentuales de audiencia del patrón.",
    )
    evidences: List[ExplorationEvidence] = Field(
        default_factory=list,
        description="Arreglo con la telemetría y evidencias visuales paso a paso.",
    )
    error_message: Optional[str] = Field(default=None, description="Detalle del error si terminó en FAILED.")
    created_at: Optional[Union[datetime, str]] = Field(default=None, description="Marca temporal de inserción en BQ.")

    def get_milestone_labels_map(self) -> Dict[str, str]:
        """Construye un mapa evento_técnico -> nombre_legible desde modelos.nombres_hitos."""
        labels: Dict[str, str] = {}
        for event_key, friendly_name in zip(self.eventos_clave_modelo, self.nombres_hitos_modelo):
            clean_key = event_key.strip().lower()
            clean_name = friendly_name.strip()
            if clean_key and clean_name:
                labels[clean_key] = clean_name
        return labels

    def compute_exploration_hash(self) -> str:
        """Calcula un hash SHA-256 determinístico de los pasos y evidencias exploradas."""
        steps_payload: List[Dict[str, Any]] = []
        for ev in sorted(self.evidences, key=lambda item: item.orden):
            steps_payload.append(
                {
                    "orden": ev.orden,
                    "nombre_evento": ev.nombre_evento,
                    "ruta": ev.ruta,
                    "items": ev.items,
                    "scroll": ev.scroll,
                    "en_patron": ev.en_patron,
                    "es_paso_friccion": ev.es_paso_friccion,
                    "bounding_box_context": (
                        ev.bounding_box_context.model_dump() if ev.bounding_box_context else None
                    ),
                    "context_notes": list(ev.context_notes),
                }
            )
        canonical_json = json.dumps(steps_payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
