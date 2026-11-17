# Módulo 4 — Generación de Insights UX

Cloud Run Job en Python encargado de analizar patrones de fricción explorados, generar diagnósticos causales claros mediante inferencia multimodal con **Qwen3.5** desplegado en **RunPod (vLLM)** y persistir los resultados de forma idempotente en **Supabase**.

---

## Arquitectura y Flujo de Ejecución

El módulo se ejecuta como un **trabajo por lotes (Cloud Run Job)** orquestado por **Google Cloud Workflows** (`trabajo-generacion-insights`), procesando un único cliente por tarea (`CLOUD_RUN_TASK_INDEX` sobre `IDS_CLIENTES`):

1. **Cláusula de guarda y recuperación en BigQuery (`BigQueryService`)**:
   - Consulta `pruebas-pfi.friccion_resultados.patrones_friccion_explorados` para `id_cliente` con `fecha_exploracion <= FECHA_EJECUCION` y `status = 'COMPLETED'`, tomando la exploración más reciente por patrón (`id_patron`) y enriqueciendo con `pruebas-pfi.friccion_resultados.modelos` (lo que permite recuperar automáticamente al día siguiente patrones cuya generación de insights haya fallado previamente).
   - Si no existen patrones explorados para ese ciclo, finaliza con código `0`.
   - Calcula las **4 distribuciones porcentuales de audiencia** (`dispositivos`, `navegadores`, `sistemas_operativos`, `paises`) cruzando las secuencias de cada patrón contra `pruebas-pfi.dw_analytics_us.eventos_usuario`.
2. **Selección incremental por novedades (`InsightProcessor` + `SupabaseService`)**:
   - Calcula un `hash_exploracion` (SHA-256) determinístico sobre los pasos, eventos, rutas, elementos interactuados y notas contextuales (`evidences`).
   - Compara contra el estado persistido en Supabase:
     - **Patrón nuevo o con cambios en pasos/evidencias:** descarga capturas, ejecuta inferencia en RunPod y realiza `upsert` completo.
     - **Mismos pasos pero métricas/fechas actualizadas:** actualiza únicamente las métricas y distribuciones en `public.fricciones` sin invocar al LLM.
     - **Sin novedades:** omite el patrón.
3. **Evidencias visuales (`GCSService`)**:
   - Descarga las capturas `.webp` desde Google Cloud Storage (`gs://pruebas-pfi-evidencias/...`) usando ADC o Service Account y las codifica en Base64 (`data:image/webp;base64,...`).
4. **Inferencia multimodal en RunPod (`PromptBuilder` + `LLMClient`)**:
   - Descubre dinámicamente el Pod activo por nombre (`LLM_POD_NOMBRE`, por defecto `friccion-llm`) vía RunPod API o usa `LLM_INFERENCE_URL` si está definida.
   - Verifica disponibilidad del modelo en `GET /v1/models` (`ensure_model_ready`).
   - Envía el prompt multimodal (métricas, audiencias, pasos con resaltado en color índigo/violeta y notas contextuales) a `/v1/chat/completions` con **streaming SSE** (`stream: true`), `User-Agent` propio, esquema `response_format` (`json_schema`) y modo razonamiento activo (`enable_thinking: true`), limpiando bloques `<think>...</think>` antes de validar con `UxDiagnosticsOutput`.
5. **Persistencia idempotente en Supabase (`SupabaseService`)**:
   - Mantiene **1 único diagnóstico vigente por patrón** mediante `upsert` en las 4 tablas relacionales (`fricciones`, `fricciones_diagnosticos`, `friccion_recorrido_pasos`, `friccion_recorrido_notas`), respetando restricciones `ON DELETE RESTRICT` (sin `CASCADE`).
6. **Logging estructurado (`logging_config.py`)**:
   - Emite logs JSON en una sola línea compatibles con Google Cloud Logging (`stdout` para `DEBUG`/`INFO`/`WARNING`, `stderr` para `ERROR`/`CRITICAL`), inyectando `fecha_ejecucion` e `id_cliente` mediante `contextvars`.

---

## Requisitos del Pod en RunPod (vLLM)

Para procesar capturas multimodales de hasta 24 pasos por patrón, el Pod `friccion-llm` debe levantarse **sin** `--language-model-only` y habilitando múltiples imágenes por prompt:

```text
--model cyankiwi/Qwen3.5-27B-AWQ-4bit --port 8000 --reasoning-parser qwen3 --max-model-len 32768 --limit-mm-per-prompt '{"image": 25}'
```

