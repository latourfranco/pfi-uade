# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Módulo 2 ("motor de análisis autónomo de fricción") de un PFI (UADE) de 4 módulos: ingesta/anonimización → **este módulo** → exploración agéntica → generador de reportes. Detecta patrones de fricción en sesiones de navegación web de forma no supervisada, con una red LSTM que estima la llegada al objetivo en cada paso y busca bifurcaciones donde esa llegada cae.

La carpeta se limpió el 2026-11-17: solo queda lo que necesita el módulo para funcionar. El resto (comparación de métodos, documentos, orquestación, originales de los archivos editados) está fuera de la carpeta, en `C:\Users\mviola\dev\respaldo_modulo_friccion_2026-11-17\`.

`PLAN_MODULO_DETECCION_FRICCION.md` (en ese respaldo) es la fuente de las referencias `§N` de los comentarios; §14 es el estado de producción. Las decisiones del plan ya se cerraron con el usuario: no se rediseñan unilateralmente.

Requisitos no negociables: respetar el orden temporal de eventos, no partir de reglas de qué es fricción, ser no supervisado, ser trazable a usuario/sesión/timestamp/URL, y reportar solo patrones con soporte de múltiples sesiones y usuarios. Nada de vocabulario de un sitio en `modulo/`. Los eventos clave los elige el LLM por cliente, y la compra solo entra post-hoc.

## Estructura

```
modulo/            el módulo (Cloud Run Job): principal, ventana, preparar, entrenamiento, nodos, embudo, red,
                   eventos_clave, llm, deteccion, seleccion, almacen, escritura, registro, config; requirements.txt
ingesta/           cliente -> región (Supabase) -> eventos (BigQuery)
preprocesamiento/  config.py, preprocessing.py (limpieza, rutas por plantilla), datos_tramos.py (orden de simultáneos)
nube/              DDL de BigQuery friccion_resultados y de Supabase (regiones)
Dockerfile, .gcloudignore   imagen del Job
tests/             pytest: unit/, integration/, sinteticos.py (clickstream sintético), conftest.py
```

Dependencias en el intérprete del usuario (site-packages del usuario, `python -I` no las ve). Correr con `PYTHONIOENCODING=utf-8`. Suite de pytest en `tests/` (unit + integration, datos sintéticos, sin nube): `python -m pytest`. Falla si algún archivo queda debajo del 85% de cobertura (hook en `tests/conftest.py`); reportes en `reports/`. El `.gcloudignore` deja `tests/` fuera de la imagen.

## Convenciones

- Cada script agrega la raíz a `sys.path` y usa imports calificados (`from modulo import ...`, `from preprocesamiento.preprocessing import ...`).
- Preprocesamiento (`modulo/preparar.py`): `drop_engagement_pings` → sesionizar (sesión de GA4; sin id, corte de 30 min) → `drop_promo_and_load_views` → `fold_scroll_events` → `filter_sessions` (≥ 4 eventos, sin tope de largo).
- Rutas por plantilla estructural (§3.2): un segmento es `{param}` si es numérico/hash o si su lugar toma > `ROUTE_PARAM_MIN_VALORES` valores. Nada de listas manuales.
- Lo aprendido por cliente (reglas de rutas, orden de simultáneos, grupos de páginas, vocabulario, eventos clave, orden del embudo, red) se guarda con el modelo.
- Si se agrega un import a otro archivo del repo, sumarlo al `Dockerfile` y al `.gcloudignore`.

## Producción

Cadena en `pruebas-pfi` (us-central1):
1. Cloud Scheduler `orquestador-pipeline-diario` (05:00 de Argentina, **en pausa**) dispara el workflow `orquestador-pipeline`.
2. El workflow llama a `mod-extraccion` (módulo 1), que pasa el GA4 del cliente a `dw_analytics_<región>.eventos_usuario`.
3. Si algún cliente no tiene modelo, el workflow prende el Pod del LLM en RunPod.
4. Corre el Cloud Run Job `trabajo-deteccion-friccion`, una tarea por cliente.
5. Borra el Pod, también si algo falla.

El Job escribe en BigQuery `friccion_resultados` y guarda los modelos en `gs://pruebas-pfi-friccion-modelos/modelos/{cliente}/{fecha}/modelo.pkl`. El yaml del workflow desplegado está en el respaldo.

- **Entrada:** `python -m modulo.principal`, con `FECHA_EJECUCION` (T, procesa hasta T−1), `IDS_CLIENTES` (JSON) y `CLOUD_RUN_TASK_INDEX`. En local: `--cliente <id> --fecha AAAA-MM-DD [--eventos-clave a,b,objetivo] [--simular]`. Desde la PC el LLM no anda (FortiClient bloquea `*.proxy.runpod.net`): en local pasar `--eventos-clave`. Cliente de prueba: `00000000-0000-0000-0000-000000000001`, datos hasta 2021-01-31, fecha útil `2021-02-01`.
- **Flujo por cliente:** ventana de las últimas 14.500 sesiones (con menos de 2.667 no entrena, `exit 0`) → sin modelo: el LLM elige los eventos clave y se entrena; con modelo: se carga del registro `friccion_resultados.modelos` → detecta → si la AUC del día cae debajo del IC95 inferior, reentrena con los mismos eventos clave → guarda el modelo y escribe todo en **una sola transacción** (MERGE por `id_patron`).
- **El módulo no prende ni apaga el Pod:** lo busca por nombre (`LLM_POD_NOMBRE=friccion-llm`, API v2 de RunPod). GPUs en orden A40 → RTX A6000 → L40 (48 GB, ≤ 1 USD/h). Si se prende un Pod a mano, borrarlo al terminar.
- **Logs:** JSON de una línea (`modulo/registro.py`), con `etapa`, `paso`, `fecha_ejecucion`, `id_cliente` y `traza_error`; ERROR va a stderr.
- **Desplegar** (sin Docker local, todo por Cloud Build): `gcloud builds submit --async --tag gcr.io/pruebas-pfi/trabajo-deteccion-friccion:vN .` y `gcloud run jobs update trabajo-deteccion-friccion --region us-central1 --image …:vN`.
- **gcloud en Windows:** usar `C:/Users/mviola/AppData/Local/Google/CLOUDS~1/GOOGLE~1/bin/gcloud.cmd` (la ruta con espacios rompe `cmd` con argumentos entre comillas). El streaming de logs de `builds submit` falla por permisos: mirar el estado con `gcloud builds describe <id>`.
- **Cuentas:** `eureka@` corre el Job (BigQuery, Storage, secretos); `scheduler-invoker@` corre el workflow y el Scheduler. Secretos en Secret Manager: `SUPABASE_DB_URL_MODULO`, `RUNPOD_API_KEY`, `VLLM_API_KEY`; en local salen del `.env`. Nunca mostrarlos ni pedirlos en el chat.
- **Antes de borrar, vaciar o pisar algo en la nube**, consultar al usuario y respaldar. `dw_analytics_us_central1` tiene clientes de prueba `cli_bm_*` que la extracción no vuelve a traer: no tocarla. Cuidar el nivel gratuito de GCP (10 GB guardados, 1 TB de consultas por mes).
