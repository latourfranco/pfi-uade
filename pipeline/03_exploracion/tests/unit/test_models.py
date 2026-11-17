"""Pruebas unitarias para validar los modelos de datos y la configuración."""

from datetime import date
import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.models import (
    BoundingBox,
    BoundingBoxContext,
    ClientInterfaceConfig,
    DeviceInfo,
    EventType,
    ExplorationReport,
    ExplorationStatus,
    SessionTrace,
    TraceEvent,
    VisualEvidence,
)


@pytest.mark.unit
def test_client_interface_config_valid() -> None:
    """Verifica la instanciación válida de ClientInterfaceConfig."""
    config = ClientInterfaceConfig(
        client_id="client-1",
        base_url="https://staging.test.com",
        test_username="user1",
        test_password_encrypted="enc_pass_123",
        custom_headers={"x-bypass": "token"},
        default_timeout_ms=5000,
    )
    assert config.client_id == "client-1"
    assert config.base_url == "https://staging.test.com"
    assert config.test_username == "user1"
    assert config.test_password_encrypted == "enc_pass_123"
    assert config.custom_headers["x-bypass"] == "token"
    assert config.default_timeout_ms == 5000


@pytest.mark.unit
def test_client_interface_config_defaults() -> None:
    """Verifica que los valores por defecto de ClientInterfaceConfig se apliquen correctamente."""
    config = ClientInterfaceConfig(
        client_id="client-2",
        base_url="https://test.com",
    )
    assert config.test_username is None
    assert config.test_password_encrypted is None
    assert config.custom_headers == {}
    assert config.default_timeout_ms == 15000


@pytest.mark.unit
def test_client_interface_config_missing_required() -> None:
    """Verifica que falle si faltan campos obligatorios."""
    with pytest.raises(ValidationError):
        ClientInterfaceConfig.model_validate({"client_id": "client-3"})


@pytest.mark.unit
def test_client_interface_config_storage_state_direct() -> None:
    """Verifica la asignación y resolución directa de storage_state en memoria."""
    sample_state = {"cookies": [{"name": "auth", "value": "123"}], "origins": []}
    config = ClientInterfaceConfig(
        client_id="client-4",
        base_url="https://shop.merch.google",
        storage_state=sample_state,
    )
    assert config.storage_state == sample_state
    assert config.resolve_storage_state() == sample_state


@pytest.mark.unit
def test_client_interface_config_storage_state_encrypted() -> None:
    """Verifica el descifrado de storage_state_encrypted utilizando la clave provista."""
    from app.security.encryption import encrypt_json, generate_aes_key

    key = generate_aes_key()
    sample_state = {"cookies": [{"name": "google_session", "value": "token_abc"}], "origins": []}
    encrypted = encrypt_json(sample_state, key)

    config = ClientInterfaceConfig(
        client_id="client-5",
        base_url="https://shop.merch.google",
        storage_state_encrypted=encrypted,
    )
    resolved = config.resolve_storage_state(encryption_key=key)
    assert resolved == sample_state


@pytest.mark.unit
def test_client_interface_config_storage_state_encrypted_invalid_payload() -> None:
    """Verifica que resolve_storage_state retorne None si el payload está corrupto."""
    config = ClientInterfaceConfig(
        client_id="client-6",
        base_url="https://shop.merch.google",
        storage_state_encrypted="payload_invalido",
    )
    assert config.resolve_storage_state(encryption_key="invalid_or_whatever_key_length_32_bytes_ok!!!") is None


@pytest.mark.unit
def test_client_interface_config_storage_state_none() -> None:
    """Verifica que resolve_storage_state retorne None cuando no hay ningún estado configurado."""
    config = ClientInterfaceConfig(
        client_id="client-7",
        base_url="https://shop.merch.google",
    )
    assert config.storage_state is None
    assert config.storage_state_encrypted is None
    assert config.resolve_storage_state() is None


@pytest.mark.unit
def test_client_interface_config_storage_state_encrypted_not_a_dict() -> None:
    """Verifica que resolve_storage_state retorne None si el contenido descifrado no es un diccionario."""
    from app.security.encryption import encrypt_json, generate_aes_key

    key = generate_aes_key()
    encrypted_list = encrypt_json(["cookie1", "cookie2"], key)

    config = ClientInterfaceConfig(
        client_id="client-8",
        base_url="https://shop.merch.google",
        storage_state_encrypted=encrypted_list,
    )
    assert config.resolve_storage_state(encryption_key=key) is None


