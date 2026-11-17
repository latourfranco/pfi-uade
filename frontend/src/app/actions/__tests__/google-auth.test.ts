import { describe, it, expect, vi, beforeEach } from 'vitest';
import { google } from 'googleapis';
import { cookies } from 'next/headers';
import { DEFAULT_CLIENTE_ID } from '@/lib/constants';
import * as orchestratorModule from '@/services/gcp/orchestrator';
import {
  initiateGoogleOAuth,
  completeSelectedPropertyIntegration,
} from '../google-auth';

vi.mock('@/services/gcp/orchestrator', () => ({
  orchestrateGa4Provisioning: vi.fn(),
}));

const mockOAuth2Methods = {
  generateAuthUrl: vi.fn(),
  setCredentials: vi.fn(),
};

class MockOAuth2 {
  generateAuthUrl = mockOAuth2Methods.generateAuthUrl;
  setCredentials = mockOAuth2Methods.setCredentials;
}

vi.mock('googleapis', () => {
  return {
    google: {
      auth: {
        OAuth2: vi.fn().mockImplementation(function () {
          return new MockOAuth2();
        }),
      },
    },
  };
});

describe('google-auth Server Actions', () => {
  const originalEnv = process.env;
  const mockCookieMap = new Map<string, { name: string; value: string }>();
  const mockCookieStore = {
    get: vi.fn((name: string) => mockCookieMap.get(name)),
    set: vi.fn((name: string, value: string) => {
      mockCookieMap.set(name, { name, value });
    }),
    delete: vi.fn((name: string) => {
      mockCookieMap.delete(name);
    }),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockCookieMap.clear();
    vi.mocked(cookies).mockResolvedValue(
      mockCookieStore as unknown as Awaited<ReturnType<typeof cookies>>
    );
    process.env = {
      ...originalEnv,
      GOOGLE_CLIENT_ID: 'test-client-id',
      GOOGLE_CLIENT_SECRET: 'test-client-secret',
      NEXT_PUBLIC_APP_URL: 'https://eureka.example.com',
    };
  });

  describe('initiateGoogleOAuth', () => {
    it('lanza un error si faltan las variables de entorno de Google OAuth', async () => {
      delete process.env.GOOGLE_CLIENT_ID;

      await expect(initiateGoogleOAuth('cli-123')).rejects.toThrow(
        'Variables de entorno GOOGLE_CLIENT_ID o GOOGLE_CLIENT_SECRET no configuradas.'
      );
    });

    it('genera la URL de OAuth y redirige usando el clienteId provisto', async () => {
      mockOAuth2Methods.generateAuthUrl.mockReturnValue(
        'https://accounts.google.com/o/oauth2/v2/auth?state=cli-123'
      );

      await expect(initiateGoogleOAuth('cli-123')).rejects.toThrow(
        'NEXT_REDIRECT: https://accounts.google.com/o/oauth2/v2/auth?state=cli-123'
      );

      expect(mockOAuth2Methods.generateAuthUrl).toHaveBeenCalledWith({
        access_type: 'offline',
        prompt: 'consent',
        scope: [
          'https://www.googleapis.com/auth/analytics.edit',
          'https://www.googleapis.com/auth/cloud-platform',
        ],
        state: 'cli-123',
      });
    });

    it('genera un clienteId temporal y URL fallback local si no se suministran', async () => {
      delete process.env.NEXT_PUBLIC_APP_URL;

      mockOAuth2Methods.generateAuthUrl.mockReturnValue(
        'https://accounts.google.com/o/oauth2/v2/auth?state=temp-uuid'
      );

      await expect(initiateGoogleOAuth()).rejects.toThrow(
        'NEXT_REDIRECT: https://accounts.google.com/o/oauth2/v2/auth?state=temp-uuid'
      );

      expect(google.auth.OAuth2).toHaveBeenCalledWith(
        'test-client-id',
        'test-client-secret',
        'http://localhost:3000/api/auth/callback/google'
      );
      expect(mockOAuth2Methods.generateAuthUrl).toHaveBeenCalledWith(
        expect.objectContaining({
          state: expect.stringMatching(/^[0-9a-f-]{36}$/i),
        })
      );
    });
  });

  describe('completeSelectedPropertyIntegration', () => {
    it('redirige con error sesion_expirada si no se proporciona propertyId en el formulario', async () => {
      const formData = new FormData();
      // No propertyId

      await expect(completeSelectedPropertyIntegration(formData)).rejects.toThrow(
        'NEXT_REDIRECT: /onboarding/fuente?error=sesion_expirada'
      );
    });

    it('redirige con error sesion_expirada si la cookie ga4_pending_auth no existe', async () => {
      const formData = new FormData();
      formData.set('propertyId', 'prop-123');
      // No cookie set en mockCookieMap

      await expect(completeSelectedPropertyIntegration(formData)).rejects.toThrow(
        'NEXT_REDIRECT: /onboarding/fuente?error=sesion_expirada'
      );
    });

    it('redirige con error sesion_invalida si el valor de la cookie ga4_pending_auth tiene JSON corrupto', async () => {
      const formData = new FormData();
      formData.set('propertyId', 'prop-123');

      mockCookieMap.set('ga4_pending_auth', {
        name: 'ga4_pending_auth',
        value: '{ invalid-json-payload',
      });

      await expect(completeSelectedPropertyIntegration(formData)).rejects.toThrow(
        'NEXT_REDIRECT: /onboarding/fuente?error=sesion_invalida'
      );
    });

    it('completa el aprovisionamiento exitosamente, borra la cookie temporal y redirige con status=success', async () => {
      const formData = new FormData();
      formData.set('propertyId', 'prop-777');

      mockCookieMap.set('ga4_pending_auth', {
        name: 'ga4_pending_auth',
        value: JSON.stringify({
          tokens: { access_token: 'fake-access-token' },
          clienteId: 'cliente-abc',
        }),
      });

      process.env.PLATFORM_SERVICE_ACCOUNT_EMAIL = 'platform-sa@example.iam.gserviceaccount.com';

      vi.mocked(orchestratorModule.orchestrateGa4Provisioning).mockResolvedValue({
        propertyId: 'prop-777',
        projectId: 'proj-target-99',
        gcpRegion: 'southamerica-west1',
        clienteId: 'cliente-abc',
      });

      await expect(completeSelectedPropertyIntegration(formData)).rejects.toThrow(
        'NEXT_REDIRECT: /onboarding/fuente?propertyId=prop-777&region=southamerica-west1&projectId=proj-target-99&status=success'
      );

      expect(orchestratorModule.orchestrateGa4Provisioning).toHaveBeenCalledWith({
        auth: expect.anything(),
        propertyId: 'prop-777',
        clienteId: 'cliente-abc',
        platformServiceAccountEmail: 'platform-sa@example.iam.gserviceaccount.com',
      });

      expect(mockCookieStore.delete).toHaveBeenCalledWith('ga4_pending_auth');
    });

    it('utiliza DEFAULT_CLIENTE_ID y cadena vacía para SA si no están presentes', async () => {
      const formData = new FormData();
      formData.set('propertyId', 'prop-888');

      mockCookieMap.set('ga4_pending_auth', {
        name: 'ga4_pending_auth',
        value: JSON.stringify({
          tokens: { access_token: 'fake-token' },
        }),
      });
      delete process.env.PLATFORM_SERVICE_ACCOUNT_EMAIL;

      vi.mocked(orchestratorModule.orchestrateGa4Provisioning).mockResolvedValue({
        propertyId: 'prop-888',
        projectId: 'proj-new',
        gcpRegion: 'US',
        clienteId: DEFAULT_CLIENTE_ID,
      });

      await expect(completeSelectedPropertyIntegration(formData)).rejects.toThrow(
        'NEXT_REDIRECT: /onboarding/fuente?propertyId=prop-888&region=US&projectId=proj-new&status=success'
      );

      expect(orchestratorModule.orchestrateGa4Provisioning).toHaveBeenCalledWith(
        expect.objectContaining({
          clienteId: expect.stringMatching(/^[0-9a-f-]{36}$/i),
          platformServiceAccountEmail: '',
        })
      );
    });

    it('redirige con error permisos_insuficientes cuando orchestrateGa4Provisioning arroja código 403', async () => {
      const formData = new FormData();
      formData.set('propertyId', 'prop-err-403');

      mockCookieMap.set('ga4_pending_auth', {
        name: 'ga4_pending_auth',
        value: JSON.stringify({
          tokens: { access_token: 'tok' },
          clienteId: 'cli-1',
        }),
      });

      vi.mocked(orchestratorModule.orchestrateGa4Provisioning).mockRejectedValue({
        code: 403,
        message: 'The caller does not have permission',
      });

      await expect(completeSelectedPropertyIntegration(formData)).rejects.toThrow(
        'NEXT_REDIRECT: /onboarding/fuente?error=permisos_insuficientes'
      );
    });

    it('redirige con error permisos_insuficientes cuando orchestrateGa4Provisioning arroja status 403', async () => {
      const formData = new FormData();
      formData.set('propertyId', 'prop-err-status-403');

      mockCookieMap.set('ga4_pending_auth', {
        name: 'ga4_pending_auth',
        value: JSON.stringify({
          tokens: { access_token: 'tok' },
          clienteId: 'cli-1',
        }),
      });

      vi.mocked(orchestratorModule.orchestrateGa4Provisioning).mockRejectedValue({
        status: 403,
      });

      await expect(completeSelectedPropertyIntegration(formData)).rejects.toThrow(
        'NEXT_REDIRECT: /onboarding/fuente?error=permisos_insuficientes'
      );
    });

    it('redirige con error error_interno ante cualquier otra falla general en orchestrateGa4Provisioning', async () => {
      const formData = new FormData();
      formData.set('propertyId', 'prop-err-500');

      mockCookieMap.set('ga4_pending_auth', {
        name: 'ga4_pending_auth',
        value: JSON.stringify({
          tokens: { access_token: 'tok' },
          clienteId: 'cli-1',
        }),
      });

      vi.mocked(orchestratorModule.orchestrateGa4Provisioning).mockRejectedValue(
        new Error('Unexpected database error')
      );

      await expect(completeSelectedPropertyIntegration(formData)).rejects.toThrow(
        'NEXT_REDIRECT: /onboarding/fuente?error=error_interno'
      );
    });
  });
});
