"""Fixtures compartidas de pytest para pruebas unitarias."""

from typing import Any, Dict
import pytest

from app.config import Settings
from app.models.exploration_models import (
    AudienceDistributionItem,
    AudienceDistributions,
    BoundingBoxContext,
    BoundingBoxCoordinates,
    DeviceInfo,
    ExplorationEvidence,
    ExplorationReport,
)
from app.models.llm_schemas import UxDiagnosticsOutput


@pytest.fixture
def mock_settings() -> Settings:
    """Configuración de prueba controlada sin dependencias de variables de entorno reales."""
    return Settings(
        _env_file=None,
        ENVIRONMENT="test",
        SUPABASE_URL="https://test-project.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY="test-service-role-key-secret",
        PLATFORM_GCP_PROJECT_ID="test-gcp-project",
        BIGQUERY_DATASET_ID="friccion_resultados",
        BIGQUERY_EXPLORATION_TABLE_NAME="patrones_friccion_explorados",
        BIGQUERY_MODELS_TABLE_NAME="modelos",
        BIGQUERY_EVENTS_DATASET_ID="dw_analytics_us",
        BIGQUERY_EVENTS_TABLE_NAME="eventos_usuario",
        GCS_BUCKET_CAPTURES="pruebas-pfi-evidencias",
        GOOGLE_APPLICATION_CREDENTIALS=None,
        RUNPOD_API_KEY="rpa_test_key",
        VLLM_API_KEY="test-vllm-token",
        LLM_POD_NOMBRE="friccion-llm",
        LLM_INFERENCE_URL="https://mock-pod-8000.proxy.runpod.net",
        LLM_MODEL_NAME="cyankiwi/Qwen3.5-27B-AWQ-4bit",
        LLM_TIMEOUT_SECONDS=10.0,
        LLM_MAX_RETRIES=2,
        LLM_MAX_TOKENS=8000,
        LLM_TEMPERATURE=0.2,
        LLM_ENABLE_THINKING=True,
        LLM_USER_AGENT="eureka-insights-test/1.0",
    )


@pytest.fixture
def sample_ux_diagnostics_dict() -> Dict[str, Any]:
    """Diccionario con estructura canónica conforme a UxDiagnosticsOutput."""
    return {
        "name": "Superposición modal bloqueante en Checkout",
        "title": "Intercepción de clics en el botón de pago por modal de suscripción",
        "subtitle": "Los usuarios en móviles no logran abonar debido a un overlay modal sin botón de cierre accesible.",
        "severity": "alta",
        "impact_summary": "-38% Conversión en Checkout",
        "diagnosis_short": (
            "El componente de suscripción por newsletter se despliega sobre el botón principal de compra "
            "en resoluciones móviles, bloqueando la interacción transaccional."
        ),
        "diagnosis_paragraphs": [
            (
                "Manifestación en la interfaz: Al alcanzar el último paso del proceso de compra, un banner flotante "
                "oculta el botón 'Finalizar compra' en pantallas inferiores a 768 píxeles de ancho."
            ),
            (
                "Causa raíz técnica: El contenedor promocional cubre el área interactiva del formulario "
                "impidiendo que los toques lleguen al botón principal de pago."
            ),
            (
                "Impacto en comportamiento: El usuario genera múltiples clics rápidos de frustración "
                "y termina cancelando la navegación sin concretar la transacción."
            ),
        ],
        "evidence": [
            "Se registraron más de 5 toques sucesivos en la misma coordenada inerte en el 84% de las sesiones móviles.",
            "La tasa de llegada al checkout cayó del 97.6% de referencia al 67.3% en este grupo.",
        ],
        "audience_summary": "Dispositivos móviles navegando con Safari en iOS y Chrome en Android.",
        "recommendations": [
            "Condicionar la aparición del modal promocional para que no se ejecute en rutas transaccionales.",
            "Garantizar un botón de cierre con tamaño táctil accesible de al menos 48x48 píxeles.",
        ],
        "journey_step_notes": [
            {
                "step_number": 1,
                "note_title": "Visualización del carrito",
                "note_description": "El usuario revisa los artículos agregados sin anomalías perceptibles.",
                "badges": ["Navegación fluida", "OK"],
                "status": "success",
                "cluster_match": "baja",
            },
            {
                "step_number": 2,
                "note_title": "Bloqueo del botón de pago",
                "note_description": "Clics interceptados en el área del botón principal con abandono inmediato.",
                "badges": ["Fricción crítica", "Overlay invasivo"],
                "status": "error",
                "cluster_match": "crítica",
            },
        ],
    }


