"""Modelos de datos para representar patrones de fricción y trazas de sesión representativa."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class EventType(str, Enum):
    """Categorías operativas de eventos para la reproducción en Playwright."""

    PAGE_VIEW = "visita_pagina"
    INTERACTION = "interaccion"
    OTHER = "otro"


_INTERACTION_EVENT_NAMES = frozenset({
    "select_item",
    "add_to_cart",
    "remove_from_cart",
    "begin_checkout",
    "view_login",
    "view_cart",
    "view_account",
    "login",
    "add_shipping_info",
    "add_billing_info",
    "add_payment_info",
    "select_promotion",
    "click",
    "search",
})

_PROTECTED_SESSION_EVENTS = frozenset({
    "login",
    "begin_checkout",
    "add_shipping_info",
    "add_billing_info",
    "add_payment_info",
    "view_account",
    "purchase",
})

_PROTECTED_ROUTE_SEGMENTS = (
    "/account",
    "/my-account",
    "/mi-cuenta",
    "/profile",
    "/perfil",
    "/orders",
    "/pedidos",
    "show=multibillto",
    "show=payment",
    "show=shipping",
    "/checkout/shipping",
    "/checkout/payment",
)


def _infer_event_type(nombre_evento: str) -> EventType:
    """Deriva la categoría operativa EventType a partir del nombre del evento GA4."""
    clean_name = nombre_evento.strip().lower()
    if clean_name == "page_view":
        return EventType.PAGE_VIEW
    if clean_name in _INTERACTION_EVENT_NAMES:
        return EventType.INTERACTION
    return EventType.OTHER


class DeviceInfo(BaseModel):
    """Metadatos del dispositivo utilizado en la sesión representativa."""

    model_config = ConfigDict(extra="ignore")

    tipo_dispositivo: str = Field(
        default="desktop",
        description="Categoría de dispositivo: desktop, mobile, tablet.",
    )
    navegador: Optional[str] = Field(
        default=None,
        description="Nombre/versión del navegador web (ej: Chrome v87.0, Safari v14.0).",
    )
    sistema_operativo: Optional[str] = Field(
        default=None,
        description="Sistema operativo del usuario (ej: Web, iOS, Android).",
    )


class TraceEvent(BaseModel):
    """Representación de un evento dentro de la tabla `friccion_resultados.sesion_representativa`."""

    model_config = ConfigDict(extra="ignore")

    orden: int = Field(
        default=0,
        description="Número de paso secuencial dentro de la sesión representativa.",
    )
    nombre_evento: str = Field(
        ...,
        description="Nombre del evento en GA4 (ej: page_view, select_item, add_to_cart).",
    )
    event_type: EventType = Field(
        default=EventType.OTHER,
        description="Categoría operativa derivada para el ejecutor de Playwright.",
    )
    ruta: str = Field(
        default="/",
        description="URL real donde ocurrió el evento.",
    )
    items: Optional[str] = Field(
        default=None,
        description="Producto a abrir o agregar al carrito.",
    )
    scroll: bool = Field(
        default=False,
        description="Indica si el usuario llegó al fondo de la página en este paso (solo contextual).",
    )
    en_patron: bool = Field(
        default=False,
        description="Indica si el evento forma parte del patrón anómalo.",
    )
    es_paso_friccion: bool = Field(
        default=False,
        description="Indica si este evento es el paso crítico de fricción.",
    )
    search_term: Optional[str] = Field(
        default=None,
        description="Término de búsqueda opcional en escenarios sintéticos o formularios.",
    )
    click_detail: Optional[str] = Field(
        default=None,
        description="Texto o detalle explícito de elemento para clic interactivo.",
    )

    @model_validator(mode="before")
    @classmethod
    def derive_event_type(cls, data: Any) -> Any:
        """Deriva automáticamente event_type a partir de nombre_evento si no fue provisto."""
        if isinstance(data, dict) and data.get("event_type") is None:
            copied = dict(data)
            copied["event_type"] = _infer_event_type(str(copied.get("nombre_evento") or ""))
            return copied
        return data


def _extract_orden(ev: Any) -> int:
    """Extrae el número de paso `orden` para ordenamiento determinista."""
    if isinstance(ev, dict):
        return int(ev.get("orden") or 0)
    if isinstance(ev, TraceEvent):
        return ev.orden
    return 0


class SessionTrace(BaseModel):
    """Patrón de fricción consolidado con su secuencia ordenada de sesión representativa."""

    model_config = ConfigDict(extra="ignore")

    id_patron: str = Field(
        ...,
        description="Identificador único del patrón de fricción.",
    )
    id_cliente: str = Field(
        ...,
        description="Identificador del cliente propietario.",
    )
    id_sesion: str = Field(
        ...,
        description="Identificador de la sesión representativa.",
    )
    fecha_exploracion: Optional[str] = Field(
        default=None,
        description="Fecha de ejecución de la exploración (formato YYYY-MM-DD).",
    )
    objetivo: Optional[str] = Field(
        default=None,
        description="Escalón del embudo que faltaba alcanzar (ej: add_to_cart, begin_checkout, purchase).",
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
        description="Cantidad de usuarios afectados por el patrón.",
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
        description="Impacto estimado: sesiones * (llegada_referencia - llegada_grupo).",
    )
    id_modelo: Optional[str] = Field(
        default=None,
        description="Identificador del entrenamiento con que se detectó por última vez.",
    )
    primera_deteccion: Optional[str] = Field(
        default=None,
        description="Fecha de primera detección (YYYY-MM-DD).",
    )
    ultima_deteccion: Optional[str] = Field(
        default=None,
        description="Fecha de última detección (YYYY-MM-DD).",
    )
    device_info: DeviceInfo = Field(
        default_factory=DeviceInfo,
        description="Metadatos del dispositivo a emular durante la navegación.",
    )
    events: List[TraceEvent] = Field(
        default_factory=list,
        description="Secuencia ordenada de pasos de la sesión representativa.",
    )

    @classmethod
    def from_friction_pattern(
        cls,
        pattern_row: Dict[str, Any],
        session_rows: Optional[List[Dict[str, Any]]] = None,
    ) -> "SessionTrace":
        """
        Construye una SessionTrace desde la cabecera de `friccion_resultados.patrones`
        y los eventos de `friccion_resultados.sesion_representativa`.
        """
        id_patron = str(pattern_row["id_patron"])
        id_cliente = str(pattern_row["id_cliente"])

        raw_events: Any = session_rows if session_rows is not None else (
            pattern_row.get("pasos") or pattern_row.get("events") or []
        )
        if not isinstance(raw_events, list):
            raw_events = []

        sorted_raw = sorted(raw_events, key=_extract_orden)

        events: List[TraceEvent] = []
        for ev in sorted_raw:
            if isinstance(ev, TraceEvent):
                events.append(ev)
            elif isinstance(ev, dict):
                events.append(TraceEvent.model_validate(ev))

        first_dict = next((ev for ev in sorted_raw if isinstance(ev, dict)), None)

        raw_id_sesion = pattern_row.get("id_sesion") or (
            first_dict.get("id_sesion") if first_dict else None
        )
        id_sesion = str(raw_id_sesion) if raw_id_sesion else f"sesion_{id_patron}"

        raw_device = pattern_row.get("device_info")
        if isinstance(raw_device, DeviceInfo):
            device_info = raw_device
        elif isinstance(raw_device, dict) and raw_device:
            device_info = DeviceInfo.model_validate(raw_device)
        elif first_dict:
            device_info = DeviceInfo(
                tipo_dispositivo=str(first_dict.get("tipo_dispositivo") or "desktop"),
                navegador=first_dict.get("navegador"),
                sistema_operativo=first_dict.get("sistema_operativo"),
            )
        else:
            device_info = DeviceInfo()

        raw_secuencia = pattern_row.get("secuencia") or []
        secuencia = [str(step) for step in raw_secuencia] if isinstance(raw_secuencia, list) else []

        def _opt_int(val: Any) -> Optional[int]:
            return int(val) if val is not None else None

        def _opt_float(val: Any) -> Optional[float]:
            return float(val) if val is not None else None

        def _opt_str(val: Any) -> Optional[str]:
            return str(val) if val is not None else None

        return cls(
            id_patron=id_patron,
            id_cliente=id_cliente,
            id_sesion=id_sesion,
            fecha_exploracion=_opt_str(pattern_row.get("fecha_exploracion")),
            objetivo=_opt_str(pattern_row.get("objetivo")),
            secuencia=secuencia,
            sesiones=_opt_int(pattern_row.get("sesiones")),
            usuarios=_opt_int(pattern_row.get("usuarios")),
            llegada_grupo=_opt_float(pattern_row.get("llegada_grupo")),
            llegada_referencia=_opt_float(pattern_row.get("llegada_referencia")),
            sesiones_perdidas=_opt_float(pattern_row.get("sesiones_perdidas")),
            id_modelo=_opt_str(pattern_row.get("id_modelo")),
            primera_deteccion=_opt_str(pattern_row.get("primera_deteccion")),
            ultima_deteccion=_opt_str(pattern_row.get("ultima_deteccion")),
            device_info=device_info,
            events=events,
        )

    def requires_authenticated_session(self) -> bool:
        """Indica si la traza avanza hacia eventos o rutas que requieren sesión compartida."""
        for ev in self.events:
            nombre = ev.nombre_evento.strip().lower()
            if nombre in _PROTECTED_SESSION_EVENTS:
                return True
            ruta_lower = (ev.ruta or "").strip().lower()
            if any(segment in ruta_lower for segment in _PROTECTED_ROUTE_SEGMENTS):
                return True
        return False

    def prefers_pre_cart_auth_jit(self) -> bool:
        """Retorna True si requiere sesión y agrega ítems antes de `login` o carece de evento `login`."""
        if not self.requires_authenticated_session():
            return False
        ordered = sorted(self.events, key=lambda e: e.orden)
        first_login_idx = next(
            (i for i, e in enumerate(ordered) if e.nombre_evento.strip().lower() == "login"),
            None,
        )
        first_cart_idx = next(
            (i for i, e in enumerate(ordered) if e.nombre_evento.strip().lower() == "add_to_cart"),
            None,
        )
        if first_cart_idx is not None:
            return first_login_idx is None or first_cart_idx < first_login_idx
        return False
