import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { NextRequest } from "next/server";
import { proxy } from "../proxy";
import * as ssr from "@supabase/ssr";

vi.mock("@supabase/ssr", () => ({
  createServerClient: vi.fn(),
}));

describe("proxy", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    vi.clearAllMocks();
    process.env = {
      ...originalEnv,
      NEXT_PUBLIC_SUPABASE_URL: "https://example.supabase.co",
      NEXT_PUBLIC_SUPABASE_ANON_KEY: "anon-key",
    };
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  it("permite continuar si faltan variables de Supabase", async () => {
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    const req = new NextRequest("http://localhost:3000/dashboard");
    const res = await proxy(req);
    expect(res.status).toBe(200);
  });

  it("redirige a /login si un usuario no autenticado intenta acceder a /dashboard", async () => {
    vi.mocked(ssr.createServerClient).mockReturnValue({
      auth: {
        getUser: vi.fn().mockResolvedValue({ data: { user: null } }),
      },
    } as never);

    const req = new NextRequest("http://localhost:3000/dashboard?event=checkout");
    const res = await proxy(req);

    expect(res.status).toBe(307);
    const location = res.headers.get("location");
    expect(location).toContain("/login?next=%2Fdashboard%3Fevent%3Dcheckout");
  });

  it("permite acceder a /dashboard cuando el usuario está autenticado y sincroniza cookies", async () => {
    vi.mocked(ssr.createServerClient).mockImplementation((_url, _key, options) => {
      options.cookies.getAll();
      options.cookies.setAll?.(
        [{ name: "sb-access-token", value: "tok", options: { path: "/" } }],
        {}
      );
      return {
        auth: {
          getUser: vi.fn().mockResolvedValue({ data: { user: { id: "u-1" } } }),
        },
      } as never;
    });

    const req = new NextRequest("http://localhost:3000/dashboard");
    const res = await proxy(req);

    expect(res.status).toBe(200);
    expect(res.cookies.get("sb-access-token")?.value).toBe("tok");
  });

  it("redirige a /dashboard si un usuario autenticado visita /login o /registro", async () => {
    vi.mocked(ssr.createServerClient).mockReturnValue({
      auth: {
        getUser: vi.fn().mockResolvedValue({ data: { user: { id: "u-1" } } }),
      },
    } as never);

    const loginRes = await proxy(new NextRequest("http://localhost:3000/login"));
    expect(loginRes.status).toBe(307);
    expect(loginRes.headers.get("location")).toBe("http://localhost:3000/dashboard");

    const regRes = await proxy(new NextRequest("http://localhost:3000/registro"));
    expect(regRes.status).toBe(307);
    expect(regRes.headers.get("location")).toBe("http://localhost:3000/dashboard");
  });
});
