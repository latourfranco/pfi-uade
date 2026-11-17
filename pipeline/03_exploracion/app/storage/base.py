"""Interfaz abstracta para proveedores de almacenamiento de evidencias visuales."""

from abc import ABC, abstractmethod


class StorageUploadError(RuntimeError):
    """Error crítico al intentar persistir una evidencia visual en el almacenamiento."""


class StorageProvider(ABC):
    """
    Contrato base abstracto para el almacenamiento y persistencia de evidencias gráficas.

    Permite desacoplar el entorno de ejecución, alternando de manera transparente entre
    almacenamiento en disco local (desarrollo/tests) y Google Cloud Storage (producción en Cloud Run).
    """

    @abstractmethod
    async def save_evidence(
        self,
        data: bytes,
        filename: str,
        content_type: str = "image/webp",
    ) -> str:
        """
        Persiste los bytes de la captura visual.

        :param data: Contenido binario del archivo.
        :param filename: Nombre o clave del archivo dentro del almacenamiento.
        :param content_type: Tipo MIME del contenido (ej. 'image/webp').
        :return: URI o URL de acceso al archivo persistido (ej. 'file://...' o 'gs://...').
        """
        pass  # pragma: no cover

    @abstractmethod
    async def read_evidence(self, file_path_or_uri: str) -> bytes:
        """
        Recupera el contenido binario de una evidencia persistida.

        :param file_path_or_uri: Ruta o URI del archivo.
        :return: Contenido en bytes del archivo.
        """
        pass  # pragma: no cover

    @abstractmethod
    async def delete_evidence(self, file_path_or_uri: str) -> bool:
        """
        Elimina un archivo del almacenamiento.

        :param file_path_or_uri: Ruta o URI del archivo.
        :return: True si se eliminó con éxito, False en caso contrario.
        """
        pass  # pragma: no cover
