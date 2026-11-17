"""Pruebas unitarias para BigQueryService y modelos de exploración."""

from datetime import date, datetime, timezone
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch
import pytest

from app.config import Settings
from app.models.exploration_models import (
    BoundingBoxContext,
    BoundingBoxCoordinates,
    ExplorationEvidence,
    ExplorationReport,
)
from app.services.bigquery_service import BigQueryService, BigQueryServiceError


@pytest.mark.unit
def test_exploration_report_compute_exploration_hash_deterministic() -> None:
    """Verifica que el hash sea determinístico independientemente del orden inicial y cambie ante novedades."""
    ev_1 = ExplorationEvidence(
        orden=1,
        nombre_evento="page_view",
        ruta="https://shop.merch.google/",
        scroll=True,
        en_patron=True,
        es_paso_friccion=False,
        screenshot_url="gs://b/1.webp",
        context_notes=["Cerrado banner de cookies"],
    )
    ev_2 = ExplorationEvidence(
        orden=2,
        nombre_evento="view_login",
        ruta="https://shop.merch.google/checkout",
        scroll=False,
        en_patron=True,
        es_paso_friccion=True,
        screenshot_url="gs://b/2.webp",
        bounding_box_context=BoundingBoxContext(
            box=BoundingBoxCoordinates(x=10.0, y=20.0, width=100.0, height=40.0),
            tag_name="button",
            element_text="Continuar",
        ),
    )

    rep_a = ExplorationReport(
        id_patron="p-1",
        id_cliente="c-1",
        id_sesion="s-1",
        fecha_exploracion="2026-11-16",
        evidences=[ev_2, ev_1],
    )
    rep_b = ExplorationReport(
        id_patron="p-1",
        id_cliente="c-1",
        id_sesion="s-1",
        fecha_exploracion="2026-11-16",
        evidences=[ev_1, ev_2],
    )
    assert rep_a.compute_exploration_hash() == rep_b.compute_exploration_hash()

    ev_2_mod = ev_2.model_copy(update={"context_notes": ["Botón deshabilitado"]})
    rep_c = rep_b.model_copy(update={"evidences": [ev_1, ev_2_mod]})
    assert rep_c.compute_exploration_hash() != rep_a.compute_exploration_hash()


