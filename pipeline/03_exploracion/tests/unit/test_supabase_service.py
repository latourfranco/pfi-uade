"""Pruebas unitarias para SupabaseService (persistencia de configuraciones y evidencias)."""

from unittest.mock import MagicMock, patch
import pytest
from app.models.client_config import ClientInterfaceConfig
from app.models.exploration_report import ExplorationReport, ExplorationStatus, VisualEvidence
from app.services.supabase_service import SupabaseService


@pytest.fixture
def mock_supabase_client():
    """Mock completo del cliente de base de datos Supabase."""
    return MagicMock()


@pytest.fixture
def sample_report():
    """Reporte de exploración para pruebas de persistencia."""
    return ExplorationReport(
        id_patron="pat_1",
        id_cliente="client_1",
        id_sesion="sesion_1",
        fecha_exploracion="2026-10-17",
        status=ExplorationStatus.COMPLETED,
        total_steps=1,
        completed_steps=1,
        started_at="2026-10-17T12:00:00Z",
        finished_at="2026-10-17T12:01:00Z",
    )


@pytest.fixture
def sample_evidence():
    """Evidencia visual para pruebas de persistencia."""
    return VisualEvidence(
        orden=0,
        nombre_evento="page_view",
        ruta="/home",
        screenshot_url="https://storage.googleapis.com/test/step0.webp",
        timestamp="2026-10-17T12:00:00Z",
    )


@pytest.mark.unit
def test_supabase_service_unconnected():
    """Verifica el comportamiento cuando no hay credenciales configuradas."""
    service = SupabaseService(supabase_url="", supabase_key="")
    assert service.is_connected() is False


