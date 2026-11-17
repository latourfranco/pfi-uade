"""Ensamblador de payloads multimodales y schemas estructurados para vLLM en RunPod."""

import logging
from typing import Any, Dict, List, Optional

from app.config import Settings, get_settings
from app.models.exploration_models import AudienceDistributionItem, ExplorationReport
from app.models.llm_schemas import UxDiagnosticsOutput

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Sos un consultor senior de Experiencia de Usuario (UX) y Producto digital. "
    "Tu objetivo es evaluar en profundidad las capturas de pantalla del recorrido web junto con las métricas "
    "de impacto y los datos de contexto para diagnosticar por qué los usuarios abandonan o tienen dificultades.\n\n"
    "Reglas fundamentales de análisis y redacción:\n"
    "1. Lenguaje claro y comprensible: redactá todo en español (variante de Argentina) de forma directa, "
    "clara y comprensible para equipos de producto, diseño y negocio. Evitá jerga técnica excesiva, "
    "nombres de eventos crudos en inglés (como 'page_view' o 'mapping_error') o identificadores internos.\n"
    "2. Análisis visual en profundidad: observá detalladamente cada captura de pantalla. En las vistas donde hubo "
    "interacción del usuario, el elemento interactuado está resaltado con un recuadro/halo translúcido "
    "(bounding box) de color índigo/violeta. Usá ese resaltado visual como guía principal para entender qué veía "
    "y qué intentó hacer la persona.\n"
    "3. Cambios entre eventos históricos y exploración en vivo: los recorridos parten de trazas históricas de "
    "analytics (GA4), por lo que el sitio web pudo haber cambiado al momento de reproducir la sesión en el "
    "navegador (por ejemplo: productos discontinuados, cambios de menú, promociones distintas o valores '(not set)' "
    "propios de datos históricos). Si las 'Notas contextuales' indican que un ítem o '(not set)' no se localizó "
    "en el DOM actual, significa que el catálogo/promoción cambió respecto al historial; NO diagnostiques un "
    "'error de etiquetado', 'fallo de mapeo' ni 'enlace roto' por ese motivo, sino analizá qué muestra hoy la "
    "captura de esa pantalla.\n"
    "4. Criterio estricto de severidad: definí 'severity' ('alta', 'media' o 'baja') evaluando únicamente el "
    "impacto cuantitativo en la conversión (sesiones perdidas, caída frente a la referencia, usuarios afectados) "
    "y la gravedad real del bloqueo en la experiencia. NO utilices las fechas de detección para calcularla.\n"
    "5. Guía de formato para cada campo del JSON:\n"
    "   - 'name': etiqueta corta y clara para tarjetas (máx. 60 caracteres, sin prefijos como 'Diagnóstico de...').\n"
    "   - 'title': título descriptivo concreto del problema (máx. 100 caracteres, sin hashes ni IDs).\n"
    "   - 'subtitle': bajada ejecutiva de 1 a 2 oraciones resumiendo qué sucede y su efecto en el negocio.\n"
    "   - 'impact_summary': etiqueta breve tipo KPI (ej: '-12.4 pp en selección · 151 sesiones perdidas').\n"
    "   - 'diagnosis_short': resumen ejecutivo en 1 párrafo claro para negocio.\n"
    "   - 'diagnosis_paragraphs': exactamente 3 párrafos distintos y complementarios: "
    "(1) Qué ve e intenta hacer la persona en la interfaz; "
    "(2) Causa probable del obstáculo en el flujo o diseño; "
    "(3) Impacto en el comportamiento del usuario y abandono.\n"
    "   - 'journey_step_notes': incluir SOLO los pasos con 'Pertenece al patrón de fricción: SÍ'. En cada nota: "
    "'note_description' debe tener 1 o 2 oraciones claras describiendo qué pasa en la pantalla (sin copiar textos "
    "del prompt como 'Pertenece al patrón...' o 'Badges:'); 'badges' debe tener 1 a 3 etiquetas breves en español "
    "claro; 'cluster_match' debe ser 'baja'/'media' en pasos normales de tránsito y 'alta'/'muy alta'/'crítica' "
    "únicamente en los pasos donde ocurre o se agrava el problema."
)