@pytest.mark.unit
def test_get_completed_exploration_reports_success_with_distributions(mock_settings: Settings) -> None:
    """Verifica consulta a BigQuery con JOIN a modelos y enriquecimiento de distribuciones."""
    mock_client = MagicMock()
    mock_query_job_main = MagicMock()
    mock_query_job_main.total_bytes_processed = 45000
    mock_query_job_main.job_id = "job-main-1"

    raw_row: Dict[str, Any] = {
        "id_patron": "aa652a79a08a6810ff6b0c5d608cba00",
        "id_cliente": "00000000-0000-0000-0000-000000000001",
        "id_sesion": "sess-101",
        "fecha_exploracion": date(2026, 11, 16),
        "status": "COMPLETED",
        "total_steps": 2,
        "completed_steps": 2,
        "started_at": datetime(2026, 11, 16, 10, 0, tzinfo=timezone.utc),
        "finished_at": datetime(2026, 11, 16, 10, 2, tzinfo=timezone.utc),
        "objetivo": "begin_checkout",
        "secuencia": ["page_view /", "view_cart /shop/…"],
        "sesiones": 120,
        "usuarios": 115,
        "llegada_grupo": 0.25,
        "llegada_referencia": 0.65,
        "sesiones_perdidas": 48.0,
        "id_modelo": "mod-1",
        "primera_deteccion": date(2021, 2, 1),
        "ultima_deteccion": date(2021, 2, 1),
        "total_sesiones_modelo": 14500,
        "objetivo_modelo": "purchase",
        "eventos_clave_modelo": ["select_item", "add_to_cart", "begin_checkout", "purchase"],
        "nombres_hitos_modelo": ["Seleccionar producto", "Agregar al carrito", "Iniciar pago", "Realizar compra"],
        "datos_desde_modelo": "2021-01-01T00:00:00Z",
        "datos_hasta_modelo": "2021-02-01T00:00:00Z",
        "device_info": {
            "tipo_dispositivo": "mobile",
            "navegador": "Android Webview v86.0",
            "sistema_operativo": "Web",
        },
        "error_message": None,
        "created_at": "2026-11-16T10:03:00Z",
        "evidences": [
            {
                "orden": 1,
                "nombre_evento": "page_view",
                "ruta": "https://shop.merch.google/",
                "items": None,
                "scroll": True,
                "en_patron": True,
                "es_paso_friccion": False,
                "screenshot_url": "gs://pruebas-pfi-evidencias/step_1.webp",
                "timestamp": "2026-11-16T10:00:10Z",
                "bounding_box_context": None,
                "context_notes": ["Se cerró el banner de cookies."],
            },
            {
                "orden": 2,
                "nombre_evento": "view_cart",
                "ruta": "https://shop.merch.google/shop/lifestyle",
                "items": "Google Tote",
                "scroll": False,
                "en_patron": True,
                "es_paso_friccion": True,
                "screenshot_url": "gs://pruebas-pfi-evidencias/step_2.webp",
                "timestamp": "2026-11-16T10:01:10Z",
                "bounding_box_context": {
                    "box": {"x": 10.0, "y": 20.0, "width": 100.0, "height": 40.0},
                    "tag_name": "button",
                    "element_text": "Pagar",
                    "role": "button",
                    "aria_label": "Botón de compra",
                    "context_type": "interaction_click",
                    "surrounding_text": "Total a pagar: $100",
                },
                "context_notes": [],
            },
        ],
    }

    mock_row_main = MagicMock()
    mock_row_main.items.return_value = raw_row.items()
    mock_query_job_main.result.return_value = [mock_row_main]

    mock_query_job_dist = MagicMock()
    mock_query_job_dist.total_bytes_processed = 100000
    dist_rows = [
        {
            "id_patron": "aa652a79a08a6810ff6b0c5d608cba00",
            "tipo_dispositivo": "mobile",
            "navegador": "Chrome v87.0",
            "sistema_operativo": "Android",
            "pais": "Argentina",
            "usuarios_cnt": 75,
        },
        {
            "id_patron": "aa652a79a08a6810ff6b0c5d608cba00",
            "tipo_dispositivo": "desktop",
            "navegador": "Safari v14.0",
            "sistema_operativo": "Macintosh",
            "pais": "United States",
            "usuarios_cnt": 25,
        },
    ]
    mock_dist_objs: List[MagicMock] = []
    for dr in dist_rows:
        m = MagicMock()
        m.items.return_value = dr.items()
        mock_dist_objs.append(m)
    mock_query_job_dist.result.return_value = mock_dist_objs

    mock_client.query.side_effect = [mock_query_job_main, mock_query_job_dist]

    svc = BigQueryService(settings=mock_settings, client=mock_client)
    reports = svc.get_completed_exploration_reports(
        client_id="00000000-0000-0000-0000-000000000001",
        batch_date="2026-11-16",
    )

    assert len(reports) == 1
    rep = reports[0]
    assert rep.id_patron == "aa652a79a08a6810ff6b0c5d608cba00"
    assert rep.fecha_exploracion == "2026-11-16"
    assert rep.total_sesiones_modelo == 14500
    assert rep.objetivo_modelo == "purchase"
    assert rep.device_info is not None
    assert rep.device_info.tipo_dispositivo == "mobile"
    assert len(rep.evidences) == 2
    assert rep.evidences[1].es_paso_friccion is True
    assert rep.evidences[1].bounding_box_context is not None
    assert rep.evidences[1].bounding_box_context.tag_name == "button"
    assert rep.audience_distributions.dispositivos[0].label == "mobile"
    assert rep.audience_distributions.dispositivos[0].percentage == 75.0
    assert rep.audience_distributions.paises[0].label == "Argentina"
    assert mock_client.query.call_count == 2
    main_sql = mock_client.query.call_args_list[0][0][0]
    dist_sql = mock_client.query.call_args_list[1][0][0]
    assert "fecha_exploracion <= CAST(@fecha_ejecucion AS DATE)" in main_sql
    assert "ORDER BY fecha_exploracion DESC, created_at DESC" in main_sql
    assert "fecha_exploracion <= CAST(@fecha_ejecucion AS DATE)" in dist_sql
    assert "ORDER BY fecha_exploracion DESC, created_at DESC" in dist_sql