@pytest.mark.unit
def test_event_type_values() -> None:
    """Verifica que los tipos operativos de eventos coincidan con los valores esperados."""
    assert EventType.PAGE_VIEW.value == "visita_pagina"
    assert EventType.INTERACTION.value == "interaccion"
    assert EventType.OTHER.value == "otro"


@pytest.mark.unit
def test_device_info_defaults() -> None:
    """Verifica que DeviceInfo use 'desktop' por defecto."""
    device = DeviceInfo()
    assert device.tipo_dispositivo == "desktop"
    assert device.navegador is None
    assert device.sistema_operativo is None


@pytest.mark.unit
def test_trace_event_inference_and_serialization(sample_trace_event: TraceEvent) -> None:
    """Verifica la derivación automática de event_type y la serialización de TraceEvent."""
    event_dict = sample_trace_event.model_dump()
    reconstructed = TraceEvent.model_validate(event_dict)
    assert reconstructed.orden == 2
    assert reconstructed.nombre_evento == "add_to_cart"
    assert reconstructed.event_type == EventType.INTERACTION
    assert reconstructed.ruta == "https://tienda-ejemplo.com/product/zapatilla"
    assert reconstructed.items == "Zapatilla Deportiva"
    assert reconstructed.en_patron is True
    assert reconstructed.es_paso_friccion is True

    # Derivación automática sin especificar event_type
    ev_pv = TraceEvent.model_validate({"orden": 1, "nombre_evento": "page_view", "ruta": "/"})
    assert ev_pv.event_type == EventType.PAGE_VIEW

    for interaction_name in (
        "select_item",
        "begin_checkout",
        "view_login",
        "view_cart",
        "login",
        "add_shipping_info",
    ):
        ev_int = TraceEvent(nombre_evento=interaction_name)
        assert ev_int.event_type == EventType.INTERACTION

    ev_other = TraceEvent(nombre_evento="custom_analytics_ping")
    assert ev_other.event_type == EventType.OTHER

    # Preserva event_type explícito sin sobrescribirlo
    ev_explicit = TraceEvent(nombre_evento="custom_event", event_type=EventType.PAGE_VIEW)
    assert ev_explicit.event_type == EventType.PAGE_VIEW


@pytest.mark.unit
def test_session_trace_structure(sample_session_trace: SessionTrace) -> None:
    """Verifica la estructura y eventos contenidos en SessionTrace."""
    assert sample_session_trace.id_patron == "pattern-friction-42"
    assert sample_session_trace.id_cliente == "client-uuid-1234"
    assert sample_session_trace.id_sesion == "trace-session-9999"
    assert sample_session_trace.fecha_exploracion == "2026-11-15"
    assert sample_session_trace.objetivo == "add_to_cart"
    assert sample_session_trace.sesiones_perdidas == 24.0
    assert len(sample_session_trace.events) == 2
    assert sample_session_trace.events[0].event_type == EventType.PAGE_VIEW
    assert sample_session_trace.events[0].scroll is True
    assert sample_session_trace.events[1].event_type == EventType.INTERACTION


@pytest.mark.unit
def test_bounding_box_and_context() -> None:
    """Verifica la creación y formato del BoundingBox y su BoundingBoxContext."""
    box = BoundingBox(x=10.5, y=20.0, width=150.0, height=40.0)
    assert box.x == 10.5
    assert box.width == 150.0

    context = BoundingBoxContext(
        box=box,
        tag_name="button",
        element_text="Comprar",
        role="button",
        aria_label="Boton comprar",
        context_type="interacted_element",
        surrounding_text="Total: $100 | Comprar",
    )
    assert context.tag_name == "button"
    assert context.context_type == "interacted_element"
    assert context.box.height == 40.0


