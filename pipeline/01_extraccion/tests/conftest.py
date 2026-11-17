import pytest
from app.config import Settings
from app.models import ClientSourceIntegration


@pytest.fixture
def mock_settings() -> Settings:
    """Fixture que provee la configuración de prueba con parámetros controlados."""
    return Settings(
        PLATFORM_GCP_PROJECT_ID="test-central-platform",
        SUPABASE_URL="https://test-project.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY="test-service-key",
        ENVIRONMENT="test",
        MAX_CONCURRENT_CLIENTS=2,
        MAX_CLIENT_RETRIES=2,
        RETRY_INITIAL_DELAY=0.01,
        RETRY_BACKOFF_FACTOR=1.5,
    )


@pytest.fixture
def sample_clients() -> list[ClientSourceIntegration]:
    """Fixture que provee una lista de clientes activos de prueba."""
    return [
        ClientSourceIntegration(
            id=1,
            cliente_id="cliente_alpha",
            ga4_property_id="123456789",
            client_gcp_project_id="client-alpha-gcp",
            gcp_region="us-central1",
            activo=True,
            ultimo_lote_sincronizado="2026-09-19",
        ),
        ClientSourceIntegration(
            id=2,
            cliente_id="cliente_beta",
            ga4_property_id="987654321",
            client_gcp_project_id="client-beta-gcp",
            gcp_region="southamerica-west1",
            activo=True,
            ultimo_lote_sincronizado=None,
        ),
    ]