class PromptBuilder:
    """Constructor de payloads multimodales estructurados para Qwen3.5 sobre vLLM."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        """Inicializa PromptBuilder con configuración inyectable.

        Args:
            settings: Instancia de configuración del módulo.
        """
        self.settings = settings or get_settings()

    @staticmethod
    def _format_distribution(items: List[AudienceDistributionItem], limit: int = 5) -> str:
        """Formatea una lista de distribuciones porcentuales para el prompt."""
        if not items:
            return "Sin datos"
        top_items = items[:limit]
        return ", ".join(f"{item.label} ({item.percentage:.1f}%)" for item in top_items)

    def build_prompt_text_from_report(
        self,
        report: ExplorationReport,
        images_map: Optional[Dict[int, str]] = None,
    ) -> str:
        """Genera el bloque textual del prompt a partir de un reporte de exploración (BigQuery).

        Args:
            report: Objeto ExplorationReport con métricas, audiencias y evidencias por paso.
            images_map: Mapeo de número de paso (orden 1-indexed) a Data URI Base64.

        Returns:
            Texto Markdown formateado para el modelo multimodal.
        """
        images_map = images_map or {}
        lines: List[str] = [
            "### CONTEXTO DEL PATRÓN DE FRICCIÓN EXPLORADO",
            f"- Estado de exploración: {report.status} ({report.completed_steps}/{report.total_steps} pasos)",
        ]

        if report.objetivo:
            lines.append(f"- Escalón del embudo afectado (objetivo del patrón): {report.objetivo}")
        if report.objetivo_modelo:
            lines.append(f"- Objetivo final de conversión del sitio: {report.objetivo_modelo}")
        if report.eventos_clave_modelo:
            lines.append(f"- Hitos principales del embudo del sitio: {' -> '.join(report.eventos_clave_modelo)}")
        if report.secuencia:
            lines.append(f"- Secuencia abstracta del patrón: {' -> '.join(report.secuencia)}")

        lines.append("\n### IMPACTO CUANTITATIVO DEL PATRÓN")
        if report.sesiones is not None:
            sesiones_line = f"- Sesiones en el patrón: {report.sesiones}"
            if report.total_sesiones_modelo and report.total_sesiones_modelo > 0:
                pct_total = (report.sesiones / report.total_sesiones_modelo) * 100.0
                sesiones_line += f" ({pct_total:.2f}% de {report.total_sesiones_modelo} sesiones del sitio)"
            lines.append(sesiones_line)
        if report.usuarios is not None:
            lines.append(f"- Usuarios únicos afectados: {report.usuarios}")
        if report.llegada_grupo is not None and report.llegada_referencia is not None:
            grupo_pct = report.llegada_grupo * 100.0
            ref_pct = report.llegada_referencia * 100.0
            caida_pp = ref_pct - grupo_pct
            lines.append(
                f"- Tasa de avance hacia '{report.objetivo or 'objetivo'}': "
                f"{grupo_pct:.1f}% en este patrón vs. {ref_pct:.1f}% de referencia "
                f"(caída de {caida_pp:.1f} puntos porcentuales)"
            )
        elif report.llegada_grupo is not None:
            lines.append(f"- Tasa de avance del grupo: {report.llegada_grupo * 100.0:.1f}%")
        if report.sesiones_perdidas is not None:
            lines.append(f"- Impacto estimado en sesiones perdidas: {report.sesiones_perdidas:.1f}")

        lines.append("\n### PERFIL DEL DISPOSITIVO Y DISTRIBUCIÓN DE AUDIENCIA")
        if report.device_info:
            lines.append(
                f"- Sesión representativa reproducida en: "
                f"{report.device_info.tipo_dispositivo or 'N/D'} | "
                f"{report.device_info.navegador or 'N/D'} | "
                f"{report.device_info.sistema_operativo or 'N/D'}"
            )
        dist = report.audience_distributions
        if dist.dispositivos or dist.navegadores or dist.sistemas_operativos or dist.paises:
            lines.append(f"- Distribución por dispositivo: {self._format_distribution(dist.dispositivos)}")
            lines.append(f"- Distribución por navegador: {self._format_distribution(dist.navegadores)}")
            lines.append(f"- Distribución por sistema operativo: {self._format_distribution(dist.sistemas_operativos)}")
            lines.append(f"- Distribución por país: {self._format_distribution(dist.paises)}")

        lines.append(
            "\n### RECORRIDO CRONOLÓGICO Y EVIDENCIAS PASO A PASO\n"
            "(Nota: los pasos marcados con 'Pertenece al patrón de fricción: No' brindan contexto previo o "
            "posterior del recorrido para entender si el usuario reintentó, dio vueltas o abandonó; "
            "'Llegó al final de la página (scroll): SÍ' indica que recorrió toda la pantalla hacia abajo)."
        )
        if not report.evidences:
            lines.append("No se registraron pasos detallados para esta exploración.")
        else:
            for ev in sorted(report.evidences, key=lambda s: s.orden):
                lines.append(f"\n[Paso {ev.orden}]")
                lines.append(f"  * Evento: {ev.nombre_evento}")
                if ev.ruta:
                    lines.append(f"  * URL / Ruta: {ev.ruta}")
                if ev.items:
                    lines.append(f"  * Producto / Ítem: {ev.items}")
                lines.append(f"  * Llegó al final de la página (scroll): {'SÍ' if ev.scroll else 'No'}")
                lines.append(f"  * Pertenece al patrón de fricción: {'SÍ' if ev.en_patron else 'No'}")
                if ev.es_paso_friccion:
                    lines.append("  * Paso donde ocurre la fricción: SÍ")

                if ev.context_notes:
                    lines.append("  * Notas contextuales de la exploración (cambios del sitio / DOM):")
                    for note in ev.context_notes:
                        lines.append(f"    - {note}")

                if ev.bounding_box_context:
                    bbox = ev.bounding_box_context
                    lines.append("  * Elemento interactuado (resaltado en color índigo/violeta en la captura):")
                    if bbox.tag_name:
                        lines.append(f"    - Etiqueta HTML: <{bbox.tag_name}>")
                    if bbox.element_text:
                        lines.append(f"    - Texto visible: '{bbox.element_text}'")
                    if bbox.role:
                        lines.append(f"    - Rol ARIA: {bbox.role}")
                    if bbox.aria_label:
                        lines.append(f"    - Aria-Label: '{bbox.aria_label}'")
                    if bbox.context_type:
                        lines.append(f"    - Tipo de interacción: {bbox.context_type}")
                    if bbox.surrounding_text:
                        lines.append(f"    - Texto cercano: '{bbox.surrounding_text}'")
                    if bbox.box:
                        lines.append(
                            f"    - Coordenadas: x={bbox.box.x}, y={bbox.box.y}, "
                            f"w={bbox.box.width}, h={bbox.box.height}"
                        )

                if ev.orden in images_map:
                    lines.append(f"  * Captura visual adjunta: Ver imagen 'Captura del Paso {ev.orden}'")

        lines.append(
            "\n### INSTRUCCIONES FINALES DE EVALUACIÓN:\n"
            "1. Analizá en profundidad todas las capturas visuales adjuntas junto con los recuadros resaltados "
            "en color índigo/violeta, las notas contextuales de la exploración y las métricas cuantitativas.\n"
            "2. Explicá claramente qué pasa en la pantalla, por qué ocurre el problema y cómo afecta al usuario "
            "y a la conversión, manteniendo un tono claro y comprensible (evitá tecnicismos y no cites IDs).\n"
            "3. Calculá 'severity' únicamente en función del impacto cuantitativo y del bloqueo real.\n"
            "4. En 'journey_step_notes' del JSON generado, incluí ÚNICAMENTE notas para los pasos marcados con "
            "'Pertenece al patrón de fricción: SÍ' (usando exactamente su número de Paso en 'step_number' y "
            "badges cortas en español)."
        )

        return "\n".join(lines)

    @staticmethod
    def _resolve_high_detail_orders(
        sorted_evidences: List[Any],
        images_map: Dict[int, str],
    ) -> set[int]:
        """Selecciona qué pasos envían imagen en detalle alto para no exceder 32k tokens en recorridos largos."""
        available_orders = [ev.orden for ev in sorted_evidences if ev.orden in images_map]
        if len(available_orders) <= 10:
            return set(available_orders)

        high_orders: set[int] = set()
        for ev in sorted_evidences:
            if ev.en_patron or ev.es_paso_friccion:
                high_orders.update({ev.orden - 1, ev.orden, ev.orden + 1})

        if not high_orders:
            return set(available_orders[-5:])

        return high_orders.intersection(available_orders)

    def build_payload_from_report(
        self,
        report: ExplorationReport,
        images_map: Optional[Dict[int, str]] = None,
    ) -> Dict[str, Any]:
        """Ensambla el payload multimodal completo para vLLM nightly (Qwen3.5 con streaming).

        Args:
            report: Reporte de exploración agéntica.
            images_map: Mapeo de número de paso (orden 1-indexed) a Data URI Base64.

        Returns:
            Payload estructurado para /v1/chat/completions con response_format y streaming.
        """
        images_map = images_map or {}
        prompt_text = self.build_prompt_text_from_report(report, images_map)

        user_content: List[Dict[str, Any]] = [
            {
                "type": "text",
                "text": prompt_text,
            }
        ]

        sorted_evidences = sorted(report.evidences, key=lambda s: s.orden)
        high_detail_orders = self._resolve_high_detail_orders(sorted_evidences, images_map)

        for ev in sorted_evidences:
            if ev.orden in images_map:
                detail = "high" if ev.orden in high_detail_orders else "low"
                user_content.append(
                    {
                        "type": "text",
                        "text": f"Captura del Paso {ev.orden} ({ev.nombre_evento}):",
                    }
                )
                user_content.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": images_map[ev.orden],
                            "detail": detail,
                        },
                    }
                )

        payload: Dict[str, Any] = {
            "model": self.settings.LLM_MODEL_NAME,
            "temperature": self.settings.LLM_TEMPERATURE,
            "max_tokens": self.settings.LLM_MAX_TOKENS,
            "stream": True,
            "stream_options": {"include_usage": True},
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_content,
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "ux_diagnostics_output",
                    "schema": UxDiagnosticsOutput.model_json_schema(),
                },
            },
            "chat_template_kwargs": {
                "enable_thinking": self.settings.LLM_ENABLE_THINKING,
            },
        }

        return payload
