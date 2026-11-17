import { assertEquals, assertRejects } from "@std/assert";
import { SupabaseClient } from "npm:@supabase/supabase-js@2";
import {
  claveVersionDiagnostico,
  normalizarTimestamp,
  obtenerDestinatariosPorClientes,
  obtenerDiagnosticosCicloPorClientes,
  obtenerPerfilesClientes,
  obtenerVersionesYaNotificadas,
  registrarNotificacionesEnviadas,
  seleccionarDiagnosticoPrincipal,
} from "../services/supabase_service.ts";
import {
  EnviarEmailParams,
  enviarEmailTransaccional,
  ResendApiError,
} from "../services/resend_service.ts";

function createMockSupabase(handlers: {
  clientes_perfil?: () => Promise<{ data: unknown; error: unknown }>;
  fricciones_diagnosticos?: () => Promise<{ data: unknown; error: unknown }>;
  notificaciones_enviadas_select?: () => Promise<{ data: unknown; error: unknown }>;
  notificaciones_enviadas_upsert?: (
    rows: unknown,
    opts: unknown,
  ) => Promise<{ error: unknown }>;
  organizacion_miembros?: () => Promise<{ data: unknown; error: unknown }>;
}): SupabaseClient {
  return {
    from: (table: string) => ({
      select: (_cols: string) => ({
        in: (_col: string, _vals: unknown[]) => {
          if (table === "clientes_perfil") {
            return handlers.clientes_perfil
              ? handlers.clientes_perfil()
              : Promise.resolve({ data: [], error: null });
          }
          if (table === "fricciones_diagnosticos") {
            return {
              eq: (_eqCol: string, _eqVal: unknown) =>
                handlers.fricciones_diagnosticos
                  ? handlers.fricciones_diagnosticos()
                  : Promise.resolve({ data: [], error: null }),
            };
          }
          if (table === "notificaciones_enviadas") {
            return {
              eq: (_eqCol: string, _eqVal: unknown) =>
                handlers.notificaciones_enviadas_select
                  ? handlers.notificaciones_enviadas_select()
                  : Promise.resolve({ data: [], error: null }),
            };
          }
          if (table === "organizacion_miembros") {
            return {
              eq: (_eqCol: string, _eqVal: unknown) =>
                handlers.organizacion_miembros
                  ? handlers.organizacion_miembros()
                  : Promise.resolve({ data: [], error: null }),
            };
          }
          return Promise.resolve({ data: [], error: null });
        },
      }),
      upsert: (rows: unknown, opts: unknown) => {
        if (table === "notificaciones_enviadas" && handlers.notificaciones_enviadas_upsert) {
          return handlers.notificaciones_enviadas_upsert(rows, opts);
        }
        return Promise.resolve({ error: null });
      },
    }),
  } as unknown as SupabaseClient;
}

// ==========================================
// Helpers de dominio
// ==========================================

Deno.test("normalizarTimestamp - unifica formatos ISO y usa fallback si es inválido", () => {
  assertEquals(
    normalizarTimestamp("2026-11-16T12:30:00+00:00", "2026-11-16"),
    "2026-11-16T12:30:00.000Z",
  );
  assertEquals(
    normalizarTimestamp(null, "2026-11-16"),
    "2026-11-16T00:00:00.000Z",
  );
  assertEquals(
    normalizarTimestamp("fecha-invalida", "2026-11-16"),
    "2026-11-16T00:00:00.000Z",
  );
});

Deno.test("seleccionarDiagnosticoPrincipal - prioriza severidad y luego sesiones perdidas", () => {
  const elegido = seleccionarDiagnosticoPrincipal([
    {
      id: "d-baja",
      friccion_id: "f-1",
      client_id: "c-1",
      nombre_corto: "Fricción baja",
      titulo: null,
      severidad: "baja",
      impacto_resumen: null,
      fecha_ejecucion: "2026-11-16",
      created_at: null,
      updated_at: null,
      sesiones_perdidas: 500,
      tasa_abandono: 0.9,
    },
    {
      id: "d-alta-menor",
      friccion_id: "f-2",
      client_id: "c-1",
      nombre_corto: "Fricción alta menor",
      titulo: null,
      severidad: "alta",
      impacto_resumen: null,
      fecha_ejecucion: "2026-11-16",
      created_at: null,
      updated_at: null,
      sesiones_perdidas: 20,
      tasa_abandono: 0.3,
    },
    {
      id: "d-alta-mayor",
      friccion_id: "f-3",
      client_id: "c-1",
      nombre_corto: "Fricción alta mayor",
      titulo: null,
      severidad: "alta",
      impacto_resumen: null,
      fecha_ejecucion: "2026-11-16",
      created_at: null,
      updated_at: null,
      sesiones_perdidas: 150,
      tasa_abandono: 0.5,
    },
  ]);

  assertEquals(elegido.id, "d-alta-mayor");
});

