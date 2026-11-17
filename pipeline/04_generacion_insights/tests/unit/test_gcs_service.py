"""Pruebas unitarias para GCSStorageProvider y GCSService."""

import base64
from typing import Any
from unittest.mock import MagicMock, patch
import pytest

from app.config import Settings
from app.models.exploration_models import ExplorationEvidence
from app.services.gcs_service import GCSService
from app.storage.gcs_storage import GCSStorageProvider


@pytest.mark.unit
def test_gcs_storage_normalize_blob_path() -> None:
    """Verifica que la normalización de rutas de blob elimine esquemas y nombres de bucket."""
    provider = GCSStorageProvider(bucket_name="my-bucket")

    assert provider._normalize_blob_path("capturas/step_1.webp") == "capturas/step_1.webp"
    assert provider._normalize_blob_path("gs://my-bucket/capturas/step_1.webp") == "capturas/step_1.webp"
    assert provider._normalize_blob_path("gs://other-bucket/img.webp") == "img.webp"
    assert provider._normalize_blob_path("/capturas/sub/test.webp") == "capturas/sub/test.webp"


@pytest.mark.unit
def test_gcs_storage_client_initialization() -> None:
    """Verifica la inicialización lazy de storage.Client con y sin credenciales."""
    with patch("google.oauth2.service_account.Credentials.from_service_account_file") as mock_creds, \
         patch("google.cloud.storage.Client") as mock_storage_cls:
        provider = GCSStorageProvider(
            bucket_name="b",
            project_id="proj",
            credentials_path="/path/to/creds.json",
        )
        _ = provider.client
        _ = provider.client  # segunda llamada reutiliza instancia en caché
        mock_creds.assert_called_once_with("/path/to/creds.json")
        mock_storage_cls.assert_called_once()

    with patch("google.cloud.storage.Client") as mock_storage_cls:
        provider_adc = GCSStorageProvider(bucket_name="b", project_id="proj")
        _ = provider_adc.client
        mock_storage_cls.assert_called_once_with(project="proj")


@pytest.mark.unit
def test_gcs_storage_download_bytes_and_base64() -> None:
    """Verifica descarga de bytes y conversión a Base64 desde GCS."""
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_blob.download_as_bytes.return_value = b"FAKE_WEBP_IMAGE_BYTES"

    mock_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    provider = GCSStorageProvider(bucket_name="my-bucket", client=mock_client)

    raw_bytes = provider.download_bytes("gs://pruebas-pfi-evidencias/img.webp")
    assert raw_bytes == b"FAKE_WEBP_IMAGE_BYTES"
    mock_client.bucket.assert_called_with("pruebas-pfi-evidencias")

    b64_str = provider.download_base64("img.webp")
    assert base64.b64decode(b64_str) == b"FAKE_WEBP_IMAGE_BYTES"


@pytest.mark.unit
def test_gcs_storage_parse_bucket_and_blob_single_part() -> None:
    """Verifica _parse_bucket_and_blob cuando la URI gs:// no tiene subcarpeta."""
    provider = GCSStorageProvider(bucket_name="default-bucket")
    bucket, clean = provider._parse_bucket_and_blob("gs://single-file-bucket")
    assert bucket == "default-bucket"
    assert clean == "single-file-bucket"


@pytest.mark.unit
def test_gcs_service_resolve_step_images_base64(mock_settings: Settings) -> None:
    """Verifica que resolve_step_images_base64 descargue las capturas usando orden 1-indexed."""
    mock_provider = MagicMock()
    mock_provider.download_base64.return_value = "AAAA1111"

    service = GCSService(storage_provider=mock_provider, settings=mock_settings)

    evidences = [
        ExplorationEvidence(
            orden=1,
            nombre_evento="page_view",
            ruta="https://shop.merch.google/",
            screenshot_url="gs://pruebas-pfi-evidencias/step_1.webp",
        ),
        ExplorationEvidence(
            orden=2,
            nombre_evento="view_cart",
            ruta="https://shop.merch.google/checkout",
            screenshot_url="gs://pruebas-pfi-evidencias/step_2.webp",
            es_paso_friccion=True,
        ),
    ]

    images_map = service.resolve_step_images_base64(evidences)
    assert len(images_map) == 2
    assert images_map[1] == "data:image/webp;base64,AAAA1111"
    assert images_map[2] == "data:image/webp;base64,AAAA1111"


