# Módulo 3: Exploración Agéntica y Captura Visual

Módulo encargado de reproducir de forma autónoma los patrones de fricción detectados en sitios web de clientes mediante **Playwright (Chromium)**, recopilar contexto semántico de interacción (`bounding_box_context` y `context_notes`) y generar evidencias visuales en formato **WebP** listas para su análisis posterior en el Módulo de Insights.

Está diseñado para ejecutarse como tarea paralela dentro de un **Google Cloud Run Job** orquestado por **Google Cloud Workflows**.

---

## Flujo de Ejecución

1. **Entrada de tarea (`app/main.py`):** Lee `FECHA_EJECUCION`, `IDS_CLIENTES`, `CLOUD_RUN_TASK_INDEX` y `CLOUD_RUN_TASK_ATTEMPT` para determinar el cliente asignado a la tarea actual.
2. **Cláusula de guarda en BigQuery (`app/job_runner.py`):** Consulta los patrones pendientes del cliente para esa fecha haciendo `JOIN` entre `friccion_resultados.patrones` y `friccion_resultados.sesion_representativa` (excluyendo los ya registrados como `COMPLETED` o `PARTIAL` en `patrones_friccion_explorados`). Si no hay pendientes (`0` filas), finaliza con código `0` sin inicializar el navegador.
3. **Configuración e inicialización:** Obtiene `ClientInterfaceConfig` desde Supabase (`clientes_integracion_fuente`), verifica la tabla de destino en BigQuery e inicializa `BrowserManager` dentro de un bloque `try / finally`.
4. **Concurrencia selectiva y aislamiento de sesiones (`app/job_runner.py`):**
   * Si el cliente cuenta con sesión configurada (`storage_state_encrypted` o `requires_authentication`), clasifica los patrones mediante `SessionTrace.requires_authenticated_session()`:
     * Los **patrones anónimos** se ejecutan en paralelo (hasta `MAX_CONCURRENCY_PER_CLIENT`, por defecto `3`) en contextos sin sesión.
     * Previo a la tanda autenticada se limpia el estado residual del carrito (`cleanup_client_session_state`), y los **patrones que requieren sesión** se ejecutan **secuencialmente (`concurrency = 1`)** para evitar contaminación cruzada entre trazas.
   * Si el cliente no utiliza autenticación, todos los patrones corren en paralelo hasta `MAX_CONCURRENCY_PER_CLIENT`.
5. **Emulación agéntica Just-In-Time (JIT), resiliencia UI y salvaguardas (`app/agent/`):**
   * Cada patrón inicia en un `BrowserContext` aislado sin sesión en el paso 0; la autenticación (`storage_state` cifrado o formulario de 1/2 pasos en `AuthHandler`) se inyecta bajo demanda ante un paso `login`, antes de `add_to_cart` cuando el flujo lo requiere o ante una barrera de login en checkout, emitiendo nota diagnóstica si la sesión guardada expiró o fue rechazada.
   * `LocatorResolver` y `TraceExecutor` resuelven menús desktop/submenús/drawers mobile, Quick View vs preservación de ficha de producto (PDP) tras `select_item`, preselección de variantes/cantidad en `add_to_cart`, espera de spinners/red tras clics, cierre automático de pop-ups (`ObstacleHandler`) y detección de overlays/drawers bloqueantes en primer plano.
   * Al finalizar cada patrón autenticado (`finally`), `LocatorResolver.clear_cart_items` vacía el carrito antes de liberar el contexto.
   * Todo el recorrido está protegido por `ActionGuard` (bloqueo de pagos reales y acciones destructivas) y `NetworkGuard` (aislamiento de red/SSRF).
6. **Evidencias y persistencia:**
   * Captura imágenes `.webp` con resaltado visual (`VisualHighlighter`) y las guarda en ruta determinística:
     `capturas/{id_cliente}/{fecha_ejecucion}/{id_patron}_{orden}.webp` (en GCS `gs://<GCS_BUCKET_NAME>/...` o en disco local).
   * Persiste incrementalmente cada `ExplorationReport` de forma idempotente en `friccion_resultados.patrones_friccion_explorados`.
