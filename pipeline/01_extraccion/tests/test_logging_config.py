import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from google.api_core.exceptions import PermissionDenied

from app.config import Settings
from app.logging_config import (
    CloudLoggingStreamHandler,
    JsonCloudFormatter,
    configure_logging,
    fecha_ejecucion_ctx,
    id_cliente_ctx,
)
from app.models import ClientSourceIntegration
from app.services.extraction_pipeline import ExtractionPipeline


@pytest.mark.unit
def test_json_logging_routes_stdout_and_stderr_with_context(capsys):
    """Prueba que logs INFO/WARNING vayan a stdout y ERROR a stderr en JSON válido con contexto."""
    configure_logging(logging.INFO)
    test_logger = logging.getLogger("test_json_logger")

    token_fecha = fecha_ejecucion_ctx.set("2026-11-14")
    token_cliente = id_cliente_ctx.set("cliente_xyz")
    try:
        test_logger.info("Proceso iniciado")
        test_logger.error("Fallo puntual", extra={"tipo_error": "PERMANENT"})
    finally:
        id_cliente_ctx.reset(token_cliente)
        fecha_ejecucion_ctx.reset(token_fecha)

    captured = capsys.readouterr()
    stdout_lines = [line for line in captured.out.strip().splitlines() if line]
    stderr_lines = [line for line in captured.err.strip().splitlines() if line]

    assert len(stdout_lines) == 1
    assert len(stderr_lines) == 1

    info_payload = json.loads(stdout_lines[0])
    assert info_payload["severity"] == "INFO"
    assert info_payload["message"] == "Proceso iniciado"
    assert "timestamp" in info_payload
    assert info_payload["id_cliente"] == "cliente_xyz"
    assert info_payload["fecha_ejecucion"] == "2026-11-14"

    error_payload = json.loads(stderr_lines[0])
    assert error_payload["severity"] == "ERROR"
    assert error_payload["message"] == "Fallo puntual"
    assert error_payload["tipo_error"] == "PERMANENT"
    assert error_payload["id_cliente"] == "cliente_xyz"
    assert error_payload["fecha_ejecucion"] == "2026-11-14"


@pytest.mark.unit
def test_json_formatter_includes_exception_traceback(capsys):
    """Prueba que las excepciones registradas incluyan el campo traza_error en el JSON."""
    configure_logging(logging.INFO)
    test_logger = logging.getLogger("test_exc_logger")

    try:
        raise RuntimeError("Error simulado de prueba")
    except RuntimeError:
        test_logger.exception("Fallo capturado", extra={"fecha_ejecucion": "2026-11-14"})

    captured = capsys.readouterr()
    assert captured.out == ""
    payload = json.loads(captured.err.strip().splitlines()[0])
    assert payload["severity"] == "ERROR"
    assert payload["message"] == "Fallo capturado"
    assert payload["fecha_ejecucion"] == "2026-11-14"
    assert "RuntimeError: Error simulado de prueba" in payload["traza_error"]


@pytest.mark.unit
def test_cloud_logging_handler_handles_emit_error():
    """Prueba que CloudLoggingStreamHandler delegue a handleError si falla el formateo."""
    handler = CloudLoggingStreamHandler()
    handler.setFormatter(JsonCloudFormatter())
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "msg", (), None)

    with patch.object(handler, "format", side_effect=ValueError("Error de formato")), \
         patch.object(handler, "handleError") as mock_handle_error:
        handler.emit(record)
        mock_handle_error.assert_called_once_with(record)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pipeline_emits_structured_json_logs_with_client_and_date(
    capsys, mock_settings: Settings, sample_clients: list[ClientSourceIntegration]
):
    """Prueba que durante un batch del pipeline todos los logs por cliente incluyan id_cliente y fecha_ejecucion."""
    configure_logging(logging.INFO)

    mock_sb = MagicMock()
    mock_sb.get_active_clients = AsyncMock(return_value=[sample_clients[0]])

    mock_bq = MagicMock()
    mock_bq.ensure_target_schema = AsyncMock()
    mock_bq.get_client_last_event_date = AsyncMock(return_value=None)
    mock_bq.check_ga4_data_available = AsyncMock(return_value=True)
    mock_bq.execute_client_merge = AsyncMock(side_effect=PermissionDenied("Sin permisos en cliente"))

    pipeline = ExtractionPipeline(mock_settings, mock_bq, mock_sb)
    await pipeline.run_batch("2026-11-14")

    captured = capsys.readouterr()
    all_lines = captured.out.strip().splitlines() + captured.err.strip().splitlines()
    assert len(all_lines) > 0

    parsed = [json.loads(line) for line in all_lines]
    # Todos los logs deben tener severity, message, timestamp y fecha_ejecucion
    for entry in parsed:
        assert "severity" in entry
        assert "message" in entry
        assert "timestamp" in entry
        assert entry["fecha_ejecucion"] == "2026-11-14"

    # Al menos los logs de procesamiento/error del cliente deben incluir id_cliente
    client_logs = [entry for entry in parsed if entry.get("id_cliente") == "cliente_alpha"]
    assert len(client_logs) >= 2
    assert any(entry["severity"] == "ERROR" for entry in client_logs)
