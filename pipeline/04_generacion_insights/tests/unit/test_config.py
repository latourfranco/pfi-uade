"""Pruebas unitarias para la configuración y carga de ajustes en app.config."""

import pytest

from app.config import Settings, get_settings


@pytest.mark.unit
def test_settings_default_values() -> None:
    """Verifica que los valores por defecto de Settings se inicialicen correctamente."""
    settings = Settings(_env_file=None)
    assert settings.ENVIRONMENT == "production"
    assert settings.PLATFORM_GCP_PROJECT_ID == "pruebas-pfi"
    assert settings.BIGQUERY_DATASET_ID == "friccion_resultados"
    assert settings.BIGQUERY_EXPLORATION_TABLE_NAME == "patrones_friccion_explorados"
    assert settings.BIGQUERY_MODELS_TABLE_NAME == "modelos"
    assert settings.BIGQUERY_EVENTS_DATASET_ID == "dw_analytics_us"
    assert settings.BIGQUERY_EVENTS_TABLE_NAME == "eventos_usuario"
    assert settings.GCS_BUCKET_CAPTURES == "pruebas-pfi-evidencias"
    assert settings.LLM_POD_NOMBRE == "friccion-llm"
    assert settings.LLM_INFERENCE_URL is None
    assert settings.LLM_MODEL_NAME == "cyankiwi/Qwen3.5-27B-AWQ-4bit"
    assert settings.LLM_TIMEOUT_SECONDS == 360.0
    assert settings.LLM_MAX_RETRIES == 3
    assert settings.LLM_READY_MAX_WAIT_SECONDS == 900.0
    assert settings.LLM_READY_POLL_INTERVAL_SECONDS == 15.0
    assert settings.LLM_MAX_TOKENS == 8000
    assert settings.LLM_TEMPERATURE == 0.2
    assert settings.LLM_ENABLE_THINKING is True
    assert settings.LLM_USER_AGENT == "eureka-insights/1.0"


@pytest.mark.unit
def test_settings_custom_values() -> None:
    """Verifica que Settings acepte valores personalizados de forma estricta."""
    custom = Settings(
        _env_file=None,
        ENVIRONMENT="staging",
        SUPABASE_URL="https://custom.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY="custom-key",
        RUNPOD_API_KEY="rpa_test_key",
        VLLM_API_KEY="vllm_test_key",
        LLM_POD_NOMBRE="custom-pod",
        LLM_INFERENCE_URL="https://pod123-8000.proxy.runpod.net",
        LLM_TIMEOUT_SECONDS=120.0,
        LLM_MAX_RETRIES=5,
        LLM_MAX_TOKENS=4096,
        LLM_TEMPERATURE=0.1,
        LLM_ENABLE_THINKING=False,
        LLM_USER_AGENT="custom-agent/2.0",
    )
    assert custom.ENVIRONMENT == "staging"
    assert custom.SUPABASE_URL == "https://custom.supabase.co"
    assert custom.SUPABASE_SERVICE_ROLE_KEY == "custom-key"
    assert custom.RUNPOD_API_KEY == "rpa_test_key"
    assert custom.VLLM_API_KEY == "vllm_test_key"
    assert custom.LLM_POD_NOMBRE == "custom-pod"
    assert custom.LLM_INFERENCE_URL == "https://pod123-8000.proxy.runpod.net"
    assert custom.LLM_TIMEOUT_SECONDS == 120.0
    assert custom.LLM_MAX_RETRIES == 5
    assert custom.LLM_MAX_TOKENS == 4096
    assert custom.LLM_TEMPERATURE == 0.1
    assert custom.LLM_ENABLE_THINKING is False
    assert custom.LLM_USER_AGENT == "custom-agent/2.0"


@pytest.mark.unit
def test_get_settings_cached() -> None:
    """Verifica que get_settings retorne la misma instancia (lru_cache)."""
    get_settings.cache_clear()
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