@pytest.mark.unit
def test_visual_evidence_creation() -> None:
    """Verifica la creación de VisualEvidence con campos de raíz y scroll contextual."""
    evidence = VisualEvidence(
        orden=1,
        nombre_evento="page_view",
        ruta="https://test.com/home",
        scroll=True,
        en_patron=True,
        es_paso_friccion=False,
        screenshot_url="gs://bucket-evidencias/client-1/trace-1/step_1.webp",
        timestamp="2026-11-15T12:00:00Z",
    )
    assert evidence.orden == 1
    assert evidence.scroll is True
    assert evidence.en_patron is True
    assert evidence.bounding_box_context is None
    assert evidence.context_notes == []

    evidence_with_notes = VisualEvidence(
        orden=2,
        nombre_evento="page_view",
        ruta="https://test.com/cat",
        screenshot_url="gs://bucket/cat.webp",
        timestamp="2026-11-15T12:00:05Z",
        context_notes=["Navegado vía menú hamburguesa mobile."],
    )
    assert evidence_with_notes.context_notes == ["Navegado vía menú hamburguesa mobile."]


@pytest.mark.unit
def test_exploration_report_lifecycle() -> None:
    """Verifica la generación del reporte final consolidado de exploración."""
    box = BoundingBox(x=0.0, y=0.0, width=100.0, height=50.0)
    ctx = BoundingBoxContext(box=box, tag_name="a", element_text="Link Roto")
    evidence = VisualEvidence(
        orden=2,
        nombre_evento="select_item",
        ruta="https://test.com/broken",
        items="Producto Roto",
        scroll=False,
        en_patron=True,
        es_paso_friccion=True,
        screenshot_url="/local/path/step_2.webp",
        timestamp="2026-11-15T12:01:00Z",
        bounding_box_context=ctx,
    )

    report = ExplorationReport(
        id_patron="pattern-789",
        id_cliente="client-456",
        id_sesion="sesion-123",
        fecha_exploracion="2026-11-15",
        status=ExplorationStatus.COMPLETED,
        total_steps=2,
        completed_steps=2,
        started_at="2026-11-15T12:00:00Z",
        finished_at="2026-11-15T12:01:10Z",
        objetivo="add_to_cart",
        secuencia=["page_view /", "select_item /broken"],
        sesiones=200,
        usuarios=180,
        llegada_grupo=0.12,
        llegada_referencia=0.32,
        sesiones_perdidas=40.0,
        id_modelo="lstm_2026-11-14",
        primera_deteccion="2026-11-14",
        ultima_deteccion="2026-11-14",
        evidences=[evidence],
    )

    assert report.status == ExplorationStatus.COMPLETED
    assert report.id_patron == "pattern-789"
    assert report.fecha_exploracion == "2026-11-15"
    assert report.sesiones_perdidas == 40.0
    assert len(report.evidences) == 1
    assert report.evidences[0].es_paso_friccion is True


@pytest.mark.unit
def test_exploration_report_default_fecha_exploracion() -> None:
    """Verifica que ExplorationReport genere por defecto la fecha actual si no se provee fecha_exploracion."""
    report = ExplorationReport(
        id_patron="pattern_now",
        id_cliente="client_now",
        id_sesion="sesion_now",
        status=ExplorationStatus.COMPLETED,
        total_steps=1,
        completed_steps=1,
        started_at="2026-11-15T23:00:00Z",
        finished_at="2026-11-15T23:00:05Z",
    )
    assert report.id_patron == "pattern_now"
    assert report.fecha_exploracion is not None
    assert len(report.fecha_exploracion) == 10


@pytest.mark.unit
def test_settings_initialization() -> None:
    """Verifica que la configuración por defecto de Settings se cargue correctamente."""
    settings = Settings()
    assert settings.ENVIRONMENT in ["production", "development", "staging"]
    assert settings.HEADLESS_MODE is True
    assert settings.DEFAULT_TIMEOUT_MS == 15000
    assert settings.DESKTOP_VIEWPORT_WIDTH == 1366
    assert settings.DESKTOP_VIEWPORT_HEIGHT == 768
    assert settings.MOBILE_VIEWPORT_WIDTH == 390
    assert settings.MOBILE_VIEWPORT_HEIGHT == 844
    assert settings.MAX_CONCURRENCY_PER_CLIENT == 3
    assert settings.STORAGE_PROVIDER in ["local", "gcs"]
    assert settings.BIGQUERY_DATASET == "friccion_resultados"

    cached = get_settings()
    assert cached is not None
    assert cached.ENVIRONMENT == settings.ENVIRONMENT


