"""Cliente del LLM que corre en un Pod de RunPod (vLLM, API compatible con OpenAI).

El módulo NO prende ni apaga el Pod (decidido con el usuario, 2026-11-15): otro proceso lo levanta antes de la
corrida. Acá solo se lo busca por nombre con la API de RunPod (alcanza con permiso de lectura de Pods) y se le
consulta por el proxy HTTP de RunPod: https://<id>-<puerto>.proxy.runpod.net/v1.

Variables de entorno: RUNPOD_API_KEY, LLM_POD_NOMBRE, VLLM_API_KEY.
"""
import json

import requests

from modulo.config import RUNPOD_API, LLM_MODELO, LLM_PARAMETROS, LLM_PUERTO, LLM_TIMEOUT_S, env


class LLMNoDisponible(RuntimeError):
    """No hay un Pod corriendo con ese nombre, o el modelo todavía no contesta."""


def buscar_endpoint() -> str:
    """URL base (…/v1) del vLLM del Pod LLM_POD_NOMBRE que está corriendo, verificando que sirve LLM_MODELO."""
    nombre = env("LLM_POD_NOMBRE")
    r = requests.get(f"{RUNPOD_API}/pods", headers={"Authorization": f"Bearer {env('RUNPOD_API_KEY')}"}, timeout=30)
    r.raise_for_status()
    pods = [p for p in r.json()["pods"] if p.get("name") == nombre and p.get("status") == "RUNNING"]
    if not pods:
        raise LLMNoDisponible(f"no hay ningún Pod corriendo con el nombre {nombre!r}")
    if len(pods) > 1:
        raise LLMNoDisponible(f"hay {len(pods)} Pods corriendo con el nombre {nombre!r}: {[p['id'] for p in pods]}")
    pod = pods[0]
    if f"{LLM_PUERTO}/http" not in pod.get("ports", []):
        raise LLMNoDisponible(f"el Pod {pod['id']} no expone {LLM_PUERTO}/http (expone {pod.get('ports')})")
    url = f"https://{pod['id']}-{LLM_PUERTO}.proxy.runpod.net/v1"
    try:
        m = requests.get(f"{url}/models", headers=_auth(), timeout=30)
    except requests.RequestException as e:
        raise LLMNoDisponible(f"el Pod {pod['id']} no contesta todavía ({type(e).__name__})") from e
    if not m.ok:
        raise LLMNoDisponible(f"el Pod {pod['id']} contesta {m.status_code}: el modelo todavía está cargando o la clave no coincide")
    modelos = [x["id"] for x in m.json().get("data", [])]
    if LLM_MODELO not in modelos:
        raise LLMNoDisponible(f"el Pod {pod['id']} sirve {modelos}, no {LLM_MODELO}")
    return url


def _auth() -> dict:
    # User-Agent propio: el proxy de RunPod está detrás de Cloudflare, que rechaza (403) clientes con el
    # User-Agent por defecto de algunas librerías (visto con urllib desde Cloud Shell, 2026-11-15)
    return {"Authorization": f"Bearer {env('VLLM_API_KEY')}", "User-Agent": "modulo-friccion/0.1"}


def consultar_json(url: str, mensajes: list[dict], esquema: dict) -> dict:
    """Una consulta con respuesta JSON que cumple `esquema` (decodificación guiada de vLLM), con modo pensamiento
    (config.LLM_PARAMETROS). Devuelve el JSON más el razonamiento y el uso de tokens, para dejarlos registrados.

    En streaming: el proxy de RunPod está detrás de Cloudflare, que corta (524) una respuesta que tarda más de
    ~100 s en llegar, y con el modo pensamiento una consulta tarda 3-5 min. Sin reintentos automáticos (un
    reintento puede dejar la primera consulta corriendo en el Pod): si falla, el error sube con su motivo."""
    cuerpo = {"model": LLM_MODELO, "messages": mensajes, **LLM_PARAMETROS,
              "response_format": {"type": "json_schema", "json_schema": {"name": "respuesta", "schema": esquema}},
              "stream": True, "stream_options": {"include_usage": True}}
    texto, razon, uso, fin = [], [], {}, None
    with requests.post(f"{url}/chat/completions", headers=_auth(), json=cuerpo, timeout=LLM_TIMEOUT_S, stream=True) as r:
        if not r.ok:
            raise RuntimeError(f"el LLM respondió {r.status_code}: {r.text[:500]}")
        for linea in r.iter_lines(decode_unicode=True):
            if not linea or not linea.startswith("data:") or linea.strip() == "data: [DONE]":
                continue
            d = json.loads(linea[5:])
            uso = d.get("usage") or uso
            for c in d.get("choices", []):
                delta = c.get("delta", {})
                razon.append(delta.get("reasoning_content") or delta.get("reasoning") or "")
                texto.append(delta.get("content") or "")
                fin = c.get("finish_reason") or fin
    texto = "".join(texto)
    if fin != "stop":
        raise RuntimeError(f"el LLM no terminó la respuesta (finish_reason={fin!r}): {texto[:300]!r}")
    try:
        respuesta = json.loads(texto)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"el LLM no devolvió JSON válido: {texto[:500]!r}") from e
    return dict(respuesta=respuesta, razonamiento="".join(razon), uso=uso)
