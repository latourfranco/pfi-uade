"""Pruebas unitarias para la configuración de logging JSON estructurado (app/logging_config.py)."""

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


@pytest.fixture(autouse=True)
def reset_logging_and_context():
    """Restaura handlers del logger raíz y variables de contexto tras cada prueba."""
    root = logging.getLogger()
    orig_handlers = list(root.handlers)
    orig_level = root.level
    token_cli = id_cliente_ctx.set(None)
    token_fecha = fecha_ejecucion_ctx.set(None)
    try:
        yield
    finally:
        root.handlers = orig_handlers
        root.setLevel(orig_level)
        id_cliente_ctx.reset(token_cli)
        fecha_ejecucion_ctx.reset(token_fecha)


@pytest.mark.unit
def test_routing_stdout_vs_stderr_and_base_fields(capsys):
    """Verifica que DEBUG/INFO/WARNING vayan a stdout y ERROR/CRITICAL a stderr en JSON de una línea."""
    configure_logging(level=logging.DEBUG)
    test_logger = logging.getLogger("test_routing")

    test_logger.debug("evento debug")
    test_logger.info("evento info")
    test_logger.warning("evento warning")
    test_logger.error("evento error")
    test_logger.critical("evento critical")

    captured = capsys.readouterr()
    stdout_lines = [line for line in captured.out.splitlines() if line.strip()]
    stderr_lines = [line for line in captured.err.splitlines() if line.strip()]

    assert len(stdout_lines) == 3
    assert len(stderr_lines) == 2

    severities_out = [json.loads(line)["severity"] for line in stdout_lines]
    severities_err = [json.loads(line)["severity"] for line in stderr_lines]
    assert severities_out == ["DEBUG", "INFO", "WARNING"]
    assert severities_err == ["ERROR", "CRITICAL"]

    first_payload = json.loads(stdout_lines[0])
    assert first_payload["message"] == "evento debug"
    assert first_payload["logger"] == "test_routing"
    assert "timestamp" in first_payload
    assert "fecha_ejecucion" not in first_payload
    assert "id_cliente" not in first_payload


@pytest.mark.unit
def test_contextvars_and_extra_attributes_injection(capsys):
    """Verifica la inyección de contextvars (id_cliente, fecha_ejecucion) y atributos extra."""
    configure_logging(level=logging.INFO)
    fecha_ejecucion_ctx.set("2026-11-15")
    id_cliente_ctx.set("00000000-0000-0000-0000-000000000001")

    test_logger = logging.getLogger("exploration_service")
    test_logger.info(
        "Exploración finalizada",
        extra={
            "patrones_explorados": 4,
            "capturas_generadas": 15,
            "_campo_interno": "debe_ignorarse",
        },
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out.strip())

    assert payload["severity"] == "INFO"
    assert payload["message"] == "Exploración finalizada"
    assert payload["logger"] == "exploration_service"
    assert payload["fecha_ejecucion"] == "2026-11-15"
    assert payload["id_cliente"] == "00000000-0000-0000-0000-000000000001"
    assert payload["patrones_explorados"] == 4
    assert payload["capturas_generadas"] == 15
    assert "_campo_interno" not in payload


@pytest.mark.unit
def test_exception_formatting_includes_traza_error(capsys):
    """Verifica que las excepciones registren el stack trace bajo la clave 'traza_error' en stderr."""
    configure_logging(level=logging.INFO)
    test_logger = logging.getLogger("exploracion_main")

    try:
        raise ValueError("Error simulado en BigQuery")
    except ValueError:
        test_logger.exception("Fallo crítico", extra={"etapa": "EXPLORACION", "intento": 1})

    captured = capsys.readouterr()
    assert captured.out == ""
    payload = json.loads(captured.err.strip())

    assert payload["severity"] == "ERROR"
    assert payload["message"] == "Fallo crítico"
    assert payload["etapa"] == "EXPLORACION"
    assert payload["intento"] == 1
    assert "traza_error" in payload
    assert "ValueError: Error simulado en BigQuery" in payload["traza_error"]


@pytest.mark.unit
def test_stream_handler_handles_formatting_exception():
    """Verifica que si format() falla dentro de emit(), se invoque handleError sin propagar excepción."""
    handler = CloudLoggingStreamHandler()
    handler.setFormatter(JsonCloudFormatter())
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="mensaje",
        args=(),
        exc_info=None,
    )

    with patch.object(handler, "format", side_effect=RuntimeError("format failure")), \
         patch.object(handler, "handleError") as mock_handle_error:
        handler.emit(record)
        mock_handle_error.assert_called_once_with(record)
