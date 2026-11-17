"""Entrenamiento de producción de un cliente: ventana -> preprocesamiento aprendido -> eventos clave -> red ->
artefacto + fila en friccion_resultados.modelos.

- No entrena si la ventana tiene menos de UMBRAL_ENTRENAMIENTO sesiones (PLAN §14; decidido con el usuario,
  2026-11-15: un cliente con pocos datos no entrena).
- Eventos clave: los elige el LLM (Pod de RunPod que levanta otro proceso). Para pruebas se pueden pasar a
  mano (eventos_clave=[...], el objetivo al final); el log y el artefacto dicen de dónde salieron.
- El modelo (reglas de rutas, orden de eventos simultáneos, grupos de páginas, vocabulario, eventos clave y su
  orden, pesos de la red, temperatura) se devuelve en memoria; lo guarda modulo/almacen.py.
"""
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # raíz del repo
from modulo import registro, nodos, embudo, red as R  # noqa: E402
from modulo.ventana import Ventana  # noqa: E402

UMBRAL_ENTRENAMIENTO = 2_667   # sesiones (PLAN §14, umbral de entrenamiento)
log = registro.logger("entrenamiento")


def elegir_eventos_clave(prep: pd.DataFrame, manual: list[str] | None) -> dict:
    """Eventos clave (el objetivo al final) y de dónde salieron."""
    if manual:
        log.warning("Eventos clave pasados a mano, no los eligió el LLM", extra={"eventos_clave": manual})
        return dict(clave=list(manual), objetivo=manual[-1], origen="manual", hitos=None)
    from modulo import eventos_clave as EC, llm
    from modulo.config import LLM_MODELO
    resumen = EC.resumir_eventos(prep)
    url = llm.buscar_endpoint()
    log.info(f"LLM encontrado; consultando ({len(resumen['eventos'])} tipos de evento)", extra={"modelo": LLM_MODELO})
    r = llm.consultar_json(url, EC.mensajes(resumen), EC.ESQUEMA)
    hitos = EC.validar(r["respuesta"], resumen)
    objetivo = next(h["evento"] for h in hitos if h["es_objetivo_principal"])
    clave = [h["evento"] for h in hitos if h["evento"] != objetivo] + [objetivo]
    return dict(clave=clave, objetivo=objetivo, origen=f"llm:{LLM_MODELO}", hitos=hitos, uso=r["uso"])


def nombres_hitos(ek: dict) -> list[str]:
    """Nombre legible de cada evento clave, en el mismo orden que ek["clave"] (2026-11-17, pedido del usuario: que
    los reportes muestren el nombre que eligió el LLM y no el del evento). Sin LLM (eventos clave a mano) no hay
    nombres: lista vacía."""
    if not ek.get("hitos"):
        return []
    por_evento = {h["evento"]: h["nombre_legible"] for h in ek["hitos"]}
    return [por_evento[e] for e in ek["clave"]]


