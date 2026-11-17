"""Pruebas unitarias para la configuración de logging estructurado JSON."""

import io
import json
import logging
from unittest.mock import patch
import pytest

from app.logging_config import (
    CloudLoggingStreamHandler,
    JsonCloudFormatter,
    configure_logging,
    fecha_ejecucion_ctx,
    id_cliente_ctx,
)


@pytest.mark.unit
def test_json_cloud_formatter_and_contextvars() -> None:
    """Verifica el payload JSON, inyección de contextvars, extra y traza_error."""
    token_fecha = fecha_ejecucion_ctx.set("2026-11-16")
    token_cliente = id_cliente_ctx.set("00000000-0000-0000-0000-000000000001")
    try:
        formatter = JsonCloudFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="main.py",
            lineno=10,
            msg="Proceso %s completado",
            args=("ok",),
            exc_info=None,
        )
        record.etapa = "GENERACION_DE_INSIGHTS"
        record._privado = "ignorar"

        parsed = json.loads(formatter.format(record))
        assert parsed["severity"] == "INFO"
        assert parsed["message"] == "Proceso ok completado"
        assert parsed["logger"] == "test_logger"
        assert parsed["fecha_ejecucion"] == "2026-11-16"
        assert parsed["id_cliente"] == "00000000-0000-0000-0000-000000000001"
        assert parsed["etapa"] == "GENERACION_DE_INSIGHTS"
        assert "_privado" not in parsed
        assert "traza_error" not in parsed
    finally:
        fecha_ejecucion_ctx.reset(token_fecha)
        id_cliente_ctx.reset(token_cliente)


@pytest.mark.unit
def test_json_cloud_formatter_with_exception_and_no_context() -> None:
    """Verifica inclusión de traza_error y ausencia de contextvars cuando no están seteadas."""
    token_fecha = fecha_ejecucion_ctx.set(None)
    token_cliente = id_cliente_ctx.set(None)
    try:
        formatter = JsonCloudFormatter()
        try:
            raise ValueError("Error de prueba")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="err_logger",
            level=logging.ERROR,
            pathname="main.py",
            lineno=20,
            msg="Fallo controlado",
            args=(),
            exc_info=exc_info,
        )
        parsed = json.loads(formatter.format(record))
        assert parsed["severity"] == "ERROR"
        assert "fecha_ejecucion" not in parsed
        assert "id_cliente" not in parsed
        assert "ValueError: Error de prueba" in parsed["traza_error"]
    finally:
        fecha_ejecucion_ctx.reset(token_fecha)
        id_cliente_ctx.reset(token_cliente)


@pytest.mark.unit
def test_cloud_logging_stream_handler_routing_and_configure() -> None:
    """Verifica enrutamiento stdout/stderr, flush y manejo de error en emit."""
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    with patch("sys.stdout", stdout_buf), patch("sys.stderr", stderr_buf):
        configure_logging(logging.INFO)
        logger = logging.getLogger("route_test")
        logger.info("Mensaje info")
        logger.warning("Mensaje warning")
        logger.error("Mensaje error")

    out_lines = [json.loads(line) for line in stdout_buf.getvalue().strip().splitlines()]
    err_lines = [json.loads(line) for line in stderr_buf.getvalue().strip().splitlines()]

    assert [item["severity"] for item in out_lines] == ["INFO", "WARNING"]
    assert [item["severity"] for item in err_lines] == ["ERROR"]

    # Verificar manejo de excepción interna dentro de emit()
    handler = CloudLoggingStreamHandler()
    record = logging.LogRecord("x", logging.INFO, "f.py", 1, "msg", (), None)
    with patch.object(handler, "format", side_effect=RuntimeError("boom")), \
         patch.object(handler, "handleError") as mock_handle_error:
        handler.emit(record)
        mock_handle_error.assert_called_once_with(record)
