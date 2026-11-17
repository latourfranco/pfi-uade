#!/usr/bin/env python3
"""Script para sembrar patrones de prueba en BigQuery (`friccion_resultados.patrones` y `sesion_representativa`).

Toma los patrones definidos en scripts/benchmark_friction_patterns.py y los inserta
asociados al id_cliente indicado en el dataset centralizado `friccion_resultados`.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List

from google.cloud import bigquery

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings  # noqa: E402
from scripts.benchmark_friction_patterns import (  # noqa: E402
    get_pattern_5_steps,
    get_pattern_10_steps,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_bigquery")


def seed_patterns(
    client_id: str = "00000000-0000-0000-0000-000000000001",
    target_date: str | None = None,
) -> bool:
    """Inserta patrones y sus sesiones representativas en `friccion_resultados`."""
    settings = get_settings()
    client = bigquery.Client(project=settings.PLATFORM_GCP_PROJECT_ID)

    dataset_id = settings.BIGQUERY_DATASET
    patrones_ref = f"{settings.PLATFORM_GCP_PROJECT_ID}.{dataset_id}.{settings.BIGQUERY_PATTERNS_TABLE_NAME}"
    sesiones_ref = f"{settings.PLATFORM_GCP_PROJECT_ID}.{dataset_id}.{settings.BIGQUERY_SESSIONS_TABLE_NAME}"

    fecha_str = target_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    logger.info(f"Target BigQuery Tables: {patrones_ref} / {sesiones_ref}")

    raw_patterns = [
        get_pattern_5_steps(iteration=1),
        get_pattern_10_steps(iteration=1),
    ]

    pattern_rows: List[Dict[str, Any]] = []
    session_rows: List[Dict[str, Any]] = []

    for pat in raw_patterns:
        pattern_id = f"{client_id}_{pat.id_patron}"
        session_id = f"{pattern_id}_{fecha_str}"

        pattern_rows.append(
            {
                "id_patron": pattern_id,
                "id_cliente": client_id,
                "objetivo": pat.objetivo or "purchase",
                "secuencia": pat.secuencia,
                "sesiones": pat.sesiones or 50,
                "usuarios": pat.usuarios or 40,
                "llegada_grupo": pat.llegada_grupo or 0.1,
                "llegada_referencia": pat.llegada_referencia or 0.4,
                "sesiones_perdidas": pat.sesiones_perdidas or 15.0,
                "id_modelo": pat.id_modelo or "seed_benchmark_v1",
                "primera_deteccion": fecha_str,
                "ultima_deteccion": fecha_str,
            }
        )

        for ev in pat.events:
            session_rows.append(
                {
                    "id_patron": pattern_id,
                    "id_sesion": session_id,
                    "orden": ev.orden,
                    "nombre_evento": ev.nombre_evento,
                    "ruta": ev.ruta,
                    "items": ev.items,
                    "scroll": ev.scroll,
                    "en_patron": ev.en_patron,
                    "es_paso_friccion": ev.es_paso_friccion,
                    "tipo_dispositivo": pat.device_info.tipo_dispositivo,
                    "navegador": pat.device_info.navegador,
                    "sistema_operativo": pat.device_info.sistema_operativo,
                }
            )

    errors_p = client.insert_rows_json(patrones_ref, pattern_rows)
    if errors_p:
        logger.error(f"Error al insertar patrones en BigQuery: {errors_p}")
        return False

    errors_s = client.insert_rows_json(sesiones_ref, session_rows)
    if errors_s:
        logger.error(f"Error al insertar sesiones representativas en BigQuery: {errors_s}")
        return False

    logger.info(
        f"Se insertaron {len(pattern_rows)} patrones y {len(session_rows)} pasos en '{dataset_id}' "
        f"para id_cliente='{client_id}', fecha='{fecha_str}'."
    )
    return True


if __name__ == "__main__":
    cid = sys.argv[1] if len(sys.argv) > 1 else "00000000-0000-0000-0000-000000000001"
    ok = seed_patterns(client_id=cid)
    sys.exit(0 if ok else 1)
