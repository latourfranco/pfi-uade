import { NextRequest, NextResponse } from "next/server";
import { google } from "googleapis";
import { cookies } from "next/headers";
import {
  getGa4AccountProperties,
  orchestrateGa4Provisioning,
} from "@/services/gcp/orchestrator";
import { DEFAULT_CLIENTE_ID } from "@/lib/constants";

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const code = searchParams.get("code");
  const clienteId = searchParams.get("state") || DEFAULT_CLIENTE_ID;
  const oauthError = searchParams.get("error");

  const baseUrl =
    process.env.NEXT_PUBLIC_APP_URL ||
    `${request.nextUrl.protocol}//${request.nextUrl.host}`;

  if (oauthError) {
    console.warn("OAuth cancelado o denegado por el usuario:", oauthError);
    return NextResponse.redirect(
      new URL("/onboarding/fuente?error=acceso_denegado", baseUrl)
    );
  }

  if (!code) {
    return NextResponse.redirect(
      new URL("/onboarding/fuente?error=parametro_invalido", baseUrl)
    );
  }

  const oauth2Client = new google.auth.OAuth2(
    process.env.GOOGLE_CLIENT_ID,
    process.env.GOOGLE_CLIENT_SECRET,
    `${baseUrl}/api/auth/callback/google`
  );

  try {
    // 1. Intercambio de código por tokens
    const { tokens } = await oauth2Client.getToken(code);
    oauth2Client.setCredentials(tokens);

    // 2. Descubrimiento de cuentas y propiedades de GA4
    const properties = await getGa4AccountProperties(oauth2Client);

    if (properties.length === 0) {
      return NextResponse.redirect(
        new URL("/onboarding/fuente?error=no_ga4_property_found", baseUrl)
      );
    }

    // 3. Si hay más de una propiedad, permitir al usuario seleccionar la adecuada
    if (properties.length > 1) {
      const cookieStore = await cookies();
      cookieStore.set(
        "ga4_pending_auth",
        JSON.stringify({
          tokens,
          clienteId,
          properties,
        }),
        {
          httpOnly: true,
          secure: process.env.NODE_ENV === "production",
          sameSite: "lax",
          maxAge: 60 * 15, // 15 minutos
          path: "/",
        }
      );

      return NextResponse.redirect(
        new URL("/onboarding/fuente/seleccionar-propiedad", baseUrl)
      );
    }

    // 4. Si hay exactamente 1 propiedad, aprovisionar automáticamente
    const singleProperty = properties[0];
    const platformServiceAccountEmail =
      process.env.PLATFORM_SERVICE_ACCOUNT_EMAIL || "";

    const result = await orchestrateGa4Provisioning({
      auth: oauth2Client,
      propertyId: singleProperty.propertyId,
      clienteId,
      platformServiceAccountEmail,
    });

    const redirectUrl = new URL("/onboarding/fuente", baseUrl);
    redirectUrl.searchParams.set("propertyId", result.propertyId);
    redirectUrl.searchParams.set("propertyName", singleProperty.propertyName);
    redirectUrl.searchParams.set("region", result.gcpRegion);
    redirectUrl.searchParams.set("projectId", result.projectId);
    redirectUrl.searchParams.set("status", "success");

    return NextResponse.redirect(redirectUrl);
  } catch (error: unknown) {
    console.error("Error durante la orquestación y callback de GA4:", error);
    const err = error as { code?: number; status?: number; message?: string };

    const errorMessage =
      err?.code === 403 || err?.status === 403
        ? "permisos_insuficientes"
        : err?.message === "NO_GA4_PROPERTY_FOUND"
        ? "no_ga4_property_found"
        : "error_interno";

    return NextResponse.redirect(
      new URL(`/onboarding/fuente?error=${errorMessage}`, baseUrl)
    );
  }
}
