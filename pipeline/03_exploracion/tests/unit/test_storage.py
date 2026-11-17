"""Pruebas unitarias para proveedores de almacenamiento (Local y Google Cloud Storage)."""

import tempfile
from unittest.mock import MagicMock, patch
import pytest
from app.storage import get_storage_provider
from app.storage.gcs_storage import GCSStorageProvider
from app.storage.local_storage import LocalStorageProvider


@pytest.mark.asyncio
@pytest.mark.unit
async def test_local_storage_lifecycle():
    """Verifica el guardado, lectura y eliminación de evidencias en almacenamiento local."""
    with tempfile.TemporaryDirectory() as temp_dir:
        provider = LocalStorageProvider(base_directory=temp_dir)

        sample_bytes = b"fake-webp-image-data-12345"
        filename = "trace_1_step_0.webp"

        # 1. Guardar
        saved_path = await provider.save_evidence(sample_bytes, filename)
        assert filename in saved_path

        # 2. Leer
        read_bytes = await provider.read_evidence(saved_path)
        assert read_bytes == sample_bytes

        # 3. Eliminar
        deleted = await provider.delete_evidence(saved_path)
        assert deleted is True

        # 4. Eliminar archivo inexistente
        assert await provider.delete_evidence(saved_path) is False

        # 5. Leer inexistente lanza FileNotFoundError
        with pytest.raises(FileNotFoundError):
            await provider.read_evidence(saved_path)


@pytest.mark.unit
def test_gcs_storage_requires_bucket():
    """Verifica que GCSStorageProvider requiera un bucket_name válido."""
    with pytest.raises(ValueError, match="El nombre del bucket GCS no puede ser nulo"):
        GCSStorageProvider(bucket_name="")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_gcs_storage_operations():
    """Verifica operaciones con Google Cloud Storage utilizando un cliente mockeado."""
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()

    mock_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob
    mock_blob.exists.return_value = True
    mock_blob.download_as_bytes.return_value = b"gcs-bytes-downloaded"

    provider = GCSStorageProvider(bucket_name="eureka-test-bucket", client=mock_client)

    # 1. Guardar
    uri = await provider.save_evidence(b"fake-bytes", "captura_step_1.webp")
    assert uri == "gs://eureka-test-bucket/captura_step_1.webp"
    mock_blob.upload_from_string.assert_called_once_with(b"fake-bytes", content_type="image/webp")

    # 2. Leer
    downloaded = await provider.read_evidence("gs://eureka-test-bucket/captura_step_1.webp")
    assert downloaded == b"gcs-bytes-downloaded"

    # 3. Eliminar
    deleted = await provider.delete_evidence("captura_step_1.webp")
    assert deleted is True
    mock_blob.delete.assert_called_once()

    # 4. Leer blob inexistente lanza FileNotFoundError
    mock_blob.exists.return_value = False
    with pytest.raises(FileNotFoundError):
        await provider.read_evidence("gs://eureka-test-bucket/no_existe.webp")

    # 5. Eliminar blob inexistente retorna False
    assert await provider.delete_evidence("gs://eureka-test-bucket/no_existe.webp") is False

    # 6. Extraer blob name con URI simple sin subcarpetas
    assert provider._extract_blob_name("gs://eureka-test-bucket") == "eureka-test-bucket"


@pytest.mark.unit
def test_storage_factory():
    """Verifica la factoría get_storage_provider según el tipo configurado."""
    with tempfile.TemporaryDirectory():
        local_p = get_storage_provider("local")
        assert isinstance(local_p, LocalStorageProvider)

        # GCS provider vía factory (bucket único centralizado en US)
        with patch("app.storage.GCSStorageProvider") as mock_gcs_cls:
            mock_instance = MagicMock()
            mock_gcs_cls.return_value = mock_instance
            gcs_p = get_storage_provider("gcs")
            assert gcs_p == mock_instance
            mock_gcs_cls.assert_called_with(
                bucket_name="pruebas-pfi-evidencias",
                location="us",
            )

            # Con bucket_name explícito
            gcs_custom = get_storage_provider("gcs", bucket_name="bucket-explicito")
            assert gcs_custom == mock_instance
            mock_gcs_cls.assert_called_with(
                bucket_name="bucket-explicito",
                location="us",
            )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_gcs_storage_auto_creates_bucket_on_not_found():
    """Verifica que si el bucket no existe al subir evidencia (NotFound), se cree automáticamente."""
    from google.cloud.exceptions import NotFound

    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()

    mock_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    # Primera llamada a upload lanza NotFound, segunda tiene éxito
    mock_blob.upload_from_string.side_effect = [NotFound("Bucket not found"), None]

    provider = GCSStorageProvider(
        bucket_name="auto-create-bucket",
        client=mock_client,
        location="southamerica-east1",
    )

    uri = await provider.save_evidence(b"screenshot-bytes", "test.webp")
    assert uri == "gs://auto-create-bucket/test.webp"

    # Verificar que create_bucket fue invocado con el nombre y la ubicación
    mock_client.create_bucket.assert_called_once_with(
        "auto-create-bucket",
        location="southamerica-east1",
    )
    assert mock_blob.upload_from_string.call_count == 2


