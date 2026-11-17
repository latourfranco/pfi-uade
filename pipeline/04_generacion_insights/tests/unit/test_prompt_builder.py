"""Pruebas unitarias para el ensamblado de prompts en app.core.prompt_builder."""

from unittest.mock import MagicMock, patch
import pytest

from app.config import Settings
from app.core.prompt_builder import SYSTEM_PROMPT, PromptBuilder
from app.models.exploration_models import (
    BoundingBoxContext,
    ExplorationEvidence,
    ExplorationReport,
)
from app.models.llm_schemas import UxDiagnosticsOutput


@pytest.mark.unit
def test_build_prompt_text_from_report_complete(
    sample_exploration_report: ExplorationReport,
    mock_settings: Settings,
) -> None:
    """Verifica que el prompt textual incluya métricas, audiencias, notas contextuales y resaltado índigo."""
    builder = PromptBuilder(settings=mock_settings)
    images_map = {1: "data:image/webp;base64,AAAA", 2: "data:image/webp;base64,BBBB"}

    text = builder.build_prompt_text_from_report(sample_exploration_report, images_map)

    assert "índigo/violeta" in SYSTEM_PROMPT
    assert "NO utilices las fechas de detección" in SYSTEM_PROMPT
    assert sample_exploration_report.id_sesion not in text
    assert "begin_checkout" in text
    assert "purchase" in text
    assert "1247" in text
    assert "14500 sesiones del sitio" in text
    assert "67.3% en este patrón vs. 97.7% de referencia" in text
    assert "378.8" in text
    assert "mobile (68.0%)" in text
    assert "United States (100.0%)" in text
    assert "[Paso 1]" in text
    assert "[Paso 2]" in text
    assert "Google Toffee Tote" in text
    assert "Se cerró un pop-up de cookies al cargar la vista." in text
    assert "Etiqueta HTML: <button>" in text
    assert "Texto visible: 'Finalizar compra'" in text
    assert "Ver imagen 'Captura del Paso 1'" in text
    assert "Ver imagen 'Captura del Paso 2'" in text


@pytest.mark.unit
def test_build_prompt_text_from_report_minimal_and_partial_metrics(mock_settings: Settings) -> None:
    """Verifica el prompt cuando faltan métricas opcionales, device_info, audiencias y evidencias."""
    builder = PromptBuilder(settings=mock_settings)
    report = ExplorationReport(
        id_patron="pat-min",
        id_cliente="cli-min",
        id_sesion="ses-min",
        fecha_exploracion="2026-11-16",
        status="COMPLETED",
        sesiones=50,
        total_sesiones_modelo=0,
        llegada_grupo=0.4,
        llegada_referencia=None,
        device_info=None,
        evidences=[],
    )

    text = builder.build_prompt_text_from_report(report, images_map={})

    assert "Sesiones en el patrón: 50" in text
    assert "sesiones del sitio" not in text
    assert "Tasa de avance del grupo: 40.0%" in text
    assert "Distribución por dispositivo" not in text
    assert "No se registraron pasos detallados para esta exploración." in text
    assert builder._format_distribution([]) == "Sin datos"


@pytest.mark.unit
def test_build_prompt_text_from_report_sparse_evidence(mock_settings: Settings) -> None:
    """Verifica evidencias con campos opcionales y bounding_box_context vacíos."""
    builder = PromptBuilder(settings=mock_settings)
    report = ExplorationReport(
        id_patron="pat-sparse",
        id_cliente="cli-sparse",
        id_sesion="ses-sparse",
        fecha_exploracion="2026-11-16",
        evidences=[
            ExplorationEvidence(
                orden=1,
                nombre_evento="page_view",
                ruta="",
                items=None,
                scroll=False,
                en_patron=False,
                es_paso_friccion=False,
                screenshot_url="gs://b/1.webp",
                context_notes=[],
                bounding_box_context=BoundingBoxContext(
                    box=None,
                    tag_name=None,
                    element_text=None,
                    role=None,
                    aria_label=None,
                    context_type=None,
                    surrounding_text=None,
                ),
            )
        ],
    )

    text = builder.build_prompt_text_from_report(report, images_map={})

    assert "URL / Ruta" not in text
    assert "Producto / Ítem" not in text
    assert "Pertenece al patrón de fricción: No" in text
    assert "Paso donde ocurre la fricción" not in text
    assert "Notas contextuales" not in text
    assert "Elemento interactuado" in text
    assert "Etiqueta HTML" not in text
    assert "Captura visual adjunta" not in text


