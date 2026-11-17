# Plataforma de Detección de Fricción UX (PFI)

Monorepo que agrupa el pipeline de análisis en GCP, las funciones y migraciones de Supabase, la orquestación con Cloud Workflows y el frontend en Next.js.

## Estructura del repositorio

```text
pfi-monorepo/
├── .github/workflows/                 # CI/CD por componente (filtrado por `paths`)
├── .vscode/settings.json              # Aislamiento de Deno vs TypeScript y rutas Python
├── frontend/                          # Aplicación web en Next.js
├── pipeline/                          # Módulos Python desplegados en Cloud Run
│   ├── 01_extraccion/                 # Cloud Run Service: mod-extraccion
│   ├── 02_deteccion_friccion/         # Cloud Run Job: trabajo-deteccion-friccion
│   ├── 03_exploracion/                # Cloud Run Job: trabajo-exploracion
│   └── 04_generacion_insights/        # Cloud Run Job: trabajo-generacion-insights
├── supabase/
│   ├── migrations/                    # Esquema SQL, índices y políticas RLS
│   └── functions/
│       └── notificaciones/            # Supabase Edge Function (Deno)
└── infra/
    └── workflows/
        └── orquestador_pipeline.yaml  # Definición de Cloud Workflows (GCP)
```

## Convenciones rápidas

- **Aislamiento de dependencias**: Cada módulo en `pipeline/` mantiene su propio `requirements.txt` / `pyproject.toml`, `Dockerfile` y `.venv/`. `frontend/` maneja su propio `package.json`.
- **Variables de entorno y secretos**: Nunca commitear archivos `.env` ni credenciales JSON de GCP; usar `.env.example` como plantilla y GCP Secret Manager en producción.
- **Deploy de orquestación**:
  ```bash
  gcloud workflows deploy orquestador-pipeline \
    --location=us-central1 \
    --source=infra/workflows/orquestador_pipeline.yaml
  ```
