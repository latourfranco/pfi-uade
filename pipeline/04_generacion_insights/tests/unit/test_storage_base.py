"""Pruebas unitarias para StorageProvider en app.storage.base."""

import pytest

from app.storage.base import StorageProvider


class ConcreteStorageProvider(StorageProvider):
    """Implementación de prueba que delega a super() para verificar el método abstracto."""

    def download_bytes(self, blob_path: str) -> bytes:
        super().download_bytes(blob_path)  # type: ignore[safe-super]
        return b"BYTES"

    def download_base64(self, blob_path: str) -> str:
        super().download_base64(blob_path)  # type: ignore[safe-super]
        return "QllURVM="


@pytest.mark.unit
def test_storage_provider_cannot_instantiate_directly() -> None:
    """Verifica que StorageProvider no pueda ser instanciado directamente por ser abstracto."""
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        StorageProvider()  # type: ignore[abstract]


@pytest.mark.unit
def test_storage_provider_base_method_execution() -> None:
    """Verifica que la invocación del método abstracto base (pass) se ejecute correctamente."""
    provider = ConcreteStorageProvider()
    assert provider.download_bytes("capturas/step_1.webp") == b"BYTES"
    assert provider.download_base64("capturas/step_1.webp") == "QllURVM="
