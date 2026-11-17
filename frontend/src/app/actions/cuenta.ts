"use server";

import { cookies } from "next/headers";
import { getEffectiveClienteId } from "@/lib/auth/session";
import {
  ClienteCuentaRepository,
  type ClientePerfil,
} from "@/repositories/cliente-cuenta.repository";
import {
  ClienteIntegracionRepository,
  type ClienteIntegracionFuente,
} from "@/repositories/cliente-integracion.repository";
import {
  ejecutarPurgaIntegralCliente,
  type PurgaResultado,
} from "@/services/account/purge-service";

export interface CuentaDataResponse {
  perfil: ClientePerfil | null;
  integracion: ClienteIntegracionFuente | null;
}

export interface ActualizarPerfilResult {
  success: boolean;
  perfil?: ClientePerfil;
  error?: string;
}

export interface SolicitarBajaResult {
  success: boolean;
  redirectUrl?: string;
  error?: string;
  purga?: PurgaResultado;
}

/**
 * Consulta el perfil institucional y la integración activa de un cliente.
 */
export async function obtenerInformacionCuenta(
  clienteId?: string
): Promise<CuentaDataResponse> {
  const effectiveClienteId = await getEffectiveClienteId(clienteId);

  const [perfil, integracion] = await Promise.all([
    ClienteCuentaRepository.findPerfilByClienteId(effectiveClienteId),
    ClienteIntegracionRepository.findActiveByClienteId(effectiveClienteId),
  ]);

  return { perfil, integracion };
}

/**
 * Actualiza o registra el perfil institucional de la cuenta.
 */
export async function actualizarPerfilInstitucionalAction(
  formData: FormData
): Promise<ActualizarPerfilResult> {
  const clienteId = await getEffectiveClienteId(
    (formData.get("clienteId") as string) || undefined
  );
  const nombreOrganizacion = (
    formData.get("nombreOrganizacion") as string
  )?.trim();
  const rubro = (formData.get("rubro") as string)?.trim() || "E-commerce";
  const tamanoEquipo =
    (formData.get("tamanoEquipo") as string)?.trim() || "50-249";
  const dominioUrl = (formData.get("dominioUrl") as string)?.trim() || null;

  if (!nombreOrganizacion || nombreOrganizacion.length < 2) {
    return {
      success: false,
      error: "El nombre de la organización debe contener al menos 2 caracteres.",
    };
  }

  try {
    const perfil = await ClienteCuentaRepository.upsertPerfil({
      clienteId,
      nombreOrganizacion,
      rubro,
      tamanoEquipo,
      dominioUrl,
    });

    return {
      success: true,
      perfil,
    };
  } catch (error: unknown) {
    console.error("Error al actualizar perfil institucional:", error);
    return {
      success: false,
      error: "Ocurrió un error al intentar actualizar el perfil institucional.",
    };
  }
}

/**
 * Procesa la baja definitiva de la cuenta en el marco del derecho de supresión de datos:
 * 1. Verifica la frase de seguridad 'ELIMINAR MI CUENTA'.
 * 2. Extrae posibles tokens de Google de las cookies activas.
 * 3. Dispara la revocación de tokens y la purga integral en BD transaccional y Data Warehouse.
 * 4. Invalida todas las cookies de sesión y temporales.
 */
export async function solicitarBajaDefinitivaCuentaAction(params: {
  clienteId?: string;
  confirmacion: string;
  motivo?: string;
}): Promise<SolicitarBajaResult> {
  const { clienteId, confirmacion, motivo } = params;
  const effectiveClienteId = await getEffectiveClienteId(clienteId);

  if (!confirmacion || confirmacion.trim() !== "ELIMINAR MI CUENTA") {
    return {
      success: false,
      error: "La frase de confirmación no coincide con 'ELIMINAR MI CUENTA'.",
    };
  }

  try {
    const cookieStore = await cookies();

    // 1. Extraer token de Google de cookies si existe
    let googleToken: string | null = null;
    const pendingAuthCookie = cookieStore.get("ga4_pending_auth");
    if (pendingAuthCookie?.value) {
      try {
        const parsed = JSON.parse(pendingAuthCookie.value);
        googleToken =
          parsed?.tokens?.access_token ||
          parsed?.tokens?.refresh_token ||
          null;
      } catch {
        // Ignorar error de parsing si la cookie estaba corrupta
      }
    }

    // 2. Ejecutar la purga integral (Google OAuth revoke + Supabase + DW BigQuery)
    const purga = await ejecutarPurgaIntegralCliente({
      clienteId: effectiveClienteId,
      token: googleToken,
      motivo:
        motivo ||
        "Solicitud voluntaria del titular (Derecho de Supresión)",
    });

    // 3. Invalidar cookies de sesión y temporales
    cookieStore.delete("ga4_pending_auth");
    cookieStore.delete("eureka_session");
    cookieStore.delete("eureka_cliente_id");

    return {
      success: true,
      redirectUrl: "/onboarding/rubro?cuenta_eliminada=true",
      purga,
    };
  } catch (error: unknown) {
    console.error("Error al procesar la baja definitiva de cuenta:", error);
    return {
      success: false,
      error:
        "Ocurrió un error al procesar la baja de la cuenta. Intente nuevamente.",
    };
  }
}
