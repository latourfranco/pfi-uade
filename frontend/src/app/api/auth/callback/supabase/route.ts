import { NextRequest, NextResponse } from "next/server";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import { ClienteCuentaRepository } from "@/repositories/cliente-cuenta.repository";

/**
 * Callback OAuth de Supabase Auth (Google Sign-In).
 * Intercambia el código PKCE por una sesión activa y redirige según el estado de onboarding.
 */
export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const code = searchParams.get("code");
  const nextParam = searchParams.get("next") || "/dashboard";
  const oauthError = searchParams.get("error");

  const baseUrl =
    process.env.NEXT_PUBLIC_APP_URL ||
    `${request.nextUrl.protocol}//${request.nextUrl.host}`;

  if (oauthError || !code) {
    return NextResponse.redirect(
      new URL("/login?error=google_auth_failed", baseUrl)
    );
  }

  try {
    const supabase = await createSupabaseServerClient();
    const { data, error } = await supabase.auth.exchangeCodeForSession(code);

    if (error || !data.user) {
      return NextResponse.redirect(
        new URL("/login?error=google_auth_failed", baseUrl)
      );
    }

    const safeNext =
      nextParam.startsWith("/") && !nextParam.startsWith("//")
        ? nextParam
        : "/dashboard";

    // Si viene desde el cierre del onboarding (/onboarding/resumen?complete=1), respetar el destino
    if (safeNext.startsWith("/onboarding/resumen")) {
      return NextResponse.redirect(new URL(safeNext, baseUrl));
    }

    const perfil = await ClienteCuentaRepository.findPerfilByClienteId(
      data.user.id
    );
    if (!perfil || perfil.onboarding_completado === false) {
      return NextResponse.redirect(new URL("/onboarding/rubro", baseUrl));
    }

    return NextResponse.redirect(new URL(safeNext, baseUrl));
  } catch (error) {
    console.error("[Supabase Auth Callback] Error intercambiando código:", error);
    return NextResponse.redirect(
      new URL("/login?error=google_auth_failed", baseUrl)
    );
  }
}
