import { SupabaseClient } from "npm:@supabase/supabase-js@2";
import {
  ClientePerfil,
  Destinatario,
  DiagnosticoFriccion,
  NotificacionEnviadaRegistro,
} from "../models.ts";

const PRIORIDAD_SEVERIDAD: Record<string, number> = {
  alta: 3,
  media: 2,
  baja: 1,
};

interface DiagnosticoQueryRow {
  id: string;
  friccion_id: string;
  nombre_corto: string | null;
  titulo: string | null;
  severidad: string | null;
  impacto_resumen: string | null;
  fecha_ejecucion: string | null;
  created_at: string | null;
  updated_at: string | null;
  fricciones:
    | {
      client_id: string;
      sesiones_perdidas: number | null;
      tasa_abandono: number | null;
    }
    | Array<{
      client_id: string;
      sesiones_perdidas: number | null;
      tasa_abandono: number | null;
    }>;
}

export function normalizarTimestamp(
  timestamp: string | null | undefined,
  fallbackFecha: string,
): string {
  if (timestamp) {
    const parsed = new Date(timestamp);
    if (!Number.isNaN(parsed.getTime())) {
      return parsed.toISOString();
    }
  }
  return `${fallbackFecha}T00:00:00.000Z`;
}

export function claveVersionDiagnostico(
  diagnosticoId: string,
  diagnosticoUpdatedAt: string,
): string {
  return `${diagnosticoId}::${diagnosticoUpdatedAt}`;
}

export function seleccionarDiagnosticoPrincipal(
  diagnosticos: DiagnosticoFriccion[],
): DiagnosticoFriccion {
  return [...diagnosticos].sort((a, b) => {
    const sevA = PRIORIDAD_SEVERIDAD[(a.severidad ?? "").toLowerCase()] ?? 0;
    const sevB = PRIORIDAD_SEVERIDAD[(b.severidad ?? "").toLowerCase()] ?? 0;
    if (sevB !== sevA) return sevB - sevA;

    const perdidasA = Number(a.sesiones_perdidas ?? 0);
    const perdidasB = Number(b.sesiones_perdidas ?? 0);
    if (perdidasB !== perdidasA) return perdidasB - perdidasA;

    const tasaA = Number(a.tasa_abandono ?? 0);
    const tasaB = Number(b.tasa_abandono ?? 0);
    return tasaB - tasaA;
  })[0];
}

export async function obtenerPerfilesClientes(
  client: SupabaseClient,
  idsClientes: string[],
): Promise<Map<string, ClientePerfil>> {
  const mapa = new Map<string, ClientePerfil>();
  if (idsClientes.length === 0) return mapa;

  const { data, error } = await client
    .from("clientes_perfil")
    .select("cliente_id, nombre_organizacion, estado_cuenta")
    .in("cliente_id", idsClientes);

  if (error) {
    throw new Error(`Error consultando clientes_perfil: ${error.message}`);
  }

  for (const row of (data ?? []) as ClientePerfil[]) {
    if (row.cliente_id) {
      mapa.set(row.cliente_id, row);
    }
  }

  return mapa;
}

export async function obtenerDiagnosticosCicloPorClientes(
  client: SupabaseClient,
  idsClientes: string[],
  fechaEjecucion: string,
): Promise<Map<string, DiagnosticoFriccion[]>> {
  const mapa = new Map<string, DiagnosticoFriccion[]>();
  if (idsClientes.length === 0) return mapa;

  const { data, error } = await client
    .from("fricciones_diagnosticos")
    .select(
      "id, friccion_id, nombre_corto, titulo, severidad, impacto_resumen, fecha_ejecucion, created_at, updated_at, fricciones!inner(client_id, sesiones_perdidas, tasa_abandono)",
    )
    .in("fricciones.client_id", idsClientes)
    .eq("fecha_ejecucion", fechaEjecucion);

  if (error) {
    throw new Error(
      `Error consultando fricciones_diagnosticos: ${error.message}`,
    );
  }

  for (const row of (data ?? []) as DiagnosticoQueryRow[]) {
    const friccion = Array.isArray(row.fricciones) ? row.fricciones[0] : row.fricciones;
    if (!friccion?.client_id) continue;

    const item: DiagnosticoFriccion = {
      id: row.id,
      friccion_id: row.friccion_id,
      client_id: friccion.client_id,
      nombre_corto: row.nombre_corto,
      titulo: row.titulo,
      severidad: row.severidad,
      impacto_resumen: row.impacto_resumen,
      fecha_ejecucion: row.fecha_ejecucion,
      created_at: row.created_at,
      updated_at: row.updated_at,
      sesiones_perdidas: friccion.sesiones_perdidas ?? null,
      tasa_abandono: friccion.tasa_abandono ?? null,
    };

    const lista = mapa.get(item.client_id) ?? [];
    lista.push(item);
    mapa.set(item.client_id, lista);
  }

  return mapa;
}

export async function obtenerVersionesYaNotificadas(
  client: SupabaseClient,
  diagnosticoIds: string[],
  fallbackFecha: string,
): Promise<Set<string>> {
  const notificadas = new Set<string>();
  if (diagnosticoIds.length === 0) return notificadas;

  const { data, error } = await client
    .from("notificaciones_enviadas")
    .select("diagnostico_id, diagnostico_updated_at")
    .in("diagnostico_id", diagnosticoIds)
    .eq("estado", "enviado");

  if (error) {
    throw new Error(
      `Error consultando notificaciones_enviadas: ${error.message}`,
    );
  }

  for (
    const row of (data ?? []) as Array<{
      diagnostico_id: string;
      diagnostico_updated_at: string;
    }>
  ) {
    if (!row.diagnostico_id) continue;
    const version = normalizarTimestamp(
      row.diagnostico_updated_at,
      fallbackFecha,
    );
    notificadas.add(claveVersionDiagnostico(row.diagnostico_id, version));
  }

  return notificadas;
}

export async function obtenerDestinatariosPorClientes(
  client: SupabaseClient,
  idsClientes: string[],
): Promise<Map<string, Destinatario[]>> {
  const mapa = new Map<string, Destinatario[]>();
  if (idsClientes.length === 0) return mapa;

  const { data, error } = await client
    .from("organizacion_miembros")
    .select("cliente_id, email, nombre")
    .in("cliente_id", idsClientes)
    .eq("activo", true);

  if (error) {
    throw new Error(
      `Error consultando organizacion_miembros: ${error.message}`,
    );
  }

  for (const row of (data ?? []) as Destinatario[]) {
    if (!row.cliente_id || !row.email) continue;
    const lista = mapa.get(row.cliente_id) ?? [];
    lista.push(row);
    mapa.set(row.cliente_id, lista);
  }

  return mapa;
}

export async function registrarNotificacionesEnviadas(
  client: SupabaseClient,
  registros: NotificacionEnviadaRegistro[],
): Promise<void> {
  if (registros.length === 0) return;

  const { error } = await client
    .from("notificaciones_enviadas")
    .upsert(registros, {
      onConflict: "diagnostico_id,diagnostico_updated_at",
      ignoreDuplicates: true,
    });

  if (error) {
    throw new Error(
      `Error registrando notificaciones_enviadas: ${error.message}`,
    );
  }
}
