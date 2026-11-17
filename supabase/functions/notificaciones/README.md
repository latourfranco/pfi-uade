# Módulo 5 — Notificaciones (Eureka)

Servicio de notificaciones por correo electrónico que se ejecuta al finalizar cada ciclo del pipeline de análisis de UX de **Eureka**, orquestado por **Google Cloud Workflows** sobre una **Supabase Edge Function** (`notificaciones`).

## ¿Qué hace?

1. **Recibe el cierre de ciclo:** Cloud Workflows invoca `POST /functions/v1/notificaciones` con `fecha_ejecucion` y la lista de `ids_clientes`.
2. **Valida acceso:** comprueba el JWT de Supabase y el secreto compartido en el header `X-Workflow-Secret`.
3. **Filtra qué notificar:** para cada cliente verifica que su cuenta esté activa (`clientes_perfil`), busca diagnósticos nuevos o actualizados en el ciclo (`fricciones_diagnosticos` + `fricciones`) y consulta los destinatarios habilitados (`organizacion_miembros`).
4. **Evita duplicados:** registra cada versión de diagnóstico enviada en `notificaciones_enviadas` para que los reintentos de Workflows no generen correos repetidos.
5. **Envía el correo con identidad de marca:** renderiza la plantilla HTML de Eureka (`DiagnosticoEmail.tsx`) y la envía vía **Resend**, aislando fallos puntuales por cliente y devolviendo un resumen JSON para auditoría.

## Estructura principal

```text
├── supabase/
│   ├── functions/notificaciones/   # Edge Function, servicios, plantilla y tests
│   └── migrations/                 # SQL de tablas organizacion_miembros y notificaciones_enviadas
├── scripts/
│   ├── preview.ts                  # Genera una vista previa local del email (preview_email.html)
│   └── test_mailpit.ts             # Prueba end-to-end local enviando correos a Mailpit (Docker)
└── deno.json                       # Configuración y tareas de Deno
```

## Variables de entorno (Supabase Secrets)

- `WORKFLOW_NOTIFICACIONES_SECRET`: secreto compartido con Cloud Workflows (`X-Workflow-Secret`).
- `RESEND_API_KEY`: clave de API para enviar correos con Resend.
- `FRONTEND_URL`: URL del dashboard de Eureka (por defecto `https://eureka.app`).
- `RESEND_FROM_EMAIL` *(opcional)*: remitente (por defecto `Eureka <alertas@eureka.app>`).

*(Supabase inyecta automáticamente `SUPABASE_URL` y `SUPABASE_SERVICE_ROLE_KEY`.)*

## Comandos útiles

```bash
# Ejecutar tests unitarios
deno task test

# Generar vista previa del email en preview_email.html
deno run --allow-write --allow-read --allow-env scripts/preview.ts

# Probar envío real en local contra Mailpit (Docker en puertos 1025 y 8025)
deno run --allow-net --allow-env scripts/test_mailpit.ts
```
