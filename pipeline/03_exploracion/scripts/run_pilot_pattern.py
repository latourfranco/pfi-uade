#!/usr/bin/env python3
"""Script piloto (Etapa 1) para ejecutar la exploración real de 1 patrón de fricción.

Consulta Supabase y BigQuery en modo lectura, ejecuta Playwright sobre un único patrón
(por defecto el de mayor `sesiones_perdidas`), guarda las evidencias localmente o en GCS,
y opcionalmente vuelca el reporte JSON para inspección antes de habilitar escritura en BigQuery.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import logging
from pathlib import Path
import sys
from typing import List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.agent.trace_executor import TraceExecutor  # noqa: E402
from app.browser.browser_manager import BrowserManager  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.logging_config import configure_logging, fecha_ejecucion_ctx, id_cliente_ctx  # noqa: E402
from app.models.exploration_report import ExplorationReport  # noqa: E402
from app.models.session_trace import SessionTrace  # noqa: E402
from app.services.bigquery_service import BigQueryService  # noqa: E402
from app.services.supabase_service import SupabaseService  # noqa: E402
from app.storage import get_storage_provider  # noqa: E402

logger = logging.getLogger("pilot_pattern")


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Procesa los argumentos CLI para la ejecución piloto de un patrón."""
    parser = argparse.ArgumentParser(
        prog="run_pilot_pattern",
        description="Ejecuta la exploración real de 1 patrón para validación visual y funcional.",
    )
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    parser.add_argument(
        "--client-id",
        "-c",
        default="00000000-0000-0000-0000-000000000001",
        help="ID del cliente a explorar.",
    )
    parser.add_argument(
        "--pattern-id",
        "-p",
        default=None,
        help="ID específico del patrón; si se omite, toma el primero (mayor sesiones_perdidas).",
    )
    parser.add_argument(
        "--batch-date",
        "-d",
        default=today_utc,
        help="Fecha de corte y de exploración (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--storage-provider",
        "-s",
        default="local",
        choices=["local", "gcs"],
        help="Destino de las capturas WebP (por defecto 'local').",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Abre Chromium con ventana visible (headless=False) para observar la navegación.",
    )
    parser.add_argument(
        "--save-bigquery",
        action="store_true",
        help="Si se indica, persiste el reporte resultante en BigQuery.",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Solo lista los patrones pendientes recuperados de BigQuery sin abrir el navegador.",
    )
    parser.add_argument(
        "--from-step",
        type=int,
        default=None,
        help="Orden inicial inclusivo del subconjunto de pasos a reproducir en piloto.",
    )
    parser.add_argument(
        "--to-step",
        type=int,
        default=None,
        help="Orden final inclusivo del subconjunto de pasos a reproducir en piloto.",
    )
    return parser.parse_args(args)


def _filter_events_by_step_range(
    trace: SessionTrace,
    from_step: Optional[int],
    to_step: Optional[int],
) -> SessionTrace:
    """Retorna una copia de `trace` acotada al rango de `orden` `[from_step, to_step]`."""
    if from_step is None and to_step is None:
        return trace
    filtered = [
        ev
        for ev in sorted(trace.events, key=lambda item: item.orden)
        if (from_step is None or ev.orden >= from_step)
        and (to_step is None or ev.orden <= to_step)
    ]
    return trace.model_copy(update={"events": filtered})


def _select_pattern(patterns: List[SessionTrace], pattern_id: Optional[str]) -> Optional[SessionTrace]:
    """Selecciona el patrón solicitado o el de mayor impacto si no se especificó."""
    if not patterns:
        return None
    if not pattern_id:
        return patterns[0]
    for pat in patterns:
        if pat.id_patron == pattern_id:
            return pat
    return None


def _print_report_summary(report: ExplorationReport) -> None:
    """Imprime un resumen legible de pasos, fricciones detectadas y evidencias."""
    print("\n" + "=" * 80)
    print(f"RESULTADO PILOTO: {report.status.value}")
    print(f"Cliente:   {report.id_cliente}")
    print(f"Patrón:    {report.id_patron}")
    print(f"Sesión:    {report.id_sesion}")
    print(f"Objetivo:  {report.objetivo} | Sesiones perdidas: {report.sesiones_perdidas}")
    print(f"Pasos:     {report.completed_steps}/{report.total_steps}")
    if report.error_message:
        print(f"Error:     {report.error_message}")
    print("-" * 80)
    for ev in report.evidences:
        bbox = (
            f"{ev.bounding_box_context.tag_name} ({ev.bounding_box_context.context_type})"
            if ev.bounding_box_context
            else "sin bbox"
        )
        print(
            f"  [{ev.orden}] {ev.nombre_evento:<18} | scroll={str(ev.scroll):<5} "
            f"| patron={str(ev.en_patron):<5} | friccion={str(ev.es_paso_friccion):<5}"
        )
        print(f"      ruta={ev.ruta} | items={ev.items}")
        print(f"      bbox={bbox} | img={ev.screenshot_url}")
        if ev.context_notes:
            print(f"      notas={' ; '.join(ev.context_notes)}")
    print("=" * 80 + "\n")


