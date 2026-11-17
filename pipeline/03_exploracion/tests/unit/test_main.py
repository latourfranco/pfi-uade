"""Pruebas unitarias para el punto de entrada oficial de Cloud Run Jobs (app/main.py)."""

import json
import logging
import os
from unittest.mock import AsyncMock, patch
import pytest
from app.logging_config import fecha_ejecucion_ctx, id_cliente_ctx
from app.main import ejecutar_tarea


@pytest.fixture(autouse=True)
def reset_contextvars():
    """Restaura las contextvars de correlación antes y después de cada test."""
    token_cli = id_cliente_ctx.set(None)
    token_fecha = fecha_ejecucion_ctx.set(None)
    try:
        yield
    finally:
        id_cliente_ctx.reset(token_cli)
        fecha_ejecucion_ctx.reset(token_fecha)


@pytest.mark.unit
def test_ejecutar_tarea_success():
    """Verifica selección del cliente por índice, inyección de contextvars y exit(0)."""
    env = {
        "IDS_CLIENTES": json.dumps(["cli_1", "cli_2"]),
        "CLOUD_RUN_TASK_INDEX": "1",
        "FECHA_EJECUCION": "2026-11-15",
        "CLOUD_RUN_TASK_ATTEMPT": "2",
    }

    with patch.dict(os.environ, env, clear=True), \
         patch("app.main.configure_logging") as mock_cfg_log, \
         patch("app.main.run_client_job", new_callable=AsyncMock, return_value=0) as mock_run:
        with pytest.raises(SystemExit) as exc_info:
            ejecutar_tarea()

        assert exc_info.value.code == 0
        mock_cfg_log.assert_called_once()
        mock_run.assert_awaited_once_with(
            client_id="cli_2",
            batch_date="2026-11-15",
            task_attempt=2,
        )
        assert id_cliente_ctx.get() == "cli_2"
        assert fecha_ejecucion_ctx.get() == "2026-11-15"


@pytest.mark.unit
@pytest.mark.parametrize("task_index", ["5", "-1"])
def test_ejecutar_tarea_index_out_of_range(task_index, caplog):
    """Verifica que un índice fuera de rango emita WARNING y salga con código 0 sin ejecutar job."""
    env = {
        "IDS_CLIENTES": json.dumps(["cli_1", "cli_2"]),
        "CLOUD_RUN_TASK_INDEX": task_index,
        "FECHA_EJECUCION": "2026-11-15",
        "CLOUD_RUN_TASK_ATTEMPT": "1",
    }

    with patch.dict(os.environ, env, clear=True), \
         patch("app.main.configure_logging"), \
         patch("app.main.run_client_job", new_callable=AsyncMock) as mock_run:
        with caplog.at_level(logging.WARNING, logger="app.main"):
            with pytest.raises(SystemExit) as exc_info:
                ejecutar_tarea()

        assert exc_info.value.code == 0
        mock_run.assert_not_awaited()
        assert any(r.levelno == logging.WARNING for r in caplog.records)


@pytest.mark.unit
@pytest.mark.parametrize(
    "env",
    [
        {"IDS_CLIENTES": '["cli_1"]'},
        {"FECHA_EJECUCION": "   ", "IDS_CLIENTES": '["cli_1"]'},
        {"FECHA_EJECUCION": "2026-11-15"},
        {"FECHA_EJECUCION": "2026-11-15", "IDS_CLIENTES": "{json-invalido"},
        {"FECHA_EJECUCION": "2026-11-15", "IDS_CLIENTES": '{"cliente": "no_es_lista"}'},
    ],
)
def test_ejecutar_tarea_missing_or_invalid_env_vars(env, caplog):
    """Verifica que variables ausentes o inválidas registren CRITICAL y salgan con código 1."""
    with patch.dict(os.environ, env, clear=True), \
         patch("app.main.configure_logging"):
        with caplog.at_level(logging.CRITICAL, logger="app.main"):
            with pytest.raises(SystemExit) as exc_info:
                ejecutar_tarea()

        assert exc_info.value.code == 1
        assert any(r.levelno == logging.CRITICAL for r in caplog.records)


@pytest.mark.unit
def test_ejecutar_tarea_job_returns_nonzero():
    """Verifica que si run_client_job retorna 1, el proceso salga con código 1."""
    env = {
        "IDS_CLIENTES": '["cli_1"]',
        "CLOUD_RUN_TASK_INDEX": "0",
        "FECHA_EJECUCION": "2026-11-15",
    }

    with patch.dict(os.environ, env, clear=True), \
         patch("app.main.configure_logging"), \
         patch("app.main.run_client_job", new_callable=AsyncMock, return_value=1):
        with pytest.raises(SystemExit) as exc_info:
            ejecutar_tarea()

        assert exc_info.value.code == 1


@pytest.mark.unit
def test_ejecutar_tarea_unhandled_exception_exits_1(caplog):
    """Verifica que una excepción no controlada en run_client_job registre ERROR y salga con código 1."""
    env = {
        "IDS_CLIENTES": '["cli_1"]',
        "CLOUD_RUN_TASK_INDEX": "0",
        "FECHA_EJECUCION": "2026-11-15",
    }

    with patch.dict(os.environ, env, clear=True), \
         patch("app.main.configure_logging"), \
         patch("app.main.run_client_job", new_callable=AsyncMock, side_effect=RuntimeError("Fallo crítico")):
        with caplog.at_level(logging.ERROR, logger="app.main"):
            with pytest.raises(SystemExit) as exc_info:
                ejecutar_tarea()

        assert exc_info.value.code == 1
        assert any(r.levelno == logging.ERROR for r in caplog.records)
