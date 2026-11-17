import pytest
from app.config import Settings
from app.models import ClientSourceIntegration
from app.services.bigquery_service import BigQueryService

# Eventos de interaccion estandar en GA4
ECOMMERCE_INTERACTION_EVENTS = [
    "click", "add_to_cart", "purchase", "view_item",
    "view_item_list", "select_item", "view_promotion",
    "select_promotion", "add_to_wishlist", "view_cart",
    "begin_checkout", "add_shipping_info", "add_payment_info",
    "remove_from_cart", "refund"
]

EXCLUDED_BASE_EVENTS = ["first_visit", "session_start", "user_engagement"]


@pytest.fixture
def merge_sql(mock_settings: Settings, sample_clients: list[ClientSourceIntegration]) -> str:
    """Fixture que genera el SQL MERGE para inspeccionar sus reglas de transformacion."""
    service = BigQueryService(mock_settings)
    return service.build_merge_query(sample_clients[0])


@pytest.mark.unit
def test_ga4_taxonomy_page_view(merge_sql: str):
    """Verifica que el evento page_view se mapee como 'visita_pagina'."""
    assert "WHEN event_name = 'page_view' THEN 'visita_pagina'" in merge_sql


@pytest.mark.unit
def test_ga4_taxonomy_scroll(merge_sql: str):
    """Verifica que el evento scroll se mapee como 'scroll'."""
    assert "WHEN event_name = 'scroll' THEN 'scroll'" in merge_sql


@pytest.mark.unit
def test_ga4_taxonomy_ecommerce_interactions(merge_sql: str):
    """Verifica que todos los eventos de interaccion/ecommerce esten categorizados como 'interaccion'."""
    for event in ECOMMERCE_INTERACTION_EVENTS:
        assert f"'{event}'" in merge_sql
    assert "THEN 'interaccion'" in merge_sql


@pytest.mark.unit
def test_ga4_taxonomy_fallback_to_other(merge_sql: str):
    """Verifica que eventos no catalogados caigan en la rama 'otro'."""
    assert "ELSE 'otro'" in merge_sql


@pytest.mark.unit
def test_ga4_excluded_base_events(merge_sql: str):
    """Verifica que los eventos de infraestructura GA4 se excluyan para evitar sobrecarga analitica."""
    for event in EXCLUDED_BASE_EVENTS:
        assert f"'{event}'" in merge_sql
    assert "event_name NOT IN ('first_visit', 'session_start', 'user_engagement')" in merge_sql


@pytest.mark.unit
def test_ga4_click_detail_flattening(merge_sql: str):
    """
    Verifica las reglas de concatenacion condicional de detalle_click:
    - link_url + ' | ' + link_text cuando ambos existen.
    - Manejo de nulos y recorte con TRIM() y NULLIF().
    """
    assert "WHERE key = 'link_url'" in merge_sql
    assert "WHERE key = 'link_text'" in merge_sql
    assert "THEN ' | ' ELSE ''" in merge_sql
    assert "NULLIF(TRIM(CONCAT(" in merge_sql


@pytest.mark.unit
def test_ga4_heterogeneous_numeric_params(merge_sql: str):
    """
    Verifica que parametros numericos puedan leerse tanto de int_value
    como de string_value mediante SAFE_CAST para protegerse de payloads inconsistentes.
    """
    # porcentaje_scroll
    assert "SELECT COALESCE(value.int_value, SAFE_CAST(value.string_value AS INT64))" in merge_sql
    assert "WHERE key = 'percent_scrolled'" in merge_sql

    # engagement_time_msec
    assert "WHERE key = 'engagement_time_msec'" in merge_sql


@pytest.mark.unit
def test_ga4_promotions_and_items_serialization(merge_sql: str):
    """Verifica la serializacion a JSON de arrays anidados (items y promociones)."""
    assert "TO_JSON_STRING(items) AS items" in merge_sql
    assert "promotion_id" in merge_sql
    assert "promotion_name" in merge_sql
    assert "creative_name" in merge_sql
    assert "creative_slot" in merge_sql


@pytest.mark.unit
def test_ga4_context_attributes_projection(merge_sql: str):
    """Verifica la proyeccion de dimensiones de contexto (geografia y dispositivo)."""
    assert "geo.country AS pais" in merge_sql
    assert "geo.city AS ciudad" in merge_sql
    assert "device.category AS tipo_dispositivo" in merge_sql
    assert "device.web_info.browser AS navegador" in merge_sql
    assert "device.operating_system AS sistema_operativo" in merge_sql
