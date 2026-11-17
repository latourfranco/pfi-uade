import { assertEquals, assertStringIncludes } from "@std/assert";
import { SupabaseClient } from "npm:@supabase/supabase-js@2";
import { handler, HandlerDeps } from "../index.ts";

const VALID_SECRET = "super_secret_workflow_token";
const CLIENTE_1 = "00000000-0000-0000-0000-000000000001";
const CLIENTE_2 = "00000000-0000-0000-0000-000000000002";

interface MockOverrides {
  perfiles?: Array<{
    cliente_id: string;
    nombre_organizacion: string;
    estado_cuenta: string;
  }>;
  perfilesError?: { message: string } | null;
  diagnosticos?: Array<{
    id: string;
    friccion_id: string;
    nombre_corto: string;
    titulo: string;
    severidad: string;
    impacto_resumen: string;
    fecha_ejecucion: string;
    created_at: string;
    updated_at: string;
    fricciones: {
      client_id: string;
      sesiones_perdidas: number;
      tasa_abandono: number;
    };
  }>;
  diagnosticosError?: { message: string } | null;
  yaNotificadas?: Array<{
    diagnostico_id: string;
    diagnostico_updated_at: string;
  }>;
  yaNotificadasError?: { message: string } | null;
  miembros?: Array<{
    cliente_id: string;
    email: string | null;
    nombre: string | null;
  }>;
  miembrosError?: { message: string } | null;
  upsertError?: { message: string } | null;
  resendResponder?: (
    body: { to: string[]; html: string; subject: string },
    callIndex: number,
  ) => { status: number; body: unknown };
  envOverrides?: Record<string, string | undefined>;
}

