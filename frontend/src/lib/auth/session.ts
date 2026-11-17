import type { User } from "@supabase/supabase-js";
import { cookies } from "next/headers";
import { DEFAULT_CLIENTE_ID } from "@/lib/constants";
import { createSupabaseServerClient } from "@/lib/supabase/server";

export const ONBOARDING_PENDING_CLIENT_COOKIE = "eureka_onboarding_client_id";

/**
 * Obtiene el usuario autenticado actual desde la sesión SSR de Supabase.
 * Retorna `null` si no hay sesión activa o si el entorno no dispone de configuración SSR.
 */
export async function getAuthenticatedUser(): Promise<User | null> {
  try {
    const supabase = await createSupabaseServerClient();
    const { data, error } = await supabase.auth.getUser();
    if (error || !data.user) {
      return null;
    }
    return data.user;
  } catch {
    return null;
  }
}

/**
 * Resuelve el `clienteId` efectivo:
 * 1. Usa el parámetro explícito si se suministra.
 * 2. Usa `user.id` si hay un usuario autenticado en Supabase Auth.
 * 3. Recurre a `DEFAULT_CLIENTE_ID` como fallback seguro.
 */
export async function getEffectiveClienteId(
  explicitClienteId?: string
): Promise<string> {
  if (explicitClienteId) {
    return explicitClienteId;
  }

  const user = await getAuthenticatedUser();
  return user?.id || DEFAULT_CLIENTE_ID;
}

/**
 * Obtiene o genera un identificador temporal de cliente para vincular integraciones
 * durante el onboarding previo a la creación de la cuenta definitiva.
 */
export async function getOrCreateOnboardingClienteId(
  explicitClienteId?: string
): Promise<string> {
  if (explicitClienteId) {
    return explicitClienteId;
  }

  const user = await getAuthenticatedUser();
  if (user?.id) {
    return user.id;
  }

  try {
    const cookieStore = await cookies();
    const existing = cookieStore.get(ONBOARDING_PENDING_CLIENT_COOKIE)?.value;
    if (existing) {
      return existing;
    }

    const generated = crypto.randomUUID();
    cookieStore.set(ONBOARDING_PENDING_CLIENT_COOKIE, generated, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: 60 * 60,
      path: "/",
    });
    return generated;
  } catch {
    return DEFAULT_CLIENTE_ID;
  }
}
