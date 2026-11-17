"""Punto de entrada oficial para la ejecución como tarea en Google Cloud Run Jobs."""

import asyncio
import json
import logging
import os
import sys
from app.job_runner import run_client_job
from app.logging_config import configure_logging, fecha_ejecucion_ctx, id_cliente_ctx

logger = logging.getLogger(__name__)


def ejecutar_tarea() -> None:
    """Lee variables de entorno de Cloud Workflows y ejecuta la exploración del cliente asignado."""
    configure_logging()

    try:
        indice_tarea = int(os.environ.get("CLOUD_RUN_TASK_INDEX", "0"))
        intento = int(os.environ.get("CLOUD_RUN_TASK_ATTEMPT", "0"))
        fecha_ejecucion = os.environ["FECHA_EJECUCION"].strip()
        ids_clientes = json.loads(os.environ["IDS_CLIENTES"])
        if not fecha_ejecucion or not isinstance(ids_clientes, list):
            raise ValueError("FECHA_EJECUCION debe ser no vacía e IDS_CLIENTES una lista JSON.")
    except Exception as exc:
        logger.critical(
            f"Error al leer variables de entorno de orquestación: {exc}",
            extra={"etapa": "EXPLORACION"},
        )
        sys.exit(1)

    fecha_ejecucion_ctx.set(fecha_ejecucion)

    if indice_tarea < 0 or indice_tarea >= len(ids_clientes):
        logger.warning(
            "Índice de tarea fuera de rango. Finalizando sin acción.",
            extra={
                "indice_tarea": indice_tarea,
                "total_clientes": len(ids_clientes),
                "etapa": "EXPLORACION",
                "intento": intento,
            },
        )
        sys.exit(0)

    id_cliente = str(ids_clientes[indice_tarea])
    id_cliente_ctx.set(id_cliente)

    try:
        exit_code = asyncio.run(
            run_client_job(
                client_id=id_cliente,
                batch_date=fecha_ejecucion,
                task_attempt=intento,
            )
        )
    except Exception:
        logger.exception(
            "Excepción crítica no controlada durante la ejecución de la tarea.",
            extra={"etapa": "EXPLORACION", "intento": intento},
        )
        sys.exit(1)

    sys.exit(exit_code)


if __name__ == "__main__":  # pragma: no cover
    ejecutar_tarea()