@pytest.mark.unit
def test_get_completed_exploration_reports_empty_and_no_enrichment(mock_settings: Settings) -> None:
    """Verifica retorno vacío sin disparar la segunda query de distribuciones."""
    mock_client = MagicMock()
    mock_query_job = MagicMock()
    mock_query_job.result.return_value = []
    mock_client.query.return_value = mock_query_job

    svc = BigQueryService(settings=mock_settings, client=mock_client)
    reports = svc.get_completed_exploration_reports("client-empty", "2026-11-16")
    assert reports == []
    mock_client.query.assert_called_once()


@pytest.mark.unit
def test_get_completed_exploration_reports_distribution_error_is_non_fatal(mock_settings: Settings) -> None:
    """Verifica que un fallo en la consulta de distribuciones no aborte el reporte principal."""
    mock_client = MagicMock()
    mock_query_job_main = MagicMock()
    raw_row: Dict[str, Any] = {
        "id_patron": "pat-ok",
        "id_cliente": "cli-1",
        "id_sesion": "ses-1",
        "fecha_exploracion": "2026-11-16",
        "evidences": [],
    }
    mock_row_obj = MagicMock()
    mock_row_obj.items.return_value = raw_row.items()
    mock_query_job_main.result.return_value = [mock_row_obj]

    mock_client.query.side_effect = [mock_query_job_main, RuntimeError("Timeout en eventos_usuario")]

    svc = BigQueryService(settings=mock_settings, client=mock_client)
    reports = svc.get_completed_exploration_reports("cli-1", "2026-11-16")
    assert len(reports) == 1
    assert reports[0].audience_distributions.dispositivos == []


@pytest.mark.unit
def test_get_completed_exploration_reports_skip_distributions_flag(mock_settings: Settings) -> None:
    """Verifica que enrich_distributions=False omita la consulta a eventos_usuario."""
    mock_client = MagicMock()
    mock_query_job = MagicMock()
    raw_row: Dict[str, Any] = {
        "id_patron": "pat-1",
        "id_cliente": "cli-1",
        "id_sesion": "ses-1",
        "fecha_exploracion": "2026-11-16",
        "evidences": [],
    }
    mock_row = MagicMock()
    mock_row.items.return_value = raw_row.items()
    mock_query_job.result.return_value = [mock_row]
    mock_client.query.return_value = mock_query_job

    svc = BigQueryService(settings=mock_settings, client=mock_client)
    reports = svc.get_completed_exploration_reports("cli-1", "2026-11-16", enrich_distributions=False)
    assert len(reports) == 1
    mock_client.query.assert_called_once()


@pytest.mark.unit
def test_get_completed_exploration_reports_error(mock_settings: Settings) -> None:
    """Verifica que fallos de BigQuery se traduzcan en BigQueryServiceError."""
    mock_client = MagicMock()
    mock_client.query.side_effect = Exception("BigQuery connection timeout")

    svc = BigQueryService(settings=mock_settings, client=mock_client)
    with pytest.raises(BigQueryServiceError, match="BigQuery connection timeout"):
        svc.get_completed_exploration_reports(
            client_id="client-xyz",
            batch_date="2026-11-16",
        )


