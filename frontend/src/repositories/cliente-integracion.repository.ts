import { getSupabaseAdmin } from "@/lib/supabase/admin";

export interface ClienteIntegracionFuente {
  id: string;
  cliente_id: string;
  ga4_property_id: string | null;
  client_gcp_project_id: string | null;
  gcp_region: string | null;
  base_url?: string | null;
  requires_authentication?: boolean | null;
  login_url?: string | null;
  test_username?: string | null;
  test_password_encrypted?: string | null;
  storage_state_encrypted?: string | null;
  activo: boolean;
  ultimo_lote_sincronizado: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateClienteIntegracionDTO {
  clienteId: string;
  ga4PropertyId: string;
  clientGcpProjectId: string;
  gcpRegion: string;
}

export interface UpsertOnboardingIntegracionDTO {
  clienteId: string;
  baseUrl?: string | null;
  requiresAuthentication?: boolean;
  loginUrl?: string | null;
  testUsername?: string | null;
  testPasswordEncrypted?: string | null;
  storageStateEncrypted?: string | null;
  ga4PropertyId?: string | null;
  clientGcpProjectId?: string | null;
  gcpRegion?: string | null;
}

/**
 * Repositorio de acceso a datos para la tabla 'clientes_integracion_fuente' en Supabase.
 */
export class ClienteIntegracionRepository {
  /**
   * Registra una nueva integración de fuente de analítica para un cliente.
   * Si ya existía una previa, desactiva las anteriores para mantener una única activa.
   */
  static async create(
    data: CreateClienteIntegracionDTO
  ): Promise<ClienteIntegracionFuente> {
    const supabase = getSupabaseAdmin();

    // Desactivar integraciones previas del mismo cliente
    await supabase
      .from("clientes_integracion_fuente")
      .update({ activo: false, updated_at: new Date().toISOString() })
      .eq("cliente_id", data.clienteId)
      .eq("activo", true);

    const { data: inserted, error } = await supabase
      .from("clientes_integracion_fuente")
      .insert({
        cliente_id: data.clienteId,
        ga4_property_id: data.ga4PropertyId,
        client_gcp_project_id: data.clientGcpProjectId,
        gcp_region: data.gcpRegion,
        activo: true,
      })
      .select()
      .single();

    if (error) {
      throw error;
    }

    return inserted as ClienteIntegracionFuente;
  }

  /**
   * Obtiene la integración activa más reciente de un cliente por su clienteId.
   */
  static async findActiveByClienteId(
    clienteId: string
  ): Promise<ClienteIntegracionFuente | null> {
    const supabase = getSupabaseAdmin();

    const { data, error } = await supabase
      .from("clientes_integracion_fuente")
      .select()
      .eq("cliente_id", clienteId)
      .eq("activo", true)
      .order("created_at", { ascending: false })
      .limit(1)
      .maybeSingle();

    if (error) {
      throw error;
    }

    return data as ClienteIntegracionFuente | null;
  }

  /**
   * Desactiva todas las integraciones activas asociadas a un clienteId.
   * Utilizado en la baja de cuenta y supresión de datos.
   */
  static async desactivarPorClienteId(clienteId: string): Promise<void> {
    const supabase = getSupabaseAdmin();

    const { error } = await supabase
      .from("clientes_integracion_fuente")
      .update({
        activo: false,
        updated_at: new Date().toISOString(),
      })
      .eq("cliente_id", clienteId)
      .eq("activo", true);

    if (error) {
      throw error;
    }
  }

  /**
   * Reasigna las integraciones activas de un cliente temporal de onboarding
   * hacia el clienteId definitivo del usuario autenticado.
   */
  static async reassignClienteId(
    fromClienteId: string,
    toClienteId: string
  ): Promise<void> {
    if (!fromClienteId || !toClienteId || fromClienteId === toClienteId) {
      return;
    }

    const supabase = getSupabaseAdmin();
    const { error } = await supabase
      .from("clientes_integracion_fuente")
      .update({
        cliente_id: toClienteId,
        updated_at: new Date().toISOString(),
      })
      .eq("cliente_id", fromClienteId)
      .eq("activo", true);

    if (error) {
      throw error;
    }
  }

  /**
   * Crea o actualiza la integración activa de un cliente con la configuración
   * de URL base, credenciales encriptadas y parámetros de GA4/GCP del onboarding.
   */
  static async upsertOnboardingConfig(
    data: UpsertOnboardingIntegracionDTO
  ): Promise<ClienteIntegracionFuente> {
    const supabase = getSupabaseAdmin();
    const existing = await ClienteIntegracionRepository.findActiveByClienteId(
      data.clienteId
    );

    const payload: Record<string, unknown> = {
      updated_at: new Date().toISOString(),
    };

    if (data.baseUrl !== undefined) payload.base_url = data.baseUrl;
    if (data.requiresAuthentication !== undefined) {
      payload.requires_authentication = data.requiresAuthentication;
    }
    if (data.loginUrl !== undefined) payload.login_url = data.loginUrl;
    if (data.testUsername !== undefined) payload.test_username = data.testUsername;
    if (data.testPasswordEncrypted !== undefined) {
      payload.test_password_encrypted = data.testPasswordEncrypted;
    }
    if (data.storageStateEncrypted !== undefined) {
      payload.storage_state_encrypted = data.storageStateEncrypted;
    }
    if (data.ga4PropertyId !== undefined) {
      payload.ga4_property_id = data.ga4PropertyId;
    }
    if (data.clientGcpProjectId !== undefined) {
      payload.client_gcp_project_id = data.clientGcpProjectId;
    }
    if (data.gcpRegion !== undefined) {
      payload.gcp_region = data.gcpRegion;
    }

    if (existing) {
      const { data: updated, error } = await supabase
        .from("clientes_integracion_fuente")
        .update(payload)
        .eq("id", existing.id)
        .select()
        .single();

      if (error) {
        throw error;
      }

      return updated as ClienteIntegracionFuente;
    }

    const { data: inserted, error } = await supabase
      .from("clientes_integracion_fuente")
      .insert({
        cliente_id: data.clienteId,
        activo: true,
        ...payload,
      })
      .select()
      .single();

    if (error) {
      throw error;
    }

    return inserted as ClienteIntegracionFuente;
  }
}
