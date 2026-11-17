"""Punto de entrada del módulo 2 (detección de fricción) como Cloud Run Job: una tarea = un cliente.

Contrato con el orquestador (workflow orquestador-pipeline):
- Entrada por variables de entorno: FECHA_EJECUCION (T, "AAAA-MM-DD"; se procesan los datos hasta T-1),
  IDS_CLIENTES (JSON), CLOUD_RUN_TASK_INDEX (qué cliente de la lista le toca a esta tarea),
  CLOUD_RUN_TASK_ATTEMPT. Credenciales: ADC (BigQuery, Cloud Storage) y SUPABASE_DB_URL_MODULO.
- Guarda inicial: sin eventos de T-1, o con menos sesiones que el umbral de entrenamiento -> log INFO y exit 0.
  Sin patrones detectados también es un resultado válido (exit 0). Error -> log ERROR y exit 1.
- Escritura atómica: todo en memoria, el modelo a GCS (o local) y recién después una sola transacción en
  BigQuery (modulo/escritura.py).

Flujo por cliente: ventana (últimas 14.500 sesiones hasta T-1) -> si no tiene modelo, entrena -> detecta -> si la
AUC del día cae debajo del IC95 inferior de la del entrenamiento, reentrena (mismos eventos clave y grupos) y
vuelve a detectar -> selecciona los patrones a publicar (modulo/seleccion.py) -> guarda el modelo nuevo -> escribe
patrones, sesión representativa y registro del modelo.

Eventos clave: los elige el LLM (Pod de RunPod que levanta otro proceso). EVENTOS_CLAVE="a,b,objetivo" los fija a
mano (solo pruebas; queda en el log).

Local:
    python -m modulo.principal --cliente <id> --fecha 2021-02-01 [--eventos-clave select_item,...,purchase] [--simular]
Cloud Run Job:
    python -m modulo.principal
"""
import argparse
import json
import os
import sys
import time
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # raíz del repo
from modulo import registro  # noqa: E402

log = registro.logger("principal")