// ==========================================
// Pruebas de supabase_service.ts
// ==========================================

Deno.test("obtenerPerfilesClientes - mapea perfiles por cliente_id y propaga errores", async () => {
  const mockClient = createMockSupabase({
    clientes_perfil: () =>
      Promise.resolve({
        data: [
          {
            cliente_id: "c-1",
            nombre_organizacion: "Acme",
            estado_cuenta: "activo",
          },
        ],
        error: null,
      }),
  });

  const perfiles = await obtenerPerfilesClientes(mockClient, ["c-1"]);
  assertEquals(perfiles.get("c-1")?.nombre_organizacion, "Acme");
  assertEquals((await obtenerPerfilesClientes(mockClient, [])).size, 0);

  await registrarNotificacionesEnviadas(mockClient, []);

  const mockError = createMockSupabase({
    clientes_perfil: () => Promise.resolve({ data: null, error: { message: "DB caída" } }),
  });
  await assertRejects(
    () => obtenerPerfilesClientes(mockError, ["c-1"]),
    Error,
    "Error consultando clientes_perfil: DB caída",
  );
});

Deno.test("obtenerDiagnosticosCicloPorClientes - agrupa por client_id con join objeto o arreglo", async () => {
  const mockClient = createMockSupabase({
    fricciones_diagnosticos: () =>
      Promise.resolve({
        data: [
          {
            id: "diag-1",
            friccion_id: "fric-1",
            nombre_corto: "Error checkout",
            titulo: "Título 1",
            severidad: "alta",
            impacto_resumen: "Alto impacto",
            fecha_ejecucion: "2026-11-16",
            created_at: "2026-11-16T01:00:00Z",
            updated_at: "2026-11-16T02:00:00Z",
            fricciones: {
              client_id: "c-1",
              sesiones_perdidas: 100,
              tasa_abandono: 0.45,
            },
          },
          {
            id: "diag-2",
            friccion_id: "fric-2",
            nombre_corto: "Demora login",
            titulo: "Título 2",
            severidad: "media",
            impacto_resumen: "Medio impacto",
            fecha_ejecucion: "2026-11-16",
            created_at: "2026-11-16T01:00:00Z",
            updated_at: "2026-11-16T03:00:00Z",
            fricciones: [
              {
                client_id: "c-2",
                sesiones_perdidas: 30,
                tasa_abandono: 0.2,
              },
            ],
          },
        ],
        error: null,
      }),
  });

  const mapa = await obtenerDiagnosticosCicloPorClientes(
    mockClient,
    ["c-1", "c-2"],
    "2026-11-16",
  );
  assertEquals(mapa.get("c-1")?.length, 1);
  assertEquals(mapa.get("c-1")?.[0].id, "diag-1");
  assertEquals(mapa.get("c-2")?.[0].sesiones_perdidas, 30);
});

