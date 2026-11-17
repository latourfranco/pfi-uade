import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  getOAuth2Client,
  revocarTokenGoogle,
} from '../google-token-revocation.service';
import { google } from 'googleapis';

const mockRevokeToken = vi.fn();

class MockOAuth2 {
  revokeToken = mockRevokeToken;
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

describe('google-token-revocation.service', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    vi.clearAllMocks();
    process.env = {
      ...originalEnv,
      GOOGLE_CLIENT_ID: 'test-client-id.apps.googleusercontent.com',
      GOOGLE_CLIENT_SECRET: 'test-client-secret',
      NEXT_PUBLIC_APP_URL: 'http://localhost:3000',
    };
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  describe('getOAuth2Client', () => {
    it('retorna una instancia de OAuth2 cuando las variables de entorno están presentes', () => {
      const client = getOAuth2Client();
      expect(client).toBeDefined();
    });

    it('lanza un error si GOOGLE_CLIENT_ID no está configurada', () => {
      delete process.env.GOOGLE_CLIENT_ID;
      expect(() => getOAuth2Client()).toThrow(
        'Variables de entorno GOOGLE_CLIENT_ID o GOOGLE_CLIENT_SECRET no configuradas.'
      );
    });

    it('lanza un error si GOOGLE_CLIENT_SECRET no está configurada', () => {
      delete process.env.GOOGLE_CLIENT_SECRET;
      expect(() => getOAuth2Client()).toThrow(
        'Variables de entorno GOOGLE_CLIENT_ID o GOOGLE_CLIENT_SECRET no configuradas.'
      );
    });
  });

  describe('revocarTokenGoogle', () => {
    it('retorna success=true y revoked=false si el token es nulo o vacío', async () => {
      const resNull = await revocarTokenGoogle(null);
      expect(resNull).toEqual({
        success: true,
        revoked: false,
        message: 'No se proporcionó un token de Google para revocar.',
      });

      const resEmpty = await revocarTokenGoogle('   ');
      expect(resEmpty).toEqual({
        success: true,
        revoked: false,
        message: 'No se proporcionó un token de Google para revocar.',
      });
    });

    it('revoca el token exitosamente a través de OAuth2Client', async () => {
      mockRevokeToken.mockResolvedValueOnce({ status: 200 });

      const result = await revocarTokenGoogle('valid-sample-token');

      expect(google.auth.OAuth2).toHaveBeenCalled();
      expect(mockRevokeToken).toHaveBeenCalledWith('valid-sample-token');
      expect(result).toEqual({
        success: true,
        revoked: true,
        message: 'Token de Google revocado exitosamente.',
      });
    });

    it('maneja con idempotencia errores de token ya expirado o invalidado (HTTP 400)', async () => {
      const err = new Error('invalid_token');
      (err as unknown as { response: { status: number } }).response = { status: 400 };

      mockRevokeToken.mockRejectedValueOnce(err);

      const result = await revocarTokenGoogle('already-revoked-token');

      expect(mockRevokeToken).toHaveBeenCalledWith('already-revoked-token');
      expect(result).toEqual({
        success: true,
        revoked: true,
        message: 'El token ya se encontraba revocado o invalidado en Google.',
      });
    });

    it('maneja con idempotencia mensajes de error que contienen "Token expired"', async () => {
      const err = new Error('Token expired: Cannot revoke expired credential');
      mockRevokeToken.mockRejectedValueOnce(err);

      const result = await revocarTokenGoogle('expired-token');

      expect(mockRevokeToken).toHaveBeenCalledWith('expired-token');
      expect(result).toEqual({
        success: true,
        revoked: true,
        message: 'El token ya se encontraba revocado o invalidado en Google.',
      });
    });

    it('retorna success=false si ocurre un error inesperado durante la revocación', async () => {
      mockRevokeToken.mockRejectedValueOnce(
        new Error('Google Server 500 Connection Timeout')
      );

      const result = await revocarTokenGoogle('problematic-token');

      expect(result).toEqual({
        success: false,
        revoked: false,
        message:
          'Error al revocar token en Google: Google Server 500 Connection Timeout',
      });
    });
  });
});
