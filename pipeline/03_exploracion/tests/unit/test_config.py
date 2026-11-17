"""Pruebas unitarias para el módulo de configuración centralizada (app/config.py)."""

import os
from unittest.mock import patch

import pytest

from app.config import Settings, get_settings


@pytest.mark.unit
def test_settings_default_values() -> None:
    """Verifica que la configuración por defecto de Settings se cargue con los valores esperados."""
    settings = Settings()
    assert settings.ENVIRONMENT in ["production", "development", "staging"]
    assert isinstance(settings.HEADLESS_MODE, bool)
    assert settings.DEFAULT_TIMEOUT_MS > 0
    assert settings.NAVIGATION_TIMEOUT_MS > 0
    assert settings.DESKTOP_VIEWPORT_WIDTH == 1366
    assert settings.DESKTOP_VIEWPORT_HEIGHT == 768
    assert settings.MOBILE_VIEWPORT_WIDTH == 390
    assert settings.MOBILE_VIEWPORT_HEIGHT == 844
    assert settings.MAX_CONCURRENCY_PER_CLIENT == 3
    assert settings.STORAGE_PROVIDER in ["local", "gcs"]
    assert settings.MAX_CLIENT_RETRIES == 3


@pytest.mark.unit
def test_settings_custom_values() -> None:
    """Verifica la inicialización de Settings con valores personalizados."""
    settings = Settings(
        ENVIRONMENT="development",
        HEADLESS_MODE=False,
        DEFAULT_TIMEOUT_MS=5000,
        NAVIGATION_TIMEOUT_MS=10000,
        DESKTOP_VIEWPORT_WIDTH=1920,
        DESKTOP_VIEWPORT_HEIGHT=1080,
        MOBILE_VIEWPORT_WIDTH=375,
        MOBILE_VIEWPORT_HEIGHT=667,
        MAX_CONCURRENCY_PER_CLIENT=5,
        STORAGE_PROVIDER="gcs",
        LOCAL_STORAGE_PATH="/tmp/evidence",
        GCS_BUCKET_NAME="custom-evidence-bucket",
        PLATFORM_GCP_PROJECT_ID="custom-project-id",
        DEFAULT_BIGQUERY_REGION="eu",
        BIGQUERY_DATASET="custom_friccion_resultados",
        BIGQUERY_PATTERNS_TABLE_NAME="custom_patrones",
        BIGQUERY_SESSIONS_TABLE_NAME="custom_sesion_representativa",
        BIGQUERY_TABLE_NAME="custom_reports",
        MAX_CLIENT_RETRIES=5,
    )
    assert settings.ENVIRONMENT == "development"
    assert settings.HEADLESS_MODE is False
    assert settings.DEFAULT_TIMEOUT_MS == 5000
    assert settings.NAVIGATION_TIMEOUT_MS == 10000
    assert settings.DESKTOP_VIEWPORT_WIDTH == 1920
    assert settings.DESKTOP_VIEWPORT_HEIGHT == 1080
    assert settings.MOBILE_VIEWPORT_WIDTH == 375
    assert settings.MOBILE_VIEWPORT_HEIGHT == 667
    assert settings.MAX_CONCURRENCY_PER_CLIENT == 5
    assert settings.STORAGE_PROVIDER == "gcs"
    assert settings.LOCAL_STORAGE_PATH == "/tmp/evidence"
    assert settings.GCS_BUCKET_NAME == "custom-evidence-bucket"
    assert settings.PLATFORM_GCP_PROJECT_ID == "custom-project-id"
    assert settings.DEFAULT_BIGQUERY_REGION == "eu"
    assert settings.BIGQUERY_DATASET == "custom_friccion_resultados"
    assert settings.BIGQUERY_PATTERNS_TABLE_NAME == "custom_patrones"
    assert settings.BIGQUERY_SESSIONS_TABLE_NAME == "custom_sesion_representativa"
    assert settings.BIGQUERY_TABLE_NAME == "custom_reports"
    assert settings.MAX_CLIENT_RETRIES == 5


@pytest.mark.unit
def test_google_application_credentials_propagated_to_env() -> None:
    """Verifica que model_post_init propague GOOGLE_APPLICATION_CREDENTIALS a os.environ si no existe."""
    with patch.dict(os.environ, {}, clear=True):
        assert "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ
        fake_creds_path = "/tmp/credentials-fake.json"
        settings = Settings(GOOGLE_APPLICATION_CREDENTIALS=fake_creds_path)

        assert settings.GOOGLE_APPLICATION_CREDENTIALS == fake_creds_path
        assert os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") == fake_creds_path


@pytest.mark.unit
def test_google_application_credentials_not_overwritten_if_already_in_env() -> None:
    """Verifica que model_post_init no sobreescriba GOOGLE_APPLICATION_CREDENTIALS si ya está en os.environ."""
    existing_creds_path = "/tmp/existing-creds.json"
    with patch.dict(os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": existing_creds_path}, clear=True):
        new_creds_path = "/tmp/new-creds.json"
        settings = Settings(GOOGLE_APPLICATION_CREDENTIALS=new_creds_path)

        assert settings.GOOGLE_APPLICATION_CREDENTIALS == new_creds_path
        # No debe haber sobreescrito la variable de entorno preexistente
        assert os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") == existing_creds_path


@pytest.mark.unit
def test_google_application_credentials_none_does_not_set_env() -> None:
    """Verifica que si GOOGLE_APPLICATION_CREDENTIALS es None, no se cree la variable en os.environ."""
    with patch.dict(os.environ, {}, clear=True):
        assert "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ
        settings = Settings(GOOGLE_APPLICATION_CREDENTIALS=None)

        assert settings.GOOGLE_APPLICATION_CREDENTIALS is None
        assert "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ


@pytest.mark.unit
def test_get_settings_caching() -> None:
    """Verifica que get_settings() devuelva una instancia cacheada singleton."""
    get_settings.cache_clear()
    settings_1 = get_settings()
    settings_2 = get_settings()
    assert settings_1 is settings_2
    get_settings.cache_clear()


@pytest.mark.unit
def test_centralized_gcs_bucket_settings() -> None:
    """Verifica la configuración por defecto y personalizable del bucket único en US."""
    default_settings = Settings(GCS_BUCKET_NAME="pruebas-pfi-evidencias", GCS_LOCATION="us")
    assert default_settings.GCS_BUCKET_NAME == "pruebas-pfi-evidencias"
    assert default_settings.GCS_LOCATION == "us"

    custom_settings = Settings(GCS_BUCKET_NAME="custom-central-bucket", GCS_LOCATION="us-central1")
    assert custom_settings.GCS_BUCKET_NAME == "custom-central-bucket"
    assert custom_settings.GCS_LOCATION == "us-central1"


@pytest.mark.unit
def test_get_target_pattern_ids() -> None:
    """Verifica el parseo CSV de TARGET_PATTERN_IDS opcional."""
    assert Settings(TARGET_PATTERN_IDS=None).get_target_pattern_ids() is None
    assert Settings(TARGET_PATTERN_IDS="  ,  ").get_target_pattern_ids() is None
    assert Settings(TARGET_PATTERN_IDS="p1, p2 ,p3").get_target_pattern_ids() == {"p1", "p2", "p3"}
