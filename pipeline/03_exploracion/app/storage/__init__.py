"""Módulo de almacenamiento de evidencias con soporte para Local y Google Cloud Storage."""

from typing import Optional
from app.config import get_settings
from app.storage.base import StorageProvider
from app.storage.gcs_storage import GCSStorageProvider
from app.storage.local_storage import LocalStorageProvider


def get_storage_provider(
    provider_type: Optional[str] = None,
    bucket_name: Optional[str] = None,
) -> StorageProvider:
    """
    Factoría para instanciar el proveedor de almacenamiento configurado.

    :param provider_type: 'local' o 'gcs'; si es None se toma de Settings.STORAGE_PROVIDER.
    :param bucket_name: Nombre explícito del bucket para GCS (opcional; por defecto Settings.GCS_BUCKET_NAME).
    :return: Instancia concreta de StorageProvider.
    """
    settings = get_settings()
    selected = (provider_type or settings.STORAGE_PROVIDER).lower().strip()
    if selected == "gcs":
        resolved_bucket = bucket_name or settings.GCS_BUCKET_NAME
        return GCSStorageProvider(bucket_name=resolved_bucket, location=settings.GCS_LOCATION)
    return LocalStorageProvider()


__all__ = [
    "GCSStorageProvider",
    "LocalStorageProvider",
    "StorageProvider",
    "get_storage_provider",
]
