"""Pruebas unitarias para el cliente LLM asíncrono con descubrimiento RunPod y streaming SSE."""

import json
from typing import Any, Dict
from unittest.mock import AsyncMock, patch
import httpx
import pytest

from app.config import Settings
from app.models.llm_schemas import UxDiagnosticsOutput
from app.services.llm_client import (
    LLMClient,
    LLMClientError,
    LLMInferenceError,
    LLMResponseValidationError,
)


def _build_mock_vllm_response(
    content: Any,
    status_code: int = 200,
    prompt_tokens: int = 150,
    completion_tokens: int = 420,
) -> httpx.Response:
    """Construye un mock de httpx.Response en formato JSON estándar de vLLM."""
    content_str = json.dumps(content) if isinstance(content, dict) else str(content)
    body = {
        "id": "chatcmpl-test-uuid",
        "object": "chat.completion",
        "model": "cyankiwi/Qwen3.5-27B-AWQ-4bit",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content_str},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        },
    }
    req = httpx.Request("POST", "https://mock-pod-8000.proxy.runpod.net/v1/chat/completions")
    return httpx.Response(status_code=status_code, json=body, request=req)


def _build_mock_sse_response(
    content_str: str,
    prompt_tokens: int = 200,
    completion_tokens: int = 600,
) -> httpx.Response:
    """Construye una respuesta SSE simulando streaming de vLLM con chunks de razonamiento y contenido."""
    mid = len(content_str) // 2
    part1 = content_str[:mid]
    part2 = content_str[mid:]
    sse_lines = [
        "data: " + json.dumps({
            "model": "cyankiwi/Qwen3.5-27B-AWQ-4bit",
            "choices": [{"delta": {"reasoning_content": "Analizando capturas..."}}],
        }),
        "",
        "data: invalid_json_ignored",
        "data: \"not_a_dict\"",
        "data: " + json.dumps({"choices": "not_a_list"}),
        "data: " + json.dumps({"choices": ["not_a_dict"]}),
        "data: " + json.dumps({"choices": [{"delta": "not_a_dict"}]}),
        "data: " + json.dumps({"choices": [{"delta": {"content": part1}}]}),
        "data: " + json.dumps({
            "choices": [{"delta": {"content": part2}}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
        }),
        "data: [DONE]",
    ]
    req = httpx.Request("POST", "https://mock-pod-8000.proxy.runpod.net/v1/chat/completions")
    return httpx.Response(status_code=200, text="\n".join(sse_lines), request=req)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_base_url_normalization_and_cache(mock_settings: Settings) -> None:
    """Verifica normalización de LLM_INFERENCE_URL con sufijos /v1 y uso de caché."""
    settings_v1 = mock_settings.model_copy(
        update={"LLM_INFERENCE_URL": "https://abc-8000.proxy.runpod.net/v1/chat/completions"}
    )
    client = LLMClient(settings=settings_v1)
    url1 = await client.resolve_base_url()
    url2 = await client.resolve_base_url()
    assert url1 == "https://abc-8000.proxy.runpod.net"
    assert url2 == url1

    client_v1_short = LLMClient(
        settings=mock_settings.model_copy(update={"LLM_INFERENCE_URL": "https://abc-8000.proxy.runpod.net/v1/"})
    )
    assert await client_v1_short.resolve_base_url() == "https://abc-8000.proxy.runpod.net"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_base_url_dynamic_runpod_discovery(mock_settings: Settings) -> None:
    """Verifica el descubrimiento dinámico del Pod en RunPod por LLM_POD_NOMBRE."""
    settings_dyn = mock_settings.model_copy(update={"LLM_INFERENCE_URL": None})
    req = httpx.Request("GET", "https://api.runpod.io/v2/pods")
    resp_list = httpx.Response(
        status_code=200,
        json=[
            {"id": "otro-pod", "name": "otro"},
            {"id": "podxyz123", "name": "friccion-llm"},
        ],
        request=req,
    )

    mock_http = AsyncMock(spec=httpx.AsyncClient)
    mock_http.get.return_value = resp_list

    client = LLMClient(settings=settings_dyn, client=mock_http)
    url = await client.resolve_base_url()
    assert url == "https://podxyz123-8000.proxy.runpod.net"
    assert mock_http.get.call_args[1]["headers"]["User-Agent"] == settings_dyn.LLM_USER_AGENT


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_base_url_dynamic_runpod_dict_and_errors(mock_settings: Settings) -> None:
    """Verifica variantes de respuesta de RunPod API y manejo de errores."""
    settings_no_key = mock_settings.model_copy(update={"LLM_INFERENCE_URL": None, "RUNPOD_API_KEY": ""})
    with pytest.raises(LLMClientError, match="RUNPOD_API_KEY"):
        await LLMClient(settings=settings_no_key).resolve_base_url()

    settings_dyn = mock_settings.model_copy(update={"LLM_INFERENCE_URL": None})
    req = httpx.Request("GET", "https://api.runpod.io/v2/pods")

    # Respuesta dict con clave 'pods'
    mock_http = AsyncMock(spec=httpx.AsyncClient)
    mock_http.get.return_value = httpx.Response(
        status_code=200,
        json={"pods": [{"id": "poddict1", "name": "friccion-llm"}]},
        request=req,
    )
    assert await LLMClient(settings=settings_dyn, client=mock_http).resolve_base_url() == (
        "https://poddict1-8000.proxy.runpod.net"
    )

    # Error HTTP desde RunPod API
    mock_http.get.side_effect = RuntimeError("Fallo de red RunPod")
    with pytest.raises(LLMClientError, match="Error consultando los Pods activos"):
        await LLMClient(settings=settings_dyn, client=mock_http).resolve_base_url()

    # 0 Pods coincidentes (respuesta no lista ni dict)
    mock_http.get.side_effect = None
    mock_http.get.return_value = httpx.Response(status_code=200, json="unexpected", request=req)
    with pytest.raises(LLMClientError, match="No se encontró ningún Pod"):
        await LLMClient(settings=settings_dyn, client=mock_http).resolve_base_url()

    # Múltiples Pods con el mismo nombre
    mock_http.get.return_value = httpx.Response(
        status_code=200,
        json={"data": [{"id": "p1", "name": "friccion-llm"}, {"id": "p2", "name": "friccion-llm"}]},
        request=req,
    )
    with pytest.raises(LLMClientError, match="debe existir exactamente uno"):
        await LLMClient(settings=settings_dyn, client=mock_http).resolve_base_url()

    # Pod sin id válido
    mock_http.get.return_value = httpx.Response(
        status_code=200,
        json=[{"id": "", "name": "friccion-llm"}],
        request=req,
    )
    with pytest.raises(LLMClientError, match="no contiene un identificador"):
        await LLMClient(settings=settings_dyn, client=mock_http).resolve_base_url()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_model_ready_success_and_timeout(mock_settings: Settings) -> None:
    """Verifica el polling resiliente sobre /v1/models hasta disponibilidad o timeout."""
    req = httpx.Request("GET", "https://mock-pod-8000.proxy.runpod.net/v1/models")
    resp_503 = httpx.Response(status_code=503, text="Loading", request=req)
    resp_200_empty = httpx.Response(status_code=200, json={"data": []}, request=req)
    resp_200_ok = httpx.Response(
        status_code=200,
        json={"data": [{"id": mock_settings.LLM_MODEL_NAME}]},
        request=req,
    )

    mock_http = AsyncMock(spec=httpx.AsyncClient)
    mock_http.get.side_effect = [resp_503, resp_200_empty, RuntimeError("conn reset"), resp_200_ok]

    settings_poll = mock_settings.model_copy(
        update={"LLM_READY_MAX_WAIT_SECONDS": 60.0, "LLM_READY_POLL_INTERVAL_SECONDS": 0.01}
    )
    client = LLMClient(settings=settings_poll, client=mock_http)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        await client.ensure_model_ready()
        await client.ensure_model_ready()  # segunda llamada usa caché _model_ready

    assert client._model_ready is True
    assert mock_http.get.call_count == 4

    # Caso timeout agotado
    settings_timeout = mock_settings.model_copy(
        update={"LLM_READY_MAX_WAIT_SECONDS": 0.0, "LLM_READY_POLL_INTERVAL_SECONDS": 0.01}
    )
    mock_http_fail = AsyncMock(spec=httpx.AsyncClient)
    mock_http_fail.get.return_value = resp_503
    client_fail = LLMClient(settings=settings_timeout, client=mock_http_fail)

    with pytest.raises(LLMInferenceError, match="no estuvo disponible"):
        await client_fail.ensure_model_ready()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_diagnostics_sse_and_think_cleanup(
    mock_settings: Settings,
    sample_ux_diagnostics_dict: Dict[str, Any],
) -> None:
    """Verifica consumo de streaming SSE y limpieza de bloques <think> y fences Markdown."""
    wrapped_content = (
        "<think>Razonamiento profundo sobre las capturas...</think>\n"
        f"```json\n{json.dumps(sample_ux_diagnostics_dict)}\n```"
    )
    mock_resp = _build_mock_sse_response(wrapped_content)

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = mock_resp

    client = LLMClient(settings=mock_settings, client=mock_client)
    result = await client.generate_diagnostics({"dummy": "payload"})

    assert isinstance(result.output, UxDiagnosticsOutput)
    assert result.output.name == sample_ux_diagnostics_dict["name"]
    assert result.prompt_tokens == 200
    assert result.completion_tokens == 600
    assert mock_client.post.call_args[1]["headers"]["Authorization"] == f"Bearer {mock_settings.VLLM_API_KEY}"
    assert mock_client.post.call_args[1]["headers"]["User-Agent"] == mock_settings.LLM_USER_AGENT


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_diagnostics_retry_on_524_and_503(
    mock_settings: Settings,
    sample_ux_diagnostics_dict: Dict[str, Any],
) -> None:
    """Verifica reintento automático ante Cloudflare 524 / vLLM 503 y éxito posterior."""
    req = httpx.Request("POST", "https://mock-pod-8000.proxy.runpod.net/v1/chat/completions")
    resp_524 = httpx.Response(status_code=524, text="Cloudflare Timeout", request=req)
    resp_200 = _build_mock_vllm_response(sample_ux_diagnostics_dict)

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.side_effect = [resp_524, resp_200]

    client = LLMClient(settings=mock_settings, client=mock_client)

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await client.generate_diagnostics({"dummy": "payload"})
        assert result.output.severity == "alta"
        assert mock_client.post.call_count == 2
        mock_sleep.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_diagnostics_retry_exhausted_503(mock_settings: Settings) -> None:
    """Verifica que el agotamiento de reintentos por 503 lance LLMInferenceError."""
    req = httpx.Request("POST", "https://mock-pod-8000.proxy.runpod.net/v1/chat/completions")
    resp_503 = httpx.Response(status_code=503, text="Service Unavailable", request=req)

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = resp_503

    client = LLMClient(settings=mock_settings, client=mock_client)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(LLMInferenceError, match="503"):
            await client.generate_diagnostics({"dummy": "payload"})

    assert mock_client.post.call_count == mock_settings.LLM_MAX_RETRIES + 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_diagnostics_network_timeout_retry_and_exhausted(
    mock_settings: Settings,
    sample_ux_diagnostics_dict: Dict[str, Any],
) -> None:
    """Verifica reintento ante ReadTimeout y excepción al agotar intentos."""
    resp_200 = _build_mock_vllm_response(sample_ux_diagnostics_dict)
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.side_effect = [httpx.ReadTimeout("Timed out"), resp_200]

    client = LLMClient(settings=mock_settings, client=mock_client)
    with patch("asyncio.sleep", new_callable=AsyncMock):
        res = await client.generate_diagnostics({"dummy": "payload"})
        assert res.output.name == sample_ux_diagnostics_dict["name"]

    mock_client.post.side_effect = httpx.ReadTimeout("Permanent timeout")
    with patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(LLMInferenceError, match="Agotados reintentos"):
            await client.generate_diagnostics({"dummy": "payload"})


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_diagnostics_non_retryable_400_and_loop_exit(mock_settings: Settings) -> None:
    """Verifica que HTTP 400 falle sin reintentos y cubra salida inesperada del bucle."""
    req = httpx.Request("POST", "https://mock-pod-8000.proxy.runpod.net/v1/chat/completions")
    resp_400 = httpx.Response(status_code=400, text="Bad Request", request=req)

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = resp_400

    client = LLMClient(settings=mock_settings, client=mock_client)
    with pytest.raises(LLMInferenceError, match="Error HTTP no recuperable 400"):
        await client.generate_diagnostics({"dummy": "payload"})
    assert mock_client.post.call_count == 1

    with patch("builtins.range", return_value=[]):
        with pytest.raises(LLMInferenceError, match="Fallo inesperado al invocar vLLM"):
            await client.generate_diagnostics({"dummy": "payload"})


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_diagnostics_validation_and_edge_cases(
    mock_settings: Settings,
    sample_ux_diagnostics_dict: Dict[str, Any],
) -> None:
    """Verifica errores de validación, tipos de contenido y creación interna de httpx.AsyncClient."""
    req = httpx.Request("POST", "https://mock-pod-8000.proxy.runpod.net/v1/chat/completions")
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    client = LLMClient(settings=mock_settings, client=mock_client)

    # 1. JSON incompleto -> ValidationError
    mock_client.post.return_value = _build_mock_vllm_response({"name": "Incompleto"})
    with pytest.raises(LLMResponseValidationError, match="UxDiagnosticsOutput"):
        await client.generate_diagnostics({})

    # 2. Contenido vacío
    mock_client.post.return_value = httpx.Response(
        status_code=200,
        json={"choices": [{"message": {"role": "assistant", "content": ""}}]},
        request=req,
    )
    with pytest.raises(LLMResponseValidationError, match="vacío"):
        await client.generate_diagnostics({})

    # 3. Sin choices
    mock_client.post.return_value = httpx.Response(status_code=200, json={"error": "bad"}, request=req)
    with pytest.raises(LLMResponseValidationError, match="choices"):
        await client.generate_diagnostics({})

    # 4. JSON raíz no-dict
    mock_client.post.return_value = httpx.Response(status_code=200, json=["not-a-dict"], request=req)
    with pytest.raises(LLMResponseValidationError, match="objeto válido"):
        await client.generate_diagnostics({})

    # 5. Content como dict válido
    mock_client.post.return_value = httpx.Response(
        status_code=200,
        json={"choices": [{"message": {"content": sample_ux_diagnostics_dict}}], "usage": {}},
        request=req,
    )
    res_dict = await client.generate_diagnostics({})
    assert res_dict.output.severity == "alta"

    # 6. Content tipo no soportado (int)
    mock_client.post.return_value = httpx.Response(
        status_code=200,
        json={"choices": [{"message": {"content": 12345}}]},
        request=req,
    )
    with pytest.raises(LLMResponseValidationError, match="Tipo de contenido no soportado"):
        await client.generate_diagnostics({})

    # 7. Error inesperado al parsear choices
    mock_client.post.return_value = httpx.Response(status_code=200, json={"choices": ["bad"]}, request=req)
    with pytest.raises(LLMResponseValidationError, match="Error parseando respuesta de vLLM"):
        await client.generate_diagnostics({})

    # 8. Sin cliente externo (usa async with httpx.AsyncClient())
    mock_instance = AsyncMock()
    mock_instance.get.return_value = httpx.Response(
        status_code=200,
        json=[{"id": "p-auto", "name": "friccion-llm"}],
        request=httpx.Request("GET", "https://api.runpod.io/v2/pods"),
    )
    mock_instance.post.return_value = _build_mock_vllm_response(sample_ux_diagnostics_dict)

    settings_dyn = mock_settings.model_copy(update={"LLM_INFERENCE_URL": None})
    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = mock_instance
        client_auto = LLMClient(settings=settings_dyn, client=None)
        res_auto = await client_auto.generate_diagnostics({})
        assert res_auto.output.name == sample_ux_diagnostics_dict["name"]


@pytest.mark.unit
def test_llm_client_headers_without_vllm_api_key() -> None:
    """Verifica cabeceras HTTP cuando VLLM_API_KEY está vacía o con espacios."""
    for key in ("", "   ", None):
        client = LLMClient(settings=Settings(_env_file=None, VLLM_API_KEY=key))
        headers = client._get_headers()
        assert "Authorization" not in headers
        assert headers["User-Agent"] == "eureka-insights/1.0"
