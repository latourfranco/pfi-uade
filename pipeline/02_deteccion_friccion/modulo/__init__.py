"""Módulo de detección de fricción para producción (local -> Cloud Run Job -> Workflows).

Cada paso es una función que recibe y devuelve datos (entrada: python -m modulo.principal):

    ventana (ingesta.eventos + preparar) -> entrenamiento o modelo guardado (almacen) -> deteccion
    -> seleccion -> escritura

El LLM que elige los eventos clave corre en un Pod de RunPod que levanta otro proceso; el módulo solo lo
encuentra (llm.buscar_endpoint) y le consulta.
"""