function getBaseMockDeps(overrides: MockOverrides = {}): {
  deps: HandlerDeps;
  sentEmails: Array<{ to: string[]; html: string; subject: string }>;
  upsertedRows: () => unknown[];
  logs: Array<{ level: string; data: Record<string, unknown> }>;
} {
  const sentEmails: Array<{ to: string[]; html: string; subject: string }> = [];
  const recordedUpserts: unknown[] = [];
  const logs: Array<{ level: string; data: Record<string, unknown> }> = [];
  let fetchCallCount = 0;

  const mockEnv = (key: string): string | undefined => {
    if (overrides.envOverrides && key in overrides.envOverrides) {
      return overrides.envOverrides[key];
    }
    const envs: Record<string, string> = {
      WORKFLOW_NOTIFICACIONES_SECRET: VALID_SECRET,
      SUPABASE_URL: "https://test.supabase.co",
      SUPABASE_SERVICE_ROLE_KEY: "test_role_key",
      RESEND_API_KEY: "re_test_key",
      FRONTEND_URL: "https://eureka.app",
    };
    return envs[key];
  };

  const defaultDiag = {
    id: "diag-1",
    friccion_id: "fric-1",
    nombre_corto: "Demora en checkout",
    titulo: "Demora crítica al confirmar compra",
    severidad: "alta",
    impacto_resumen: "Caída de ventas",
    fecha_ejecucion: "2026-11-16",
    created_at: "2026-11-16T01:00:00Z",
    updated_at: "2026-11-16T02:00:00Z",
    fricciones: {
      client_id: CLIENTE_1,
      sesiones_perdidas: 120,
      tasa_abandono: 0.42,
    },
  };

  const mockClient = {
    from: (table: string) => ({
      select: (_cols: string) => ({
        in: (_col: string, vals: string[]) => {
          if (table === "clientes_perfil") {
            const rows = overrides.perfiles ?? [
              {
                cliente_id: CLIENTE_1,
                nombre_organizacion: "Tienda Eureka",
                estado_cuenta: "activo",
              },
            ];
            return Promise.resolve({
              data: rows.filter((r) => vals.includes(r.cliente_id)),
              error: overrides.perfilesError ?? null,
            });
          }

          if (table === "fricciones_diagnosticos") {
            return {
              eq: (_eqCol: string, eqVal: string) => {
                const rows = overrides.diagnosticos ?? [defaultDiag];
                return Promise.resolve({
                  data: rows.filter(
                    (r) =>
                      vals.includes(r.fricciones.client_id) &&
                      r.fecha_ejecucion === eqVal,
                  ),
                  error: overrides.diagnosticosError ?? null,
                });
              },
            };
          }

          if (table === "notificaciones_enviadas") {
            return {
              eq: (_eqCol: string, _eqVal: string) => {
                const rows = overrides.yaNotificadas ?? [];
                return Promise.resolve({
                  data: rows.filter((r) => vals.includes(r.diagnostico_id)),
                  error: overrides.yaNotificadasError ?? null,
                });
              },
            };
          }

          if (table === "organizacion_miembros") {
            return {
              eq: (_eqCol: string, _eqVal: boolean) => {
                const rows = overrides.miembros ?? [
                  {
                    cliente_id: CLIENTE_1,
                    email: "dev@eureka.app",
                    nombre: "Franco",
                  },
                ];
                return Promise.resolve({
                  data: rows.filter((r) => vals.includes(r.cliente_id)),
                  error: overrides.miembrosError ?? null,
                });
              },
            };
          }

          return Promise.resolve({ data: [], error: null });
        },
      }),
      upsert: (rows: unknown[]) => {
        if (overrides.upsertError) {
          return Promise.resolve({ error: overrides.upsertError });
        }
        recordedUpserts.push(...rows);
        return Promise.resolve({ error: null });
      },
    }),
  } as unknown as SupabaseClient;

  const mockFetch: typeof fetch = (_url, init) => {
    fetchCallCount++;
    const body = JSON.parse(init?.body as string) as {
      to: string[];
      html: string;
      subject: string;
    };
    sentEmails.push(body);

    if (overrides.resendResponder) {
      const custom = overrides.resendResponder(body, fetchCallCount);
      return Promise.resolve(
        new Response(
          typeof custom.body === "string" ? custom.body : JSON.stringify(custom.body),
          {
            status: custom.status,
            headers: { "Content-Type": "application/json" },
          },
        ),
      );
    }

    return Promise.resolve(
      new Response(JSON.stringify({ id: `resend_${fetchCallCount}` }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
  };

  return {
    deps: {
      env: mockEnv,
      createClient: () => mockClient,
      fetch: mockFetch,
      log: (level, line) => {
        logs.push({ level, data: JSON.parse(line) });
      },
    },
    sentEmails,
    upsertedRows: () => recordedUpserts,
    logs,
  };
}

// ==========================================
// 1. Seguridad y Método HTTP
// ==========================================

Deno.test("Handler - Retorna 405 cuando el método HTTP es GET", async () => {
  const req = new Request("http://localhost/notificaciones", { method: "GET" });
  const res = await handler(req);
  assertEquals(res.status, 405);
  const json = await res.json();
  assertEquals(json.error, "Método no permitido");
});

Deno.test("Handler - Retorna 401 cuando falta la cabecera X-Workflow-Secret", async () => {
  const { deps } = getBaseMockDeps();
  const req = new Request("http://localhost/notificaciones", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  const res = await handler(req, deps);
  assertEquals(res.status, 401);
});

Deno.test("Handler - Retorna 401 cuando el secreto es incorrecto o no está configurado", async () => {
  const { deps } = getBaseMockDeps();
  const req = new Request("http://localhost/notificaciones", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Workflow-Secret": "token_equivocado",
    },
    body: JSON.stringify({}),
  });
  const res = await handler(req, deps);
  assertEquals(res.status, 401);

  const { deps: noSecretDeps } = getBaseMockDeps({
    envOverrides: { WORKFLOW_NOTIFICACIONES_SECRET: undefined },
  });
  const reqNoSecret = new Request("http://localhost/notificaciones", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Workflow-Secret": VALID_SECRET,
    },
    body: JSON.stringify({}),
  });
  const resNoSecret = await handler(reqNoSecret, noSecretDeps);
  assertEquals(resNoSecret.status, 401);
});

