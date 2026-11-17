"""Configuración centralizada del módulo de generación de insights mediante Pydantic Settings."""

from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Ajustes de entorno y configuración para la generación de diagnósticos UX."""

    ENVIRONMENT: str = "production"

    # Supabase Transaccional
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # GCP / BigQuery & Cloud Storage (Único dataset de resultados y único bucket en US)
    PLATFORM_GCP_PROJECT_ID: str = "pruebas-pfi"
    BIGQUERY_DATASET_ID: str = "friccion_resultados"
    BIGQUERY_EXPLORATION_TABLE_NAME: str = "patrones_friccion_explorados"
    BIGQUERY_MODELS_TABLE_NAME: str = "modelos"
    BIGQUERY_EVENTS_DATASET_ID: str = "dw_analytics_us"
    BIGQUERY_EVENTS_TABLE_NAME: str = "eventos_usuario"
    GCS_BUCKET_CAPTURES: str = "pruebas-pfi-evidencias"
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None

    # Servicio de Inferencia en RunPod Pod (vLLM - Qwen3.5 con razonamiento)
    RUNPOD_API_KEY: Optional[str] = None
    VLLM_API_KEY: Optional[str] = None
    LLM_POD_NOMBRE: str = "friccion-llm"
    LLM_INFERENCE_URL: Optional[str] = None
    LLM_MODEL_NAME: str = "cyankiwi/Qwen3.5-27B-AWQ-4bit"
    LLM_TIMEOUT_SECONDS: float = 360.0
    LLM_MAX_RETRIES: int = 3
    LLM_READY_MAX_WAIT_SECONDS: float = 900.0
    LLM_READY_POLL_INTERVAL_SECONDS: float = 15.0
    LLM_MAX_TOKENS: int = 8000
    LLM_TEMPERATURE: float = 0.2
    LLM_ENABLE_THINKING: bool = True
    LLM_USER_AGENT: str = "eureka-insights/1.0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Retorna una instancia singleton cacheada de Settings."""
    return Settings()