Deno.test("supabase_service - ramas vacías, nulas y errores en consultas", async () => {
  const mockEmpty = createMockSupabase({});
  assertEquals((await obtenerDiagnosticosCicloPorClientes(mockEmpty, [], "2026-11-16")).size, 0);
  assertEquals((await obtenerVersionesYaNotificadas(mockEmpty, [], "2026-11-16")).size, 0);
  assertEquals((await obtenerDestinatariosPorClientes(mockEmpty, [])).size, 0);

  const mockNullData = createMockSupabase({
    clientes_perfil: () => Promise.resolve({ data: [{ cliente_id: "" }], error: null }),
    fricciones_diagnosticos: () =>
      Promise.resolve({
        data: [
          {
            id: "diag-sin-client",
            friccion_id: "f-0",
            nombre_corto: null,
            titulo: null,
            severidad: null,
            impacto_resumen: null,
            fecha_ejecucion: null,
            created_at: null,
            updated_at: null,
            fricciones: [],
          },
          {
            id: "diag-null-metrics",
            friccion_id: "f-1",
            nombre_corto: "N",
            titulo: null,
            severidad: null,
            impacto_resumen: null,
            fecha_ejecucion: "2026-11-16",
            created_at: null,
            updated_at: null,
            fricciones: { client_id: "c-9", sesiones_perdidas: null, tasa_abandono: null },
          },
        ],
        error: null,
      }),
    notificaciones_enviadas_select: () =>
      Promise.resolve({
        data: [{ diagnostico_id: "", diagnostico_updated_at: "2026-11-16T00:00:00Z" }],
        error: null,
      }),
  });

  assertEquals((await obtenerPerfilesClientes(mockNullData, ["c-9"])).size, 0);
  const diags = await obtenerDiagnosticosCicloPorClientes(mockNullData, ["c-9"], "2026-11-16");
  assertEquals(diags.get("c-9")?.length, 1);
  assertEquals(diags.get("c-9")?.[0].sesiones_perdidas, null);
  assertEquals((await obtenerVersionesYaNotificadas(mockNullData, ["diag-1"], "2026-11-16")).size, 0);

  const mockErrs = createMockSupabase({
    fricciones_diagnosticos: () => Promise.resolve({ data: null, error: { message: "err diag" } }),
    notificaciones_enviadas_select: () => Promise.resolve({ data: null, error: { message: "err notif" } }),
  });
  await assertRejects(
    () => obtenerDiagnosticosCicloPorClientes(mockErrs, ["c-1"], "2026-11-16"),
    Error,
    "Error consultando fricciones_diagnosticos: err diag",
  );
  await assertRejects(
    () => obtenerVersionesYaNotificadas(mockErrs, ["d-1"], "2026-11-16"),
    Error,
    "Error consultando notificaciones_enviadas: err notif",
  );
});

Deno.test("obtenerVersionesYaNotificadas - normaliza timestamps y retorna set de claves", async () => {
  const mockClient = createMockSupabase({
    notificaciones_enviadas_select: () =>
      Promise.resolve({
        data: [
          {
            diagnostico_id: "diag-1",
            diagnostico_updated_at: "2026-11-16T02:00:00+00:00",
          },
        ],
        error: null,
      }),
  });

  const set = await obtenerVersionesYaNotificadas(
    mockClient,
    ["diag-1"],
    "2026-11-16",
  );
  assertEquals(
    set.has(claveVersionDiagnostico("diag-1", "2026-11-16T02:00:00.000Z")),
    true,
  );
});

Deno.test("obtenerDestinatariosPorClientes - agrupa por cliente y filtra emails vacíos", async () => {
  const mockClient = createMockSupabase({
    organizacion_miembros: () =>
      Promise.resolve({
        data: [
          { cliente_id: "c-1", email: "user1@example.com", nombre: "Usuario Uno" },
          { cliente_id: "c-1", email: "", nombre: "Sin Email" },
          { cliente_id: "c-1", email: null, nombre: "Email Null" },
          { cliente_id: "c-2", email: "user2@example.com", nombre: "Usuario Dos" },
        ],
        error: null,
      }),
  });

  const mapa = await obtenerDestinatariosPorClientes(mockClient, ["c-1", "c-2"]);
  assertEquals(mapa.get("c-1")?.length, 1);
  assertEquals(mapa.get("c-1")?.[0].email, "user1@example.com");
  assertEquals(mapa.get("c-2")?.length, 1);
});

Deno.test("obtenerDestinatariosPorClientes - lanza error cuando falla Supabase", async () => {
  const mockClient = createMockSupabase({
    organizacion_miembros: () =>
      Promise.resolve({
        data: null,
        error: { message: "Error de conexión" },
      }),
  });

  await assertRejects(
    () => obtenerDestinatariosPorClientes(mockClient, ["c-1"]),
    Error,
    "Error consultando organizacion_miembros: Error de conexión",
  );
});

