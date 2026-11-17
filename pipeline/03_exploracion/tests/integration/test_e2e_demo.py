"""Prueba de integración end-to-end completa con Playwright Chromium real y datos simulados."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional
from unittest.mock import MagicMock, patch

from playwright.async_api import Route
import pytest

from app.job_runner import run_client_job
from app.models.client_config import ClientInterfaceConfig
from app.models.exploration_report import ExplorationReport, ExplorationStatus
from app.models.session_trace import (
    DeviceInfo,
    EventType,
    SessionTrace,
    TraceEvent,
)
from app.safety.network_guard import NetworkGuard
from app.services.bigquery_service import BigQueryService
from app.services.supabase_service import SupabaseService
from app.storage.local_storage import LocalStorageProvider

BASE_TEST_URL = "https://tienda-demo.pfi.com"

HTML_HOME = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Tienda Demo - Inicio</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
           margin: 0; padding: 40px; background: #f8fafc; color: #1e293b; }
    .hero { background: white; padding: 30px; border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); max-width: 600px; margin: 0 auto; text-align: center; }
    h1 { color: #0f172a; margin-top: 0; }
    .btn { display: inline-block; padding: 12px 24px; background: #2563eb; color: white;
           text-decoration: none; border-radius: 8px; font-weight: 600; margin-top: 20px; }
  </style>
</head>
<body>
  <div class="hero">
    <h1>Bienvenido a la Tienda de Prueba</h1>
    <p>Esta aplicación web simula el entorno de staging de un cliente de la plataforma.</p>
    <a href="/catalogo" class="btn">Explorar Catálogo</a>
  </div>
</body>
</html>
"""