@pytest.mark.unit
def test_gcs_storage_ensure_bucket_exists():
    """Verifica el método ensure_bucket_exists en diferentes escenarios."""
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    provider = GCSStorageProvider(
        bucket_name="check-bucket",
        client=mock_client,
        location=None,
    )

    # Caso 1: El bucket ya existe
    mock_bucket.exists.return_value = True
    assert provider.ensure_bucket_exists() is True
    mock_client.create_bucket.assert_not_called()

    # Caso 2: El bucket no existe, se crea sin location especificada
    mock_bucket.exists.return_value = False
    assert provider.ensure_bucket_exists() is True
    mock_client.create_bucket.assert_called_once_with("check-bucket")

    # Caso 3: Error al crear el bucket
    mock_client.create_bucket.side_effect = RuntimeError("GCS error")
    assert provider.ensure_bucket_exists() is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_deterministic_nested_paths_and_overwrite(caplog):
    """Verifica rutas determinísticas con subdirectorios y sobreescritura en Local y GCS."""
    import logging
    from pathlib import Path

    deterministic_key = "capturas/cliente_1/2026-11-15/pat_1_0.webp"

    # 1. LocalStorageProvider con subdirectorios y sobreescritura
    with tempfile.TemporaryDirectory() as temp_dir:
        local_provider = LocalStorageProvider(base_directory=temp_dir)
        saved_v1 = await local_provider.save_evidence(b"version-1", deterministic_key)
        expected_suffix = str(Path("capturas") / "cliente_1" / "2026-11-15" / "pat_1_0.webp")
        assert saved_v1.endswith(expected_suffix)
        assert Path(saved_v1).resolve().is_relative_to(local_provider.base_path)
        assert await local_provider.read_evidence(saved_v1) == b"version-1"

        # Sobreescritura en la misma ruta determinística
        saved_v2 = await local_provider.save_evidence(b"version-2", deterministic_key)
        assert saved_v2 == saved_v1
        assert await local_provider.read_evidence(saved_v2) == b"version-2"

        # Sanitización ante path traversal
        sanitized_path = await local_provider.save_evidence(b"safe", f"/../../{deterministic_key}")
        assert sanitized_path == saved_v1
        assert await local_provider.read_evidence(sanitized_path) == b"safe"

        # Nombre inválido sin partes seguras
        with pytest.raises(ValueError, match="no es válido"):
            await local_provider.save_evidence(b"invalid", "../..")

    # 2. GCSStorageProvider con ruta determinística, sobreescritura y extras de log
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    gcs_provider = GCSStorageProvider(bucket_name="eureka-test-bucket", client=mock_client)

    with caplog.at_level(logging.INFO, logger="app.storage.gcs_storage"):
        uri_1 = await gcs_provider.save_evidence(b"gcs-v1", deterministic_key)
        uri_2 = await gcs_provider.save_evidence(b"gcs-v2", f"/{deterministic_key}")

    expected_uri = f"gs://eureka-test-bucket/{deterministic_key}"
    assert uri_1 == expected_uri
    assert uri_2 == expected_uri
    assert mock_bucket.blob.call_args_list == [
        ((deterministic_key,),),
        ((deterministic_key,),),
    ]
    assert mock_blob.upload_from_string.call_count == 2

    upload_records = [r for r in caplog.records if getattr(r, "gcs_uri", None) == expected_uri]
    assert len(upload_records) == 2
    assert upload_records[0].bucket == "eureka-test-bucket"