@pytest.mark.unit
def test_bigquery_client_initialization(mock_settings: Settings) -> None:
    """Verifica la inicialización lazy del cliente de BigQuery con archivo de credenciales y con ADC."""
    with patch("google.oauth2.service_account.Credentials.from_service_account_file") as mock_creds, \
         patch("google.cloud.bigquery.Client") as mock_bq_cls:
        settings_sa = mock_settings.model_copy(update={"GOOGLE_APPLICATION_CREDENTIALS": "/creds/sa.json"})
        svc_sa = BigQueryService(settings=settings_sa)

        client_sa = svc_sa.client
        assert client_sa is not None
        assert svc_sa.client is client_sa
        mock_creds.assert_called_once_with("/creds/sa.json")
        mock_bq_cls.assert_called_once_with(
            project=settings_sa.PLATFORM_GCP_PROJECT_ID,
            credentials=mock_creds.return_value,
        )

    with patch("google.cloud.bigquery.Client") as mock_bq_cls:
        settings_adc = mock_settings.model_copy(update={"GOOGLE_APPLICATION_CREDENTIALS": None})
        svc_adc = BigQueryService(settings=settings_adc)

        client_adc = svc_adc.client
        assert client_adc is not None
        mock_bq_cls.assert_called_once_with(project=settings_adc.PLATFORM_GCP_PROJECT_ID)


@pytest.mark.unit
def test_bigquery_service_default_init() -> None:
    """Verifica la inicialización por defecto de BigQueryService sin argumentos."""
    with patch("app.services.bigquery_service.get_settings") as mock_get_settings:
        mock_get_settings.return_value = MagicMock()
        svc = BigQueryService()
        assert svc.settings == mock_get_settings.return_value
        assert svc._client is None


@pytest.mark.unit
def test_parse_row_and_distributions_edge_cases(mock_settings: Settings) -> None:
    """Verifica casos borde en _parse_row_to_report, _build_distributions_map y _to_distribution_items."""
    svc = BigQueryService(settings=mock_settings)

    row_edge: Dict[str, Any] = {
        "id_patron": "pat-edge",
        "id_cliente": "cli-edge",
        "id_sesion": "ses-edge",
        "fecha_exploracion": "   ",
        "primera_deteccion": None,
        "ultima_deteccion": "2026-11-15",
        "device_info": "not_a_dict",
        "evidences": [
            "not_a_dict",
            None,
            {
                "orden": 0,
                "screenshot_url": "gs://b/img.webp",
                "bounding_box_context": {
                    "box": "invalid_box",
                    "tag_name": "span",
                },
            },
        ],
    }

    report = svc._parse_row_to_report(row_edge)
    assert report.fecha_exploracion == ""
    assert report.primera_deteccion is None
    assert report.ultima_deteccion == "2026-11-15"
    assert report.device_info is None
    assert len(report.evidences) == 1
    assert report.evidences[0].orden == 1
    assert report.evidences[0].bounding_box_context is not None
    assert report.evidences[0].bounding_box_context.box is None

    # Distribuciones con filas sucias, contadores <= 0 y etiquetas vacías
    dist_map = svc._build_distributions_map([
        {"id_patron": None, "usuarios_cnt": 10},
        {"id_patron": "p1", "usuarios_cnt": 0},
        {"id_patron": "p1", "usuarios_cnt": None},
        {
            "id_patron": "p1",
            "tipo_dispositivo": "   ",
            "navegador": None,
            "sistema_operativo": "iOS",
            "pais": "AR",
            "usuarios_cnt": 5,
        },
    ])
    assert "p1" in dist_map
    assert dist_map["p1"].dispositivos[0].label == "Desconocido"
    assert dist_map["p1"].navegadores[0].label == "Desconocido"
    assert svc._to_distribution_items({}) == []
    assert svc._to_distribution_items({"x": 0}) == []

    # Caso: reporte sin match en distributions_by_pattern
    mock_client = MagicMock()
    mock_job = MagicMock()
    mock_job.result.return_value = []
    mock_client.query.return_value = mock_job
    svc_with_client = BigQueryService(settings=mock_settings, client=mock_client)
    rep_unmatched = ExplorationReport(
        id_patron="sin-match",
        id_cliente="c1",
        id_sesion="s1",
        fecha_exploracion="2026-11-16",
    )
    svc_with_client._enrich_audience_distributions("c1", "2026-11-16", [rep_unmatched])
    assert rep_unmatched.audience_distributions.dispositivos == []
