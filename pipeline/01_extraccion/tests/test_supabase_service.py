from unittest.mock import MagicMock, patch
import pytest
from app.config import Settings
from app.services.supabase_service import SupabaseService


@pytest.mark.unit
@pytest.mark.parametrize(
    "url,key",
    [
        ("", ""),
        ("https://example.supabase.co", ""),
        ("", "test-service-key"),
    ],
)
def test_supabase_missing_credentials_raises_value_error(url: str, key: str):
    """Prueba que inicializar el cliente sin SUPABASE_URL o KEY lance ValueError."""
    bad_settings = Settings(SUPABASE_URL=url, SUPABASE_SERVICE_ROLE_KEY=key)
    service = SupabaseService(bad_settings)
    with pytest.raises(ValueError) as exc_info:
        _ = service.client
    assert "SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY deben estar configurados" in str(exc_info.value)


@pytest.mark.unit
def test_supabase_client_lazy_initialization_success(mock_settings: Settings):
    """Prueba que el cliente se inicialice correctamente de forma perezosa cuando hay credenciales."""
    service = SupabaseService(mock_settings)
    mock_created_client = MagicMock()

    with patch("app.services.supabase_service.create_client", return_value=mock_created_client) as mock_create:
        client1 = service.client
        assert client1 == mock_created_client
        mock_create.assert_called_once_with(
            mock_settings.SUPABASE_URL,
            mock_settings.SUPABASE_SERVICE_ROLE_KEY,
        )

        # Segundo acceso reutiliza self._client sin llamar nuevamente a create_client
        client2 = service.client
        assert client2 == mock_created_client
        assert mock_create.call_count == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_active_clients(mock_settings: Settings):
    """Prueba la obtención de clientes activos filtrando por activo = True."""
    mock_sb_client = MagicMock()
    mock_query = MagicMock()
    mock_sb_client.table.return_value.select.return_value = mock_query
    mock_query.eq.return_value.execute.return_value.data = [
        {
            "id": 1,
            "cliente_id": "cli_1",
            "ga4_property_id": "111",
            "client_gcp_project_id": "proj-1",
            "gcp_region": "us-central1",
            "activo": True,
            "ultimo_lote_sincronizado": None,
        }
    ]

    service = SupabaseService(mock_settings, client=mock_sb_client)
    clients = await service.get_active_clients()

    assert len(clients) == 1
    assert clients[0].cliente_id == "cli_1"
    assert clients[0].activo is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_active_clients_with_cliente_id_filter(mock_settings: Settings):
    """Prueba que pasar cliente_id aplique el filtro adicional .eq('cliente_id', cliente_id)."""
    mock_sb_client = MagicMock()
    mock_query = MagicMock()
    mock_sb_client.table.return_value.select.return_value = mock_query
    # Chain: eq("activo", True).eq("cliente_id", "cli_123")
    mock_query.eq.return_value = mock_query
    mock_query.execute.return_value.data = [
        {
            "id": 10,
            "cliente_id": "cli_123",
            "ga4_property_id": "999",
            "client_gcp_project_id": "proj-999",
            "gcp_region": "us-central1",
            "activo": True,
            "ultimo_lote_sincronizado": "2026-09-18",
        }
    ]

    service = SupabaseService(mock_settings, client=mock_sb_client)
    clients = await service.get_active_clients(cliente_id="cli_123")

    assert len(clients) == 1
    assert clients[0].cliente_id == "cli_123"
    assert mock_query.eq.call_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_active_clients_none_data_returns_empty_list(mock_settings: Settings):
    """Prueba que si response.data es None o vacio, se retorne una lista vacia."""
    mock_sb_client = MagicMock()
    mock_query = MagicMock()
    mock_sb_client.table.return_value.select.return_value = mock_query
    mock_query.eq.return_value.execute.return_value.data = None

    service = SupabaseService(mock_settings, client=mock_sb_client)
    clients = await service.get_active_clients()
    assert clients == []
