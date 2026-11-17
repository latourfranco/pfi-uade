import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  signInWithGoogleAction,
  signOutAction,
  getAuthSessionSummaryAction,
  completeOnboardingAction,
} from "../auth";
import * as serverModule from "@/lib/supabase/server";
import * as sessionModule from "@/lib/auth/session";
import { ClienteCuentaRepository } from "@/repositories/cliente-cuenta.repository";
import { ClienteIntegracionRepository } from "@/repositories/cliente-integracion.repository";
import { cookies } from "next/headers";

vi.mock("@/lib/supabase/server", () => ({
  createSupabaseServerClient: vi.fn(),
}));

vi.mock("@/lib/auth/session", async (importOriginal) => {
  const actual = await importOriginal<typeof sessionModule>();
  return {
    ...actual,
    getAuthenticatedUser: vi.fn(),
  };
});

vi.mock("@/repositories/cliente-cuenta.repository", () => ({
  ClienteCuentaRepository: {
    findPerfilByClienteId: vi.fn(),
    upsertPerfil: vi.fn(),
    upsertAdminMember: vi.fn(),
  },
}));

vi.mock("@/repositories/cliente-integracion.repository", () => ({
  ClienteIntegracionRepository: {
    reassignClienteId: vi.fn(),
    upsertOnboardingConfig: vi.fn(),
  },
}));

vi.mock("next/headers", () => ({
  cookies: vi.fn(),
}));

