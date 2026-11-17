"use server";

import { google, type Auth } from "googleapis";
import { redirect } from "next/navigation";
import { cookies } from "next/headers";
import { getOrCreateOnboardingClienteId } from "@/lib/auth/session";
import { orchestrateGa4Provisioning } from "@/services/gcp/orchestrator";

const GOOGLE_SCOPES = [
  "https://www.googleapis.com/auth/analytics.edit",
  "https://www.googleapis.com/auth/cloud-platform",
];

function getOAuth2Client() {
  const clientId = process.env.GOOGLE_CLIENT_ID;
  const clientSecret = process.env.GOOGLE_CLIENT_SECRET;
  const appUrl = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";

  if (!clientId || !clientSecret) {
    throw new Error(
      "Variables de entorno GOOGLE_CLIENT_ID o GOOGLE_CLIENT_SECRET no configuradas."
    );
  }

  return new google.auth.OAuth2(
    clientId,
    clientSecret,
    `${appUrl}/api/auth/callback/google`
  );
}

/**
 * Inicia el flujo de autorización OAuth 2.0 con Google
 */
export async function initiateGoogleOAuth(clienteId?: string) {
  const oauth2Client = getOAuth2Client();
  const effectiveClienteId = await getOrCreateOnboardingClienteId(clienteId);

  const authUrl = oauth2Client.generateAuthUrl({
    access_type: "offline",
    prompt: "consent",
    scope: GOOGLE_SCOPES,
    state: effectiveClienteId,
  });

  redirect(authUrl);
}

/**
 * Completa la integración cuando el usuario selecciona una propiedad de GA4 específica
 * entre las múltiples encontradas en su cuenta.
 */
export async function completeSelectedPropertyIntegration(formData: FormData) {
  const propertyId = formData.get("propertyId") as string;
  const cookieStore = await cookies();
  const pendingAuthCookie = cookieStore.get("ga4_pending_auth");

  if (!propertyId || !pendingAuthCookie?.value) {
    redirect("/onboarding/fuente?error=sesion_expirada");
  }

  let pendingData: {
    tokens: Auth.Credentials;
    clienteId: string;
  };

  try {
    pendingData = JSON.parse(pendingAuthCookie.value);
  } catch {
    redirect("/onboarding/fuente?error=sesion_invalida");
  }

  const oauth2Client = getOAuth2Client();
  oauth2Client.setCredentials(pendingData.tokens);

  const platformServiceAccountEmail =
    process.env.PLATFORM_SERVICE_ACCOUNT_EMAIL || "";

  let result: Awaited<ReturnType<typeof orchestrateGa4Provisioning>>;

  try {
    const resolvedClienteId = await getOrCreateOnboardingClienteId(
      pendingData.clienteId || undefined
    );
    result = await orchestrateGa4Provisioning({
      auth: oauth2Client,
      propertyId,
      clienteId: resolvedClienteId,
      platformServiceAccountEmail,
    });

    // Limpiar cookie de estado temporal
    cookieStore.delete("ga4_pending_auth");
  } catch (error: unknown) {
    console.error("Error al completar integración de GA4 seleccionada:", error);
    const err = error as { code?: number; status?: number };
    const errorCode =
      err?.code === 403 || err?.status === 403
        ? "permisos_insuficientes"
        : "error_interno";
    redirect(`/onboarding/fuente?error=${errorCode}`);
  }

  redirect(
    `/onboarding/fuente?propertyId=${encodeURIComponent(
      result.propertyId
    )}&region=${encodeURIComponent(
      result.gcpRegion
    )}&projectId=${encodeURIComponent(result.projectId)}&status=success`
  );
}
