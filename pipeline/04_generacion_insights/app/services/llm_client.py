"""Cliente HTTP asíncrono resiliente para vLLM en Pods de RunPod con streaming SSE."""

import asyncio
from dataclasses import dataclass
import json
import logging
import random
import re
import time
from typing import Any, Dict, List, Optional

import httpx
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.models.llm_schemas import UxDiagnosticsOutput

logger = logging.getLogger(__name__)

RUNPOD_PODS_API_URL = "https://api.runpod.io/v2/pods"
RETRY_STATUS_CODES = {429, 500, 502, 503, 504, 524}
RETRY_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.RemoteProtocolError,
    httpx.WriteTimeout,
)


class LLMClientError(Exception):
    """Excepción base para errores de comunicación, descubrimiento o inferencia con vLLM."""
    pass


class LLMInferenceError(LLMClientError):
    """Fallo definitivo de inferencia tras agotar los reintentos."""
    pass


class LLMResponseValidationError(LLMClientError):
    """Fallo en la validación sintáctica o de esquema de la salida del LLM."""
    pass


@dataclass
class LLMGenerationResult:
    """Contenedor de resultado del diagnóstico y métricas de consumo de tokens."""

    output: UxDiagnosticsOutput
    prompt_tokens: int
    completion_tokens: int
    model_name: str