describe("actions/auth", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    process.env.NEXT_PUBLIC_APP_URL = "http://localhost:3000";
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue(undefined),
      delete: vi.fn(),
    } as never);
  });

  describe("getAuthSessionSummaryAction", () => {
    it("retorna authenticated=false cuando no hay sesión", async () => {
      vi.mocked(sessionModule.getAuthenticatedUser).mockResolvedValue(null);
      const res = await getAuthSessionSummaryAction();
      expect(res).toEqual({
        authenticated: false,
        email: null,
        nombreOrganizacion: null,
      });
    });

    it("retorna datos del perfil cuando el usuario está autenticado", async () => {
      vi.mocked(sessionModule.getAuthenticatedUser).mockResolvedValue({
        id: "u-1",
        email: "ana@acme.com",
        user_metadata: { full_name: "Ana Google" },
      } as never);
      vi.mocked(ClienteCuentaRepository.findPerfilByClienteId).mockResolvedValue({
        nombre_organizacion: "Acme Corp",
      } as never);

      const res = await getAuthSessionSummaryAction();
      expect(res).toEqual({
        authenticated: true,
        email: "ana@acme.com",
        nombreOrganizacion: "Acme Corp",
      });
    });
  });

  describe("signInWithGoogleAction", () => {
    it("inicia OAuth con Google y redirige a la URL de autorización", async () => {
      const signInWithOAuthMock = vi.fn().mockResolvedValue({
        data: { url: "https://accounts.google.com/o/oauth2/auth" },
        error: null,
      });
      vi.mocked(serverModule.createSupabaseServerClient).mockResolvedValue({
        auth: { signInWithOAuth: signInWithOAuthMock },
      } as never);

      await expect(
        signInWithGoogleAction("/onboarding/resumen?complete=1")
      ).rejects.toThrow(
        "NEXT_REDIRECT: https://accounts.google.com/o/oauth2/auth"
      );

      expect(signInWithOAuthMock).toHaveBeenCalledWith({
        provider: "google",
        options: {
          redirectTo:
            "http://localhost:3000/api/auth/callback/supabase?next=%2Fonboarding%2Fresumen%3Fcomplete%3D1",
          queryParams: {
            access_type: "offline",
            prompt: "select_account",
          },
        },
      });
    });

    it("retorna error cuando signInWithOAuth falla o lanza excepción", async () => {
      vi.mocked(serverModule.createSupabaseServerClient).mockResolvedValue({
        auth: {
          signInWithOAuth: vi.fn().mockResolvedValue({
            data: { url: null },
            error: new Error("oauth error"),
          }),
        },
      } as never);

      const resErr = await signInWithGoogleAction();
      expect(resErr.success).toBe(false);
      expect(resErr.error).toContain("Google");

      vi.mocked(serverModule.createSupabaseServerClient).mockRejectedValue(
        new Error("network")
      );
      const resCatch = await signInWithGoogleAction("//evil.com");
      expect(resCatch.success).toBe(false);
    });
  });

  describe("signOutAction", () => {
    it("cierra sesión y redirige a /login", async () => {
      const signOutMock = vi.fn().mockResolvedValue({ error: null });
      vi.mocked(serverModule.createSupabaseServerClient).mockResolvedValue({
        auth: { signOut: signOutMock },
      } as never);

      await expect(signOutAction()).rejects.toThrow("NEXT_REDIRECT: /login");
      expect(signOutMock).toHaveBeenCalled();

      vi.mocked(serverModule.createSupabaseServerClient).mockRejectedValueOnce(
        new Error("signOut failed")
      );
      await expect(signOutAction()).rejects.toThrow("NEXT_REDIRECT: /login");
    });
  });

  describe("completeOnboardingAction", () => {
    it("retorna error si el usuario no está autenticado con Google", async () => {
      vi.mocked(sessionModule.getAuthenticatedUser).mockResolvedValue(null);

      const res = await completeOnboardingAction({
        rubro: "Retail",
        tamano: "10-49",
        baseUrl: "https://tienda.com",
      });

      expect(res.success).toBe(false);
      expect(res.error).toContain("Google");
    });

    it("reasigna integración temporal y persiste credenciales encriptadas para usuario de Google", async () => {
      vi.mocked(sessionModule.getAuthenticatedUser).mockResolvedValue({
        id: "google-uid-1",
        email: "owner@tienda.com",
        user_metadata: { full_name: "Owner Tienda" },
      } as never);

      const deleteMock = vi.fn();
      vi.mocked(cookies).mockResolvedValue({
        get: vi.fn().mockReturnValue({ value: "temp-client-99" }),
        delete: deleteMock,
      } as never);

      const authPayloadRaw = JSON.stringify({
        mode: "credentials",
        encrypted: true,
        usernameHint: "qa@tienda.com",
        ciphertext: "cipher-123",
      });

      const res = await completeOnboardingAction({
        rubro: "Retail",
        tamano: "10-49",
        baseUrl: "https://tienda.com",
        authPayloadRaw,
        propertyId: "prop-1",
        projectId: "proj-1",
        region: "us-central1",
        nombreOrganizacion: "Tienda SRL",
      });

      expect(res).toEqual({
        success: true,
        redirectUrl: "/dashboard?onboarding=true",
      });
      expect(ClienteIntegracionRepository.reassignClienteId).toHaveBeenCalledWith(
        "temp-client-99",
        "google-uid-1"
      );
      expect(deleteMock).toHaveBeenCalledWith(
        sessionModule.ONBOARDING_PENDING_CLIENT_COOKIE
      );
      expect(ClienteCuentaRepository.upsertPerfil).toHaveBeenCalledWith({
        clienteId: "google-uid-1",
        email: "owner@tienda.com",
        nombreOrganizacion: "Tienda SRL",
        rubro: "Retail",
        tamanoEquipo: "10-49",
        dominioUrl: "https://tienda.com",
        onboardingCompletado: true,
      });
      expect(ClienteIntegracionRepository.upsertOnboardingConfig).toHaveBeenCalledWith(
        expect.objectContaining({
          clienteId: "google-uid-1",
          baseUrl: "https://tienda.com",
          requiresAuthentication: true,
          testUsername: "qa@tienda.com",
          testPasswordEncrypted: "cipher-123",
          storageStateEncrypted: null,
          ga4PropertyId: "prop-1",
          clientGcpProjectId: "proj-1",
          gcpRegion: "us-central1",
        })
      );
      expect(ClienteCuentaRepository.upsertAdminMember).toHaveBeenCalledWith({
        clienteId: "google-uid-1",
        email: "owner@tienda.com",
        nombre: "Tienda SRL",
      });
    });

    it("completa onboarding con storage_state y fallback de nombreOrganizacion", async () => {
      vi.mocked(sessionModule.getAuthenticatedUser).mockResolvedValue({
        id: "existing-uid",
        email: "existing@org.com",
        user_metadata: {},
      } as never);
      vi.mocked(ClienteCuentaRepository.findPerfilByClienteId).mockResolvedValue(
        null
      );

      const authPayloadRaw = JSON.stringify({
        mode: "storage_state",
        encrypted: true,
        ciphertext: "enc-storage-state",
      });

      const res = await completeOnboardingAction({
        rubro: "Fintech",
        tamano: "250+",
        baseUrl: "https://fintech.com",
        authPayloadRaw,
      });

      expect(res).toEqual({
        success: true,
        redirectUrl: "/dashboard?onboarding=true",
      });
      expect(ClienteCuentaRepository.upsertPerfil).toHaveBeenCalledWith(
        expect.objectContaining({
          nombreOrganizacion: "existing",
        })
      );
    });

    it("maneja authPayloadRaw inválido y errores de base de datos", async () => {
      vi.mocked(sessionModule.getAuthenticatedUser).mockResolvedValue({
        id: "u-auth",
        email: "uauth@tienda.com",
        user_metadata: {},
      } as never);
      vi.mocked(ClienteCuentaRepository.findPerfilByClienteId).mockResolvedValue(
        null
      );

      const invalidJsonRes = await completeOnboardingAction({
        rubro: "Retail",
        tamano: "10-49",
        baseUrl: "",
        authPayloadRaw: "{invalid-json",
      });
      expect(invalidJsonRes.success).toBe(true);

      const noneModeRes = await completeOnboardingAction({
        rubro: "",
        tamano: "",
        baseUrl: "",
        authPayloadRaw: JSON.stringify({ mode: "none", encrypted: false, ciphertext: "" }),
      });
      expect(noneModeRes.success).toBe(true);

      vi.mocked(sessionModule.getAuthenticatedUser).mockResolvedValueOnce({
        id: "u-no-email",
        email: "",
        user_metadata: {},
      } as never);
      const noEmailRes = await completeOnboardingAction({
        rubro: "Retail",
        tamano: "10-49",
        baseUrl: "",
      });
      expect(noEmailRes.success).toBe(true);

      vi.mocked(ClienteCuentaRepository.upsertPerfil).mockRejectedValueOnce(
        new Error("db fail")
      );
      const failRes = await completeOnboardingAction({
        rubro: "Retail",
        tamano: "10-49",
        baseUrl: "",
      });
      expect(failRes.success).toBe(false);
    });
  });
});
