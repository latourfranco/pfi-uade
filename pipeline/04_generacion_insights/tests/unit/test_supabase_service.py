"""Pruebas unitarias para el servicio de persistencia incremental en Supabase."""

from unittest.mock import MagicMock, patch
import pytest

from app.config import Settings
from app.models.exploration_models import ExplorationReport
from app.models.llm_schemas import UxDiagnosticsOutput
from app.services.supabase_service import (
    SupabaseService,
    SupabaseServiceError,
    resolve_milestone_label,
)


@pytest.mark.unit
def test_supabase_service_missing_credentials() -> None:
    """Verifica que intentar obtener el cliente sin credenciales lance SupabaseServiceError."""
    for url, key in [("", ""), ("https://x.supabase.co", ""), ("", "key")]:
        settings = Settings(_env_file=None, SUPABASE_URL=url, SUPABASE_SERVICE_ROLE_KEY=key)
        service = SupabaseService(settings=settings)
        with pytest.raises(SupabaseServiceError, match="deben estar configurados"):
            _ = service.client


@pytest.mark.unit
def test_supabase_service_client_initialization_and_caching(mock_settings: Settings) -> None:
    """Verifica inicialización y caché de Supabase Client."""
    with patch("app.services.supabase_service.create_client") as mock_create_client:
        mock_instance = MagicMock()
        mock_create_client.return_value = mock_instance
        service = SupabaseService(settings=mock_settings)

        c1 = service.client
        c2 = service.client
        assert c1 is mock_instance
        assert c2 is mock_instance
        mock_create_client.assert_called_once_with(
            mock_settings.SUPABASE_URL,
            mock_settings.SUPABASE_SERVICE_ROLE_KEY,
        )


@pytest.mark.unit
def test_get_existing_patterns_state_and_errors(mock_settings: Settings) -> None:
    """Verifica la consulta del estado previo de patrones y diagnósticos en Supabase."""
    mock_client = MagicMock()
    mock_fricciones = MagicMock()
    mock_diag = MagicMock()

    mock_client.table.side_effect = lambda name: mock_fricciones if name == "fricciones" else mock_diag

    res_fricc = MagicMock()
    res_fricc.data = [
        {
            "id": "pat-1",
            "hash_exploracion": "abc",
            "ultima_deteccion": "2026-11-15",
            "sesiones": 100,
            "usuarios": 90,
            "sesiones_perdidas": 25.5,
        },
        {
            "id": "pat-2",
            "hash_exploracion": "def",
            "ultima_deteccion": None,
            "sesiones": 50,
            "usuarios": 45,
            "sesiones_perdidas": None,
        },
        "invalid_row",
    ]
    mock_fricciones.select.return_value.eq.return_value.execute.return_value = res_fricc

    res_diag = MagicMock()
    res_diag.data = [
        {"id": "diag-1", "friccion_id": "pat-1"},
        {"id": "diag-orphan", "friccion_id": "pat-other"},
        "invalid_diag",
    ]
    mock_diag.select.return_value.in_.return_value.execute.return_value = res_diag

    service = SupabaseService(settings=mock_settings, client=mock_client)
    state = service.get_existing_patterns_state("cli-1")

    assert state["pat-1"]["has_diagnosis"] is True
    assert state["pat-1"]["diagnostico_id"] == "diag-1"
    assert state["pat-1"]["sesiones_perdidas"] == 25.5
    assert state["pat-2"]["has_diagnosis"] is False

    # Caso sin filas en fricciones (y data no lista)
    res_fricc.data = "not_a_list"
    assert service.get_existing_patterns_state("cli-empty") == {}

    # Caso error en Supabase
    mock_fricciones.select.return_value.eq.return_value.execute.side_effect = RuntimeError("DB down")
    with pytest.raises(SupabaseServiceError, match="Error consultando estado previo"):
        service.get_existing_patterns_state("cli-err")


@pytest.mark.unit
def test_has_quantitative_changes(sample_exploration_report: ExplorationReport) -> None:
    """Verifica la detección de cambios en métricas cuantitativas o ultima_deteccion."""
    base_state = {
        "ultima_deteccion": sample_exploration_report.ultima_deteccion,
        "sesiones": sample_exploration_report.sesiones,
        "usuarios": sample_exploration_report.usuarios,
        "sesiones_perdidas": sample_exploration_report.sesiones_perdidas,
    }
    assert SupabaseService.has_quantitative_changes(sample_exploration_report, base_state) is False
    assert SupabaseService.has_quantitative_changes(
        sample_exploration_report, {**base_state, "ultima_deteccion": "2021-02-02"}
    ) is True
    assert SupabaseService.has_quantitative_changes(
        sample_exploration_report, {**base_state, "sesiones": 999}
    ) is True
    assert SupabaseService.has_quantitative_changes(
        sample_exploration_report, {**base_state, "usuarios": 999}
    ) is True
    assert SupabaseService.has_quantitative_changes(
        sample_exploration_report, {**base_state, "sesiones_perdidas": None}
    ) is True
    assert SupabaseService.has_quantitative_changes(
        sample_exploration_report, {**base_state, "sesiones_perdidas": 500.0}
    ) is True
    rep_none_lost = sample_exploration_report.model_copy(update={"sesiones_perdidas": None})
    assert SupabaseService.has_quantitative_changes(rep_none_lost, {**base_state, "sesiones_perdidas": None}) is False


