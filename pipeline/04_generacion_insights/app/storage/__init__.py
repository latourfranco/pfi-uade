"""Módulo de almacenamiento y abstracciones de proveedores."""

from app.storage.base import StorageProvider
from app.storage.gcs_storage import GCSStorageProvider

__all__ = ["StorageProvider", "GCSStorageProvider"]
