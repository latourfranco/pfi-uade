"""Contrato abstracto para proveedores de almacenamiento en la nube."""

from abc import ABC, abstractmethod


class StorageProvider(ABC):
    """Interfaz base para servicios de almacenamiento de objetos."""

    @abstractmethod
    def download_bytes(self, blob_path: str) -> bytes:
        """Descarga el contenido binario del objeto almacenado.

        Args:
            blob_path: Ruta o URI gs:// del objeto a descargar.

        Returns:
            Bytes crudos del objeto.
        """
        pass

    @abstractmethod
    def download_base64(self, blob_path: str) -> str:
        """Descarga el contenido del objeto y lo codifica como string Base64.

        Args:
            blob_path: Ruta o URI gs:// del objeto a descargar.

        Returns:
            Cadena Base64 del contenido binario.
        """
        pass