Deno.test("Handler - Acepta fallback NOTIFICATION_WEBHOOK_SECRET", async () => {
  const { deps } = getBaseMockDeps({
    envOverrides: {
      WORKFLOW_NOTIFICACIONES_SECRET: undefined,
      NOTIFICATION_WEBHOOK_SECRET: VALID_SECRET,
    },
  });
  const req = new Request("http://localhost/notificaciones", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Workflow-Secret": VALID_SECRET,
    },
    body: JSON.stringify({ fecha_ejecucion: "2026-11-16", ids_clientes: [] }),
  });
  const res = await handler(req, deps);
  assertEquals(res.status, 200);
});

// ==========================================
// 2. Validación de Payload JSON
// ==========================================

Deno.test("Handler - Retorna 400 cuando el cuerpo no es JSON válido", async () => {
  const { deps } = getBaseMockDeps();
  const req = new Request("http://localhost/notificaciones", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Workflow-Secret": VALID_SECRET,
    },
    body: "no_es_json",
  });
  const res = await handler(req, deps);
  assertEquals(res.status, 400);
});

Deno.test("Handler - Retorna 400 si fecha_ejecucion o ids_clientes son inválidos", async () => {
  const { deps } = getBaseMockDeps();
  const casos = [
    { ids_clientes: [CLIENTE_1] },
    { fecha_ejecucion: "2026-02-30", ids_clientes: [CLIENTE_1] },
    { fecha_ejecucion: "2026-11-16", ids_clientes: "no-array" },
    { fecha_ejecucion: "2026-11-16", ids_clientes: [""] },
  ];

  for (const body of casos) {
    const req = new Request("http://localhost/notificaciones", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Workflow-Secret": VALID_SECRET,
      },
      body: JSON.stringify(body),
    });
    const res = await handler(req, deps);
    assertEquals(res.status, 400);
  }
});

Deno.test("Handler - Retorna 200 con resumen en cero si ids_clientes está vacío", async () => {
  const { deps, sentEmails } = getBaseMockDeps();
  const req = new Request("http://localhost/notificaciones", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Workflow-Secret": VALID_SECRET,
    },
    body: JSON.stringify({
      fecha_ejecucion: "2026-11-16",
      ids_clientes: [],
    }),
  });

  const res = await handler(req, deps);
  assertEquals(res.status, 200);
  assertEquals(sentEmails.length, 0);
  const json = await res.json();
  assertEquals(json, {
    estado: "COMPLETADO",
    fecha_ejecucion: "2026-11-16",
    clientes_procesados: 0,
    clientes_notificados: 0,
    clientes_omitidos: 0,
    clientes_fallidos: 0,
    detalle: [],
  });
});

// ==========================================
// 3. Flujos de Negocio e Idempotencia
// ==========================================

Deno.test("Handler - Omite cliente con cuenta inactiva y sin diagnósticos", async () => {
  const { deps, sentEmails } = getBaseMockDeps({
    perfiles: [
      {
        cliente_id: CLIENTE_1,
        nombre_organizacion: "Org Baja",
        estado_cuenta: "baja_solicitada",
      },
    ],
    diagnosticos: [],
  });

  const req = new Request("http://localhost/notificaciones", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Workflow-Secret": VALID_SECRET,
    },
    body: JSON.stringify({
      fecha_ejecucion: "2026-11-16",
      ids_clientes: [CLIENTE_1, CLIENTE_2],
    }),
  });

  const res = await handler(req, deps);
  assertEquals(res.status, 200);
  assertEquals(sentEmails.length, 0);
  const json = await res.json();
  assertEquals(json.clientes_procesados, 2);
  assertEquals(json.clientes_omitidos, 2);
  assertEquals(json.detalle[0].motivo, "cuenta_inactiva");
  assertEquals(json.detalle[1].motivo, "sin_diagnosticos");
});