@pytest.mark.unit
def test_supabase_service_initialization_with_credentials():
    """Verifica la inicialización de Supabase con URL y key válidas y cuando create_client falla."""
    with patch("app.services.supabase_service.create_client") as mock_create:
        mock_client = MagicMock()
        mock_create.return_value = mock_client

        # Éxito
        service_ok = SupabaseService(supabase_url="https://test.supabase.co", supabase_key="secret-key")
        assert service_ok.is_connected() is True
        assert service_ok.client == mock_client

        # Error en create_client
        mock_create.side_effect = Exception("Fallo de conexión inicial")
        service_fail = SupabaseService(supabase_url="https://test.supabase.co", supabase_key="secret-key")
        assert service_fail.is_connected() is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_client_interface_config_success(mock_supabase_client):
    """Verifica la recuperación exitosa de la configuración de un cliente."""
    mock_table = MagicMock()
    mock_supabase_client.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.limit.return_value = mock_table

    mock_response = MagicMock()
    mock_response.data = [
        {
            "client_id": "client_abc",
            "base_url": "https://staging.tienda.com",
            "requires_authentication": False,
            "custom_headers": {"X-Test": "1"},
            "default_timeout_ms": 10000,
        }
    ]
    mock_table.execute.return_value = mock_response

    service = SupabaseService(client=mock_supabase_client)
    assert service.is_connected() is True

    config = await service.get_client_interface_config("client_abc")
    assert config is not None
    assert isinstance(config, ClientInterfaceConfig)
    assert config.client_id == "client_abc"
    assert config.base_url == "https://staging.tienda.com"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_client_interface_config_edge_cases(mock_supabase_client):
    """Verifica casos borde: desconectado, no encontrado, respuesta inválida o excepción."""
    # Desconectado
    service_unconnected = SupabaseService(supabase_url="", supabase_key="")
    assert await service_unconnected.get_client_interface_config("client_1") is None

    # No encontrado
    mock_table = MagicMock()
    mock_supabase_client.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.limit.return_value = mock_table
    mock_response = MagicMock()
    mock_response.data = []
    mock_table.execute.return_value = mock_response

    service = SupabaseService(client=mock_supabase_client)
    assert await service.get_client_interface_config("inexistente") is None

    # Respuesta que no es un diccionario
    mock_response.data = ["no_es_un_dict"]
    assert await service.get_client_interface_config("invalido") is None

    # Respuesta sin base_url
    mock_response.data = [{"cliente_id": "client_sin_url", "base_url": None}]
    assert await service.get_client_interface_config("client_sin_url") is None

    # Excepción en execute
    mock_table.execute.side_effect = Exception("Timeout de conexión con base de datos")
    assert await service.get_client_interface_config("con_error") is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_exploration_report(mock_supabase_client, sample_report):
    """Verifica el guardado de reportes, incluyendo casos desconectado y fallo en base de datos."""
    # Desconectado
    service_unconnected = SupabaseService(supabase_url="", supabase_key="")
    assert await service_unconnected.save_exploration_report(sample_report) is False

    # Éxito
    mock_table = MagicMock()
    mock_supabase_client.table.return_value = mock_table
    mock_table.upsert.return_value = mock_table
    mock_response = MagicMock()
    mock_response.data = [{"id": 1, "id_patron": "pat_1", "id_sesion": "sesion_1"}]
    mock_table.execute.return_value = mock_response

    service = SupabaseService(client=mock_supabase_client)
    assert await service.save_exploration_report(sample_report) is True

    # Error en base de datos
    mock_table.execute.side_effect = Exception("Violación de clave primaria")
    assert await service.save_exploration_report(sample_report) is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_visual_evidence(mock_supabase_client, sample_evidence):
    """Verifica el guardado de evidencias visuales, incluyendo casos desconectado y fallo."""
    # Desconectado
    service_unconnected = SupabaseService(supabase_url="", supabase_key="")
    assert await service_unconnected.save_visual_evidence(sample_evidence, "sesion_1") is False

    # Éxito
    mock_table = MagicMock()
    mock_supabase_client.table.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_response = MagicMock()
    mock_response.data = [{"id": 100}]
    mock_table.execute.return_value = mock_response

    service = SupabaseService(client=mock_supabase_client)
    assert await service.save_visual_evidence(sample_evidence, "sesion_1") is True

    # Error en base de datos
    mock_table.execute.side_effect = Exception("Error de conexión al insertar")
    assert await service_unconnected.save_visual_evidence(sample_evidence, "sesion_1") is False
    assert await service.save_visual_evidence(sample_evidence, "sesion_1") is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_client_source_integration_success(mock_supabase_client):
    """Verifica la recuperación exitosa de ClientSourceIntegration desde clientes_integracion_fuente."""
    mock_table = MagicMock()
    mock_supabase_client.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.limit.return_value = mock_table

    mock_response = MagicMock()
    mock_response.data = [
        {
            "id": 12,
            "cliente_id": "cliente_demo",
            "ga4_property_id": "properties/123456",
            "client_gcp_project_id": "pfi-demo-project",
            "gcp_region": "southamerica-east1",
            "activo": True,
            "ultimo_lote_sincronizado": "2026-10-17T12:00:00Z",
        }
    ]
    mock_table.execute.return_value = mock_response

    service = SupabaseService(client=mock_supabase_client)
    res = await service.get_client_source_integration("cliente_demo")
    assert res is not None
    assert res.cliente_id == "cliente_demo"
    assert res.client_gcp_project_id == "pfi-demo-project"
    assert res.gcp_region == "southamerica-east1"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_client_source_integration_edge_cases(mock_supabase_client):
    """Verifica casos borde de get_client_source_integration (desconectado, vacío, inválido, error)."""
    # Desconectado
    service_unconnected = SupabaseService(supabase_url="", supabase_key="")
    assert await service_unconnected.get_client_source_integration("cliente_x") is None

    # No encontrado (vacío)
    mock_table = MagicMock()
    mock_supabase_client.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.limit.return_value = mock_table
    mock_response = MagicMock()
    mock_response.data = []
    mock_table.execute.return_value = mock_response

    service = SupabaseService(client=mock_supabase_client)
    assert await service.get_client_source_integration("cliente_x") is None

    # Respuesta no dict
    mock_response.data = ["string_invalido"]
    assert await service.get_client_source_integration("cliente_x") is None

    # Excepción al ejecutar
    mock_table.execute.side_effect = Exception("Conexión abortada")
    assert await service.get_client_source_integration("cliente_x") is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_client_storage_state_success(mock_supabase_client):
    """Verifica la actualización exitosa de storage_state_encrypted en Supabase."""
    mock_table = MagicMock()
    mock_supabase_client.table.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.eq.return_value = mock_table

    mock_response = MagicMock()
    mock_response.data = [{"cliente_id": "cliente_1", "storage_state_encrypted": "enc_data_123"}]
    mock_table.execute.return_value = mock_response

    service = SupabaseService(client=mock_supabase_client)
    success = await service.update_client_storage_state("cliente_1", "enc_data_123")

    assert success is True
    mock_table.update.assert_called_once_with({"storage_state_encrypted": "enc_data_123"})
    mock_table.eq.assert_called_once_with("cliente_id", "cliente_1")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_client_storage_state_unconnected_or_error(mock_supabase_client):
    """Verifica casos de desconexión o fallo al actualizar storage_state_encrypted."""
    # Desconectado
    service_unconnected = SupabaseService(supabase_url="", supabase_key="")
    assert await service_unconnected.update_client_storage_state("cliente_1", "enc_data") is False

    # Error en execute
    mock_table = MagicMock()
    mock_supabase_client.table.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.execute.side_effect = Exception("Fallo de red Supabase")

    service = SupabaseService(client=mock_supabase_client)
    assert await service.update_client_storage_state("cliente_1", "enc_data") is False
