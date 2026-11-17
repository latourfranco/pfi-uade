import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient, SupabaseClient } from "npm:@supabase/supabase-js@2";
import { renderAsync } from "npm:@react-email/components@0.0.22";
import React from "npm:react@18.3.1";
import { DiagnosticoEmail } from "./templates/DiagnosticoEmail.tsx";
import {
  claveVersionDiagnostico,
  normalizarTimestamp,
  obtenerDestinatariosPorClientes,
  obtenerDiagnosticosCicloPorClientes,
  obtenerPerfilesClientes,
  obtenerVersionesYaNotificadas,
  registrarNotificacionesEnviadas,
  seleccionarDiagnosticoPrincipal,
} from "./services/supabase_service.ts";
import { enviarEmailTransaccional, ResendApiError } from "./services/resend_service.ts";
import {
  ClientePerfil,
  Destinatario,
  DetalleClienteResultado,
  DiagnosticoFriccion,
  NotificacionEnviadaRegistro,
  RespuestaNotificaciones,
  WorkflowNotificacionesPayload,
} from "./models.ts";

export interface HandlerDeps {
  env?: (key: string) => string | undefined;
  fetch?: typeof fetch;
  createClient?: (url: string, key: string) => SupabaseClient;
  renderAsync?: typeof renderAsync;
  log?: (level: "INFO" | "WARN" | "ERROR", line: string) => void;
}

const JSON_HEADERS = { "Content-Type": "application/json" };
const ETAPA = "NOTIFICACIONES";
const FECHA_REGEX = /^\d{4}-\d{2}-\d{2}$/;

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: JSON_HEADERS,
  });
}

function defaultLogger(level: "INFO" | "WARN" | "ERROR", line: string): void {
  if (level === "ERROR") {
    console.error(line);
  } else {
    console.log(line);
  }
}

function emitirLog(
  logFn: (level: "INFO" | "WARN" | "ERROR", line: string) => void,
  nivel: "INFO" | "WARN" | "ERROR",
  evento: string,
  datos: {
    fecha_ejecucion: string | null;
    id_cliente?: string | null;
    metricas?: Record<string, unknown>;
    error?: string;
  },
): void {
  const payload = {
    timestamp: new Date().toISOString(),
    nivel,
    etapa: ETAPA,
    evento,
    fecha_ejecucion: datos.fecha_ejecucion,
    id_cliente: datos.id_cliente ?? null,
    ...(datos.metricas ? { metricas: datos.metricas } : {}),
    ...(datos.error ? { error: datos.error } : {}),
  };
  logFn(nivel, JSON.stringify(payload));
}

function compararSecretosSeguro(a: string, b: string): boolean {
  const encoder = new TextEncoder();
  const bytesA = encoder.encode(a);
  const bytesB = encoder.encode(b);
  if (bytesA.length !== bytesB.length) return false;
  let diff = 0;
  for (let i = 0; i < bytesA.length; i++) {
    diff |= bytesA[i] ^ bytesB[i];
  }
  return diff === 0;
}

function esFechaCalendarioValida(fecha: string): boolean {
  if (!FECHA_REGEX.test(fecha)) return false;
  const [anio, mes, dia] = fecha.split("-").map(Number);
  const date = new Date(Date.UTC(anio, mes - 1, dia));
  return (
    date.getUTCFullYear() === anio &&
    date.getUTCMonth() === mes - 1 &&
    date.getUTCDate() === dia
  );
}

function validarPayload(
  raw: unknown,
): { ok: true; data: WorkflowNotificacionesPayload } | { ok: false } {
  if (!raw || typeof raw !== "object") return { ok: false };
  const obj = raw as Record<string, unknown>;
  const fecha = obj.fecha_ejecucion;
  const ids = obj.ids_clientes;

  if (typeof fecha !== "string" || !esFechaCalendarioValida(fecha)) {
    return { ok: false };
  }
  if (
    !Array.isArray(ids) ||
    ids.some((id) => typeof id !== "string" || id.trim().length === 0)
  ) {
    return { ok: false };
  }

  const idsUnicos = Array.from(new Set(ids.map((id) => id.trim())));
  return {
    ok: true,
    data: {
      fecha_ejecucion: fecha,
      ids_clientes: idsUnicos,
    },
  };
}

