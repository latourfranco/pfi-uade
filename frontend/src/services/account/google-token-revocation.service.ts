import { google } from "googleapis";

export interface RevocacionTokenResult {
  success: boolean;
  revoked: boolean;
  message: string;
}

/**
 * Obtiene una instancia configurada de OAuth2Client para operaciones de autenticación de Google.
 */
export function getOAuth2Client() {
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
 * Revoca un token OAuth 2.0 ante los servidores de autorización de Google Identity.
 * Garantiza idempotencia: si el token ya no es válido, expiró o ya fue revocado previamente,
 * se considera exitoso sin interrumpir el proceso de supresión de la cuenta.
 */
export async function revocarTokenGoogle(
  token?: string | null
): Promise<RevocacionTokenResult> {
  if (!token || token.trim() === "") {
    return {
      success: true,
      revoked: false,
      message: "No se proporcionó un token de Google para revocar.",
    };
  }

  try {
    const oauth2Client = getOAuth2Client();
    await oauth2Client.revokeToken(token.trim());

    return {
      success: true,
      revoked: true,
      message: "Token de Google revocado exitosamente.",
    };
  } catch (error: unknown) {
    const err = error as {
      message?: string;
      code?: number | string;
      response?: { status?: number; data?: unknown };
    };
    const errorMessage = err?.message || String(error);
    const status = err?.response?.status;

    // Si el token ya expiró o fue revocado en Google (400 invalid_token), se asume revocado exitosamente (idempotente)
    if (
      status === 400 ||
      errorMessage.toLowerCase().includes("invalid_token") ||
      errorMessage.toLowerCase().includes("token expired")
    ) {
      console.warn(
        "[Google Revocation] El token ya no era válido o ya había sido revocado en Google."
      );
      return {
        success: true,
        revoked: true,
        message: "El token ya se encontraba revocado o invalidado en Google.",
      };
    }

    console.error(
      "[Google Revocation] Error al intentar revocar token en Google:",
      errorMessage
    );
    return {
      success: false,
      revoked: false,
      message: `Error al revocar token en Google: ${errorMessage}`,
    };
  }
}
