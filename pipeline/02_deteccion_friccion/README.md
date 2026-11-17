# Módulo 2 — Detección de fricción

Detecta patrones de fricción en sesiones de navegación de cualquier sitio con GA4, sin reglas previas ni
etiquetas. Cada día, por cliente:

1. **Ventana** (`modulo/ventana.py`, `modulo/preparar.py`): toma las últimas 14.500 sesiones completas hasta T−1,
   leídas de BigQuery (`ingesta/`). Con menos de 2.667 no entrena (`exit 0`).
2. **Modelo**: si el cliente no tiene modelo, el LLM elige los eventos clave (`modulo/eventos_clave.py`,
   `modulo/llm.py`), se aprenden el preprocesamiento y el embudo (`modulo/nodos.py`, `modulo/embudo.py`) y se
   entrena la red LSTM (`modulo/red.py`, `modulo/entrenamiento.py`). Si ya tiene, se carga (`modulo/almacen.py`).
3. **Detección** (`modulo/deteccion.py`): busca bifurcaciones donde la llegada al objetivo cae. Si la AUC del día
   queda debajo del IC95 inferior del entrenamiento, reentrena.
4. **Selección y escritura** (`modulo/seleccion.py`, `modulo/escritura.py`): una sola transacción en BigQuery
   `friccion_resultados`, con MERGE por `id_patron`.

## Estructura

| Carpeta | Contenido |
|---|---|
| `modulo/` | el módulo; entrada `python -m modulo.principal` |
| `ingesta/` | cliente → región (Supabase) → eventos (BigQuery) |
| `preprocesamiento/` | funciones comunes: limpieza de eventos, rutas por plantilla, orden de eventos simultáneos |
| `nube/` | DDL de `friccion_resultados` (BigQuery) y de las regiones (Supabase) |
| `Dockerfile`, `.gcloudignore` | imagen del Cloud Run Job |

## Correr

```bash
pip install -r modulo/requirements.txt torch
cp .env.example .env          # completar
gcloud auth application-default login
PYTHONIOENCODING=utf-8 python -m modulo.principal --cliente <id> --fecha AAAA-MM-DD \
    [--eventos-clave a,b,objetivo] [--simular]
```

`--simular` no guarda el modelo ni escribe en BigQuery. `--eventos-clave` evita el LLM.

En Cloud Run el Job recibe `FECHA_EJECUCION`, `IDS_CLIENTES` (JSON) y `CLOUD_RUN_TASK_INDEX`. Una tarea
procesa un cliente.

## Pruebas

```bash
PYTHONIOENCODING=utf-8 python -m pytest              # todo
PYTHONIOENCODING=utf-8 python -m pytest -m unit      # solo unitarias
```

Datos sintéticos en memoria (`tests/sinteticos.py`) y dobles para Supabase, BigQuery, Cloud Storage y el LLM:
ningún test toca la nube. La corrida falla si algún archivo de `modulo/`, `ingesta/` o `preprocesamiento/` queda
debajo del 85% de cobertura (líneas + ramas). Reportes en `reports/`: `pytest_report.html`, `coverage_html/`,
`coverage.json` y `coverage-python.info` (lcov).

## Desplegar

```bash
gcloud builds submit --async --tag gcr.io/pruebas-pfi/trabajo-deteccion-friccion:vN .
gcloud run jobs update trabajo-deteccion-friccion --region us-central1 --image gcr.io/pruebas-pfi/trabajo-deteccion-friccion:vN
```