def procesar_cliente(id_cliente: str, fecha_ejecucion: str, eventos_clave: list[str] | None,
                     simular: bool = False) -> dict:
    from google.cloud import bigquery
    from ingesta.clientes import buscar_fuente
    from ingesta.config_nube import cargar_config
    from ingesta.eventos import contar_eventos_dia, leer_eventos, rango_fechas
    from modulo import almacen, deteccion, escritura, seleccion, ventana as VEN
    from modulo.entrenamiento import entrenar_cliente, UMBRAL_ENTRENAMIENTO

    T = date.fromisoformat(fecha_ejecucion)
    hasta = T - timedelta(days=1)
    cfg = cargar_config()
    fuente = buscar_fuente(id_cliente, cfg.supabase_db_url)

    n_dia = contar_eventos_dia(fuente, cfg.gcp_project, hasta)
    if n_dia == 0:
        log.info(f"Sin eventos del {hasta} para este cliente. Se omite.", extra={"dia_datos": str(hasta)})
        return dict(estado="OMITIDO_SIN_EVENTOS")
    rango = rango_fechas(fuente, cfg.gcp_project)
    v = VEN.armar_ventana(lambda d, h: leer_eventos(fuente, cfg.gcp_project, d, h), rango[0], hasta)
    if v.sesiones < UMBRAL_ENTRENAMIENTO:
        log.info(f"{v.sesiones:,} sesiones, menos que el mínimo de {UMBRAL_ENTRENAMIENTO:,}. Se omite.",
                 extra={"sesiones": v.sesiones, "umbral": UMBRAL_ENTRENAMIENTO})
        return dict(estado="OMITIDO_POCAS_SESIONES", sesiones=v.sesiones)

    bq = bigquery.Client(project=cfg.gcp_project, location="US")
    vigente = almacen.ultimo_modelo(bq, cfg.gcp_project, id_cliente)
    nuevo = None
    if vigente is None:
        log.info("El cliente no tiene modelo: se entrena", extra={"paso": "Modelo"})
        r = entrenar_cliente(id_cliente, v, fecha_ejecucion, eventos_clave)
        modelo, nuevo = r
    else:
        with registro.paso(log, "Carga del modelo", id_modelo=vigente["id_modelo"]):
            modelo = almacen.cargar_modelo(vigente["artefacto"])

    with registro.paso(log, "Detección") as res:
        patrones, resumen = deteccion.detectar(modelo, v.eventos, log)
        res.update(resumen)

    if vigente is not None and resumen["auc_del_dia"] < vigente["auc_ic95_inf"]:
        log.warning(f"AUC del día {resumen['auc_del_dia']} < IC95 inferior del entrenamiento "
                    f"{vigente['auc_ic95_inf']}: se reentrena", extra={"paso": "Modelo"})
        modelo, nuevo = entrenar_cliente(id_cliente, v, fecha_ejecucion, base=modelo)
        with registro.paso(log, "Detección con el modelo nuevo") as res:
            patrones, resumen = deteccion.detectar(modelo, v.eventos, log)
            res.update(resumen)

    with registro.paso(log, "Selección de patrones") as res:
        patrones, resumen_sel = seleccion.seleccionar(patrones, id_cliente)
        res.update(resumen_sel)

    if simular:
        pats, pasos = escritura.filas(patrones, id_cliente, modelo["id_modelo"], fecha_ejecucion)
        log.info("Simulación: no se guarda el modelo ni se escribe en BigQuery",
                 extra={"patrones": len(pats), "pasos_sesion": len(pasos), "modelo_nuevo": bool(nuevo),
                        "top3": [" > ".join(p["secuencia"]) for p in pats[:3]]})
        return dict(estado="SIMULADO", patrones=len(pats), id_modelo=modelo["id_modelo"])

    if nuevo:
        with registro.paso(log, "Guardado del modelo") as res:
            nuevo["artefacto"] = almacen.guardar_modelo(modelo, id_cliente, fecha_ejecucion)
            res.update(id_modelo=nuevo["id_modelo"], artefacto=nuevo["artefacto"])

    with registro.paso(log, "Escritura en BigQuery") as res:
        pats, pasos = escritura.filas(patrones, id_cliente, modelo["id_modelo"], fecha_ejecucion)
        res.update(patrones=len(pats), pasos_sesion=len(pasos), modelo_nuevo=bool(nuevo),
                   **escritura.escribir(bq, cfg.gcp_project, pats, pasos, nuevo))
    if not pats:
        log.info("El modelo no detectó patrones de fricción en la ventana (resultado válido)")
    return dict(estado="OK", patrones=len(pats), id_modelo=modelo["id_modelo"])


def ejecutar_tarea() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cliente"); ap.add_argument("--fecha"); ap.add_argument("--eventos-clave")
    ap.add_argument("--simular", action="store_true", help="no guarda el modelo ni escribe en BigQuery")
    a = ap.parse_args()
    indice = int(os.environ.get("CLOUD_RUN_TASK_INDEX", "0"))
    intento = int(os.environ.get("CLOUD_RUN_TASK_ATTEMPT", "0"))
    fecha = a.fecha or os.environ.get("FECHA_EJECUCION")
    ids = [a.cliente] if a.cliente else json.loads(os.environ.get("IDS_CLIENTES", "[]"))
    if fecha:
        registro.fecha_ejecucion_ctx.set(fecha)
    if not fecha or indice >= len(ids):
        log.warning("Sin FECHA_EJECUCION o índice de tarea fuera de rango. Finalizando sin acción.",
                    extra={"indice_tarea": indice, "clientes": len(ids)})
        sys.exit(0)
    id_cliente = ids[indice]
    registro.id_cliente_ctx.set(id_cliente)
    ek = a.eventos_clave or os.environ.get("EVENTOS_CLAVE")
    t = time.time()
    try:
        log.info("Iniciando detección de fricción", extra={"intento": intento})
        r = procesar_cliente(id_cliente, fecha, ek.split(",") if ek else None, simular=a.simular)
        log.info("Detección de fricción finalizada", extra={"duracion_s": round(time.time() - t, 1), **r})
        sys.exit(0)
    except Exception as e:
        log.exception(f"Error en detección de fricción: {e}", extra={"intento": intento,
                                                                    "duracion_s": round(time.time() - t, 1)})
        sys.exit(1)


if __name__ == "__main__":
    ejecutar_tarea()
