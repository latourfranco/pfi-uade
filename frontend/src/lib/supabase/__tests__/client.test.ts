import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createSupabaseBrowserClient } from "../client";
import * as ssr from "@supabase/ssr";

vi.mock("@supabase/ssr", () => ({
  createBrowserClient: vi.fn(),
}));

describe("createSupabaseBrowserClient", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    vi.clearAllMocks();
    process.env = { ...originalEnv };
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  it("lanza error si faltan NEXT_PUBLIC_SUPABASE_URL o NEXT_PUBLIC_SUPABASE_ANON_KEY", () => {
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

    expect(() => createSupabaseBrowserClient()).toThrow(
      "Configuración de Supabase incompleta"
    );
  });

  it("crea el cliente de navegador cuando las variables están definidas", () => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://example.supabase.co";
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = "anon-key";
    const fakeClient = { auth: {} };
    vi.mocked(ssr.createBrowserClient).mockReturnValue(fakeClient as never);

    const client = createSupabaseBrowserClient();

    expect(ssr.createBrowserClient).toHaveBeenCalledWith(
      "https://example.supabase.co",
      "anon-key"
    );
    expect(client).toBe(fakeClient);
  });
});
