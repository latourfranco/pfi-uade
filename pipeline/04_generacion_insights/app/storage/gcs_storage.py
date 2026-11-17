"""Implementación de StorageProvider para Google Cloud Storage."""

import base64
import logging
from typing import Optional, Tuple

from google.cloud import storage  # type: ignore[attr-defined]
from google.oauth2 import service_account

from app.storage.base import StorageProvider

logger = logging.getLogger(__name__)


class GCSStorageProvider(StorageProvider):
    """Proveedor de almacenamiento en Google Cloud Storage con descarga directa y Base64."""

    def __init__(
        self,
        bucket_name: str,
        project_id: Optional[str] = None,
        credentials_path: Optional[str] = None,
        client: Optional[storage.Client] = None,
    ) -> None:
        """Inicializa el proveedor de almacenamiento para GCS.

        Args:
            bucket_name: Nombre por defecto del bucket en GCS donde residen las capturas.
            project_id: ID del proyecto de GCP.
            credentials_path: Ruta al archivo JSON de credenciales de Service Account (opcional).
            client: Instancia preexistente de storage.Client para inyección de dependencias o tests.
        """
        self.bucket_name = bucket_name
        self.project_id = project_id
        self.credentials_path = credentials_path
        self._client = client

    @property
    def client(self) -> storage.Client:
        """Obtiene o inicializa el cliente de Google Cloud Storage."""
        if self._client is None:
            if self.credentials_path:
                logger.info("Inicializando cliente GCS con credenciales de archivo: %s", self.credentials_path)
                credentials = service_account.Credentials.from_service_account_file(self.credentials_path)
                self._client = storage.Client(project=self.project_id, credentials=credentials)
            else:
                logger.info("Inicializando cliente GCS con credenciales por defecto (ADC)")
                self._client = storage.Client(project=self.project_id)
        return self._client

    def _parse_bucket_and_blob(self, blob_path: str) -> Tuple[str, str]:
        """Extrae el bucket de destino y la ruta limpia del blob.

        Permite resolver de forma transparente tanto URIs con esquema 'gs://<bucket>/<blob>'
        como rutas relativas 'path/img.webp'.

        Args:
            blob_path: Ruta relativa o URI canónica 'gs://...'.

        Returns:
            Tupla (bucket_name, clean_blob_path).
        """
        path = blob_path.strip()
        if path.startswith("gs://"):
            parts = path[5:].split("/", 1)
            if len(parts) == 2:
                return parts[0], parts[1]
            return self.bucket_name, parts[0]
        return self.bucket_name, path.lstrip("/")

    def _normalize_blob_path(self, blob_path: str) -> str:
        """Normaliza la ruta del blob eliminando prefijos de esquema y bucket.

        Args:
            blob_path: Ruta que puede ser 'gs://bucket/path/img.webp' o 'path/img.webp'.

        Returns:
            Ruta limpia del blob relativa al bucket.
        """
        _, clean_path = self._parse_bucket_and_blob(blob_path)
        return clean_path

    def download_bytes(self, blob_path: str) -> bytes:
        """Descarga los bytes de una captura WebP desde GCS.

        Args:
            blob_path: URI canónica 'gs://...' o ruta relativa del objeto.

        Returns:
            Bytes crudos del archivo descargado.
        """
        bucket_name, clean_path = self._parse_bucket_and_blob(blob_path)
        logger.debug("Descargando bytes de blob '%s' desde bucket '%s'", clean_path, bucket_name)
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(clean_path)
        return bytes(blob.download_as_bytes())

    def download_base64(self, blob_path: str) -> str:
        """Descarga una captura WebP desde GCS y la codifica en cadena Base64.

        Args:
            blob_path: URI canónica 'gs://...' o ruta relativa del objeto.

        Returns:
            Cadena en Base64 correspondiente a la imagen WebP.
        """
        raw_bytes = self.download_bytes(blob_path)
        return base64.b64encode(raw_bytes).decode("utf-8")
