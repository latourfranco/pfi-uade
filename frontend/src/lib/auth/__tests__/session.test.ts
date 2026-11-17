import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  getAuthenticatedUser,
  getEffectiveClienteId,
  getOrCreateOnboardingClienteId,
  ONBOARDING_PENDING_CLIENT_COOKIE,
} from "../session";
import { DEFAULT_CLIENTE_ID } from "@/lib/constants";
import * as serverModule from "@/lib/supabase/server";
import { cookies } from "next/headers";

vi.mock("@/lib/supabase/server", () => ({
  createSupabaseServerClient: vi.fn(),
}));

vi.mock("next/headers", () => ({
  cookies: vi.fn(),
}));

describe("auth/session", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("getAuthenticatedUser", () => {
    it("retorna el usuario cuando la sesión es válida", async () => {
      const fakeUser = { id: "user-123", email: "user@eureka.io" };
      vi.mocked(serverModule.createSupabaseServerClient).mockResolvedValue({
        auth: {
          getUser: vi.fn().mockResolvedValue({ data: { user: fakeUser }, error: null }),
        },
      } as never);

      const user = await getAuthenticatedUser();
      expect(user).toEqual(fakeUser);
    });

    it("retorna null si Supabase devuelve error o no hay usuario", async () => {
      vi.mocked(serverModule.createSupabaseServerClient).mockResolvedValue({
        auth: {
          getUser: vi.fn().mockResolvedValue({ data: { user: null }, error: new Error("no session") }),
        },
      } as never);

      const user = await getAuthenticatedUser();
      expect(user).toBeNull();
    });

    it("retorna null si createSupabaseServerClient lanza una excepción", async () => {
      vi.mocked(serverModule.createSupabaseServerClient).mockRejectedValue(new Error("no env"));

      const user = await getAuthenticatedUser();
      expect(user).toBeNull();
    });
  });

  describe("getEffectiveClienteId", () => {
    it("prioriza el clienteId explícito cuando se provee", async () => {
      const result = await getEffectiveClienteId("explicit-id");
      expect(result).toBe("explicit-id");
      expect(serverModule.createSupabaseServerClient).not.toHaveBeenCalled();
    });

    it("retorna user.id cuando hay sesión autenticada", async () => {
      vi.mocked(serverModule.createSupabaseServerClient).mockResolvedValue({
        auth: {
          getUser: vi.fn().mockResolvedValue({ data: { user: { id: "auth-uid-1" } }, error: null }),
        },
      } as never);

      const result = await getEffectiveClienteId();
      expect(result).toBe("auth-uid-1");
    });

    it("usa DEFAULT_CLIENTE_ID cuando no hay sesión", async () => {
      vi.mocked(serverModule.createSupabaseServerClient).mockResolvedValue({
        auth: {
          getUser: vi.fn().mockResolvedValue({ data: { user: null }, error: null }),
        },
      } as never);

      const result = await getEffectiveClienteId();
      expect(result).toBe(DEFAULT_CLIENTE_ID);
    });
  });

  describe("getOrCreateOnboardingClienteId", () => {
    it("retorna explicitClienteId o user.id si existen", async () => {
      expect(await getOrCreateOnboardingClienteId("exp-1")).toBe("exp-1");

      vi.mocked(serverModule.createSupabaseServerClient).mockResolvedValue({
        auth: {
          getUser: vi.fn().mockResolvedValue({ data: { user: { id: "uid-2" } }, error: null }),
        },
      } as never);
      expect(await getOrCreateOnboardingClienteId()).toBe("uid-2");
    });

    it("lee la cookie temporal existente cuando no hay sesión", async () => {
      vi.mocked(serverModule.createSupabaseServerClient).mockResolvedValue({
        auth: {
          getUser: vi.fn().mockResolvedValue({ data: { user: null }, error: null }),
        },
      } as never);

      const getMock = vi.fn().mockReturnValue({ value: "pending-uuid-99" });
      vi.mocked(cookies).mockResolvedValue({ get: getMock, set: vi.fn() } as never);

      const res = await getOrCreateOnboardingClienteId();
      expect(getMock).toHaveBeenCalledWith(ONBOARDING_PENDING_CLIENT_COOKIE);
      expect(res).toBe("pending-uuid-99");
    });

    it("genera y guarda un UUID temporal en cookie cuando no existe previamente", async () => {
      vi.mocked(serverModule.createSupabaseServerClient).mockResolvedValue({
        auth: {
          getUser: vi.fn().mockResolvedValue({ data: { user: null }, error: null }),
        },
      } as never);

      const setMock = vi.fn();
      vi.mocked(cookies).mockResolvedValue({
        get: vi.fn().mockReturnValue(undefined),
        set: setMock,
      } as never);

      const res = await getOrCreateOnboardingClienteId();
      expect(res).toMatch(/^[0-9a-f-]{36}$/i);
      expect(setMock).toHaveBeenCalledWith(
        ONBOARDING_PENDING_CLIENT_COOKIE,
        res,
        expect.objectContaining({ httpOnly: true, path: "/" })
      );
    });
  });
});
