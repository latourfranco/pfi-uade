from unittest.mock import AsyncMock
import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app, get_pipeline
from app.models import BatchExtractionResponse


@pytest.fixture
def client_app(mock_settings: Settings):
    """Cliente de pruebas de FastAPI con dependencias sobreescritas."""
    app.dependency_overrides[get_settings] = lambda: mock_settings
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.mark.unit
def test_health_endpoint(client_app: TestClient):
    """Prueba que el endpoint /health devuelva 200 OK y estado 'ok'."""
    response = client_app.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data


@pytest.mark.integration
def test_extract_events_success(client_app: TestClient):
    """Prueba que el endpoint /extraer devuelva el contrato de salida esperado con código 200."""
    mock_pipeline = AsyncMock()
    mock_pipeline.run_batch.return_value = BatchExtractionResponse(
        fecha_ejecucion="2026-09-20",
        clientes_exitosos=["cli_test"],
        clientes_omitidos=[],
        clientes_fallidos=[],
    )
    app.dependency_overrides[get_pipeline] = lambda: mock_pipeline

    response = client_app.post(
        "/extraer",
        json={"fecha_ejecucion": "2026-09-20", "cliente_id": "cli_test"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data == {
        "fecha_ejecucion": "2026-09-20",
        "clientes_exitosos": ["cli_test"],
        "clientes_omitidos": [],
        "clientes_fallidos": [],
    }
    mock_pipeline.run_batch.assert_called_once_with(
        target_date_str="2026-09-20",
        cliente_id="cli_test",
    )


@pytest.mark.unit
def test_extract_events_invalid_date(client_app: TestClient):
    """Prueba que el endpoint /extraer con fecha inválida responda 400 Bad Request."""
    mock_pipeline = AsyncMock()
    mock_pipeline.run_batch.side_effect = ValueError("Formato de fecha inválido '2026/09/20'")
    app.dependency_overrides[get_pipeline] = lambda: mock_pipeline

    response = client_app.post(
        "/extraer",
        json={"fecha_ejecucion": "2026/09/20"},
    )
    assert response.status_code == 400
    data = response.json()
    assert "Formato de fecha inválido" in data["error"]


@pytest.mark.unit
def test_extract_events_internal_error_500(client_app: TestClient):
    """Prueba que un fallo no controlado del pipeline devuelva código 500 Internal Server Error."""
    mock_pipeline = AsyncMock()
    mock_pipeline.run_batch.side_effect = RuntimeError("Fallo catastrófico en BigQuery")
    app.dependency_overrides[get_pipeline] = lambda: mock_pipeline

    response = client_app.post(
        "/extraer",
        json={"fecha_ejecucion": "2026-09-20"},
    )
    assert response.status_code == 500
    data = response.json()
    assert "Error interno en la extracción batch" in data["error"]


@pytest.mark.unit
def test_extract_events_default_empty_request(client_app: TestClient):
    """Prueba que el endpoint acepte una petición sin body (None) usando defaults."""
    mock_pipeline = AsyncMock()
    mock_pipeline.run_batch.return_value = BatchExtractionResponse(
        fecha_ejecucion="2026-09-20",
        clientes_exitosos=[],
        clientes_omitidos=[],
        clientes_fallidos=[],
    )
    app.dependency_overrides[get_pipeline] = lambda: mock_pipeline

    response = client_app.post("/extraer")
    assert response.status_code == 200
    mock_pipeline.run_batch.assert_called_once_with(
        target_date_str=None,
        cliente_id=None,
    )


@pytest.mark.integration
def test_get_pipeline_dependency_injection(mock_settings: Settings):
    """Prueba el inyector de dependencias real get_pipeline."""
    pipeline = get_pipeline(settings=mock_settings)
    assert pipeline is not None
    assert pipeline.settings == mock_settings
    assert pipeline.bigquery_service is not None
    assert pipeline.supabase_service is not None
