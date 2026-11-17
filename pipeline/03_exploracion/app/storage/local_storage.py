"""Proveedor de almacenamiento local en sistema de archivos para desarrollo y pruebas."""

import asyncio
import logging
from pathlib import Path
from typing import Optional
from app.config import get_settings
from app.storage.base import StorageProvider

logger = logging.getLogger(__name__)


class LocalStorageProvider(StorageProvider):
    """
    Implementación de StorageProvider para almacenamiento local en disco.
    """

    def __init__(self, base_directory: Optional[str] = None) -> None:
        """
        Inicializa el proveedor de almacenamiento local.

        :param base_directory: Directorio base de almacenamiento; si es None usa LOCAL_STORAGE_PATH.
        """
        raw_path = base_directory or get_settings().LOCAL_STORAGE_PATH
        self.base_path = Path(raw_path).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"[LocalStorageProvider] Directorio base inicializado en: {self.base_path}")

    async def save_evidence(
        self,
        data: bytes,
        filename: str,
        content_type: str = "image/webp",
    ) -> str:
        """
        Guarda los bytes en el sistema de archivos local.
        """
        # Normalizar filename permitiendo subdirectorios relativos seguros dentro de base_path
        safe_parts = [part for part in Path(filename.lstrip("/")).parts if part not in ("", ".", "..")]
        if not safe_parts:
            raise ValueError("El nombre de archivo de evidencia no es válido.")
        target_path = self.base_path.joinpath(*safe_parts)

        def _write() -> None:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(data)

        await asyncio.to_thread(_write)
        logger.info(f"[LocalStorageProvider] Evidencia guardada en: {target_path}")
        return str(target_path)

    async def read_evidence(self, file_path_or_uri: str) -> bytes:
        """
        Lee los bytes de un archivo local.
        """
        clean_path = file_path_or_uri.replace("file://", "")
        target_path = Path(clean_path).resolve()

        if not target_path.exists() or not target_path.is_file():
            raise FileNotFoundError(f"El archivo de evidencia no existe: {file_path_or_uri}")

        def _read() -> bytes:
            return target_path.read_bytes()

        return await asyncio.to_thread(_read)

    async def delete_evidence(self, file_path_or_uri: str) -> bool:
        """
        Elimina un archivo del almacenamiento local.
        """
        clean_path = file_path_or_uri.replace("file://", "")
        target_path = Path(clean_path).resolve()

        if target_path.exists():
            def _delete() -> None:
                target_path.unlink()

            await asyncio.to_thread(_delete)
            logger.info(f"[LocalStorageProvider] Archivo eliminado: {target_path}")
            return True

        return False
