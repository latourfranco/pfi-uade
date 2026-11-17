import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "../route";
import * as serverModule from "@/lib/supabase/server";
import { ClienteCuentaRepository } from "@/repositories/cliente-cuenta.repository";

vi.mock("@/lib/supabase/server", () => ({
  createSupabaseServerClient: vi.fn(),
}));

vi.mock("@/repositories/cliente-cuenta.repository", () => ({
  ClienteCuentaRepository: {
    findPerfilByClienteId: vi.fn(),
  },
}));

describe("GET /api/auth/callback/supabase", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    process.env.NEXT_PUBLIC_APP_URL = "http://localhost:3000";
  });

  it("redirige a /login?error=google_auth_failed si falta code o viene error OAuth", async () => {
    const resNoCode = await GET(
      new NextRequest("http://localhost:3000/api/auth/callback/supabase")
    );
    expect(resNoCode.headers.get("location")).toBe(
      "http://localhost:3000/login?error=google_auth_failed"
    );

    const resOAuthErr = await GET(
      new NextRequest(
        "http://localhost:3000/api/auth/callback/supabase?error=access_denied"
      )
    );
    expect(resOAuthErr.headers.get("location")).toBe(
      "http://localhost:3000/login?error=google_auth_failed"
    );
  });

  it("redirige a /login?error=google_auth_failed si exchangeCodeForSession falla", async () => {
    vi.mocked(serverModule.createSupabaseServerClient).mockResolvedValue({
      auth: {
        exchangeCodeForSession: vi.fn().mockResolvedValue({
          data: { user: null },
          error: new Error("invalid code"),
        }),
      },
    } as never);

    const res = await GET(
      new NextRequest(
        "http://localhost:3000/api/auth/callback/supabase?code=abc"
      )
    );
    expect(res.headers.get("location")).toBe(
      "http://localhost:3000/login?error=google_auth_failed"
    );
  });

  it("respeta next=/onboarding/resumen?complete=1 tras autenticar con Google", async () => {
    vi.mocked(serverModule.createSupabaseServerClient).mockResolvedValue({
      auth: {
        exchangeCodeForSession: vi.fn().mockResolvedValue({
          data: { user: { id: "u-google-1" } },
          error: null,
        }),
      },
    } as never);

    const res = await GET(
      new NextRequest(
        "http://localhost:3000/api/auth/callback/supabase?code=abc&next=%2Fonboarding%2Fresumen%3Fcomplete%3D1"
      )
    );
    expect(res.headers.get("location")).toBe(
      "http://localhost:3000/onboarding/resumen?complete=1"
    );
  });

  it("redirige a /onboarding/rubro si el usuario aún no completó onboarding", async () => {
    vi.mocked(serverModule.createSupabaseServerClient).mockResolvedValue({
      auth: {
        exchangeCodeForSession: vi.fn().mockResolvedValue({
          data: { user: { id: "u-google-2" } },
          error: null,
        }),
      },
    } as never);
    vi.mocked(ClienteCuentaRepository.findPerfilByClienteId).mockResolvedValue({
      onboarding_completado: false,
    } as never);

    const res = await GET(
      new NextRequest(
        "http://localhost:3000/api/auth/callback/supabase?code=abc"
      )
    );
    expect(res.headers.get("location")).toBe(
      "http://localhost:3000/onboarding/rubro"
    );
  });

  it("redirige a next cuando el onboarding ya fue completado", async () => {
    vi.mocked(serverModule.createSupabaseServerClient).mockResolvedValue({
      auth: {
        exchangeCodeForSession: vi.fn().mockResolvedValue({
          data: { user: { id: "u-google-3" } },
          error: null,
        }),
      },
    } as never);
    vi.mocked(ClienteCuentaRepository.findPerfilByClienteId).mockResolvedValue({
      onboarding_completado: true,
    } as never);

    const res = await GET(
      new NextRequest(
        "http://localhost:3000/api/auth/callback/supabase?code=abc&next=%2Fdashboard%2Fcuenta"
      )
    );
    expect(res.headers.get("location")).toBe(
      "http://localhost:3000/dashboard/cuenta"
    );
  });

  it("redirige a /login?error=google_auth_failed si ocurre una excepción", async () => {
    vi.mocked(serverModule.createSupabaseServerClient).mockRejectedValue(
      new Error("boom")
    );

    const res = await GET(
      new NextRequest(
        "http://localhost:3000/api/auth/callback/supabase?code=abc"
      )
    );
    expect(res.headers.get("location")).toBe(
      "http://localhost:3000/login?error=google_auth_failed"
    );
  });
});