@pytest.mark.unit
def test_gcs_service_download_image_bytes(mock_settings: Settings) -> None:
    """Verifica la delegación de download_image_bytes hacia el storage_provider."""
    mock_provider = MagicMock()
    mock_provider.download_bytes.return_value = b"MOCK_BYTES"

    service = GCSService(storage_provider=mock_provider, settings=mock_settings)
    result = service.download_image_bytes("capturas/step_1.webp")

    assert result == b"MOCK_BYTES"
    mock_provider.download_bytes.assert_called_once_with("capturas/step_1.webp")


@pytest.mark.unit
def test_gcs_service_resolve_step_images_base64_dicts_and_edge_cases(mock_settings: Settings) -> None:
    """Verifica resolve_step_images_base64 con dicts, rutas vacías y tipos desconocidos."""
    mock_provider = MagicMock()
    mock_provider.download_base64.return_value = "BASE64_DATA"

    service = GCSService(storage_provider=mock_provider, settings=mock_settings)

    items = [
        {"orden": 3, "screenshot_url": "step3.webp"},
        {"screenshot_url": "step1_fallback.webp"},
        {"orden": 9, "screenshot_url": ""},
        {"orden": 10, "screenshot_url": None},
        ExplorationEvidence(orden=11, screenshot_url="   "),
        "invalid_item_type",
    ]

    images_map = service.resolve_step_images_base64(items)  # type: ignore[arg-type]

    assert len(images_map) == 2
    assert images_map[3] == "data:image/webp;base64,BASE64_DATA"
    assert images_map[1] == "data:image/webp;base64,BASE64_DATA"
    assert 9 not in images_map
    assert 10 not in images_map
    assert 11 not in images_map


@pytest.mark.unit
def test_gcs_service_resolve_step_images_base64_error_handling(mock_settings: Settings) -> None:
    """Verifica que fallos individuales en descarga no detengan la resolución de imágenes."""
    mock_provider = MagicMock()

    def side_effect(path: str) -> str:
        if path == "error.webp":
            raise RuntimeError("Fallo de red en descarga GCS")
        return "OK_BASE64"

    mock_provider.download_base64.side_effect = side_effect
    service = GCSService(storage_provider=mock_provider, settings=mock_settings)

    items: list[dict[str, Any]] = [
        {"orden": 1, "screenshot_url": "ok.webp"},
        {"orden": 2, "screenshot_url": "error.webp"},
    ]

    images_map = service.resolve_step_images_base64(items)
    assert len(images_map) == 1
    assert images_map[1] == "data:image/webp;base64,OK_BASE64"
    assert 2 not in images_map


@pytest.mark.unit
def test_gcs_service_default_initialization() -> None:
    """Verifica la inicialización por defecto de GCSService sin argumentos."""
    with patch("app.services.gcs_service.get_settings") as mock_get_settings, \
         patch("app.services.gcs_service.GCSStorageProvider") as mock_storage_cls:
        settings_instance = MagicMock()
        settings_instance.GCS_BUCKET_CAPTURES = "pruebas-pfi-evidencias"
        settings_instance.PLATFORM_GCP_PROJECT_ID = "pruebas-pfi"
        settings_instance.GOOGLE_APPLICATION_CREDENTIALS = "/creds.json"
        mock_get_settings.return_value = settings_instance

        service = GCSService()

        assert service.settings == settings_instance
        mock_storage_cls.assert_called_once_with(
            bucket_name="pruebas-pfi-evidencias",
            project_id="pruebas-pfi",
            credentials_path="/creds.json",
        )
