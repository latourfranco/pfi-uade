"""Configuración centralizada del módulo de exploración agéntica."""

import os
from functools import lru_cache
from typing import Optional, Set
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Ajustes de configuración cargados desde variables de entorno o archivo .env."""

    # Entorno y servicio
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "production")

    # Configuración de Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    # Clave de cifrado AES-256 (32 bytes en formato hex o base64), provista vía variable de entorno
    AES_ENCRYPTION_KEY: str = os.getenv("AES_ENCRYPTION_KEY", "")

    # Parámetros del navegador Playwright
    HEADLESS_MODE: bool = os.getenv("HEADLESS_MODE", "true").lower() == "true"
    DEFAULT_TIMEOUT_MS: int = int(os.getenv("DEFAULT_TIMEOUT_MS", "15000"))
    NAVIGATION_TIMEOUT_MS: int = int(os.getenv("NAVIGATION_TIMEOUT_MS", "30000"))
    PAGE_SETTLE_SECONDS: float = float(os.getenv("PAGE_SETTLE_SECONDS", "5.0"))

    # Resoluciones de viewport por defecto
    DESKTOP_VIEWPORT_WIDTH: int = int(os.getenv("DESKTOP_VIEWPORT_WIDTH", "1366"))
    DESKTOP_VIEWPORT_HEIGHT: int = int(os.getenv("DESKTOP_VIEWPORT_HEIGHT", "768"))
    MOBILE_VIEWPORT_WIDTH: int = int(os.getenv("MOBILE_VIEWPORT_WIDTH", "390"))
    MOBILE_VIEWPORT_HEIGHT: int = int(os.getenv("MOBILE_VIEWPORT_HEIGHT", "844"))

    # Concurrencia de sesiones por cliente
    MAX_CONCURRENCY_PER_CLIENT: int = int(os.getenv("MAX_CONCURRENCY_PER_CLIENT", "3"))

    # Almacenamiento de evidencias gráficas (único bucket centralizado en US)
    STORAGE_PROVIDER: str = os.getenv("STORAGE_PROVIDER", "gcs")  # "local" o "gcs"
    LOCAL_STORAGE_PATH: str = os.getenv("LOCAL_STORAGE_PATH", "./evidence_storage")
    GCS_BUCKET_NAME: str = os.getenv("GCS_BUCKET_NAME", "pruebas-pfi-evidencias") or "pruebas-pfi-evidencias"
    GCS_LOCATION: str = os.getenv("GCS_LOCATION", "us")

    # Google Cloud Platform (Proyecto Central de la Plataforma)
    PLATFORM_GCP_PROJECT_ID: str = os.getenv(
        "PLATFORM_GCP_PROJECT_ID",
        os.getenv("BIGQUERY_PROJECT_ID", "pruebas-pfi"),
    )
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", None)
    DEFAULT_BIGQUERY_REGION: str = os.getenv("DEFAULT_BIGQUERY_REGION", "us")
    BIGQUERY_DATASET: str = os.getenv("BIGQUERY_DATASET", "friccion_resultados")
    BIGQUERY_PATTERNS_TABLE_NAME: str = os.getenv("BIGQUERY_PATTERNS_TABLE_NAME", "patrones")
    BIGQUERY_SESSIONS_TABLE_NAME: str = os.getenv("BIGQUERY_SESSIONS_TABLE_NAME", "sesion_representativa")
    BIGQUERY_TABLE_NAME: str = os.getenv("BIGQUERY_TABLE_NAME", "patrones_friccion_explorados")

    # Resiliencia y reintentos
    MAX_CLIENT_RETRIES: int = int(os.getenv("MAX_CLIENT_RETRIES", "3"))

    # Filtro opcional por IDs de patrón separados por coma (para corridas acotadas/pruebas)
    TARGET_PATTERN_IDS: Optional[str] = os.getenv("TARGET_PATTERN_IDS", None)

    def get_target_pattern_ids(self) -> Optional[Set[str]]:
        """Retorna el conjunto de IDs de patrón filtrados si TARGET_PATTERN_IDS está configurado."""
        if not self.TARGET_PATTERN_IDS:
            return None
        ids = {item.strip() for item in self.TARGET_PATTERN_IDS.split(",") if item.strip()}
        return ids or None

    def model_post_init(self, __context: object) -> None:
        """Asegura que las credenciales de GCP se propaguen al entorno del proceso si están definidas."""
        if self.GOOGLE_APPLICATION_CREDENTIALS and "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.GOOGLE_APPLICATION_CREDENTIALS

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Instancia singleton en caché de la configuración."""
    return Settings()