@pytest.mark.unit
def test_update_pattern_metrics_only(
    mock_settings: Settings,
    sample_exploration_report: ExplorationReport,
) -> None:
    """Verifica actualización parcial de métricas y manejo de errores en Supabase."""
    mock_client = MagicMock()
    mock_fricciones = MagicMock()
    mock_client.table.return_value = mock_fricciones

    service = SupabaseService(settings=mock_settings, client=mock_client)
    service.update_pattern_metrics_only(sample_exploration_report)

    mock_fricciones.update.assert_called_once()
    updated_payload = mock_fricciones.update.call_args[0][0]
    assert "id" not in updated_payload
    assert "client_id" not in updated_payload
    assert updated_payload["sesiones"] == sample_exploration_report.sesiones
    assert len(updated_payload["distribucion_dispositivos"]) == 2

    mock_fricciones.update.return_value.eq.return_value.execute.side_effect = RuntimeError("Update error")
    with pytest.raises(SupabaseServiceError, match="Error actualizando métricas"):
        service.update_pattern_metrics_only(sample_exploration_report)


@pytest.mark.unit
def test_save_diagnostics_full_upsert_without_cascade(
    mock_settings: Settings,
    sample_exploration_report: ExplorationReport,
    sample_ux_diagnostics: UxDiagnosticsOutput,
) -> None:
    """Verifica el upsert completo en las 4 tablas y limpieza ordenada sin CASCADE."""
    mock_client = MagicMock()
    call_order: list[str] = []
    tables = {
        "fricciones": MagicMock(),
        "fricciones_diagnosticos": MagicMock(),
        "friccion_recorrido_pasos": MagicMock(),
        "friccion_recorrido_notas": MagicMock(),
    }

    def table_router(name: str) -> MagicMock:
        call_order.append(name)
        return tables[name]

    mock_client.table.side_effect = table_router

    tables["fricciones_diagnosticos"].upsert.return_value.execute.return_value.data = [{"id": "diag-uuid-1"}]
    tables["friccion_recorrido_pasos"].upsert.return_value.execute.return_value.data = [
        {"id": "paso-uuid-1", "numero_paso": 1},
        {"id": "paso-uuid-2", "numero_paso": 2},
    ]
    tables["friccion_recorrido_notas"].upsert.return_value.execute.return_value.data = [
        {"id": "nota-1"},
        {"id": "nota-2"},
    ]

    service = SupabaseService(settings=mock_settings, client=mock_client)
    result = service.save_diagnostics(
        report=sample_exploration_report,
        diagnostico=sample_ux_diagnostics,
        prompt_tokens=300,
        completion_tokens=700,
    )

    assert result["diagnostico_id"] == "diag-uuid-1"
    assert result["notas_count"] == 2

    # Verificar orden: fricciones -> diagnosticos -> delete notas -> delete pasos -> upsert pasos -> upsert notas
    assert call_order == [
        "fricciones",
        "fricciones_diagnosticos",
        "friccion_recorrido_notas",
        "friccion_recorrido_pasos",
        "friccion_recorrido_pasos",
        "friccion_recorrido_notas",
    ]
    tables["fricciones"].upsert.assert_called_once()
    assert tables["fricciones"].upsert.call_args[1]["on_conflict"] == "id"
    assert tables["fricciones_diagnosticos"].upsert.call_args[1]["on_conflict"] == "friccion_id"
    assert tables["friccion_recorrido_pasos"].upsert.call_args[1]["on_conflict"] == "friccion_id,numero_paso"
    assert tables["friccion_recorrido_notas"].upsert.call_args[1]["on_conflict"] == "friccion_id,numero_paso"


