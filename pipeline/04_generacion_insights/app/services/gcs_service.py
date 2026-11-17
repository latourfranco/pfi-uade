"""Servicio para descarga y codificación Base64 de capturas WebP en Google Cloud Storage."""

import logging
from typing import Any, Dict, Optional, Sequence, Union

from app.config import Settings, get_settings
from app.models.exploration_models import ExplorationEvidence
from app.storage.base import StorageProvider
from app.storage.gcs_storage import GCSStorageProvider

logger = logging.getLogger(__name__)


class GCSService:
    """Servicio de alto nivel para descarga y codificación Base64 de capturas en GCS."""

    def __init__(
        self,
        storage_provider: Optional[StorageProvider] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        """Inicializa GCSService con inyección opcional de proveedor o settings.

        Args:
            storage_provider: Implementación de StorageProvider (GCS por defecto).
            settings: Configuración del microservicio.
        """
        self.settings = settings or get_settings()
        self.storage_provider = storage_provider or GCSStorageProvider(
            bucket_name=self.settings.GCS_BUCKET_CAPTURES,
            project_id=self.settings.PLATFORM_GCP_PROJECT_ID,
            credentials_path=self.settings.GOOGLE_APPLICATION_CREDENTIALS,
        )

    def download_image_bytes(self, screenshot_path: str) -> bytes:
        """Descarga los bytes directos de una captura WebP en GCS.

        Args:
            screenshot_path: Ruta relativa o URI canónica gs://...

        Returns:
            Bytes de la imagen descargada.
        """
        return self.storage_provider.download_bytes(screenshot_path)

    def download_image_base64(self, screenshot_path: str) -> str:
        """Descarga la captura y genera un data URI Base64 compatible con vLLM.

        Args:
            screenshot_path: Ruta relativa o URI canónica gs://...

        Returns:
            String con formato 'data:image/webp;base64,<payload>'.
        """
        b64 = self.storage_provider.download_base64(screenshot_path)
        return f"data:image/webp;base64,{b64}"

    def resolve_step_images_base64(
        self,
        steps_or_evidences: Sequence[Union[ExplorationEvidence, Dict[str, Any]]],
    ) -> Dict[int, str]:
        """Descarga y convierte a Base64 todas las capturas disponibles usando 'orden' 1-indexed.

        Args:
            steps_or_evidences: Lista de evidencias de exploración de BigQuery.

        Returns:
            Mapeo de número de paso (orden) a Data URI Base64.
        """
        images_map: Dict[int, str] = {}
        for item in steps_or_evidences:
            step_num = 1
            path: Optional[str] = None

            if isinstance(item, ExplorationEvidence):
                step_num = item.orden
                path = item.screenshot_url
            elif isinstance(item, dict):
                step_num = int(item.get("orden") or 1)
                path = item.get("screenshot_url")

            if path and path.strip():
                try:
                    images_map[step_num] = self.download_image_base64(path)
                except Exception as exc:
                    logger.warning(
                        "Fallo al descargar y codificar Base64 para paso %d (path: %s): %s",
                        step_num,
                        path,
                        exc,
                    )
        return images_map