@pytest.mark.unit
def test_session_trace_from_friction_pattern_relational() -> None:
    """Verifica la construcción de SessionTrace desde filas de patrones + sesion_representativa."""
    pattern_row = {
        "id_patron": "pat_99",
        "id_cliente": "00000000-0000-0000-0000-000000000001",
        "objetivo": "begin_checkout",
        "secuencia": ["page_view /", "add_to_cart /shop"],
        "sesiones": 466,
        "usuarios": 435,
        "llegada_grupo": 0.46,
        "llegada_referencia": 0.57,
        "sesiones_perdidas": 49.3,
        "id_modelo": "lstm_2026-11-14",
        "primera_deteccion": date(2026, 11, 14),
        "ultima_deteccion": date(2026, 11, 14),
    }
    # Eventos intencionalmente desordenados por orden
    session_rows = [
        {
            "id_patron": "pat_99",
            "id_sesion": "usr1_1607479125280232",
            "orden": 3,
            "nombre_evento": "add_to_cart",
            "ruta": "https://shop.merch.google/product/hoodie",
            "items": "YouTube Black Zip Hoodie",
            "scroll": False,
            "en_patron": True,
            "es_paso_friccion": True,
            "tipo_dispositivo": "mobile",
            "navegador": "Chrome v86.0",
            "sistema_operativo": "iOS",
        },
        {
            "id_patron": "pat_99",
            "id_sesion": "usr1_1607479125280232",
            "orden": 1,
            "nombre_evento": "page_view",
            "ruta": "https://shop.merch.google/",
            "items": None,
            "scroll": True,
            "en_patron": False,
            "es_paso_friccion": False,
            "tipo_dispositivo": "mobile",
            "navegador": "Chrome v86.0",
            "sistema_operativo": "iOS",
        },
        {
            "id_patron": "pat_99",
            "id_sesion": "usr1_1607479125280232",
            "orden": 2,
            "nombre_evento": "select_item",
            "ruta": "https://shop.merch.google/shop/new",
            "items": "YouTube Black Zip Hoodie",
            "scroll": False,
            "en_patron": True,
            "es_paso_friccion": False,
            "tipo_dispositivo": "mobile",
            "navegador": "Chrome v86.0",
            "sistema_operativo": "iOS",
        },
    ]

    trace = SessionTrace.from_friction_pattern(pattern_row, session_rows)

    assert trace.id_patron == "pat_99"
    assert trace.id_cliente == "00000000-0000-0000-0000-000000000001"
    assert trace.id_sesion == "usr1_1607479125280232"
    assert trace.objetivo == "begin_checkout"
    assert trace.secuencia == ["page_view /", "add_to_cart /shop"]
    assert trace.sesiones == 466
    assert trace.usuarios == 435
    assert trace.sesiones_perdidas == 49.3
    assert trace.primera_deteccion == "2026-11-14"
    assert trace.ultima_deteccion == "2026-11-14"
    assert trace.device_info.tipo_dispositivo == "mobile"
    assert trace.device_info.navegador == "Chrome v86.0"
    assert trace.device_info.sistema_operativo == "iOS"

    assert [e.orden for e in trace.events] == [1, 2, 3]
    assert trace.events[0].event_type == EventType.PAGE_VIEW
    assert trace.events[0].scroll is True
    assert trace.events[1].event_type == EventType.INTERACTION
    assert trace.events[1].en_patron is True
    assert trace.events[2].es_paso_friccion is True