@pytest.fixture
def sample_ux_diagnostics(sample_ux_diagnostics_dict: Dict[str, Any]) -> UxDiagnosticsOutput:
    """Instancia Pydantic validada de UxDiagnosticsOutput."""
    return UxDiagnosticsOutput.model_validate(sample_ux_diagnostics_dict)


@pytest.fixture
def sample_exploration_report() -> ExplorationReport:
    """Reporte de exploración agéntica canónico compatible con BigQuery."""
    return ExplorationReport(
        id_patron="aa652a79a08a6810ff6b0c5d608cba00",
        id_cliente="00000000-0000-0000-0000-000000000001",
        id_sesion="5aef221daf5dd7a561fbc209b05d8f972bb2706e328e16fd8f671f5ffac50de2_1610604951",
        fecha_exploracion="2026-11-16",
        status="COMPLETED",
        total_steps=2,
        completed_steps=2,
        objetivo="begin_checkout",
        secuencia=["view_cart /checkout/…", "view_login /checkout/…"],
        sesiones=1247,
        usuarios=1171,
        llegada_grupo=0.6728,
        llegada_referencia=0.9765,
        sesiones_perdidas=378.75,
        id_modelo="00000000-0000-0000-0000-000000000001_2021-02-01",
        primera_deteccion="2021-02-01",
        ultima_deteccion="2021-02-01",
        total_sesiones_modelo=14500,
        objetivo_modelo="purchase",
        eventos_clave_modelo=["select_item", "add_to_cart", "begin_checkout", "purchase"],
        nombres_hitos_modelo=["Seleccionar producto", "Agregar al carrito", "Iniciar pago", "Realizar compra"],
        device_info=DeviceInfo(
            tipo_dispositivo="mobile",
            navegador="Safari v14.0",
            sistema_operativo="iOS",
        ),
        audience_distributions=AudienceDistributions(
            dispositivos=[
                AudienceDistributionItem(label="mobile", percentage=68.0),
                AudienceDistributionItem(label="desktop", percentage=32.0),
            ],
            navegadores=[AudienceDistributionItem(label="Safari v14.0", percentage=100.0)],
            sistemas_operativos=[AudienceDistributionItem(label="iOS", percentage=100.0)],
            paises=[AudienceDistributionItem(label="United States", percentage=100.0)],
        ),
        evidences=[
            ExplorationEvidence(
                orden=1,
                nombre_evento="view_cart",
                ruta="https://shop.merch.google/checkout?show=basket",
                items=None,
                scroll=True,
                en_patron=True,
                es_paso_friccion=False,
                screenshot_url="gs://pruebas-pfi-evidencias/capturas/c1/2026-11-16/p1_1.webp",
                bounding_box_context=None,
                context_notes=["Se cerró un pop-up de cookies al cargar la vista."],
            ),
            ExplorationEvidence(
                orden=2,
                nombre_evento="view_login",
                ruta="https://shop.merch.google/checkout?show=basket",
                items="Google Toffee Tote",
                scroll=False,
                en_patron=True,
                es_paso_friccion=True,
                screenshot_url="gs://pruebas-pfi-evidencias/capturas/c1/2026-11-16/p1_2.webp",
                bounding_box_context=BoundingBoxContext(
                    box=BoundingBoxCoordinates(x=120.0, y=340.0, width=200.0, height=48.0),
                    tag_name="button",
                    element_text="Finalizar compra",
                    role="button",
                    aria_label="Pagar orden",
                    context_type="interaction_click",
                    surrounding_text="Total $4500 - Envío gratis",
                ),
                context_notes=[],
            ),
        ],
    )
