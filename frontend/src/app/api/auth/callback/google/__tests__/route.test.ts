import { describe, it, expect, vi, beforeEach } from 'vitest';
import { NextRequest } from 'next/server';
import { cookies } from 'next/headers';
import { DEFAULT_CLIENTE_ID } from '@/lib/constants';
import * as orchestratorModule from '@/services/gcp/orchestrator';
import { GET } from '../route';

vi.mock('@/services/gcp/orchestrator', () => ({
  getGa4AccountProperties: vi.fn(),
  orchestrateGa4Provisioning: vi.fn(),
}));

const mockOAuth2Methods = {
  getToken: vi.fn(),
  setCredentials: vi.fn(),
};

class MockOAuth2 {
  getToken = mockOAuth2Methods.getToken;
  setCredentials = mockOAuth2Methods.setCredentials;
}

vi.mock('googleapis', () => ({
  google: {
    auth: {
      OAuth2: vi.fn().mockImplementation(function () {
        return new MockOAuth2();
      }),
    },
  },
}));

describe('GET /api/auth/callback/google', () => {
  const originalEnv = process.env;
  const mockCookieMap = new Map<string, { name: string; value: string; options?: unknown }>();
  const mockCookieStore = {
    get: vi.fn((name: string) => mockCookieMap.get(name)),
    set: vi.fn((name: string, value: string, options?: unknown) => {
      mockCookieMap.set(name, { name, value, options });
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
      GOOGLE_CLIENT_ID: 'test-google-id',
      GOOGLE_CLIENT_SECRET: 'test-google-secret',
      NEXT_PUBLIC_APP_URL: 'https://eureka.example.com',
      PLATFORM_SERVICE_ACCOUNT_EMAIL: 'sa@central.iam.gserviceaccount.com',
    };
  });

  function createRequest(url: string): NextRequest {
    return new NextRequest(new URL(url, 'https://eureka.example.com'));
  }

  it('redirige a error=acceso_denegado si el usuario canceló o denegó OAuth en Google', async () => {
    const req = createRequest('/api/auth/callback/google?error=access_denied');
    const response = await GET(req);

    expect(response.status).toBe(307);
    const location = response.headers.get('location');
    expect(location).toBe('https://eureka.example.com/onboarding/fuente?error=acceso_denegado');
  });

  it('redirige a error=parametro_invalido si la URL no incluye el parámetro code', async () => {
    const req = createRequest('/api/auth/callback/google?state=cli-123');
    const response = await GET(req);

    expect(response.status).toBe(307);
    const location = response.headers.get('location');
    expect(location).toBe('https://eureka.example.com/onboarding/fuente?error=parametro_invalido');
  });

  it('utiliza el host de la petición si NEXT_PUBLIC_APP_URL no está definido', async () => {
    delete process.env.NEXT_PUBLIC_APP_URL;

    const req = new NextRequest(new URL('http://localhost:3000/api/auth/callback/google?error=access_denied'));
    const response = await GET(req);

    const location = response.headers.get('location');
    expect(location).toBe('http://localhost:3000/onboarding/fuente?error=acceso_denegado');
  });

  it('redirige a error=no_ga4_property_found si la cuenta de Google no contiene propiedades de GA4', async () => {
    mockOAuth2Methods.getToken.mockResolvedValue({
      tokens: { access_token: 'valid-token' },
    });
    vi.mocked(orchestratorModule.getGa4AccountProperties).mockResolvedValue([]);

    const req = createRequest('/api/auth/callback/google?code=auth-code-123');
    const response = await GET(req);

    const location = response.headers.get('location');
    expect(location).toBe('https://eureka.example.com/onboarding/fuente?error=no_ga4_property_found');
  });

  it('almacena cookie temporal y redirige a seleccionar-propiedad cuando existen múltiples propiedades', async () => {
    mockOAuth2Methods.getToken.mockResolvedValue({
      tokens: { access_token: 'multi-token' },
    });
    const mockProps = [
      { propertyId: 'p1', propertyName: 'Propiedad 1', accountName: 'Cuenta 1' },
      { propertyId: 'p2', propertyName: 'Propiedad 2', accountName: 'Cuenta 1' },
    ];
    vi.mocked(orchestratorModule.getGa4AccountProperties).mockResolvedValue(mockProps);

    const req = createRequest('/api/auth/callback/google?code=code-multi&state=cli-custom');
    const response = await GET(req);

    expect(mockCookieStore.set).toHaveBeenCalledWith(
      'ga4_pending_auth',
      JSON.stringify({
        tokens: { access_token: 'multi-token' },
        clienteId: 'cli-custom',
        properties: mockProps,
      }),
      expect.objectContaining({
        httpOnly: true,
        path: '/',
        maxAge: 900,
      })
    );

    const location = response.headers.get('location');
    expect(location).toBe('https://eureka.example.com/onboarding/fuente/seleccionar-propiedad');
  });

  it('configura secure: true en cookie cuando NODE_ENV es production', async () => {
    (process.env as Record<string, string | undefined>).NODE_ENV = 'production';

    mockOAuth2Methods.getToken.mockResolvedValue({
      tokens: { access_token: 'multi-token' },
    });
    vi.mocked(orchestratorModule.getGa4AccountProperties).mockResolvedValue([
      { propertyId: 'p1', propertyName: 'Prop 1', accountName: 'Acc 1' },
      { propertyId: 'p2', propertyName: 'Prop 2', accountName: 'Acc 1' },
    ]);

    const req = createRequest('/api/auth/callback/google?code=code-multi');
    await GET(req);

    expect(mockCookieStore.set).toHaveBeenCalledWith(
      'ga4_pending_auth',
      expect.any(String),
      expect.objectContaining({
        secure: true,
      })
    );
  });

  it('aprovisiona automáticamente y redirige con query params cuando existe exactamente 1 propiedad', async () => {
    mockOAuth2Methods.getToken.mockResolvedValue({
      tokens: { access_token: 'single-token' },
    });
    vi.mocked(orchestratorModule.getGa4AccountProperties).mockResolvedValue([
      { propertyId: 'p-single', propertyName: 'Propiedad Única', accountName: 'Cuenta A' },
    ]);
    vi.mocked(orchestratorModule.orchestrateGa4Provisioning).mockResolvedValue({
      propertyId: 'p-single',
      projectId: 'proj-auto-created',
      gcpRegion: 'southamerica-west1',
      clienteId: 'cli-from-state',
    });

    const req = createRequest('/api/auth/callback/google?code=single-code&state=cli-from-state');
    const response = await GET(req);

    expect(orchestratorModule.orchestrateGa4Provisioning).toHaveBeenCalledWith({
      auth: expect.anything(),
      propertyId: 'p-single',
      clienteId: 'cli-from-state',
      platformServiceAccountEmail: 'sa@central.iam.gserviceaccount.com',
    });

    const location = response.headers.get('location');
    const targetUrl = new URL(location!);
    expect(targetUrl.pathname).toBe('/onboarding/fuente');
    expect(targetUrl.searchParams.get('propertyId')).toBe('p-single');
    expect(targetUrl.searchParams.get('propertyName')).toBe('Propiedad Única');
    expect(targetUrl.searchParams.get('region')).toBe('southamerica-west1');
    expect(targetUrl.searchParams.get('projectId')).toBe('proj-auto-created');
    expect(targetUrl.searchParams.get('status')).toBe('success');
  });

  it('utiliza DEFAULT_CLIENTE_ID y cadena vacía para SA si state y PLATFORM_SERVICE_ACCOUNT_EMAIL no se proveen', async () => {
    delete process.env.PLATFORM_SERVICE_ACCOUNT_EMAIL;

    mockOAuth2Methods.getToken.mockResolvedValue({ tokens: {} });
    vi.mocked(orchestratorModule.getGa4AccountProperties).mockResolvedValue([
      { propertyId: 'p-only', propertyName: 'Solo Uno', accountName: 'Mi Cuenta' },
    ]);
    vi.mocked(orchestratorModule.orchestrateGa4Provisioning).mockResolvedValue({
      propertyId: 'p-only',
      projectId: 'proj-99',
      gcpRegion: 'US',
      clienteId: DEFAULT_CLIENTE_ID,
    });

    const req = createRequest('/api/auth/callback/google?code=single-code');
    await GET(req);

    expect(orchestratorModule.orchestrateGa4Provisioning).toHaveBeenCalledWith(
      expect.objectContaining({
        clienteId: DEFAULT_CLIENTE_ID,
        platformServiceAccountEmail: '',
      })
    );
  });

  describe('manejo de excepciones durante el callback', () => {
    it('redirige a error=permisos_insuficientes si el error contiene code 403', async () => {
      mockOAuth2Methods.getToken.mockRejectedValue({
        code: 403,
        message: 'Permission denied',
      });

      const req = createRequest('/api/auth/callback/google?code=error-403');
      const response = await GET(req);

      expect(response.headers.get('location')).toBe(
        'https://eureka.example.com/onboarding/fuente?error=permisos_insuficientes'
      );
    });

    it('redirige a error=permisos_insuficientes si el error contiene status 403', async () => {
      mockOAuth2Methods.getToken.mockRejectedValue({
        status: 403,
      });

      const req = createRequest('/api/auth/callback/google?code=error-status-403');
      const response = await GET(req);

      expect(response.headers.get('location')).toBe(
        'https://eureka.example.com/onboarding/fuente?error=permisos_insuficientes'
      );
    });

    it('redirige a error=no_ga4_property_found si el error tiene message NO_GA4_PROPERTY_FOUND', async () => {
      mockOAuth2Methods.getToken.mockRejectedValue({
        message: 'NO_GA4_PROPERTY_FOUND',
      });

      const req = createRequest('/api/auth/callback/google?code=error-no-prop');
      const response = await GET(req);

      expect(response.headers.get('location')).toBe(
        'https://eureka.example.com/onboarding/fuente?error=no_ga4_property_found'
      );
    });

    it('redirige a error=error_interno ante cualquier otra excepción imprevista', async () => {
      mockOAuth2Methods.getToken.mockRejectedValue(new Error('Internal server timeout'));

      const req = createRequest('/api/auth/callback/google?code=fatal-err');
      const response = await GET(req);

      expect(response.headers.get('location')).toBe(
        'https://eureka.example.com/onboarding/fuente?error=error_interno'
      );
    });
  });
});
