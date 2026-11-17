"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import {
  getAuthenticatedUser,
  ONBOARDING_PENDING_CLIENT_COOKIE,
} from "@/lib/auth/session";
import { ClienteCuentaRepository } from "@/repositories/cliente-cuenta.repository";
import { ClienteIntegracionRepository } from "@/repositories/cliente-integracion.repository";
import type { StoredOnboardingAuth } from "@/lib/onboarding-auth";

export interface AuthActionResult {
  success: boolean;
  redirectUrl?: string;
  error?: string;
}

export interface AuthSessionSummary {
  authenticated: boolean;
  email: string | null;
  nombreOrganizacion: string | null;
}

export interface CompleteOnboardingPayload {
  rubro: string;
  tamano: string;
  baseUrl: string;
  authPayloadRaw?: string | null;
  propertyId?: string | null;
  projectId?: string | null;
  region?: string | null;
  nombreOrganizacion?: string;
}

function parseOnboardingAuthRaw(
  raw?: string | null
): Partial<StoredOnboardingAuth> | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<StoredOnboardingAuth>;
    if (
      parsed &&
      (parsed.mode === "none" ||
        parsed.mode === "credentials" ||
        parsed.mode === "storage_state")
    ) {
      return parsed;
    }
    return null;
  } catch {
    return null;
  }
}

export async function getAuthSessionSummaryAction(): Promise<AuthSessionSummary> {
  const user = await getAuthenticatedUser();
  if (!user) {
    return { authenticated: false, email: null, nombreOrganizacion: null };
  }

  let nombreOrganizacion: string | null =
    (user.user_metadata?.nombre_organizacion as string | undefined) ||
    (user.user_metadata?.full_name as string | undefined) ||
    null;

  try {
    const perfil = await ClienteCuentaRepository.findPerfilByClienteId(user.id);
    if (perfil?.nombre_organizacion) {
      nombreOrganizacion = perfil.nombre_organizacion;
    }
  } catch {
    // Usar metadata como fallback
  }

  return {
    authenticated: true,
    email: user.email || null,
    nombreOrganizacion,
  };
}

/**
 * Inicia el flujo de autenticación con Google mediante Supabase Auth (PKCE OAuth).
 */
export async function signInWithGoogleAction(
  nextPath = "/dashboard"
): Promise<AuthActionResult> {
  const safeNext =
    nextPath.startsWith("/") && !nextPath.startsWith("//")
      ? nextPath
      : "/dashboard";
  const appUrl = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";
  const redirectTo = `${appUrl}/api/auth/callback/supabase?next=${encodeURIComponent(
    safeNext
  )}`;

  let authUrl: string | null = null;
  try {
    const supabase = await createSupabaseServerClient();
    const { data, error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo,
        queryParams: {
          access_type: "offline",
          prompt: "select_account",
        },
      },
    });

    if (error || !data?.url) {
      return {
        success: false,
        error: "No pudimos iniciar la autenticación con Google. Intentá nuevamente.",
      };
    }

    authUrl = data.url;
  } catch (error) {
    console.error("[signInWithGoogleAction] Error iniciando OAuth:", error);
    return {
      success: false,
      error: "Ocurrió un error al conectar con Google. Intentá nuevamente.",
    };
  }

  redirect(authUrl);
}

export async function signOutAction(): Promise<void> {
  try {
    const supabase = await createSupabaseServerClient();
    await supabase.auth.signOut();
  } catch (error) {
    console.error("[signOutAction] Error al cerrar sesión:", error);
  }
  redirect("/login");
}

/**
 * Finaliza el flujo de onboarding para el usuario autenticado con Google:
 * - Reasigna integraciones temporales de GA4 hacia el cliente_id definitivo (`user.id`).
 * - Persiste `clientes_perfil` (`onboarding_completado = true`), `clientes_integracion_fuente`
 *   (URL base + credenciales encriptadas) y `organizacion_miembros`.
 */
export async function completeOnboardingAction(
  payload: CompleteOnboardingPayload
): Promise<AuthActionResult> {
  try {
    const user = await getAuthenticatedUser();
    if (!user) {
      return {
        success: false,
        error: "Debés iniciar sesión con Google para activar tu cuenta.",
      };
    }

    const userId = user.id;
    const userEmail = user.email || "";
    let orgName = (payload.nombreOrganizacion || "").trim();

    if (!orgName) {
      const existingPerfil = await ClienteCuentaRepository.findPerfilByClienteId(
        userId
      );
      orgName =
        existingPerfil?.nombre_organizacion ||
        (user.user_metadata?.nombre_organizacion as string | undefined) ||
        (user.user_metadata?.full_name as string | undefined) ||
        userEmail.split("@")[0] ||
        "Mi Organización";
    }

    const cookieStore = await cookies();
    const pendingClientId = cookieStore.get(
      ONBOARDING_PENDING_CLIENT_COOKIE
    )?.value;
    if (pendingClientId) {
      await ClienteIntegracionRepository.reassignClienteId(
        pendingClientId,
        userId
      );
      cookieStore.delete(ONBOARDING_PENDING_CLIENT_COOKIE);
    }

    const baseUrl = payload.baseUrl.trim() || null;

    await ClienteCuentaRepository.upsertPerfil({
      clienteId: userId,
      email: userEmail || null,
      nombreOrganizacion: orgName,
      rubro: payload.rubro || "E-commerce",
      tamanoEquipo: payload.tamano || "50-249",
      dominioUrl: baseUrl,
      onboardingCompletado: true,
    });

    const parsedAuth = parseOnboardingAuthRaw(payload.authPayloadRaw);
    const requiresAuthentication =
      parsedAuth?.mode === "credentials" || parsedAuth?.mode === "storage_state";

    await ClienteIntegracionRepository.upsertOnboardingConfig({
      clienteId: userId,
      baseUrl,
      requiresAuthentication,
      loginUrl: null,
      testUsername:
        parsedAuth?.mode === "credentials" ? parsedAuth.usernameHint ?? null : null,
      testPasswordEncrypted:
        parsedAuth?.mode === "credentials"
          ? parsedAuth.ciphertext ?? null
          : null,
      storageStateEncrypted:
        parsedAuth?.mode === "storage_state"
          ? parsedAuth.ciphertext ?? null
          : null,
      ...(payload.propertyId ? { ga4PropertyId: payload.propertyId } : {}),
      ...(payload.projectId ? { clientGcpProjectId: payload.projectId } : {}),
      ...(payload.region ? { gcpRegion: payload.region } : {}),
    });

    if (userEmail) {
      await ClienteCuentaRepository.upsertAdminMember({
        clienteId: userId,
        email: userEmail,
        nombre: orgName,
      });
    }

    return {
      success: true,
      redirectUrl: "/dashboard?onboarding=true",
    };
  } catch (error) {
    console.error("[completeOnboardingAction] Error al finalizar onboarding:", error);
    return {
      success: false,
      error: "No pudimos guardar tu configuración. Intentá nuevamente.",
    };
  }
}