HTML_CATALOGO = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Catálogo de Productos</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
           margin: 0; padding: 40px; background: #f8fafc; color: #1e293b; min-height: 1800px; }
    .card { background: white; padding: 24px; border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); max-width: 500px; margin: 0 auto 30px; }
    .spacer { height: 600px; }
    .btn-checkout { display: inline-block; width: 100%; padding: 14px; background: #dc2626; color: white;
                    border: none; border-radius: 8px; font-size: 16px; font-weight: 700; cursor: pointer; }
    .error-alert { display: none; margin-top: 16px; padding: 14px; background: #fee2e2;
                   border: 1px solid #ef4444; color: #991b1b; border-radius: 8px; font-weight: 500; }
  </style>
</head>
<body>
  <div class="card">
    <h2>Zapatillas Running Pro 2026</h2>
    <p>Excelente amortiguación y respuesta para carreras de larga distancia.</p>
    <p><strong>Precio: $120.00 USD</strong></p>
  </div>

  <div class="spacer"></div>

  <div class="card" id="seccion-checkout">
    <h2>Resumen del Carrito</h2>
    <p>1x Zapatillas Running Pro 2026 — $120.00 USD</p>
    <button id="btn-cupon" class="btn-checkout">Aplicar Cupón</button>
    <div id="error-alert" class="error-alert">
      Error 500: Falló la validación del código promocional en el servidor.
    </div>
  </div>

  <script>
    document.getElementById('btn-cupon').addEventListener('click', function() {
      const alertBox = document.getElementById('error-alert');
      alertBox.style.display = 'block';
      throw new Error('CouponAPIException: Error 500 al validar cupón de descuento');
    });
  </script>
</body>
</html>
"""


async def _mock_network_guard_route(self: NetworkGuard, route: Route) -> None:
    """Intercepción de red en memoria para responder con la tienda web ficticia."""
    url = route.request.url
    if "tienda-demo.pfi.com" in url:
        if "/catalogo" in url:
            await route.fulfill(status=200, content_type="text/html; charset=utf-8", body=HTML_CATALOGO)
        else:
            await route.fulfill(status=200, content_type="text/html; charset=utf-8", body=HTML_HOME)
    else:
        await route.continue_()


class MockSupabaseService(SupabaseService):
    """Simula la consulta de configuración del cliente en Supabase."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.called_client_id: Optional[str] = None
        self.client = MagicMock()

    async def get_client_interface_config(self, client_id: str) -> Optional[ClientInterfaceConfig]:
        self.called_client_id = client_id
        return ClientInterfaceConfig(
            client_id=client_id,
            base_url=self.base_url,
            requires_authentication=False,
            default_timeout_ms=10000,
        )


class MockBigQueryService(BigQueryService):
    """Simula la lectura de patrones y la persistencia de reportes en BigQuery."""

    def __init__(self, patterns: List[SessionTrace]) -> None:
        super().__init__(client=None)
        self.patterns = patterns
        self.saved_reports: List[ExplorationReport] = []
        self.saved_rows: List[dict[str, Any]] = []

    async def get_friction_patterns_for_client(
        self,
        client_id: str,
        batch_date: str,
        region: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> List[SessionTrace]:
        return self.patterns

    async def ensure_exploration_table_exists(
        self,
        region: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> bool:
        return True

    async def save_exploration_report(
        self,
        report: ExplorationReport,
        region: Optional[str] = None,
        project_id: Optional[str] = None,
        idempotent: bool = True,
    ) -> bool:
        self.saved_reports.append(report)
        row = self.report_to_row(report)
        self.saved_rows.append(row)
        return True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_pipeline_e2e_execution(tmp_path: Path) -> None:
    """Ejecuta el pipeline completo de punta a punta con Chromium real y almacenamiento temporal."""
    output_dir = tmp_path / "e2e_evidences"
    output_dir.mkdir(parents=True, exist_ok=True)
    storage_provider = LocalStorageProvider(base_directory=str(output_dir))

    client_id = "cliente-ecommerce-demo"
    fecha_exploracion = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    fictitious_trace = SessionTrace(
        id_patron="patron-abandono-checkout-504",
        id_cliente=client_id,
        id_sesion="sesion_e2e_demo_001",
        fecha_exploracion=fecha_exploracion,
        objetivo="purchase",
        secuencia=["page_view /", "click /", "page_view /catalogo", "click /catalogo"],
        sesiones=80,
        usuarios=65,
        llegada_grupo=0.1,
        llegada_referencia=0.35,
        sesiones_perdidas=20.0,
        id_modelo="mod_demo",
        primera_deteccion=fecha_exploracion,
        ultima_deteccion=fecha_exploracion,
        device_info=DeviceInfo(
            tipo_dispositivo="desktop",
            navegador="Chrome",
            sistema_operativo="macOS",
        ),
        events=[
            TraceEvent(
                orden=0,
                nombre_evento="page_view",
                event_type=EventType.PAGE_VIEW,
                ruta="/",
                en_patron=True,
            ),
            TraceEvent(
                orden=1,
                nombre_evento="click",
                event_type=EventType.INTERACTION,
                click_detail="Explorar Catálogo",
                ruta="/",
                en_patron=True,
            ),
            TraceEvent(
                orden=2,
                nombre_evento="page_view",
                event_type=EventType.PAGE_VIEW,
                ruta="/catalogo",
                scroll=True,
                en_patron=True,
            ),
            TraceEvent(
                orden=3,
                nombre_evento="click",
                event_type=EventType.INTERACTION,
                click_detail="Aplicar Cupón",
                ruta="/catalogo",
                scroll=True,
                en_patron=True,
                es_paso_friccion=True,
            ),
            TraceEvent(
                orden=4,
                nombre_evento="error_observation",
                event_type=EventType.OTHER,
                ruta="/catalogo",
                scroll=True,
                en_patron=True,
            ),
        ],
    )

    supabase_mock = MockSupabaseService(base_url=BASE_TEST_URL)
    bigquery_mock = MockBigQueryService(patterns=[fictitious_trace])

    with (
        patch("app.job_runner.get_storage_provider", return_value=storage_provider),
        patch.object(NetworkGuard, "handle_route", new=_mock_network_guard_route),
    ):
        exit_code = await run_client_job(
            client_id=client_id,
            batch_date=fecha_exploracion,
            region="us-central1",
            max_concurrency=1,
            supabase_service=supabase_mock,
            bigquery_service=bigquery_mock,
        )

    assert exit_code == 0
    assert supabase_mock.called_client_id == client_id
    assert len(bigquery_mock.saved_reports) == 1
    assert len(bigquery_mock.saved_rows) == 1

    report = bigquery_mock.saved_reports[0]
    row = bigquery_mock.saved_rows[0]

    assert report.id_patron == "patron-abandono-checkout-504"
    assert report.id_sesion == "sesion_e2e_demo_001"
    assert report.id_cliente == client_id
    assert report.fecha_exploracion == fecha_exploracion
    assert report.status == ExplorationStatus.COMPLETED
    assert report.total_steps == 5
    assert report.completed_steps == 5
    assert len(report.evidences) == 5
    assert all(ev.screenshot_url != "" for ev in report.evidences)
    assert any(ev.scroll for ev in report.evidences)
    assert any(ev.es_paso_friccion for ev in report.evidences)
    assert any(ev.bounding_box_context is not None for ev in report.evidences)

    generated_webps = list(output_dir.rglob("*.webp"))
    assert len(generated_webps) == len(report.evidences)
    assert row["id_patron"] == "patron-abandono-checkout-504"
    assert row["id_sesion"] == "sesion_e2e_demo_001"
    assert len(row["evidences"]) == len(report.evidences)
