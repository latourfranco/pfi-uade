"""Dónde se guardan y de dónde se cargan los modelos.

Ruta determinística (reglas de orquestación, sección 4): modelos/{id_cliente}/{fecha_ejecucion}/modelo.pkl,
sobreescribiendo un archivo previo del mismo ciclo.
- Con la variable MODELOS_BUCKET (Cloud Run): gs://<MODELOS_BUCKET>/modelos/...
- Sin ella (local): resultados/modelos/...
El registro de cuál es el modelo vigente de cada cliente es la tabla friccion_resultados.modelos (el más
reciente por `entrenado`); su columna artefacto tiene la ruta.
"""
import io
import os

import torch

from modulo.config import RAIZ

DIR_LOCAL = os.path.join(RAIZ, "resultados")


def ruta_modelo(id_cliente: str, fecha_ejecucion: str) -> str:
    rel = f"modelos/{id_cliente}/{fecha_ejecucion}/modelo.pkl"
    bucket = os.environ.get("MODELOS_BUCKET")
    return f"gs://{bucket}/{rel}" if bucket else os.path.join(DIR_LOCAL, *rel.split("/"))


def guardar_modelo(modelo: dict, id_cliente: str, fecha_ejecucion: str) -> str:
    ruta = ruta_modelo(id_cliente, fecha_ejecucion)
    if ruta.startswith("gs://"):
        from google.cloud import storage
        buf = io.BytesIO(); torch.save(modelo, buf)
        bucket, nombre = ruta[5:].split("/", 1)
        storage.Client().bucket(bucket).blob(nombre).upload_from_string(buf.getvalue(),
                                                                        content_type="application/octet-stream")
    else:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        torch.save(modelo, ruta)
    return ruta


def cargar_modelo(ruta: str) -> dict:
    if ruta.startswith("gs://"):
        from google.cloud import storage
        bucket, nombre = ruta[5:].split("/", 1)
        datos = storage.Client().bucket(bucket).blob(nombre).download_as_bytes()
        return torch.load(io.BytesIO(datos), weights_only=False)
    return torch.load(ruta, weights_only=False)


def ultimo_modelo(bq, proyecto: str, id_cliente: str) -> dict | None:
    """Fila del modelo vigente del cliente en friccion_resultados.modelos, o None si nunca se entrenó."""
    from google.cloud import bigquery
    sql = f"""select * from `{proyecto}.friccion_resultados.modelos` where id_cliente = @c
              order by entrenado desc limit 1"""
    cfg = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("c", "STRING", id_cliente)],
                                  labels={"modulo": "friccion"})
    filas = list(bq.query(sql, job_config=cfg).result())
    return dict(filas[0].items()) if filas else None