export async function handler(
  req: Request,
  deps: HandlerDeps = {},
): Promise<Response> {
  const env = deps.env ?? ((key: string) => Deno.env.get(key));
  const fetchFn = deps.fetch ?? fetch;
  const clientFactory = deps.createClient ?? createClient;
  const renderFn = deps.renderAsync ?? renderAsync;
  const logFn = deps.log ?? defaultLogger;

  // 1. Validar método HTTP
  if (req.method !== "POST") {
    return jsonResponse({ error: "Método no permitido" }, 405);
  }

  // 2. Validar autenticidad de Cloud Workflows (X-Workflow-Secret)
  const secretHeader = req.headers.get("x-workflow-secret");
  const expectedSecret = env("WORKFLOW_NOTIFICACIONES_SECRET") ||
    env("NOTIFICATION_WEBHOOK_SECRET");

  if (
    !expectedSecret ||
    !secretHeader ||
    !compararSecretosSeguro(secretHeader, expectedSecret)
  ) {
    emitirLog(logFn, "WARN", "autenticacion_fallida", {
      fecha_ejecucion: null,
    });
    return jsonResponse({ error: "No autorizado" }, 401);
  }

  // 3. Validar payload JSON del orquestador
  let rawBody: unknown;
  try {
    rawBody = await req.json();
  } catch (_e) {
    return jsonResponse({ error: "Payload JSON inválido" }, 400);
  }

  const validacion = validarPayload(rawBody);
  if (!validacion.ok) {
    return jsonResponse({ error: "Payload inválido o incompleto" }, 400);
  }

  const { fecha_ejecucion: fechaEjecucion, ids_clientes: idsClientes } = validacion.data;

  // Sin clientes para procesar: no es un error
  if (idsClientes.length === 0) {
    const respuestaVacia: RespuestaNotificaciones = {
      estado: "COMPLETADO",
      fecha_ejecucion: fechaEjecucion,
      clientes_procesados: 0,
      clientes_notificados: 0,
      clientes_omitidos: 0,
      clientes_fallidos: 0,
      detalle: [],
    };
    emitirLog(logFn, "INFO", "ejecucion_sin_clientes", {
      fecha_ejecucion: fechaEjecucion,
      metricas: {
        clientes_procesados: 0,
        clientes_notificados: 0,
        clientes_omitidos: 0,
        clientes_fallidos: 0,
      },
    });
    return jsonResponse(respuestaVacia, 200);
  }

  const supabaseUrl = env("SUPABASE_URL") || "";
  const serviceRoleKey = env("SUPABASE_SERVICE_ROLE_KEY") || "";
  const resendApiKey = env("RESEND_API_KEY") || "";
  const frontendUrl = env("FRONTEND_URL") || "https://eureka.app";
  const resendFrom = env("RESEND_FROM_EMAIL") || "Eureka <alertas@eureka.app>";

  if (!supabaseUrl || !serviceRoleKey || !resendApiKey) {
    emitirLog(logFn, "ERROR", "configuracion_incompleta", {
      fecha_ejecucion: fechaEjecucion,
      error: "Faltan variables de entorno requeridas",
    });
    return jsonResponse({ error: "Configuración de entorno incompleta" }, 500);
  }

  const supabase = clientFactory(supabaseUrl, serviceRoleKey);

  // 4. Consultas globales por lote a Supabase (fallos aquí retornan 500 para reintento de Workflows)
  let perfilesMap: Map<string, ClientePerfil>;
  let diagnosticosMap: Map<string, DiagnosticoFriccion[]>;
  let versionesNotificadasSet: Set<string>;
  let destinatariosMap: Map<string, Destinatario[]>;

  try {
    perfilesMap = await obtenerPerfilesClientes(supabase, idsClientes);

    const clientesActivos = idsClientes.filter((id) => {
      const perfil = perfilesMap.get(id);
      return !perfil || perfil.estado_cuenta === "activo";
    });

    diagnosticosMap = await obtenerDiagnosticosCicloPorClientes(
      supabase,
      clientesActivos,
      fechaEjecucion,
    );

    const todosDiagnosticoIds = Array.from(diagnosticosMap.values())
      .flat()
      .map((d) => d.id);

    const clientesConDiagnosticos = clientesActivos.filter(
      (id) => (diagnosticosMap.get(id)?.length ?? 0) > 0,
    );

    [versionesNotificadasSet, destinatariosMap] = await Promise.all([
      obtenerVersionesYaNotificadas(
        supabase,
        todosDiagnosticoIds,
        fechaEjecucion,
      ),
      obtenerDestinatariosPorClientes(supabase, clientesConDiagnosticos),
    ]);
  } catch (error) {
    const err = error as Error;
    emitirLog(logFn, "ERROR", "error_consulta_global", {
      fecha_ejecucion: fechaEjecucion,
      error: err.message,
    });
    return jsonResponse({ error: err.message }, 500);
  }

  // 5. Procesamiento aislado por cliente
  const detalle: DetalleClienteResultado[] = [];
  let clientesNotificados = 0;
  let clientesOmitidos = 0;
  let clientesFallidos = 0;
  let fallosGlobalesOTransitorios = 0;

  for (const clienteId of idsClientes) {
    const perfil = perfilesMap.get(clienteId);
    if (perfil && perfil.estado_cuenta !== "activo") {
      clientesOmitidos++;
      detalle.push({
        cliente_id: clienteId,
        estado: "omitido",
        motivo: "cuenta_inactiva",
        diagnosticos_notificados: 0,
        destinatarios: 0,
      });
      emitirLog(logFn, "INFO", "cliente_omitido", {
        fecha_ejecucion: fechaEjecucion,
        id_cliente: clienteId,
        metricas: { motivo: "cuenta_inactiva" },
      });
      continue;
    }

    const diagnosticosCiclo = diagnosticosMap.get(clienteId) ?? [];
    if (diagnosticosCiclo.length === 0) {
      clientesOmitidos++;
      detalle.push({
        cliente_id: clienteId,
        estado: "omitido",
        motivo: "sin_diagnosticos",
        diagnosticos_notificados: 0,
        destinatarios: 0,
      });
      emitirLog(logFn, "INFO", "cliente_omitido", {
        fecha_ejecucion: fechaEjecucion,
        id_cliente: clienteId,
        metricas: { motivo: "sin_diagnosticos" },
      });
      continue;
    }

    const pendientes = diagnosticosCiclo.filter((diag) => {
      const version = normalizarTimestamp(
        diag.updated_at ?? diag.created_at,
        fechaEjecucion,
      );
      return !versionesNotificadasSet.has(
        claveVersionDiagnostico(diag.id, version),
      );
    });

    if (pendientes.length === 0) {
      clientesOmitidos++;
      detalle.push({
        cliente_id: clienteId,
        estado: "omitido",
        motivo: "ya_notificado",
        diagnosticos_notificados: 0,
        destinatarios: 0,
      });
      emitirLog(logFn, "INFO", "cliente_omitido", {
        fecha_ejecucion: fechaEjecucion,
        id_cliente: clienteId,
        metricas: { motivo: "ya_notificado" },
      });
      continue;
    }

    const destinatarios = destinatariosMap.get(clienteId) ?? [];
    if (destinatarios.length === 0) {
      clientesOmitidos++;
      detalle.push({
        cliente_id: clienteId,
        estado: "omitido",
        motivo: "sin_destinatarios",
        diagnosticos_notificados: 0,
        destinatarios: 0,
      });
      emitirLog(logFn, "INFO", "cliente_omitido", {
        fecha_ejecucion: fechaEjecucion,
        id_cliente: clienteId,
        metricas: { motivo: "sin_destinatarios" },
      });
      continue;
    }

    const principal = seleccionarDiagnosticoPrincipal(pendientes);
    const correos = destinatarios.map((d) => d.email);

    try {
      const html = await renderFn(
        React.createElement(DiagnosticoEmail, {
          nombreCliente: perfil?.nombre_organizacion || destinatarios[0].nombre || "Equipo",
          totalFricciones: pendientes.length,
          friccionPrincipal: principal.nombre_corto ?? principal.titulo ?? "Patrón no tipificado",
          impactoResumen: principal.impacto_resumen ?? "Impacto moderado",
          severidad: principal.severidad ?? "media",
          enlaceDashboard: `${frontendUrl}/dashboard`,
        }),
      );

      const resendResult = await enviarEmailTransaccional(
        resendApiKey,
        {
          from: resendFrom,
          to: correos,
          subject: "[Eureka] Nuevo diagnóstico de fricción disponible",
          html,
        },
        fetchFn,
      );

      const registros: NotificacionEnviadaRegistro[] = pendientes.map(
        (diag) => ({
          cliente_id: clienteId,
          friccion_id: diag.friccion_id,
          diagnostico_id: diag.id,
          diagnostico_updated_at: normalizarTimestamp(
            diag.updated_at ?? diag.created_at,
            fechaEjecucion,
          ),
          fecha_ejecucion: fechaEjecucion,
          resend_email_id: resendResult.id ?? null,
          destinatarios: correos,
          estado: "enviado",
        }),
      );

      try {
        await registrarNotificacionesEnviadas(supabase, registros);
      } catch (regError) {
        emitirLog(logFn, "ERROR", "error_registro_idempotencia", {
          fecha_ejecucion: fechaEjecucion,
          id_cliente: clienteId,
          error: (regError as Error).message,
        });
      }

      clientesNotificados++;
      detalle.push({
        cliente_id: clienteId,
        estado: "notificado",
        motivo: "enviado",
        diagnosticos_notificados: pendientes.length,
        destinatarios: correos.length,
        resend_id: resendResult.id,
      });
      emitirLog(logFn, "INFO", "notificacion_enviada", {
        fecha_ejecucion: fechaEjecucion,
        id_cliente: clienteId,
        metricas: {
          diagnosticos_notificados: pendientes.length,
          destinatarios: correos.length,
          resend_id: resendResult.id,
        },
      });
    } catch (error) {
      const err = error as Error;
      const esGlobalOTransitorio = err instanceof ResendApiError ? err.esGlobal : true;
      if (esGlobalOTransitorio) {
        fallosGlobalesOTransitorios++;
      }

      clientesFallidos++;
      detalle.push({
        cliente_id: clienteId,
        estado: "fallido",
        motivo: "error_envio",
        diagnosticos_notificados: 0,
        destinatarios: correos.length,
        error: err.message,
      });
      emitirLog(logFn, "ERROR", "error_envio_cliente", {
        fecha_ejecucion: fechaEjecucion,
        id_cliente: clienteId,
        error: err.message,
        metricas: { destinatarios: correos.length },
      });
    }
  }

  const respuesta: RespuestaNotificaciones = {
    estado: clientesFallidos > 0 ? "COMPLETADO_CON_ERRORES" : "COMPLETADO",
    fecha_ejecucion: fechaEjecucion,
    clientes_procesados: idsClientes.length,
    clientes_notificados: clientesNotificados,
    clientes_omitidos: clientesOmitidos,
    clientes_fallidos: clientesFallidos,
    detalle,
  };

  emitirLog(logFn, "INFO", "ejecucion_finalizada", {
    fecha_ejecucion: fechaEjecucion,
    metricas: {
      clientes_procesados: idsClientes.length,
      clientes_notificados: clientesNotificados,
      clientes_omitidos: clientesOmitidos,
      clientes_fallidos: clientesFallidos,
    },
  });

  // Devolver 500 solo si ningún envío tuvo éxito y todos los fallos fueron globales/transitorios
  if (
    clientesNotificados === 0 &&
    clientesFallidos > 0 &&
    fallosGlobalesOTransitorios === clientesFallidos
  ) {
    return jsonResponse(respuesta, 500);
  }

  return jsonResponse(respuesta, 200);
}

// Iniciar servidor solo si no estamos en entorno de pruebas
if (import.meta.main) {
  // @ts-ignore: Deno.serve es estándar en Deno 1.40+
  if (typeof Deno?.serve === "function") {
    // @ts-ignore: Deno.serve es estándar en Deno 1.40+
    Deno.serve((req: Request) => handler(req));
  } else {
    serve((req: Request) => handler(req));
  }
}
