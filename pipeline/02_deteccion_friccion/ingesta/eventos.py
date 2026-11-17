"""BigQuery: eventos de un cliente en el formato que espera el preprocesamiento.

La salida tiene las columnas y formatos que espera preprocesamiento/.
"""
import json
from datetime import date

import numpy as np
import pandas as pd
from google.cloud import bigquery

from ingesta.clientes import FuenteEventos

COLUMNAS = ["id_usuario", "nombre_evento", "tipo_evento", "ruta", "timestamp", "detalle_click",
            "termino_busqueda", "porcentaje_scroll", "tiempo_engagement_ms", "items", "promociones",
            "pais", "ciudad", "tipo_dispositivo", "navegador", "sistema_operativo", "id_sesion"]
NUMERICAS = ("porcentaje_scroll", "tiempo_engagement_ms")


def consulta(fuente: FuenteEventos, desde: date | None, hasta: date | None) -> tuple[str, list]:
    """SQL parametrizado. Filtra por cliente (clustering) y, si se da, por fecha_evento (partición): BigQuery
    lee solo los bloques de ese cliente y ese período. El período de cada corrida está pendiente de definir."""
    where = ["cliente_id = @cliente_id"]
    params = [bigquery.ScalarQueryParameter("cliente_id", "STRING", fuente.cliente_id)]
    if desde is not None:
        where.append("fecha_evento >= @desde")
        params.append(bigquery.ScalarQueryParameter("desde", "DATE", desde))
    if hasta is not None:
        where.append("fecha_evento <= @hasta")
        params.append(bigquery.ScalarQueryParameter("hasta", "DATE", hasta))
    columnas = ", ".join(COLUMNAS)
    return f"select {columnas} from {fuente.tabla} where {' and '.join(where)}", params


def rango_fechas(fuente: FuenteEventos, gcp_project: str) -> tuple[date, date] | None:
    """Primer y último fecha_evento del cliente (None si no tiene eventos). La ventana cuenta hacia atrás
    desde el último día con datos, no desde el calendario: sirve para un cliente con datos históricos y no
    falla si el export de GA4 se atrasa. Lee solo la columna fecha_evento de los bloques del cliente."""
    sql = f"select min(fecha_evento), max(fecha_evento) from {fuente.tabla} where cliente_id = @cliente_id"
    cfg = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("cliente_id", "STRING", fuente.cliente_id)],
        labels={"modulo": "friccion"})
    cliente = bigquery.Client(project=gcp_project, location=fuente.bq_ubicacion)
    primero, ultimo = next(iter(cliente.query(sql, job_config=cfg).result()))
    return None if ultimo is None else (primero, ultimo)


def contar_eventos_dia(fuente: FuenteEventos, gcp_project: str, dia: date) -> int:
    """Eventos del cliente en un día (guarda inicial del módulo: si es 0 no hay nada que procesar). Lee una sola
    partición y solo los bloques del cliente."""
    sql = f"select count(*) from {fuente.tabla} where cliente_id = @cliente_id and fecha_evento = @dia"
    cfg = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("cliente_id", "STRING", fuente.cliente_id),
        bigquery.ScalarQueryParameter("dia", "DATE", dia)], labels={"modulo": "friccion"})
    cliente = bigquery.Client(project=gcp_project, location=fuente.bq_ubicacion)
    return int(next(iter(cliente.query(sql, job_config=cfg).result()))[0])


def leer_eventos(fuente: FuenteEventos, gcp_project: str, desde: date | None = None,
                 hasta: date | None = None, max_bytes: int | None = None) -> pd.DataFrame:
    """Eventos del cliente, ordenados por usuario y tiempo.

    max_bytes: tope de bytes a procesar (BigQuery rechaza la consulta antes de correrla si lo supera).
    """
    sql, params = consulta(fuente, desde, hasta)
    cliente = bigquery.Client(project=gcp_project, location=fuente.bq_ubicacion)
    cfg = bigquery.QueryJobConfig(query_parameters=params, labels={"modulo": "friccion"})
    if max_bytes is not None:   # la API rechaza None: solo se setea si hay tope
        cfg.maximum_bytes_billed = max_bytes
    df = cliente.query(sql, job_config=cfg).to_dataframe()
    return a_formato_motor(df)


def _nombres(valor, campo: str):
    """JSON de GA4 (lista de objetos) -> "nombre1; nombre2"; nulo si no hay ninguno. Un texto que no es JSON
    (otra fuente) se deja como está."""
    if not isinstance(valor, str):
        return np.nan
    try:
        lista = json.loads(valor)
    except ValueError:
        return valor
    if lista is None:   # TO_JSON_STRING de un valor nulo da el texto "null"
        return np.nan
    if not isinstance(lista, list):
        return valor
    nombres = [str(o[campo]) for o in lista if isinstance(o, dict) and o.get(campo) not in (None, "")]
    return "; ".join(nombres) if nombres else np.nan


def a_formato_motor(df: pd.DataFrame) -> pd.DataFrame:
    """Tipos y convenciones que espera preprocesamiento/:
    - timestamp como texto 'AAAA-MM-DD HH:MM:SS.ffffff UTC' (lo parsea preprocessing._parse_timestamp);
    - numéricos como float con NaN y nulos de texto como NaN; los valores de texto no se tocan;
    - orden por usuario y tiempo. BigQuery no garantiza orden de filas; si hay dos eventos del mismo usuario
      en el mismo instante, el motor reordena los momentos simultáneos con el orden aprendido en detección (datos_tramos.orden_tipico). nombre_evento solo
      desempata para que el resultado sea determinista."""
    df = df.reindex(columns=COLUMNAS).copy()
    ts = pd.to_datetime(df["timestamp"], utc=True)
    df["timestamp"] = ts.dt.strftime("%Y-%m-%d %H:%M:%S.%f") + " UTC"
    for c in NUMERICAS:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    df["id_sesion"] = pd.to_numeric(df["id_sesion"], errors="coerce").astype("Int64")   # ga_session_id; nulo si GA4 no lo mandó
    # La extracción guarda items y promociones como JSON de GA4; el motor los usa como nombres separados por "; "
    df["items"] = df["items"].map(lambda x: _nombres(x, "item_name"))
    df["promociones"] = df["promociones"].map(lambda x: _nombres(x, "promotion_name"))
    for c in set(COLUMNAS) - {"timestamp", "id_sesion", *NUMERICAS}:
        df[c] = df[c].astype("object").where(df[c].notna(), np.nan)
    orden = np.lexsort((df["nombre_evento"].fillna("").to_numpy(), ts.to_numpy(), df["id_usuario"].to_numpy()))
    return df.iloc[orden].reset_index(drop=True)