Deno.test("Handler - Idempotencia omite diagnósticos ya notificados en misma versión", async () => {
  const { deps, sentEmails } = getBaseMockDeps({
    yaNotificadas: [
      {
        diagnostico_id: "diag-1",
        diagnostico_updated_at: "2026-11-16T02:00:00.000Z",
      },
    ],
  });

  const req = new Request("http://localhost/notificaciones", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Workflow-Secret": VALID_SECRET,
    },
    body: JSON.stringify({
      fecha_ejecucion: "2026-11-16",
      ids_clientes: [CLIENTE_1],
    }),
  });

  const res = await handler(req, deps);
  assertEquals(res.status, 200);
  assertEquals(sentEmails.length, 0);
  const json = await res.json();
  assertEquals(json.clientes_omitidos, 1);
  assertEquals(json.detalle[0].motivo, "ya_notificado");
});

Deno.test("Handler - Flujo exitoso completo con múltiples diagnósticos, idempotencia y logs estructurados", async () => {
  const { deps, sentEmails, upsertedRows, logs } = getBaseMockDeps({
    diagnosticos: [
      {
        id: "diag-1",
        friccion_id: "fric-1",
        nombre_corto: "Demora en checkout",
        titulo: "Checkout lento",
        severidad: "alta",
        impacto_resumen: "Pérdida de ventas",
        fecha_ejecucion: "2026-11-16",
        created_at: "2026-11-16T01:00:00Z",
        updated_at: "2026-11-16T02:00:00Z",
        fricciones: {
          client_id: CLIENTE_1,
          sesiones_perdidas: 100,
          tasa_abandono: 0.4,
        },
      },
      {
        id: "diag-2",
        friccion_id: "fric-2",
        nombre_corto: "Botón oculto en móvil",
        titulo: "Botón oculto",
        severidad: "media",
        impacto_resumen: "Fricción visual",
        fecha_ejecucion: "2026-11-16",
        created_at: "2026-11-16T01:00:00Z",
        updated_at: "2026-11-16T02:00:00Z",
        fricciones: {
          client_id: CLIENTE_1,
          sesiones_perdidas: 40,
          tasa_abandono: 0.2,
        },
      },
    ],
    miembros: [
      { cliente_id: CLIENTE_1, email: "lead@test.com", nombre: "Gonzalo" },
      { cliente_id: CLIENTE_1, email: "dev@test.com", nombre: "Lucía" },
    ],
  });

  const req = new Request("http://localhost/notificaciones", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Workflow-Secret": VALID_SECRET,
    },
    body: JSON.stringify({
      fecha_ejecucion: "2026-11-16",
      ids_clientes: [CLIENTE_1, CLIENTE_1], // verifica deduplicación
    }),
  });

  const res = await handler(req, deps);
  assertEquals(res.status, 200);
  const json = await res.json();
  assertEquals(json.estado, "COMPLETADO");
  assertEquals(json.clientes_procesados, 1);
  assertEquals(json.clientes_notificados, 1);
  assertEquals(json.clientes_omitidos, 0);
  assertEquals(json.clientes_fallidos, 0);
  assertEquals(json.detalle[0].diagnosticos_notificados, 2);
  assertEquals(json.detalle[0].destinatarios, 2);

  assertEquals(sentEmails.length, 1);
  assertEquals(sentEmails[0].to, ["lead@test.com", "dev@test.com"]);
  assertStringIncludes(sentEmails[0].html, "2");
  assertEquals(upsertedRows().length, 2);

  const sentLog = logs.find((l) => l.data.evento === "notificacion_enviada");
  assertEquals(sentLog?.data.etapa, "NOTIFICACIONES");
  assertEquals(sentLog?.data.fecha_ejecucion, "2026-11-16");
  assertEquals(sentLog?.data.id_cliente, CLIENTE_1);
});

// ==========================================
// 4. Resiliencia, Aislamiento y Errores 500
// ==========================================

