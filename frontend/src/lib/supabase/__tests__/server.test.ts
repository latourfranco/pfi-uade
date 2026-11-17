import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createSupabaseServerClient } from "../server";
import * as ssr from "@supabase/ssr";
import { cookies } from "next/headers";

vi.mock("@supabase/ssr", () => ({
  createServerClient: vi.fn(),
}));

vi.mock("next/headers", () => ({
  cookies: vi.fn(),
}));

describe("createSupabaseServerClient", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    vi.clearAllMocks();
    process.env = { ...originalEnv };
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  it("lanza error si faltan NEXT_PUBLIC_SUPABASE_URL o NEXT_PUBLIC_SUPABASE_ANON_KEY", async () => {
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

    await expect(createSupabaseServerClient()).rejects.toThrow(
      "Configuración de Supabase incompleta"
    );
  });

  it("crea el cliente SSR y delega getAll/setAll al cookieStore", async () => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://example.supabase.co";
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = "anon-key";

    const getAllMock = vi.fn().mockReturnValue([{ name: "sb", value: "1" }]);
    const setMock = vi.fn();
    vi.mocked(cookies).mockResolvedValue({
      getAll: getAllMock,
      set: setMock,
    } as never);

    vi.mocked(ssr.createServerClient).mockImplementation(
      (_url, _key, options) => {
        const all = options.cookies.getAll();
        expect(all).toEqual([{ name: "sb", value: "1" }]);
        options.cookies.setAll?.(
          [{ name: "sb-token", value: "abc", options: { path: "/" } }],
          {}
        );
        return { auth: {} } as never;
      }
    );

    const client = await createSupabaseServerClient();
    expect(client).toEqual({ auth: {} });
    expect(setMock).toHaveBeenCalledWith("sb-token", "abc", { path: "/" });
  });

  it("ignora errores en setAll cuando cookies son de solo lectura en Server Components", async () => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://example.supabase.co";
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = "anon-key";

    vi.mocked(cookies).mockResolvedValue({
      getAll: vi.fn().mockReturnValue([]),
      set: vi.fn(() => {
        throw new Error("Cookies are read-only");
      }),
    } as never);

    vi.mocked(ssr.createServerClient).mockImplementation(
      (_url, _key, options) => {
        expect(() =>
          options.cookies.setAll?.(
            [{ name: "sb-token", value: "abc", options: {} }],
            {}
          )
        ).not.toThrow();
        return { auth: {} } as never;
      }
    );

    await createSupabaseServerClient();
  });
});