async def run_pilot(parsed: argparse.Namespace) -> int:
    """Ejecuta el flujo piloto completo para un único patrón real."""
    id_cliente_ctx.set(parsed.client_id)
    fecha_ejecucion_ctx.set(parsed.batch_date)

    settings = get_settings()
    sb = SupabaseService()
    bq = BigQueryService()

    if not sb.is_connected():
        logger.error("No hay conexión activa a Supabase. Revisá SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY.")
        return 1
    if not bq.is_connected():
        logger.error(
            "No hay conexión activa a BigQuery. "
            "Revisá GOOGLE_APPLICATION_CREDENTIALS y PLATFORM_GCP_PROJECT_ID."
        )
        return 1

    config = await sb.get_client_interface_config(parsed.client_id)
    if not config:
        logger.error(f"No se encontró configuración válida para cliente_id='{parsed.client_id}' en Supabase.")
        return 1

    patterns = await bq.get_friction_patterns_for_client(
        client_id=parsed.client_id,
        batch_date=parsed.batch_date,
        region=config.gcp_region or settings.DEFAULT_BIGQUERY_REGION,
    )
    if not patterns:
        logger.info("No se encontraron patrones pendientes en BigQuery para los parámetros dados.")
        return 0

    if parsed.list_only:
        print(f"\nPatrones pendientes ({len(patterns)}):")
        for idx, pat in enumerate(patterns, start=1):
            print(
                f"  {idx:2d}. id_patron={pat.id_patron} | objetivo={pat.objetivo} "
                f"| pasos={len(pat.events)} | sesiones_perdidas={pat.sesiones_perdidas}"
            )
        return 0

    if parsed.from_step is not None and parsed.to_step is not None and parsed.from_step > parsed.to_step:
        logger.error(f"Rango de pasos inválido: --from-step ({parsed.from_step}) > --to-step ({parsed.to_step}).")
        return 1
    if parsed.save_bigquery and (parsed.from_step is not None or parsed.to_step is not None):
        logger.error("No se permite --save-bigquery al ejecutar un subconjunto parcial (--from-step / --to-step).")
        return 1

    selected = _select_pattern(patterns, parsed.pattern_id)
    if not selected:
        logger.error(f"Patrón '{parsed.pattern_id}' no encontrado entre los {len(patterns)} pendientes.")
        return 1

    original_total = len(selected.events)
    selected = _filter_events_by_step_range(selected, parsed.from_step, parsed.to_step)
    if not selected.events:
        logger.error(
            f"Ningún paso de '{selected.id_patron}' cae dentro del rango "
            f"[{parsed.from_step or 1}..{parsed.to_step or original_total}]."
        )
        return 1

    selected.fecha_exploracion = parsed.batch_date
    range_note = (
        f" [subconjunto {parsed.from_step or 'inicio'}..{parsed.to_step or 'fin'} de {original_total}]"
        if (parsed.from_step is not None or parsed.to_step is not None)
        else ""
    )
    logger.info(
        f"Ejecutando piloto sobre id_patron='{selected.id_patron}' "
        f"(pasos={len(selected.events)}{range_note}, sesiones_perdidas={selected.sesiones_perdidas})"
    )

    storage = get_storage_provider(
        provider_type=parsed.storage_provider,
        region=config.gcp_region or settings.DEFAULT_BIGQUERY_REGION,
    )

    async def _save_evidence(data: bytes, filename: str, step: int) -> str:
        return await storage.save_evidence(data, filename)

    mgr = BrowserManager()
    if parsed.headed:
        mgr.settings.HEADLESS_MODE = False

    await mgr.start()
    try:
        executor = TraceExecutor(browser_manager=mgr, evidence_saver=_save_evidence)
        report = await executor.execute_trace(selected, config)
    finally:
        await mgr.close()

    _print_report_summary(report)

    report_dir = Path(settings.LOCAL_STORAGE_PATH) / report.id_cliente / report.fecha_exploracion
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{report.id_patron}_report.json"
    report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    logger.info(f"Reporte JSON guardado localmente en: {report_path}")

    if parsed.save_bigquery:
        ok = await bq.save_exploration_report(report=report, idempotent=True)
        logger.info(f"Persistencia en BigQuery: {'OK' if ok else 'ERROR'}")
        return 0 if ok else 1

    return 0


def main() -> None:
    """Punto de entrada CLI."""
    configure_logging()
    parsed = parse_args()
    sys.exit(asyncio.run(run_pilot(parsed)))


if __name__ == "__main__":
    main()
