"""Proveedor de almacenamiento en Google Cloud Storage para entornos Cloud Run en producción."""

import asyncio
import logging
from typing import Any, Optional
from google.cloud import storage  # type: ignore[attr-defined,import-untyped]
from google.cloud.exceptions import NotFound  # type: ignore[attr-defined,import-untyped]
from app.config import get_settings
from app.storage.base import StorageProvider

logger = logging.getLogger(__name__)


class GCSStorageProvider(StorageProvider):
    """
    Implementación de StorageProvider para Google Cloud Storage (GCS).
    """

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        client: Optional[Any] = None,
        location: Optional[str] = None,
    ) -> None:
        """
        Inicializa el proveedor de almacenamiento en Google Cloud Storage.

        :param bucket_name: Nombre del bucket GCS; si es None usa GCS_BUCKET_NAME de Settings.
        :param client: Instancia opcional de storage.Client (útil para inyección en tests).
        :param location: Ubicación regional de GCP para crear el bucket si no existe (opcional).
        """
        self.bucket_name = bucket_name if bucket_name is not None else get_settings().GCS_BUCKET_NAME
        if not self.bucket_name:
            raise ValueError("El nombre del bucket GCS no puede ser nulo o vacío.")

        self.client = client or storage.Client()
        self.location = location
        self.bucket = self.client.bucket(self.bucket_name)
        logger.info(f"[GCSStorageProvider] Conectado al bucket GCS: '{self.bucket_name}'")

    def _create_bucket_sync(self) -> None:
        """Crea el bucket en GCS de forma síncrona si no existe."""
        create_kwargs: dict[str, Any] = {}
        if self.location:
            create_kwargs["location"] = self.location
        self.client.create_bucket(self.bucket_name, **create_kwargs)
        logger.info(
            f"[GCSStorageProvider] Bucket '{self.bucket_name}' creado exitosamente "
            f"(location='{self.location or 'default'}')."
        )

    def ensure_bucket_exists(self) -> bool:
        """Verifica si el bucket existe en GCS; si no existe, lo crea automáticamente."""
        try:
            if not self.bucket.exists():
                logger.info(f"[GCSStorageProvider] Bucket '{self.bucket_name}' no encontrado; creándolo...")
                self._create_bucket_sync()
            return True
        except Exception as exc:
            logger.warning(
                f"[GCSStorageProvider] Error al verificar/crear bucket '{self.bucket_name}': {exc}"
            )
            return False

    async def save_evidence(
        self,
        data: bytes,
        filename: str,
        content_type: str = "image/webp",
    ) -> str:
        """
        Sube los bytes de la captura a Google Cloud Storage, creando el bucket automáticamente si no existe.
        """
        blob_name = filename.lstrip("/")
        blob = self.bucket.blob(blob_name)

        def _upload() -> None:
            try:
                blob.upload_from_string(data, content_type=content_type)
            except NotFound:
                logger.info(
                    f"[GCSStorageProvider] Bucket '{self.bucket_name}' no encontrado al subir evidencia. "
                    "Creando bucket automáticamente..."
                )
                self._create_bucket_sync()
                blob.upload_from_string(data, content_type=content_type)

        await asyncio.to_thread(_upload)
        gcs_uri = f"gs://{self.bucket_name}/{blob_name}"
        logger.info(
            f"[GCSStorageProvider] Evidencia subida exitosamente a: {gcs_uri}",
            extra={"gcs_uri": gcs_uri, "bucket": self.bucket_name},
        )
        return gcs_uri

    async def read_evidence(self, file_path_or_uri: str) -> bytes:
        """
        Descarga los bytes de una evidencia alojada en GCS.
        """
        blob_name = self._extract_blob_name(file_path_or_uri)
        blob = self.bucket.blob(blob_name)

        def _download() -> bytes:
            if not blob.exists():
                raise FileNotFoundError(f"El blob de GCS no existe: {file_path_or_uri}")
            return blob.download_as_bytes()

        return await asyncio.to_thread(_download)

    async def delete_evidence(self, file_path_or_uri: str) -> bool:
        """
        Elimina un blob de Google Cloud Storage.
        """
        blob_name = self._extract_blob_name(file_path_or_uri)
        blob = self.bucket.blob(blob_name)

        def _delete() -> bool:
            if blob.exists():
                blob.delete()
                logger.info(f"[GCSStorageProvider] Blob eliminado: {blob_name}")
                return True
            return False

        return await asyncio.to_thread(_delete)

    def _extract_blob_name(self, uri: str) -> str:
        """Extrae el nombre del blob desde una URI 'gs://bucket/blob_name' o path directo."""
        if uri.startswith("gs://"):
            parts = uri.replace("gs://", "").split("/", 1)
            if len(parts) > 1:
                return parts[1]
            return parts[0]
        return uri.lstrip("/")