@pytest.mark.unit
def test_session_trace_from_friction_pattern_edge_cases() -> None:
    """Verifica fallbacks de device_info, pasos embebidos, instancias TraceEvent y elementos no válidos."""
    # Caso 1: DeviceInfo instanciado directo + TraceEvent preconstruido + elemento ignorado
    ev_obj = TraceEvent(orden=2, nombre_evento="page_view", ruta="/")
    trace_1 = SessionTrace.from_friction_pattern({
        "id_patron": "p_1",
        "id_cliente": "c_1",
        "device_info": DeviceInfo(tipo_dispositivo="tablet", navegador="Safari", sistema_operativo="iPadOS"),
        "pasos": [ev_obj, "elemento_invalido"],
    })
    assert trace_1.id_sesion == "sesion_p_1"
    assert trace_1.device_info.tipo_dispositivo == "tablet"
    assert len(trace_1.events) == 1
    assert trace_1.events[0].orden == 2

    # Caso 2: device_info como dict y pasos no-lista
    trace_2 = SessionTrace.from_friction_pattern({
        "id_patron": "p_2",
        "id_cliente": "c_2",
        "device_info": {"tipo_dispositivo": "mobile"},
        "events": "no_es_lista",
    })
    assert trace_2.device_info.tipo_dispositivo == "mobile"
    assert trace_2.events == []

    # Caso 3: Sin device_info ni eventos
    trace_3 = SessionTrace.from_friction_pattern({
        "id_patron": "p_3",
        "id_cliente": "c_3",
    })
    assert trace_3.device_info.tipo_dispositivo == "desktop"
    assert trace_3.events == []


@pytest.mark.unit
def test_session_trace_requires_authenticated_session() -> None:
    """Verifica clasificación de trazas anónimas vs. dependientes de sesión compartida."""
    trace_anon_view_login = SessionTrace(
        id_patron="p_anon",
        id_cliente="c_1",
        id_sesion="s_1",
        events=[
            TraceEvent(orden=1, nombre_evento="page_view", ruta="/"),
            TraceEvent(orden=2, nombre_evento="add_to_cart", ruta="/product/1"),
            TraceEvent(orden=3, nombre_evento="view_login", ruta="/checkout?show=basket"),
        ],
    )
    assert trace_anon_view_login.requires_authenticated_session() is False

    trace_with_login = SessionTrace(
        id_patron="p_login",
        id_cliente="c_1",
        id_sesion="s_2",
        events=[
            TraceEvent(orden=1, nombre_evento="view_login", ruta="/"),
            TraceEvent(orden=2, nombre_evento="login", ruta="/"),
        ],
    )
    assert trace_with_login.requires_authenticated_session() is True

    trace_checkout = SessionTrace(
        id_patron="p_checkout",
        id_cliente="c_1",
        id_sesion="s_3",
        events=[
            TraceEvent(orden=1, nombre_evento="page_view", ruta="/checkout?show=multibillto"),
        ],
    )
    assert trace_checkout.requires_authenticated_session() is True

    # Familia A: login ocurre antes de add_to_cart -> JIT permanece en paso login
    trace_fam_a = SessionTrace(
        id_patron="p_fam_a",
        id_cliente="c_1",
        id_sesion="s_fa",
        events=[
            TraceEvent(orden=1, nombre_evento="login", ruta="/"),
            TraceEvent(orden=2, nombre_evento="add_to_cart", ruta="/product/1"),
            TraceEvent(orden=3, nombre_evento="begin_checkout", ruta="/checkout"),
        ],
    )
    assert trace_fam_a.prefers_pre_cart_auth_jit() is False

    # Familia B: add_to_cart antes de login o sin login -> JIT antes de add_to_cart
    trace_fam_b = SessionTrace(
        id_patron="p_fam_b",
        id_cliente="c_1",
        id_sesion="s_fb",
        events=[
            TraceEvent(orden=1, nombre_evento="add_to_cart", ruta="/product/1"),
            TraceEvent(orden=2, nombre_evento="login", ruta="/checkout?show=basket"),
            TraceEvent(orden=3, nombre_evento="begin_checkout", ruta="/checkout?show=multibillto"),
        ],
    )
    assert trace_fam_b.prefers_pre_cart_auth_jit() is True

    trace_no_login_checkout = SessionTrace(
        id_patron="p_no_login",
        id_cliente="c_1",
        id_sesion="s_nl",
        events=[
            TraceEvent(orden=1, nombre_evento="add_to_cart", ruta="/product/1"),
            TraceEvent(orden=2, nombre_evento="add_billing_info", ruta="/checkout?show=multibillto"),
        ],
    )
    assert trace_no_login_checkout.prefers_pre_cart_auth_jit() is True
    assert trace_anon_view_login.prefers_pre_cart_auth_jit() is False