class LLMClient:
    """Cliente para interactuar con el Pod vLLM en RunPod vía API compatible con OpenAI."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        """Inicializa el cliente LLM.

        Args:
            settings: Configuración general del módulo.
            client: Instancia preconfigurada de httpx.AsyncClient para pruebas o pooling.
        """
        self.settings = settings or get_settings()
        self._external_client = client
        self._resolved_base_url: Optional[str] = None
        self._model_ready: bool = False

    def _get_headers(self) -> Dict[str, str]:
        """Construye cabeceras HTTP para el servidor vLLM detrás del proxy de RunPod."""
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "User-Agent": self.settings.LLM_USER_AGENT,
        }
        if self.settings.VLLM_API_KEY and self.settings.VLLM_API_KEY.strip():
            headers["Authorization"] = f"Bearer {self.settings.VLLM_API_KEY.strip()}"
        return headers

    def _get_runpod_headers(self) -> Dict[str, str]:
        """Construye cabeceras HTTP para consultar la API de gestión de Pods en RunPod."""
        api_key = (self.settings.RUNPOD_API_KEY or "").strip()
        return {
            "Content-Type": "application/json",
            "User-Agent": self.settings.LLM_USER_AGENT,
            "Authorization": f"Bearer {api_key}",
        }

    @staticmethod
    def _normalize_base_url(raw_url: str) -> str:
        """Normaliza la URL base eliminando sufijos /v1 o /v1/chat/completions."""
        cleaned = raw_url.strip().rstrip("/")
        if cleaned.endswith("/v1/chat/completions"):
            cleaned = cleaned[: -len("/v1/chat/completions")]
        elif cleaned.endswith("/v1"):
            cleaned = cleaned[: -len("/v1")]
        return cleaned.rstrip("/")

    async def _http_get(self, url: str, headers: Dict[str, str], timeout: httpx.Timeout) -> httpx.Response:
        """Ejecuta un GET reutilizando el cliente inyectado o uno temporal."""
        if self._external_client:
            return await self._external_client.get(url, headers=headers, timeout=timeout)
        async with httpx.AsyncClient() as client:
            return await client.get(url, headers=headers, timeout=timeout)

    async def _http_post(
        self,
        url: str,
        payload: Dict[str, Any],
        headers: Dict[str, str],
        timeout: httpx.Timeout,
    ) -> httpx.Response:
        """Ejecuta un POST reutilizando el cliente inyectado o uno temporal."""
        if self._external_client:
            return await self._external_client.post(url, json=payload, headers=headers, timeout=timeout)
        async with httpx.AsyncClient() as client:
            return await client.post(url, json=payload, headers=headers, timeout=timeout)

    async def resolve_base_url(self) -> str:
        """Resuelve la URL base del endpoint vLLM (configuración fija o descubrimiento en RunPod)."""
        if self._resolved_base_url:
            return self._resolved_base_url

        if self.settings.LLM_INFERENCE_URL and self.settings.LLM_INFERENCE_URL.strip():
            self._resolved_base_url = self._normalize_base_url(self.settings.LLM_INFERENCE_URL)
            return self._resolved_base_url

        if not self.settings.RUNPOD_API_KEY or not self.settings.RUNPOD_API_KEY.strip():
            raise LLMClientError(
                "Debe configurarse LLM_INFERENCE_URL o RUNPOD_API_KEY para descubrir el Pod en RunPod."
            )

        timeout = httpx.Timeout(timeout=30.0, connect=10.0)
        try:
            response = await self._http_get(
                RUNPOD_PODS_API_URL,
                headers=self._get_runpod_headers(),
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise LLMClientError(f"Error consultando los Pods activos en RunPod: {exc}") from exc

        pods: List[Any]
        if isinstance(data, list):
            pods = data
        elif isinstance(data, dict):
            raw_pods = data.get("pods") if "pods" in data else data.get("data", [])
            pods = raw_pods if isinstance(raw_pods, list) else []
        else:
            pods = []

        target_name = self.settings.LLM_POD_NOMBRE
        matching = [p for p in pods if isinstance(p, dict) and p.get("name") == target_name]

        if len(matching) == 0:
            raise LLMClientError(f"No se encontró ningún Pod en RunPod con nombre '{target_name}'.")
        if len(matching) > 1:
            raise LLMClientError(
                f"Se encontraron {len(matching)} Pods con nombre '{target_name}'; debe existir exactamente uno."
            )

        pod_id = str(matching[0].get("id") or "").strip()
        if not pod_id:
            raise LLMClientError(f"El Pod '{target_name}' en RunPod no contiene un identificador 'id' válido.")

        self._resolved_base_url = f"https://{pod_id}-8000.proxy.runpod.net"
        logger.info("Pod RunPod descubierto: '%s' -> %s", target_name, self._resolved_base_url)
        return self._resolved_base_url

    async def ensure_model_ready(self) -> None:
        """Verifica con backoff que el modelo vLLM esté cargado y disponible en /v1/models."""
        if self._model_ready:
            return

        base_url = await self.resolve_base_url()
        models_url = f"{base_url}/v1/models"
        headers = self._get_headers()
        timeout = httpx.Timeout(timeout=30.0, connect=10.0)

        max_wait = max(0.0, self.settings.LLM_READY_MAX_WAIT_SECONDS)
        poll_interval = max(0.1, self.settings.LLM_READY_POLL_INTERVAL_SECONDS)
        deadline = time.monotonic() + max_wait

        while True:
            try:
                response = await self._http_get(models_url, headers=headers, timeout=timeout)
                if response.status_code == 200:
                    payload = response.json()
                    models_list = payload.get("data", []) if isinstance(payload, dict) else []
                    model_ids = [
                        str(item.get("id"))
                        for item in models_list
                        if isinstance(item, dict) and item.get("id")
                    ]
                    if self.settings.LLM_MODEL_NAME in model_ids:
                        self._model_ready = True
                        logger.info("Modelo vLLM listo en %s: %s", base_url, self.settings.LLM_MODEL_NAME)
                        return
                    logger.info(
                        "Endpoint /v1/models respondió 200 pero '%s' aún no figura en %s.",
                        self.settings.LLM_MODEL_NAME,
                        model_ids,
                    )
                else:
                    logger.warning(
                        "Endpoint %s aún no está listo (HTTP %d).",
                        models_url,
                        response.status_code,
                    )
            except Exception as exc:
                logger.warning("Fallo consultando disponibilidad en %s: %s", models_url, exc)

            if time.monotonic() >= deadline:
                raise LLMInferenceError(
                    f"El modelo '{self.settings.LLM_MODEL_NAME}' no estuvo disponible en {models_url} "
                    f"tras esperar {max_wait:.0f} segundos."
                )

            await asyncio.sleep(poll_interval)

    async def generate_diagnostics(self, payload: Dict[str, Any]) -> LLMGenerationResult:
        """Envía el payload multimodal a vLLM (soporta streaming SSE y JSON) y valida la salida.

        Args:
            payload: Diccionario con messages, response_format, stream, model, etc.

        Returns:
            LLMGenerationResult con el objeto UxDiagnosticsOutput y métricas de tokens.

        Raises:
            LLMInferenceError: Si el servidor falla tras los reintentos permitidos.
            LLMResponseValidationError: Si la respuesta no satisface el esquema Pydantic.
        """
        base_url = await self.resolve_base_url()
        url = f"{base_url}/v1/chat/completions"
        headers = self._get_headers()
        timeout = httpx.Timeout(timeout=self.settings.LLM_TIMEOUT_SECONDS, connect=15.0)

        max_retries = max(0, self.settings.LLM_MAX_RETRIES)
        last_exception: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                logger.info(
                    "Invocando inferencia LLM en %s (intento %d/%d)...",
                    url,
                    attempt + 1,
                    max_retries + 1,
                )

                response = await self._http_post(url, payload, headers, timeout)

                if response.status_code in RETRY_STATUS_CODES:
                    logger.warning(
                        "Error HTTP transitorio %d de vLLM en intento %d: %s",
                        response.status_code,
                        attempt + 1,
                        response.text[:200],
                    )
                    if attempt < max_retries:
                        delay = (2 ** attempt) * 2.0 + random.uniform(0.1, 0.5)
                        await asyncio.sleep(delay)
                        continue
                    raise LLMInferenceError(
                        f"vLLM respondió con status {response.status_code}: {response.text[:300]}"
                    )

                response.raise_for_status()
                data = self._extract_response_data(response)
                return self._parse_llm_response(data)

            except RETRY_EXCEPTIONS as exc:
                last_exception = exc
                logger.warning(
                    "Fallo de red al conectar con vLLM en intento %d/%d: %s",
                    attempt + 1,
                    max_retries + 1,
                    exc,
                )
                if attempt < max_retries:
                    delay = (2 ** attempt) * 2.0 + random.uniform(0.1, 0.5)
                    await asyncio.sleep(delay)
                    continue
                raise LLMInferenceError(
                    f"Agotados reintentos por fallo de red con vLLM: {exc}"
                ) from exc
            except httpx.HTTPStatusError as exc:
                logger.error("Error HTTP no recuperable de vLLM (%d): %s", exc.response.status_code, exc.response.text)
                raise LLMInferenceError(f"Error HTTP no recuperable {exc.response.status_code}: {exc}") from exc

        raise LLMInferenceError(f"Fallo inesperado al invocar vLLM: {last_exception}")

    def _extract_response_data(self, response: httpx.Response) -> Dict[str, Any]:
        """Extrae payload estructurado tanto de respuestas JSON estándar como de streams SSE."""
        raw_text = response.text
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

        if any(line.startswith("data:") for line in lines):
            content_parts: List[str] = []
            reasoning_parts: List[str] = []
            usage: Dict[str, Any] = {}
            model_name = self.settings.LLM_MODEL_NAME
            finish_reason: Optional[str] = None

            for line in lines:
                if not line.startswith("data:"):
                    continue
                payload_str = line[5:].strip()
                if payload_str == "[DONE]":
                    continue
                try:
                    chunk = json.loads(payload_str)
                except json.JSONDecodeError:
                    continue

                if not isinstance(chunk, dict):
                    continue
                if chunk.get("model"):
                    model_name = str(chunk["model"])
                if isinstance(chunk.get("usage"), dict):
                    usage = chunk["usage"]

                choices = chunk.get("choices")
                if isinstance(choices, list) and choices:
                    choice0 = choices[0]
                    if isinstance(choice0, dict):
                        if choice0.get("finish_reason"):
                            finish_reason = str(choice0["finish_reason"])
                        delta = choice0.get("delta") or choice0.get("message") or {}
                        if isinstance(delta, dict):
                            piece = delta.get("content")
                            if isinstance(piece, str):
                                content_parts.append(piece)
                            r_piece = delta.get("reasoning_content") or delta.get("reasoning")
                            if isinstance(r_piece, str):
                                reasoning_parts.append(r_piece)

            return {
                "choices": [
                    {
                        "finish_reason": finish_reason,
                        "message": {
                            "role": "assistant",
                            "content": "".join(content_parts),
                            "reasoning_content": "".join(reasoning_parts),
                        },
                    }
                ],
                "usage": usage,
                "model": model_name,
            }

        parsed = response.json()
        if not isinstance(parsed, dict):
            raise LLMResponseValidationError("La respuesta JSON de vLLM no es un objeto válido.")
        return parsed

    @staticmethod
    def _clean_json_content(raw_content: str) -> str:
        """Elimina bloques <think>...</think> y delimitadores Markdown antes de validar JSON."""
        text = raw_content.strip()
        if "</think>" in text:
            text = text.split("</think>", 1)[1].strip()
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        return text.strip()

    def _parse_llm_response(self, data: Dict[str, Any]) -> LLMGenerationResult:
        """Extrae el contenido generado y valida contra UxDiagnosticsOutput."""
        try:
            choices = data.get("choices", [])
            if not choices:
                raise LLMResponseValidationError("La respuesta de vLLM no contiene la clave 'choices'.")

            message = choices[0].get("message", {})
            raw_content = message.get("content")

            if not raw_content:
                finish_reason = choices[0].get("finish_reason")
                reasoning_len = len(str(message.get("reasoning_content") or ""))
                raise LLMResponseValidationError(
                    "El contenido generado por el modelo está vacío "
                    f"(finish_reason={finish_reason}, reasoning_chars={reasoning_len})."
                )

            if isinstance(raw_content, str):
                cleaned = self._clean_json_content(raw_content)
                parsed_output = UxDiagnosticsOutput.model_validate_json(cleaned)
            elif isinstance(raw_content, dict):
                parsed_output = UxDiagnosticsOutput.model_validate(raw_content)
            else:
                raise LLMResponseValidationError(f"Tipo de contenido no soportado: {type(raw_content)}")

            usage = data.get("usage", {})
            prompt_tokens = int(usage.get("prompt_tokens", 0))
            completion_tokens = int(usage.get("completion_tokens", 0))
            model_name = str(data.get("model", self.settings.LLM_MODEL_NAME))

            return LLMGenerationResult(
                output=parsed_output,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model_name=model_name,
            )

        except LLMResponseValidationError:
            raise
        except (ValidationError, json.JSONDecodeError) as exc:
            logger.error("Fallo de validación Pydantic sobre la salida del LLM: %s", exc)
            err_msg = f"Estructura devuelta por LLM no conforme a UxDiagnosticsOutput: {exc}"
            raise LLMResponseValidationError(err_msg) from exc
        except Exception as exc:
            logger.error("Error al procesar la respuesta de vLLM: %s", exc)
            raise LLMResponseValidationError(f"Error parseando respuesta de vLLM: {exc}") from exc