Deno.test("Handler - Aísla fallo puntual de un cliente sin bloquear al resto", async () => {
  const { deps, sentEmails } = getBaseMockDeps({
    perfiles: [
      {
        cliente_id: CLIENTE_1,
        nombre_organizacion: "Cliente Malo",
        estado_cuenta: "activo",
      },
      {
        cliente_id: CLIENTE_2,
        nombre_organizacion: "Cliente Bueno",
        estado_cuenta: "activo",
      },
    ],
    diagnosticos: [
      {
        id: "diag-1",
        friccion_id: "fric-1",
        nombre_corto: "F1",
        titulo: "T1",
        severidad: "alta",
        impacto_resumen: "Imp",
        fecha_ejecucion: "2026-11-16",
        created_at: "2026-11-16T01:00:00Z",
        updated_at: "2026-11-16T02:00:00Z",
        fricciones: {
          client_id: CLIENTE_1,
          sesiones_perdidas: 10,
          tasa_abandono: 0.1,
        },
      },
      {
        id: "diag-2",
        friccion_id: "fric-2",
        nombre_corto: "F2",
        titulo: "T2",
        severidad: "media",
        impacto_resumen: "Imp",
        fecha_ejecucion: "2026-11-16",
        created_at: "2026-11-16T01:00:00Z",
        updated_at: "2026-11-16T02:00:00Z",
        fricciones: {
          client_id: CLIENTE_2,
          sesiones_perdidas: 20,
          tasa_abandono: 0.2,
        },
      },
    ],
    miembros: [
      { cliente_id: CLIENTE_1, email: "invalido@", nombre: "Uno" },
      { cliente_id: CLIENTE_2, email: "ok@eureka.app", nombre: "Dos" },
    ],
    resendResponder: (_body, callIndex) => {
      if (callIndex === 1) {
        return { status: 422, body: "Invalid recipient" };
      }
      return { status: 200, body: { id: "resend_ok_2" } };
    },
  });

  const req = new Request("http://localhost/notificaciones", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Workflow-Secret": VALID_SECRET,
    },
    body: JSON.stringify({
      fecha_ejecucion: "2026-11-16",
      ids_clientes: [CLIENTE_1, CLIENTE_2],
    }),
  });

  const res = await handler(req, deps);
  assertEquals(res.status, 200);
  assertEquals(sentEmails.length, 2);
  const json = await res.json();
  assertEquals(json.estado, "COMPLETADO_CON_ERRORES");
  assertEquals(json.clientes_notificados, 1);
  assertEquals(json.clientes_fallidos, 1);
  assertEquals(json.detalle[0].estado, "fallido");
  assertEquals(json.detalle[1].estado, "notificado");
});

Deno.test("Handler - Retorna 500 cuando falla consulta global a Supabase o Resend cae globalmente", async () => {
  const { deps: dbErrDeps } = getBaseMockDeps({
    diagnosticosError: { message: "Timeout en Postgres" },
  });

  const reqDb = new Request("http://localhost/notificaciones", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Workflow-Secret": VALID_SECRET,
    },
    body: JSON.stringify({
      fecha_ejecucion: "2026-11-16",
      ids_clientes: [CLIENTE_1],
    }),
  });
  const resDb = await handler(reqDb, dbErrDeps);
  assertEquals(resDb.status, 500);

  const { deps: resendDownDeps } = getBaseMockDeps({
    resendResponder: () => ({ status: 503, body: "Service Unavailable" }),
  });
  const reqResend = new Request("http://localhost/notificaciones", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Workflow-Secret": VALID_SECRET,
    },
    body: JSON.stringify({
      fecha_ejecucion: "2026-11-16",
      ids_clientes: [CLIENTE_1],
    }),
  });
  const resResend = await handler(reqResend, resendDownDeps);
  assertEquals(resResend.status, 500);
});

Deno.test("Handler - Retorna 500 cuando faltan variables de entorno críticas", async () => {
  const { deps } = getBaseMockDeps({
    envOverrides: {
      RESEND_API_KEY: undefined,
    },
  });

  const req = new Request("http://localhost/notificaciones", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Workflow-Secret": VALID_SECRET,
    },
    body: JSON.stringify({
      fecha_ejecucion: "2026-11-16",
      ids_clientes: [CLIENTE_1],
    }),
  });
  const res = await handler(req, deps);
  assertEquals(res.status, 500);
});