Deno.test("registrarNotificacionesEnviadas - ejecuta upsert idempotente y lanza error si falla", async () => {
  let capturedOpts: unknown = null;
  const mockClient = createMockSupabase({
    notificaciones_enviadas_upsert: (_rows, opts) => {
      capturedOpts = opts;
      return Promise.resolve({ error: null });
    },
  });

  await registrarNotificacionesEnviadas(mockClient, [
    {
      cliente_id: "c-1",
      friccion_id: "f-1",
      diagnostico_id: "d-1",
      diagnostico_updated_at: "2026-11-16T02:00:00.000Z",
      fecha_ejecucion: "2026-11-16",
      resend_email_id: "re_1",
      destinatarios: ["a@test.com"],
      estado: "enviado",
    },
  ]);

  assertEquals(capturedOpts, {
    onConflict: "diagnostico_id,diagnostico_updated_at",
    ignoreDuplicates: true,
  });

  await registrarNotificacionesEnviadas(mockClient, []);

  const mockError = createMockSupabase({
    notificaciones_enviadas_upsert: () => Promise.resolve({ error: { message: "Insert fallido" } }),
  });
  await assertRejects(
    () =>
      registrarNotificacionesEnviadas(mockError, [
        {
          cliente_id: "c-1",
          friccion_id: "f-1",
          diagnostico_id: "d-1",
          diagnostico_updated_at: "2026-11-16T02:00:00.000Z",
          fecha_ejecucion: "2026-11-16",
          resend_email_id: null,
          destinatarios: [],
          estado: "enviado",
        },
      ]),
    Error,
    "Error registrando notificaciones_enviadas: Insert fallido",
  );
});

// ==========================================
// Pruebas de resend_service.ts
// ==========================================

Deno.test("enviarEmailTransaccional - envía petición HTTPS correcta a la API de Resend", async () => {
  let capturedUrl = "";
  let capturedOptions: RequestInit | undefined;

  const mockFetch: typeof fetch = (
    input: RequestInfo | URL,
    init?: RequestInit,
  ) => {
    capturedUrl = input.toString();
    capturedOptions = init;
    return Promise.resolve(
      new Response(JSON.stringify({ id: "resend_msg_001" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
  };

  const params: EnviarEmailParams = {
    from: "Eureka <alertas@eureka.app>",
    to: ["dev@empresa.com"],
    subject: "Reporte de UX",
    html: "<p>Hola</p>",
  };

  const resultado = await enviarEmailTransaccional(
    "re_test_key_123",
    params,
    mockFetch,
  );

  assertEquals(resultado.id, "resend_msg_001");
  assertEquals(capturedUrl, "https://api.resend.com/emails");
  assertEquals(capturedOptions?.method, "POST");

  const headers = capturedOptions?.headers as Record<string, string>;
  assertEquals(headers["Content-Type"], "application/json");
  assertEquals(headers["Authorization"], "Bearer re_test_key_123");

  const parsedBody = JSON.parse(capturedOptions?.body as string);
  assertEquals(parsedBody, params);
});

Deno.test("enviarEmailTransaccional - clasifica errores transitorios vs puntuales", async () => {
  const mock429: typeof fetch = () =>
    Promise.resolve(
      new Response("Rate limit exceeded", { status: 429 }),
    );

  const err429 = await assertRejects(
    () =>
      enviarEmailTransaccional(
        "re_test",
        { from: "a", to: ["b"], subject: "s", html: "h" },
        mock429,
      ),
    ResendApiError,
    "Fallo en Resend API (429): Rate limit exceeded",
  );
  assertEquals(err429.esTransitorio, true);
  assertEquals(err429.esGlobal, true);

  const mock422: typeof fetch = () =>
    Promise.resolve(
      new Response("Invalid email address", { status: 422 }),
    );

  const err422 = await assertRejects(
    () =>
      enviarEmailTransaccional(
        "re_test",
        { from: "a", to: ["bad"], subject: "s", html: "h" },
        mock422,
      ),
    ResendApiError,
    "Fallo en Resend API (422): Invalid email address",
  );
  assertEquals(err422.esTransitorio, false);
  assertEquals(err422.esGlobal, false);
});
