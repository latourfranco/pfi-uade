"""Fixtures compartidos para la suite de pruebas unitarias y de integración."""

import os
import pytest
from app.models import (
    ClientInterfaceConfig,
    DeviceInfo,
    EventType,
    SessionTrace,
    TraceEvent,
)

# Desactivar esperas artificiales en la suite de pruebas unitarias
os.environ["PAGE_SETTLE_SECONDS"] = "0.0"


@pytest.fixture
def sample_client_config() -> ClientInterfaceConfig:
    """Fixture con una configuración típica de cliente de prueba."""
    return ClientInterfaceConfig(
        client_id="client-uuid-1234",
        base_url="https://staging.tienda-ejemplo.com",
        test_username="qa_tester@ejemplo.com",
        test_password_encrypted="encrypted_mock_token_abc123",
        custom_headers={"x-preprod-bypass": "secret_token_777"},
        default_timeout_ms=10000,
    )


@pytest.fixture
def sample_trace_event() -> TraceEvent:
    """Fixture con un evento representativo de interacción."""
    return TraceEvent(
        orden=2,
        nombre_evento="add_to_cart",
        event_type=EventType.INTERACTION,
        ruta="https://tienda-ejemplo.com/product/zapatilla",
        items="Zapatilla Deportiva",
        scroll=False,
        en_patron=True,
        es_paso_friccion=True,
    )


@pytest.fixture
def sample_session_trace(sample_trace_event: TraceEvent) -> SessionTrace:
    """Fixture con una traza completa de sesión representativa."""
    return SessionTrace(
        id_patron="pattern-friction-42",
        id_cliente="client-uuid-1234",
        id_sesion="trace-session-9999",
        fecha_exploracion="2026-11-15",
        objetivo="add_to_cart",
        secuencia=["page_view /carrito", "add_to_cart /product/zapatilla"],
        sesiones=120,
        usuarios=110,
        llegada_grupo=0.15,
        llegada_referencia=0.35,
        sesiones_perdidas=24.0,
        id_modelo="lstm_2026-11-14",
        primera_deteccion="2026-11-14",
        ultima_deteccion="2026-11-14",
        device_info=DeviceInfo(
            tipo_dispositivo="desktop",
            navegador="Chrome v126.0",
            sistema_operativo="Web",
        ),
        events=[
            TraceEvent(
                orden=1,
                nombre_evento="page_view",
                event_type=EventType.PAGE_VIEW,
                ruta="https://tienda-ejemplo.com/carrito",
                scroll=True,
                en_patron=True,
                es_paso_friccion=False,
            ),
            sample_trace_event,
        ],
    )
