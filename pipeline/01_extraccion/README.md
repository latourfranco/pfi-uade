# Pipeline Batch de Extracción Cross-Project (Python + BigQuery)

Servicio backend en **FastAPI** diseñado para automatizar la extracción periódica de eventos crudos de Google Analytics 4 (GA4) desde las instancias de BigQuery de los clientes hacia los Data Warehouses regionales (`dw_analytics_<region>`) en el proyecto central de la plataforma.

---

## Características Principales

1. **Idempotencia Atómica (`MERGE`)**: Utiliza `MERGE` con clave compuesta natural `(cliente_id, fecha_evento, event_timestamp, id_usuario, nombre_evento)` y `WHEN NOT MATCHED THEN INSERT ROW`, asegurando **cero duplicados y cero pérdida de datos**.
2. **Orquestación Asíncrona Multi-Región**: Ejecuta las consultas de BigQuery respetando la propiedad `location=gcp_region` de cada cliente y gestiona la concurrencia con `asyncio.Semaphore`.
3. **Resiliencia & Reintentos Inteligentes**:
   - Clasificación de errores en tiempo de ejecución (*transient* vs *permanent*).
   - Reintentos automáticos con *Exponential Backoff + Jitter* ante caídas temporales de red o límites de cuota (429, 503).
   - Segunda pasada automática (*Second-Chance Pass*) en el mismo lote para clientes que sufrieron fallos transitorios.
4. **Seguridad OIDC en Cloud Run**: Autenticación delegada en el proxy IAM de Cloud Run (`--no-allow-unauthenticated`) para invocaciones desde **Google Cloud Workflows** (`roles/run.invoker`).
5. **Lectura de Integraciones en Supabase (Solo Lectura)**: Filtro de clientes activos (`activo = true`) sin escrituras en Supabase.
6. **Observabilidad Estructurada**: Logs JSON en `stdout`/`stderr` compatibles con Google Cloud Logging (`severity`, `message`, `timestamp`, `id_cliente`, `fecha_ejecucion`).

---

## Variables de Entorno (`.env`)

```env
# Google Cloud Platform (Proyecto Central)
PLATFORM_GCP_PROJECT_ID=tu-proyecto-central
GOOGLE_APPLICATION_CREDENTIALS=/ruta/a/tu/credentials.json

# Supabase (Modo solo lectura)
SUPABASE_URL=https://tu-proyecto.supabase.co
SUPABASE_SERVICE_ROLE_KEY=tu-service-role-key

# Configuración de Ejecución
ENVIRONMENT=production
PORT=8080
GA4_INITIAL_BACKFILL_DAYS=60
MAX_CONCURRENT_CLIENTS=5
MAX_CLIENT_RETRIES=3
```

---

## Endpoints de la API

### 1. `GET /health`
Verifica la disponibilidad del servicio.

**Respuesta (200 OK):**
```json
{
  "status": "ok",
  "timestamp": "2026-11-14T21:40:00Z",
  "environment": "production"
}
```

### 2. `POST /extraer`
Disparado por Google Cloud Workflows o invocado manualmente para iniciar la extracción.

* **Headers:** `Authorization: Bearer <OIDC_TOKEN>` (validado por Cloud Run IAM)
* **Body (Opcional):**
```json
{
  "fecha_ejecucion": "2026-11-14",
  "cliente_id": "id_cliente_1"
}
```
*Si `fecha_ejecucion` ($T$) se omite, toma la fecha actual en UTC. En la primera extracción de un cliente (`MAX(fecha_evento)` inexistente en BigQuery) se extraen los últimos 60 días (`[T-60, T-1]`); a partir de la segunda ejecución, se extrae de forma incremental desde `MAX(fecha_evento) + 1 día` hasta `T-1` (acotado al TTL de 60 días). Si `cliente_id` se omite, se procesan todos los clientes con `activo = true`.*

**Respuesta (200 OK):**
```json
{
  "fecha_ejecucion": "2026-11-14",
  "clientes_exitosos": ["id_cliente_1", "id_cliente_2"],
  "clientes_omitidos": ["id_cliente_3"],
  "clientes_fallidos": []
}
```

---

## Despliegue en Google Cloud Platform

### 1. Construir y Desplegar en Cloud Run

```bash
# Construir imagen con Cloud Build
gcloud builds submit --tag gcr.io/$PLATFORM_GCP_PROJECT_ID/batch-ga4-extractor

# Desplegar en Cloud Run con timeout extendido (1800s) y autenticación privada
gcloud run deploy batch-ga4-extractor \
  --image gcr.io/$PLATFORM_GCP_PROJECT_ID/batch-ga4-extractor \
  --platform managed \
  --region us-central1 \
  --no-allow-unauthenticated \
  --timeout 1800s \
  --set-env-vars PLATFORM_GCP_PROJECT_ID=$PLATFORM_GCP_PROJECT_ID,SUPABASE_URL=$SUPABASE_URL,SUPABASE_SERVICE_ROLE_KEY=$SUPABASE_SERVICE_ROLE_KEY
```

---

## Desarrollo Local y Tests

```bash
# 1. Crear y activar entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Ejecutar suite de pruebas
pytest

# 4. Iniciar servidor de desarrollo
uvicorn app.main:app --reload --port 8080
```
