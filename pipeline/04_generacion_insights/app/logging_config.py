"""Configuración de logging estructurado JSON compatible con Google Cloud Logging."""

import contextvars
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

id_cliente_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("id_cliente", default=None)
fecha_ejecucion_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("fecha_ejecucion", default=None)

_STANDARD_RECORD_ATTRS = frozenset({
    "args", "asctime", "created", "exc_info", "exc_text", "filename",
    "funcName", "levelname", "levelno", "lineno", "module", "msecs",
    "message", "msg", "name", "pathname", "process", "processName",
    "relativeCreated", "stack_info", "taskName", "thread", "threadName",
})


class JsonCloudFormatter(logging.Formatter):
    """Formateador JSON estructurado en una línea compatible con Google Cloud Logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Serializa el registro de log como payload JSON en una línea."""
        payload: Dict[str, Any] = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "logger": record.name,
        }

        fecha_ctx = fecha_ejecucion_ctx.get()
        if fecha_ctx is not None:
            payload["fecha_ejecucion"] = fecha_ctx

        cliente_ctx = id_cliente_ctx.get()
        if cliente_ctx is not None:
            payload["id_cliente"] = cliente_ctx

        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_ATTRS and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            payload["traza_error"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


class CloudLoggingStreamHandler(logging.Handler):
    """Enruta logs ERROR/CRITICAL a stderr y el resto a stdout en formato JSON."""

    def emit(self, record: logging.LogRecord) -> None:
        """Escribe el evento formateado en stdout o stderr con flush inmediato."""
        try:
            mensaje_json = self.format(record)
            destino = sys.stderr if record.levelno >= logging.ERROR else sys.stdout
            destino.write(mensaje_json + "\n")
            destino.flush()
        except Exception:
            self.handleError(record)


def configure_logging(level: int = logging.INFO) -> None:
    """Configura el logger raíz para emitir logs JSON estructurados hacia Cloud Logging."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()

    handler = CloudLoggingStreamHandler()
    handler.setLevel(level)
    handler.setFormatter(JsonCloudFormatter())
    root_logger.addHandler(handler)