7. **Observabilidad:** Emite logs JSON estructurados de una línea (`app/logging_config.py`) compatibles con Google Cloud Logging (`INFO`/`WARNING` a `stdout`, `ERROR`/`CRITICAL` a `stderr`), con correlación automática por `fecha_ejecucion` e `id_cliente`.

---

## Estructura Principal

```text
app/
├── main.py                 # Punto de entrada oficial para Cloud Run Jobs
├── job_runner.py           # Orquestación por cliente, guarda inicial y concurrencia selectiva
├── logging_config.py       # Logging JSON estructurado para Cloud Logging
├── config.py               # Configuración centralizada (Pydantic Settings)
├── agent/                  # TraceExecutor, UrlResolver, LocatorResolver y AuthHandler (JIT)
├── browser/                # BrowserManager, ObstacleHandler y VisualHighlighter WebP
├── safety/                 # ActionGuard y NetworkGuard
├── security/               # Cifrado/descifrado AES-256-GCM de credenciales y storage_state
├── services/               # Clientes BigQueryService y SupabaseService
├── storage/                # Proveedores GCSStorageProvider y LocalStorageProvider
└── models/                 # Modelos Pydantic (SessionTrace, ExplorationReport, ClientInterfaceConfig)
tests/
├── unit/                   # Pruebas unitarias
└── integration/            # Pruebas de integración (flujo E2E con Chromium)
```

---

## Configuración y Variables de Entorno

Usa `.env.example` como plantilla base para desarrollo local.

### Variables de Orquestación (Cloud Run Jobs)
| Variable | Descripción |
| :--- | :--- |
| `FECHA_EJECUCION` | Fecha del ciclo en formato `YYYY-MM-DD`. |
| `IDS_CLIENTES` | Lista JSON serializada con los IDs de clientes activos (ej. `'["cli_1", "cli_2"]'`). |
| `CLOUD_RUN_TASK_INDEX` | Índice de la tarea dentro de `IDS_CLIENTES` (por defecto `0`). |
| `CLOUD_RUN_TASK_ATTEMPT` | Número de reintento de la tarea (por defecto `0`). |

### Variables Principales de Infraestructura
| Variable | Valor por defecto / Ejemplo | Uso |
| :--- | :--- | :--- |
| `PLATFORM_GCP_PROJECT_ID` | `pruebas-pfi` | Proyecto GCP central de BigQuery. |
| `DEFAULT_BIGQUERY_REGION` | `us` | Región por defecto de ejecución en BigQuery. |
| `BIGQUERY_DATASET` | `friccion_resultados` | Dataset centralizado de entrada y salida en BigQuery. |
| `BIGQUERY_PATTERNS_TABLE_NAME` | `patrones` | Tabla de entrada de patrones detectados. |
| `BIGQUERY_SESSIONS_TABLE_NAME` | `sesion_representativa` | Tabla con los pasos secuenciales por patrón. |
| `BIGQUERY_TABLE_NAME` | `patrones_friccion_explorados` | Tabla de salida de reportes de exploración. |
| `STORAGE_PROVIDER` | `gcs` (`local` en dev) | Destino de capturas `.webp`. |
| `GCS_BUCKET_NAME` | `pruebas-pfi-evidencias` | Bucket único centralizado para evidencias en GCS. |
| `GCS_LOCATION` | `us` | Ubicación geográfica del bucket centralizado en GCS. |
| `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` | — | Lectura de configuración de clientes. |
| `AES_ENCRYPTION_KEY` | 64 hex chars (dev) | Clave AES-256-GCM para credenciales y `storage_state` cifrados. |
| `MAX_CONCURRENCY_PER_CLIENT` | `3` | Máximo de patrones anónimos concurrentes en Chromium. |

---

## Ejecución

### Instalación local
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### Modos de ejecución
```bash
# 1. Modo productivo Cloud Run Job
FECHA_EJECUCION="2026-11-15" IDS_CLIENTES='["cliente_1"]' CLOUD_RUN_TASK_INDEX=0 python -m app.main

# 2. Ejecución manual por cliente (desarrollo)
python -m app.job_runner --client-id cliente_1 --batch-date 2026-11-15 --storage-provider local
```

---

## Pruebas y Calidad

```bash
# Suite completa con cobertura de líneas y ramas
.venv/bin/pytest

# Linter y chequeo estático de tipos
.venv/bin/flake8 app tests
.venv/bin/mypy app tests
```