@pytest.mark.unit
def test_build_payload_from_report(
    sample_exploration_report: ExplorationReport,
    mock_settings: Settings,
) -> None:
    """Verifica el payload multimodal con etiquetas intercaladas por paso para vLLM nightly."""
    builder = PromptBuilder(settings=mock_settings)
    images_map = {1: "data:image/webp;base64,AAAA", 2: "data:image/webp;base64,BBBB"}

    payload = builder.build_payload_from_report(sample_exploration_report, images_map)

    assert payload["model"] == mock_settings.LLM_MODEL_NAME
    assert payload["temperature"] == mock_settings.LLM_TEMPERATURE
    assert payload["max_tokens"] == mock_settings.LLM_MAX_TOKENS
    assert payload["stream"] is True
    assert payload["stream_options"] == {"include_usage": True}
    assert payload["chat_template_kwargs"] == {"enable_thinking": True}
    assert payload["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "ux_diagnostics_output",
            "schema": UxDiagnosticsOutput.model_json_schema(),
        },
    }

    messages = payload["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == SYSTEM_PROMPT
    user_content = messages[1]["content"]
    # 1 texto principal + (1 etiqueta + 1 imagen) * 2 pasos = 5 elementos
    assert len(user_content) == 5
    assert user_content[0]["type"] == "text"
    assert user_content[1] == {"type": "text", "text": "Captura del Paso 1 (view_cart):"}
    assert user_content[2]["image_url"]["url"] == "data:image/webp;base64,AAAA"
    assert user_content[3] == {"type": "text", "text": "Captura del Paso 2 (view_login):"}
    assert user_content[4]["image_url"]["url"] == "data:image/webp;base64,BBBB"


@pytest.mark.unit
def test_build_payload_from_report_partial_images(
    sample_exploration_report: ExplorationReport,
    mock_settings: Settings,
) -> None:
    """Verifica que si falta la imagen de un paso en images_map se omita del payload."""
    builder = PromptBuilder(settings=mock_settings)
    images_map = {1: "data:image/webp;base64,SOLO_PASO_1"}

    payload = builder.build_payload_from_report(sample_exploration_report, images_map)
    user_content = payload["messages"][1]["content"]

    assert len(user_content) == 3
    assert user_content[1] == {"type": "text", "text": "Captura del Paso 1 (view_cart):"}
    assert user_content[2]["image_url"]["url"] == "data:image/webp;base64,SOLO_PASO_1"


@pytest.mark.unit
def test_build_payload_long_journey_adaptive_detail(mock_settings: Settings) -> None:
    """Verifica que en recorridos >10 capturas solo los pasos del patrón y vecinos usen detail='high'."""
    builder = PromptBuilder(settings=mock_settings)

    evidences_with_pattern = [
        ExplorationEvidence(
            orden=i,
            nombre_evento="page_view",
            ruta=f"https://shop.merch.google/p/{i}",
            en_patron=(i == 11),
            es_paso_friccion=(i == 11),
            screenshot_url=f"gs://b/{i}.webp",
        )
        for i in range(1, 13)
    ]
    images_map = {i: f"data:image/webp;base64,IMG_{i}" for i in range(1, 13)}
    rep = ExplorationReport(
        id_patron="pat-long",
        id_cliente="cli-long",
        id_sesion="ses-long",
        fecha_exploracion="2026-11-16",
        evidences=evidences_with_pattern,
    )

    payload = builder.build_payload_from_report(rep, images_map)
    image_blocks = [item for item in payload["messages"][1]["content"] if item["type"] == "image_url"]
    details_by_step = {idx + 1: blk["image_url"]["detail"] for idx, blk in enumerate(image_blocks)}

    # Solo pasos 10, 11, 12 en detail='high'
    assert details_by_step[1] == "low"
    assert details_by_step[9] == "low"
    assert details_by_step[10] == "high"
    assert details_by_step[11] == "high"
    assert details_by_step[12] == "high"

    # Caso sin ningún paso marcado en_patron/es_paso_friccion -> últimos 5 en high
    evidences_no_flag = [
        ev.model_copy(update={"en_patron": False, "es_paso_friccion": False})
        for ev in evidences_with_pattern
    ]
    high_set = builder._resolve_high_detail_orders(evidences_no_flag, images_map)
    assert high_set == {8, 9, 10, 11, 12}


@pytest.mark.unit
def test_prompt_builder_default_init() -> None:
    """Verifica inicialización por defecto de PromptBuilder sin argumentos."""
    with patch("app.core.prompt_builder.get_settings") as mock_get_settings:
        mock_get_settings.return_value = MagicMock()
        builder = PromptBuilder()
        assert builder.settings == mock_get_settings.return_value
