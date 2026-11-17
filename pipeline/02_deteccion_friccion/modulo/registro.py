"""Logs del módulo, con el estándar del pipeline (reglas_de_orquestacion_modulo2.md, sección 5).

- Una línea JSON por log: severity, message, timestamp (UTC ISO 8601), logger, etapa ("DETECCION_DE_FRICCION",
  la etiqueta del módulo en el workflow), fecha_ejecucion e id_cliente (contextvars) y los campos de `extra`
  en el nivel raíz. Una excepción va en traza_error.
- DEBUG, INFO y WARNING a stdout; ERROR y CRITICAL a stderr; flush en cada línea. Sin archivos de log.
- El paso interno del módulo (ventana, entrenamiento, detección...) va en el campo `paso`: `etapa` ya es la del
  workflow.
- Local (fuera de Cloud Run) se puede pedir texto legible con LOG_FORMATO=texto.

Uso:
    log = registro.logger("ventana")
    with registro.paso(log, "Ventana y sesionización") as res:
        ...
        res["sesiones"] = 14500          # sale en el log de fin del paso
"""
import contextlib
import contextvars
import io
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

ETAPA = "DETECCION_DE_FRICCION"
id_cliente_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("id_cliente", default=None)
fecha_ejecucion_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("fecha_ejecucion", default=None)

_ESTANDAR = frozenset({
    "args", "asctime", "created", "exc_info", "exc_text", "filename", "funcName", "levelname", "levelno", "lineno",
    "module", "msecs", "message", "msg", "name", "pathname", "process", "processName", "relativeCreated",
    "stack_info", "taskName", "thread", "threadName",
})


def _extra(r: logging.LogRecord) -> dict:
    return {k: v for k, v in r.__dict__.items() if k not in _ESTANDAR and not k.startswith("_")}


class JsonCloudFormatter(logging.Formatter):
    def format(self, r: logging.LogRecord) -> str:
        d = {"severity": r.levelname, "message": r.getMessage(), "timestamp": datetime.now(timezone.utc).isoformat(),
             "logger": r.name, "etapa": ETAPA}
        if fecha_ejecucion_ctx.get() is not None:
            d["fecha_ejecucion"] = fecha_ejecucion_ctx.get()
        if id_cliente_ctx.get() is not None:
            d["id_cliente"] = id_cliente_ctx.get()
        d.update(_extra(r))
        if r.exc_info:
            d["traza_error"] = self.formatException(r.exc_info)
        return json.dumps(d, ensure_ascii=False, default=str)


class TextoFormatter(logging.Formatter):
    def format(self, r: logging.LogRecord) -> str:
        ex = _extra(r)
        linea = f"{datetime.now().strftime('%H:%M:%S')} {r.levelname:<7} [{r.name}] {r.getMessage()}"
        if ex:
            linea += "  " + " ".join(f"{k}={v}" for k, v in ex.items())
        return linea + (("\n" + self.formatException(r.exc_info)) if r.exc_info else "")


class CloudLoggingStreamHandler(logging.Handler):
    """ERROR/CRITICAL a stderr, el resto a stdout, con flush en cada línea. Escribe en las salidas reales del
    proceso (sys.__stdout__/__stderr__): paso() redirige sys.stdout para capturar los print() de preprocesamiento/,
    y los logs no tienen que quedar atrapados ahí."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            destino = sys.__stderr__ if record.levelno >= logging.ERROR else sys.__stdout__
            destino.write(self.format(record) + "\n")
            destino.flush()
        except Exception:
            self.handleError(record)


def configurar(nivel: str | None = None) -> None:
    raiz = logging.getLogger("friccion")
    if raiz.handlers:
        return
    h = CloudLoggingStreamHandler()
    texto = os.environ.get("LOG_FORMATO") == "texto" and not (os.environ.get("CLOUD_RUN_JOB") or os.environ.get("K_SERVICE"))
    h.setFormatter(TextoFormatter() if texto else JsonCloudFormatter())
    raiz.addHandler(h)
    raiz.setLevel(nivel or os.environ.get("LOG_NIVEL", "INFO"))
    raiz.propagate = False


def logger(nombre: str) -> logging.Logger:
    configurar()
    return logging.getLogger(f"friccion.{nombre}")


@contextlib.contextmanager
def paso(log: logging.Logger, nombre: str, **contexto):
    """Log al empezar y al terminar el paso (duración y lo que se cargue en el dict), o el error con su traza.
    Los print() de las funciones compartidas de preprocesamiento/ van a DEBUG: en INFO queda el resumen."""
    log.info(f"{nombre}: inicio", extra={"paso": nombre, **contexto})
    resultados: dict = {}
    salida = io.StringIO()
    t = time.time()
    try:
        with contextlib.redirect_stdout(salida):
            yield resultados
    except Exception:
        log.exception(f"{nombre}: error", extra={"paso": nombre, "duracion_s": round(time.time() - t, 1)})
        raise
    finally:
        for linea in salida.getvalue().splitlines():
            if linea.strip():
                log.debug(linea.strip(), extra={"paso": nombre})
    log.info(f"{nombre}: fin", extra={"paso": nombre, "duracion_s": round(time.time() - t, 1), **resultados})