def entrenar_cliente(id_cliente: str, v: Ventana, fecha_ejecucion: str, eventos_clave: list[str] | None = None,
                     base: dict | None = None) -> tuple[dict, dict] | None:
    """Entrena con la ventana del cliente, en memoria. Devuelve (modelo, fila del registro de modelos), o None si
    no entrena. Guardar el modelo (GCS o local) y registrarlo lo hace quien llama (principal.py), en ese orden y
    antes de escribir resultados: escritura atómica (reglas de orquestación, sección 4).
    base: modelo anterior del cliente (reentrenamiento). Se reutilizan sus reglas de rutas, orden de eventos,
    grupos de páginas y eventos clave, y el vocabulario solo suma nodos nuevos: así los nodos, los objetivos y los
    id_patron no cambian (los eventos clave se deciden una vez por cliente)."""
    registro.id_cliente_ctx.set(id_cliente)
    if v.sesiones < UMBRAL_ENTRENAMIENTO:
        log.warning(f"No se entrena: {v.sesiones:,} sesiones, el mínimo es {UMBRAL_ENTRENAMIENTO:,}",
                    extra={"sesiones": v.sesiones, "umbral": UMBRAL_ENTRENAMIENTO})
        return None
    entrenado = datetime.now(timezone.utc)
    id_modelo = f"{id_cliente}_{fecha_ejecucion}"   # uno por cliente y ciclo: la ruta en GCS es determinística
    prep = v.eventos

    if base:
        apr, ek = base["aprendido"], base["eventos_clave"]
        log.info("Reentrenamiento: se reutilizan reglas de rutas, grupos de páginas y eventos clave del modelo "
                 "anterior", extra={"paso": "Preprocesamiento aprendido", "modelo_anterior": base["id_modelo"]})
    else:
        with registro.paso(log, "Preprocesamiento aprendido") as res:
            apr, tabla_grupos = nodos.aprender(prep)
            g = tabla_grupos[tabla_grupos.grupo != "sola"]
            res.update(plantillas=len(tabla_grupos), grupos=g.grupo.nunique(), paginas_agrupadas=len(g),
                       paginas_solas=int((tabla_grupos.grupo == "sola").sum()))
        for grupo, d in g.sort_values("visitas", ascending=False).groupby("grupo", sort=False):
            log.info(f"Grupo {grupo}: {len(d)} páginas, p. ej. {', '.join(d.pagina.head(3))}",
                     extra={"paso": "Preprocesamiento aprendido"})

        with registro.paso(log, "Eventos clave") as res:
            ek = elegir_eventos_clave(prep, eventos_clave)
            res.update(eventos_clave=ek["clave"], objetivo=ek["objetivo"], origen=ek["origen"])
            if ek["hitos"]:
                for h in ek["hitos"]:
                    log.info(f"Hito {h['evento']} ({h['nombre_legible']}): {h['motivo']}", extra={"paso": "Eventos clave"})

    with registro.paso(log, "Secuencias y embudo") as res:
        ses = nodos.secuencias(prep, apr)
        vocab = nodos.vocabulario(ses)
        if base:   # los nodos del modelo anterior se conservan; se suman los nuevos
            vocab = {t: i for i, t in enumerate(sorted(set(base["vocab"]) | set(vocab)))}
        clave = ek["clave"]
        faltan = [e for e in clave if not any(t.split("@")[0] == e for t in vocab)]
        if faltan:
            raise ValueError(f"eventos clave que no aparecen en la ventana: {faltan}")
        A = embudo.construir(nodos.a_ids(ses, vocab), ses.user.values, embudo.evbit(vocab, clave))
        orden = embudo.aprender_orden(A, len(clave))
        PEND, NEXT = embudo.logros(A, orden)
        goal = embudo.objetivos(A, PEND, orden)
        valid, y, _ = embudo.etiquetas(A, PEND, NEXT, goal)
        llegan = {clave[b]: round(100 * float(np.bincount(A["S"][~PEND[b]], minlength=A["nses"]).astype(bool).mean()), 1)
                  for b in range(len(clave))}
        res.update(sesiones=A["nses"], usuarios=A["nus"], nodos=len(vocab), pasos=A["n"],
                   orden_embudo=" -> ".join(clave[i] for i in orden), pct_sesiones_que_llegan=llegan)

    with registro.paso(log, "Entrenamiento de la red") as res:
        red, T, info = R.entrenar(A, PEND, goal, valid, y, len(vocab), log)
        res.update(info)

    modelo = dict(id_modelo=id_modelo, id_cliente=id_cliente, entrenado=entrenado.isoformat(), aprendido=apr,
                  vocab=vocab, eventos_clave=ek, orden_embudo=orden,
                  red=dict(estado=red.state_dict(), V=len(vocab), nk=len(clave), temperatura=T),
                  info=info, ventana=dict(desde=str(v.desde), hasta=str(v.hasta), sesiones=v.sesiones))
    fila = dict(id_modelo=id_modelo, id_cliente=id_cliente, entrenado=entrenado.isoformat(),
                datos_desde=pd.Timestamp(ses.ini.min()).isoformat(), datos_hasta=pd.Timestamp(ses.ini.max()).isoformat(),
                sesiones=int(A["nses"]), objetivo=ek["objetivo"], eventos_clave=clave,
                nombres_hitos=nombres_hitos(ek), auc=info["auc"],
                auc_ic95_inf=info["auc_ic95_inf"], artefacto=None)   # artefacto: lo completa quien lo guarda
    return modelo, fila