---

## Estructura del Proyecto

```text
generacion_insights/
├── app/
│   ├── config.py                    # Configuración centralizada (Pydantic Settings)
│   ├── logging_config.py            # Formatter JSON y handlers stdout/stderr para GCP
│   ├── main.py                      # Entrypoint CLI del Cloud Run Job
│   ├── core/
│   │   ├── processor.py             # Orquestador incremental por patrón
│   │   └── prompt_builder.py        # Ensamblador de prompts multimodales y schema JSON
│   ├── models/
│   │   ├── exploration_models.py    # Modelos de reportes, evidencias, audiencias y hash
│   │   ├── llm_schemas.py           # Schema Pydantic UxDiagnosticsOutput
│   │   └── response_models.py       # Resultado de ejecución por patrón
│   ├── services/
│   │   ├── bigquery_service.py      # Consultas a friccion_resultados y dw_analytics_us
│   │   ├── gcs_service.py           # Conversión Base64 de capturas WebP
│   │   ├── llm_client.py            # Cliente RunPod/vLLM con streaming SSE y backoff
│   │   └── supabase_service.py      # Upsert idempotente 1:1 en Supabase
│   └── storage/
│       ├── base.py                  # Interfaz abstracta StorageProvider
│       └── gcs_storage.py           # Implementación Google Cloud Storage
├── sql/
│   └── fase1_migracion_supabase.sql # DDL de adaptación y limpieza de tablas en Supabase
├── tests/
│   ├── conftest.py
│   └── unit/                        # Pruebas unitarias aisladas de I/O
├── .env.example
├── requirements.txt
├── pytest.ini
├── mypy.ini
└── .flake8
```

---

## Variables de Entorno

### Variables inyectadas por Cloud Workflows / Cloud Run Jobs
| Variable | Descripción | Ejemplo |
| :--- | :--- | :--- |
| `FECHA_EJECUCION` | Fecha del ciclo del pipeline (`YYYY-MM-DD`). | `2026-11-16` |
| `IDS_CLIENTES` | Arreglo JSON con los UUIDs de clientes activos. | `'["00000000-0000-0000-0000-000000000001"]'` |
| `CLOUD_RUN_TASK_INDEX` | Índice en base `0` de la tarea actual (inyectado por Cloud Run). | `0` |
| `CLOUD_RUN_TASK_ATTEMPT` | Número de intento actual en base `0` (inyectado por Cloud Run). | `0` |

### Variables de configuración de aplicación (`.env.example`)
- **Supabase:** `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`.
- **GCP (BigQuery & GCS):** `PLATFORM_GCP_PROJECT_ID`, `BIGQUERY_DATASET_ID`, `BIGQUERY_EXPLORATION_TABLE_NAME`, `BIGQUERY_MODELS_TABLE_NAME`, `BIGQUERY_EVENTS_DATASET_ID`, `BIGQUERY_EVENTS_TABLE_NAME`, `GCS_BUCKET_CAPTURES`, `GOOGLE_APPLICATION_CREDENTIALS` (opcional si corre con ADC).
- **RunPod / vLLM:** `RUNPOD_API_KEY`, `VLLM_API_KEY`, `LLM_POD_NOMBRE`, `LLM_INFERENCE_URL` (opcional para URL fija), `LLM_MODEL_NAME`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`, `LLM_READY_MAX_WAIT_SECONDS`, `LLM_READY_POLL_INTERVAL_SECONDS`, `LLM_MAX_TOKENS`, `LLM_TEMPERATURE`, `LLM_ENABLE_THINKING`, `LLM_USER_AGENT`.

---

## Ejecución Local

1. Instalar dependencias en el entorno virtual:
   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```
2. Configurar `.env` a partir de `.env.example`.
3. Ejecutar una tarea simulando Cloud Run Jobs:
   ```bash
   FECHA_EJECUCION="2026-11-16" \
   IDS_CLIENTES='["00000000-0000-0000-0000-000000000001"]' \
   CLOUD_RUN_TASK_INDEX=0 \
   .venv/bin/python -m app.main
   ```

---

## Tests y Calidad de Código

```bash
# Ejecutar suite unitaria con cobertura de statements y branches
.venv/bin/pytest

# Linter
.venv/bin/flake8 app tests

# Chequeo estático de tipos
.venv/bin/mypy app tests
```
