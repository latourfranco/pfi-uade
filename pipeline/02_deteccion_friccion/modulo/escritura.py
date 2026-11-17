"""Escritura de resultados en BigQuery, atómica e idempotente (reglas de orquestación, sección 4).

1. Se cargan los datos a tablas temporales con jobs de carga (no se cobran).
2. Un solo script con BEGIN TRANSACTION ... COMMIT:
   - patrones: MERGE por id_patron (si existe se actualizan cifras, id_modelo y ultima_deteccion; primera_deteccion
     no se toca). Reglas acordadas con el usuario el 2026-11-14/15;
   - sesion_representativa: solo para patrones que todavía no tienen (se explora una sola vez);
   - modelos: MERGE por id_modelo (re-correr el mismo ciclo no duplica el registro).
   Si algo falla, la transacción se revierte: no queda ningún patrón de ese cliente y ciclo a medio escribir.
3. Las temporales se borran siempre.
El modelo ya tiene que estar guardado (GCS o local) antes de llamar acá.
"""
import hashlib
import json
import uuid

from google.cloud import bigquery

DATASET = "friccion_resultados"


def id_patron(id_cliente: str, objetivo: str, secuencia: list[str]) -> str:
    """Hash de cliente + objetivo + secuencia: el mismo patrón tiene el mismo id en todas las corridas."""
    clave = json.dumps([id_cliente, objetivo, secuencia], ensure_ascii=False)
    return hashlib.sha256(clave.encode()).hexdigest()[:32]


def filas(patrones: list[dict], id_cliente: str, id_modelo: str, fecha: str) -> tuple[list[dict], list[dict]]:
    """Filas de patrones y de sesion_representativa a partir de deteccion.detectar."""
    pats, pasos = [], []
    for p in patrones:
        idp = id_patron(id_cliente, p["objetivo"], p["secuencia"])
        pats.append(dict(id_patron=idp, id_cliente=id_cliente, objetivo=p["objetivo"], secuencia=p["secuencia"],
                         sesiones=p["sesiones"], usuarios=p["usuarios"], llegada_grupo=p["llegada_grupo"],
                         llegada_referencia=p["llegada_referencia"], sesiones_perdidas=p["sesiones_perdidas"],
                         id_modelo=id_modelo, primera_deteccion=fecha, ultima_deteccion=fecha))
        for k, x in enumerate(p["pasos"], 1):
            pasos.append(dict(id_patron=idp, orden=k, **x))
    return pats, pasos


def escribir(bq: bigquery.Client, proyecto: str, patrones: list[dict], pasos: list[dict],
             modelo: dict | None) -> dict:
    T = lambda n: f"`{proyecto}.{DATASET}.{n}`"  # noqa: E731
    temporales, stmts = [], []

    def temporal(destino, datos):
        tabla = f"{proyecto}.{DATASET}._carga_{uuid.uuid4().hex[:12]}"
        cfg = bigquery.LoadJobConfig(schema=bq.get_table(f"{proyecto}.{DATASET}.{destino}").schema,
                                     source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
                                     write_disposition="WRITE_TRUNCATE")
        bq.load_table_from_json(datos, tabla, job_config=cfg).result()
        temporales.append(tabla)
        return f"`{tabla}`"

    try:
        if modelo:
            tm = temporal("modelos", [modelo])
            stmts.append(f"""MERGE {T('modelos')} T USING {tm} S ON T.id_modelo = S.id_modelo
                WHEN MATCHED THEN UPDATE SET entrenado = S.entrenado, datos_desde = S.datos_desde,
                  datos_hasta = S.datos_hasta, sesiones = S.sesiones, objetivo = S.objetivo,
                  eventos_clave = S.eventos_clave, nombres_hitos = S.nombres_hitos, auc = S.auc, auc_ic95_inf = S.auc_ic95_inf, artefacto = S.artefacto
                WHEN NOT MATCHED THEN INSERT ROW;""")
        if patrones:
            tp = temporal("patrones", patrones)
            stmts.append(f"""MERGE {T('patrones')} T USING {tp} S ON T.id_patron = S.id_patron
                WHEN MATCHED THEN UPDATE SET sesiones = S.sesiones, usuarios = S.usuarios,
                  llegada_grupo = S.llegada_grupo, llegada_referencia = S.llegada_referencia,
                  sesiones_perdidas = S.sesiones_perdidas, id_modelo = S.id_modelo, ultima_deteccion = S.ultima_deteccion
                WHEN NOT MATCHED THEN INSERT ROW;""")
        if pasos:
            ts = temporal("sesion_representativa", pasos)
            stmts.append(f"""INSERT INTO {T('sesion_representativa')}
                SELECT * FROM {ts} WHERE id_patron NOT IN (SELECT DISTINCT id_patron FROM {T('sesion_representativa')});""")
        if not stmts:
            return dict(job_id=None, bytes_procesados=0)
        job = bq.query("BEGIN TRANSACTION;\n" + "\n".join(stmts) + "\nCOMMIT TRANSACTION;",
                       job_config=bigquery.QueryJobConfig(labels={"modulo": "friccion"}))
        job.result()
        return dict(job_id=job.job_id, bytes_procesados=job.total_bytes_processed or 0)
    finally:
        for t in temporales:
            bq.delete_table(t, not_found_ok=True)
