import os
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración de la aplicación cargada desde variables de entorno o archivo .env."""

    # Google Cloud Platform (Proyecto central de la plataforma)
    PLATFORM_GCP_PROJECT_ID: str = os.getenv("PLATFORM_GCP_PROJECT_ID", "default-platform-project")
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    # Configuración de Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    # Configuración de Ejecución y Resiliencia
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "production")
    PORT: int = int(os.getenv("PORT", "8080"))
    GA4_INITIAL_BACKFILL_DAYS: int = int(os.getenv("GA4_INITIAL_BACKFILL_DAYS", "60"))
    MAX_CONCURRENT_CLIENTS: int = int(os.getenv("MAX_CONCURRENT_CLIENTS", "5"))
    MAX_CLIENT_RETRIES: int = int(os.getenv("MAX_CLIENT_RETRIES", "3"))
    RETRY_INITIAL_DELAY: float = float(os.getenv("RETRY_INITIAL_DELAY", "2.0"))
    RETRY_BACKOFF_FACTOR: float = float(os.getenv("RETRY_BACKOFF_FACTOR", "2.0"))

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """Instancia singleton en caché de la configuración."""
    return Settings()
