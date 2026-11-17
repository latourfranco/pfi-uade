import { getSupabaseAdmin } from "@/lib/supabase/admin";

export type EstadoCuenta = "activo" | "baja_solicitada" | "purgado";
export type EstadoPurga = "en_proceso" | "completada" | "fallida";

export interface ClientePerfil {
  id: string;
  cliente_id: string;
  email?: string | null;
  nombre_organizacion: string;
  rubro: string;
  tamano_equipo: string;
  dominio_url: string | null;
  estado_cuenta: EstadoCuenta;
  onboarding_completado?: boolean;
  created_at: string;
  updated_at: string;
}

export interface UpsertClientePerfilDTO {
  clienteId: string;
  email?: string | null;
  nombreOrganizacion: string;
  rubro?: string;
  tamanoEquipo?: string;
  dominioUrl?: string | null;
  onboardingCompletado?: boolean;
}

export interface AuditoriaSupresion {
  id: string;
  cliente_id: string;
  fecha_solicitud: string;
  motivo: string;
  tokens_revocados: boolean;
  sesiones_invalidadas: boolean;
  bd_transaccional_purgada: boolean;
  dw_purga_disparada: boolean;
  estado_purga: EstadoPurga;
  metadata?: Record<string, unknown> | null;
}

export interface RegistrarAuditoriaSupresionDTO {
  clienteId: string;
  motivo?: string;
  tokensRevocados?: boolean;
  sesionesInvalidadas?: boolean;
  bdTransaccionalPurgada?: boolean;
  dwPurgaDisparada?: boolean;
  estadoPurga?: EstadoPurga;
  metadata?: Record<string, unknown>;
}

/**
 * Repositorio de acceso a datos para la gestión del perfil institucional
 * y el registro auditable del ejercicio del derecho de supresión de datos en Supabase.
 */
export class ClienteCuentaRepository {
  /**
   * Obtiene el perfil institucional asociado a un clienteId.
   */
  static async findPerfilByClienteId(
    clienteId: string
  ): Promise<ClientePerfil | null> {
    const supabase = getSupabaseAdmin();

    const { data, error } = await supabase
      .from("clientes_perfil")
      .select()
      .eq("cliente_id", clienteId)
      .maybeSingle();

    if (error) {
      throw error;
    }

    return data as ClientePerfil | null;
  }

  /**
   * Crea o actualiza el perfil institucional de un cliente (upsert).
   */
  static async upsertPerfil(
    data: UpsertClientePerfilDTO
  ): Promise<ClientePerfil> {
    const supabase = getSupabaseAdmin();

    const payload: Record<string, unknown> = {
      cliente_id: data.clienteId,
      nombre_organizacion: data.nombreOrganizacion,
      updated_at: new Date().toISOString(),
    };

    if (data.email !== undefined) {
      payload.email = data.email;
    }
    if (data.rubro !== undefined) {
      payload.rubro = data.rubro;
    }
    if (data.tamanoEquipo !== undefined) {
      payload.tamano_equipo = data.tamanoEquipo;
    }
    if (data.dominioUrl !== undefined) {
      payload.dominio_url = data.dominioUrl;
    }
    if (data.onboardingCompletado !== undefined) {
      payload.onboarding_completado = data.onboardingCompletado;
    }

    const { data: upserted, error } = await supabase
      .from("clientes_perfil")
      .upsert(payload, { onConflict: "cliente_id" })
      .select()
      .single();

    if (error) {
      throw error;
    }

    return upserted as ClientePerfil;
  }

  /**
   * Marca la cuenta de un cliente con estado 'baja_solicitada'.
   */
  static async marcarBajaCuenta(
    clienteId: string
  ): Promise<ClientePerfil | null> {
    const supabase = getSupabaseAdmin();

    const { data, error } = await supabase
      .from("clientes_perfil")
      .update({
        estado_cuenta: "baja_solicitada" as EstadoCuenta,
        updated_at: new Date().toISOString(),
      })
      .eq("cliente_id", clienteId)
      .select()
      .maybeSingle();

    if (error) {
      throw error;
    }

    return data as ClientePerfil | null;
  }

  /**
   * Registra una nueva entrada de auditoría para el ejercicio del derecho de supresión.
   */
  static async registrarAuditoriaSupresion(
    data: RegistrarAuditoriaSupresionDTO
  ): Promise<AuditoriaSupresion> {
    const supabase = getSupabaseAdmin();

    const { data: inserted, error } = await supabase
      .from("auditoria_supresion_datos")
      .insert({
        cliente_id: data.clienteId,
        motivo:
          data.motivo ??
          "Solicitud voluntaria del titular (Derecho de Supresión)",
        tokens_revocados: data.tokensRevocados ?? false,
        sesiones_invalidadas: data.sesionesInvalidadas ?? false,
        bd_transaccional_purgada: data.bdTransaccionalPurgada ?? false,
        dw_purga_disparada: data.dwPurgaDisparada ?? false,
        estado_purga: data.estadoPurga ?? "en_proceso",
        metadata: data.metadata ?? {},
      })
      .select()
      .single();

    if (error) {
      throw error;
    }

    return inserted as AuditoriaSupresion;
  }

  /**
   * Actualiza el estado de una orden de purga en la tabla de auditoría.
   */
  static async actualizarEstadoAuditoria(
    id: string,
    estadoPurga: EstadoPurga,
    metadata?: Record<string, unknown>
  ): Promise<AuditoriaSupresion> {
    const supabase = getSupabaseAdmin();

    const payload: Record<string, unknown> = {
      estado_purga: estadoPurga,
    };

    if (metadata !== undefined) {
      payload.metadata = metadata;
    }

    const { data: updated, error } = await supabase
      .from("auditoria_supresion_datos")
      .update(payload)
      .eq("id", id)
      .select()
      .single();

    if (error) {
      throw error;
    }

    return updated as AuditoriaSupresion;
  }

  /**
   * Registra o actualiza al usuario titular como administrador en organizacion_miembros.
   */
  static async upsertAdminMember(params: {
    clienteId: string;
    email: string;
    nombre: string;
  }): Promise<void> {
    const supabase = getSupabaseAdmin();
    const now = new Date().toISOString();

    const { data: existing, error: selectError } = await supabase
      .from("organizacion_miembros")
      .select("id")
      .eq("cliente_id", params.clienteId)
      .eq("email", params.email)
      .maybeSingle();

    if (selectError) {
      throw selectError;
    }

    if (existing) {
      const { error: updateError } = await supabase
        .from("organizacion_miembros")
        .update({
          nombre: params.nombre,
          rol: "admin",
          activo: true,
          updated_at: now,
        })
        .eq("id", existing.id);

      if (updateError) {
        throw updateError;
      }
      return;
    }

    const { error: insertError } = await supabase
      .from("organizacion_miembros")
      .insert({
        cliente_id: params.clienteId,
        email: params.email,
        nombre: params.nombre,
        rol: "admin",
        activo: true,
        updated_at: now,
      });

    if (insertError) {
      throw insertError;
    }
  }
}
