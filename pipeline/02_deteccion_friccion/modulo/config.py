"""Parámetros del módulo de producción. Cada valor con su fuente (PLAN §14)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # raíz del repo
from preprocesamiento.config import RAIZ  # noqa: E402,F401

# --- Ventana (PLAN §14, "Ventana única", 2026-11-15) --------------------------------------------------
# Entrenamiento y corrida diaria leen las últimas VENTANA_SESIONES sesiones válidas (umbral de ejecución,
# codo de potencia.py). Valor de este sitio con un método repetible. Cómo se arma la ventana: pendiente.
VENTANA_SESIONES = 14_500

# --- Sesión (decidido con el usuario, 2026-11-15) -------------------------------------------------------
# La sesión es la de GA4 (ga_session_id, que la extracción guarda como id_sesion). Si un evento llega sin
# ella (cookies rechazadas, Measurement Protocol), se calcula como GA4: corte por 30 min de inactividad.
SESION_SIN_ID_S = 1800

# --- LLM para elegir los eventos clave ------------------------------------------------------------------
# Pod de RunPod levantado por otro proceso; el módulo lo busca por nombre (API REST v2; la v1 se retiró el
# 2026-11-15) y le habla por el proxy HTTP de RunPod al vLLM del contenedor.
RUNPOD_API = "https://api.runpod.io/v2"
LLM_MODELO = "cyankiwi/Qwen3.5-27B-AWQ-4bit"
LLM_PUERTO = 8000
LLM_TIMEOUT_S = 900   # con modo pensamiento una consulta tarda 3-5 min (medido 2026-11-15)
# Modo pensamiento (2026-11-15): sin él, el modelo aplicaba las reglas de la consigna de forma despareja (bien en un
# sitio, mal en otro); razonando, acertó en este sitio y en dos sitios de otro tipo. Parámetros recomendados en la
# página del modelo para el modo pensamiento, con semilla fija: la misma consulta da la misma respuesta.
LLM_PARAMETROS = dict(temperature=0.6, top_p=0.95, top_k=20, seed=0, max_tokens=20_000,
                      chat_template_kwargs={"enable_thinking": True})


def env(nombre: str) -> str:
    """Variable de entorno; en local la toma del .env (gitignored). En Cloud Run llega por Secret Manager."""
    v = os.environ.get(nombre)
    if v is None:
        from dotenv import dotenv_values
        v = dotenv_values(os.path.join(RAIZ, ".env")).get(nombre)
    if not v:
        raise RuntimeError(f"Falta la variable de entorno {nombre}")
    return v.strip()