@pytest.mark.unit
def test_save_diagnostics_step_fallback_and_edge_cases(
    mock_settings: Settings,
    sample_exploration_report: ExplorationReport,
    sample_ux_diagnostics: UxDiagnosticsOutput,
) -> None:
    """Verifica respaldo _fetch_step_id_mapping, reporte vacío y captura de errores en save_diagnostics."""
    mock_client = MagicMock()
    tables = {
        "fricciones": MagicMock(),
        "fricciones_diagnosticos": MagicMock(),
        "friccion_recorrido_pasos": MagicMock(),
        "friccion_recorrido_notas": MagicMock(),
    }
    mock_client.table.side_effect = lambda name: tables[name]

    # Subcaso 1: upsert de pasos no devuelve filas -> usa _fetch_step_id_mapping; diag sin id; notas.data None
    tables["fricciones_diagnosticos"].upsert.return_value.execute.return_value.data = ["invalid"]
    tables["friccion_recorrido_pasos"].upsert.return_value.execute.return_value.data = []
    tables["friccion_recorrido_pasos"].select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "fallback-p1", "numero_paso": 1}
    ]
    tables["friccion_recorrido_notas"].upsert.return_value.execute.return_value.data = None

    service = SupabaseService(settings=mock_settings, client=mock_client)
    res = service.save_diagnostics(sample_exploration_report, sample_ux_diagnostics)
    assert res["diagnostico_id"] is None
    assert res["notas_count"] == 0
    notas_rows = tables["friccion_recorrido_notas"].upsert.call_args[0][0]
    assert notas_rows[0]["paso_id"] == "fallback-p1"
    assert "paso_id" not in notas_rows[1]

    # Subcaso 2: _fetch_step_id_mapping falla y report sin evidencias ni notas
    tables["friccion_recorrido_pasos"].select.return_value.eq.return_value.execute.side_effect = RuntimeError("fail")
    assert service._fetch_step_id_mapping("x") == {}
    tables["friccion_recorrido_pasos"].select.return_value.eq.return_value.execute.side_effect = None
    tables["friccion_recorrido_pasos"].select.return_value.eq.return_value.execute.return_value.data = "not_list"
    assert service._fetch_step_id_mapping("x") == {}
    tables["friccion_recorrido_pasos"].select.return_value.eq.return_value.execute.return_value.data = [
        "bad",
        {"id": None, "numero_paso": 1},
        {"id": "p1", "numero_paso": None},
    ]
    assert service._fetch_step_id_mapping("x") == {}

    empty_rep = sample_exploration_report.model_copy(
        update={"evidences": [], "device_info": None, "llegada_grupo": None}
    )
    empty_diag = sample_ux_diagnostics.model_copy(update={"journey_step_notes": []})
    res_empty = service.save_diagnostics(empty_rep, empty_diag)
    assert res_empty["notas_count"] == 0

    # Subcaso 3: fallo de BD encapsulado en SupabaseServiceError
    mock_client.table.side_effect = RuntimeError("DB failure")
    with pytest.raises(SupabaseServiceError, match="Error persistiendo datos en Supabase"):
        service.save_diagnostics(sample_exploration_report, sample_ux_diagnostics)


@pytest.mark.unit
def test_resolve_milestone_label_and_payload_labels(
    mock_settings: Settings,
    sample_exploration_report: ExplorationReport,
) -> None:
    """Verifica el mapeo de nombres amigables desde modelos.nombres_hitos en BigQuery."""
    milestone_labels = sample_exploration_report.get_milestone_labels_map()
    assert resolve_milestone_label("begin_checkout", milestone_labels) == "Iniciar pago"
    assert resolve_milestone_label("add_to_cart", milestone_labels) == "Agregar al carrito"
    assert resolve_milestone_label("begin_checkout /checkout", milestone_labels) == "Iniciar pago"
    assert resolve_milestone_label("custom_step_event", milestone_labels) is None
    assert resolve_milestone_label("   ", milestone_labels) is None
    assert resolve_milestone_label(None, milestone_labels) is None

    payload = SupabaseService._build_fricciones_payload(
        report=sample_exploration_report,
        nombre="Test",
        exploration_hash="hash-1",
    )
    assert payload["evento_clave"] == sample_exploration_report.objetivo
    assert payload["evento_clave_nombre"] == "Iniciar pago"
    assert payload["secuencia_nombres"] == sample_exploration_report.secuencia

    empty_labels_report = sample_exploration_report.model_copy(update={"nombres_hitos_modelo": []})
    empty_payload = SupabaseService._build_fricciones_payload(
        report=empty_labels_report,
        nombre="Test",
        exploration_hash="hash-2",
    )
    assert empty_payload["evento_clave_nombre"] is None

    partial_labels_report = sample_exploration_report.model_copy(
        update={
            "eventos_clave_modelo": ["select_item", ""],
            "nombres_hitos_modelo": ["Seleccionar producto", "   "],
        }
    )
    assert partial_labels_report.get_milestone_labels_map() == {"select_item": "Seleccionar producto"}
