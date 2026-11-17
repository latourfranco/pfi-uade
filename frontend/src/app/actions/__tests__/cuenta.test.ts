import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  obtenerInformacionCuenta,
  actualizarPerfilInstitucionalAction,
  solicitarBajaDefinitivaCuentaAction,
} from '../cuenta';
import { ClienteCuentaRepository } from '@/repositories/cliente-cuenta.repository';
import { ClienteIntegracionRepository } from '@/repositories/cliente-integracion.repository';
import * as purgeServiceModule from '@/services/account/purge-service';
import { cookies } from 'next/headers';
import { DEFAULT_CLIENTE_ID } from '@/lib/constants';

vi.mock('@/repositories/cliente-cuenta.repository', () => ({
  ClienteCuentaRepository: {
    findPerfilByClienteId: vi.fn(),
    upsertPerfil: vi.fn(),
  },
}));

vi.mock('@/repositories/cliente-integracion.repository', () => ({
  ClienteIntegracionRepository: {
    findActiveByClienteId: vi.fn(),
  },
}));

vi.mock('@/services/account/purge-service', () => ({
  ejecutarPurgaIntegralCliente: vi.fn(),
}));

describe('cuenta Server Actions', () => {
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
  });

  describe('obtenerInformacionCuenta', () => {
    it('obtiene el perfil y la integración con el clienteId provisto', async () => {
      const fakePerfil = {
        id: 'p-1',
        cliente_id: 'cli-99',
        nombre_organizacion: 'Org Test',
        rubro: 'SaaS',
        tamano_equipo: '11-49',
        dominio_url: 'https://org.test',
        estado_cuenta: 'activo' as const,
        created_at: '2026-10-24T10:00:00Z',
        updated_at: '2026-10-24T10:00:00Z',
      };
      const fakeIntegracion = {
        id: 'i-1',
        cliente_id: 'cli-99',
        ga4_property_id: 'ga4-99',
        client_gcp_project_id: 'proj-99',
        gcp_region: 'us-east1',
        activo: true,
        ultimo_lote_sincronizado: null,
        created_at: '2026-10-24T10:00:00Z',
        updated_at: '2026-10-24T10:00:00Z',
      };

      vi.mocked(ClienteCuentaRepository.findPerfilByClienteId).mockResolvedValue(fakePerfil);
      vi.mocked(ClienteIntegracionRepository.findActiveByClienteId).mockResolvedValue(fakeIntegracion);

      const result = await obtenerInformacionCuenta('cli-99');

      expect(ClienteCuentaRepository.findPerfilByClienteId).toHaveBeenCalledWith('cli-99');
      expect(ClienteIntegracionRepository.findActiveByClienteId).toHaveBeenCalledWith('cli-99');
      expect(result).toEqual({
        perfil: fakePerfil,
        integracion: fakeIntegracion,
      });
    });

    it('utiliza DEFAULT_CLIENTE_ID si no se suministra clienteId', async () => {
      vi.mocked(ClienteCuentaRepository.findPerfilByClienteId).mockResolvedValue(null);
      vi.mocked(ClienteIntegracionRepository.findActiveByClienteId).mockResolvedValue(null);

      const result = await obtenerInformacionCuenta();

      expect(ClienteCuentaRepository.findPerfilByClienteId).toHaveBeenCalledWith(DEFAULT_CLIENTE_ID);
      expect(ClienteIntegracionRepository.findActiveByClienteId).toHaveBeenCalledWith(DEFAULT_CLIENTE_ID);
      expect(result).toEqual({ perfil: null, integracion: null });
    });
  });

  describe('actualizarPerfilInstitucionalAction', () => {
    it('retorna error si el nombre de la organización está vacío o tiene menos de 2 caracteres', async () => {
      const formData = new FormData();
      formData.set('nombreOrganizacion', 'A');

      const result = await actualizarPerfilInstitucionalAction(formData);

      expect(result).toEqual({
        success: false,
        error: 'El nombre de la organización debe contener al menos 2 caracteres.',
      });
      expect(ClienteCuentaRepository.upsertPerfil).not.toHaveBeenCalled();
    });

    it('actualiza el perfil exitosamente con los datos provistos en FormData', async () => {
      const formData = new FormData();
      formData.set('clienteId', 'cli-custom');
      formData.set('nombreOrganizacion', 'Innovatech Corp');
      formData.set('rubro', 'Fintech');
      formData.set('tamanoEquipo', '250+');
      formData.set('dominioUrl', 'https://innovatech.com');

      const fakeUpdated = {
        id: 'p-2',
        cliente_id: 'cli-custom',
        nombre_organizacion: 'Innovatech Corp',
        rubro: 'Fintech',
        tamano_equipo: '250+',
        dominio_url: 'https://innovatech.com',
        estado_cuenta: 'activo' as const,
        created_at: '2026-10-24T10:00:00Z',
        updated_at: '2026-10-24T10:00:00Z',
      };

      vi.mocked(ClienteCuentaRepository.upsertPerfil).mockResolvedValue(fakeUpdated);

      const result = await actualizarPerfilInstitucionalAction(formData);

      expect(ClienteCuentaRepository.upsertPerfil).toHaveBeenCalledWith({
        clienteId: 'cli-custom',
        nombreOrganizacion: 'Innovatech Corp',
        rubro: 'Fintech',
        tamanoEquipo: '250+',
        dominioUrl: 'https://innovatech.com',
      });
      expect(result).toEqual({
        success: true,
        perfil: fakeUpdated,
      });
    });

    it('retorna error amigable si el repositorio arroja una excepción', async () => {
      const formData = new FormData();
      formData.set('nombreOrganizacion', 'Valid Name');

      vi.mocked(ClienteCuentaRepository.upsertPerfil).mockRejectedValue(
        new Error('Database unique constraint failed')
      );

      const result = await actualizarPerfilInstitucionalAction(formData);

      expect(result).toEqual({
        success: false,
        error: 'Ocurrió un error al intentar actualizar el perfil institucional.',
      });
    });
  });

  describe('solicitarBajaDefinitivaCuentaAction', () => {
    it('retorna error si la confirmación no coincide con "ELIMINAR MI CUENTA"', async () => {
      const result = await solicitarBajaDefinitivaCuentaAction({
        confirmacion: 'ELIMINAR',
      });

      expect(result).toEqual({
        success: false,
        error: "La frase de confirmación no coincide con 'ELIMINAR MI CUENTA'.",
      });
      expect(purgeServiceModule.ejecutarPurgaIntegralCliente).not.toHaveBeenCalled();
    });

    it('procesa la baja exitosamente, extrae token de cookie, purga e invalida cookies', async () => {
      mockCookieMap.set('ga4_pending_auth', {
        name: 'ga4_pending_auth',
        value: JSON.stringify({
          tokens: { access_token: 'google-active-token' },
        }),
      });

      const fakePurgaResult = {
        success: true,
        auditoriaId: 'aud-xyz',
        tokensRevocados: true,
        sesionesInvalidadas: true,
        bdTransaccionalPurgada: true,
        dwPurgaDisparada: true,
      };

      vi.mocked(purgeServiceModule.ejecutarPurgaIntegralCliente).mockResolvedValue(fakePurgaResult);

      const result = await solicitarBajaDefinitivaCuentaAction({
        clienteId: 'cli-del',
        confirmacion: 'ELIMINAR MI CUENTA',
        motivo: 'Motivo de prueba',
      });

      expect(purgeServiceModule.ejecutarPurgaIntegralCliente).toHaveBeenCalledWith({
        clienteId: 'cli-del',
        token: 'google-active-token',
        motivo: 'Motivo de prueba',
      });

      // Verificación de invalidación de cookies
      expect(mockCookieStore.delete).toHaveBeenCalledWith('ga4_pending_auth');
      expect(mockCookieStore.delete).toHaveBeenCalledWith('eureka_session');
      expect(mockCookieStore.delete).toHaveBeenCalledWith('eureka_cliente_id');

      expect(result).toEqual({
        success: true,
        redirectUrl: '/onboarding/rubro?cuenta_eliminada=true',
        purga: fakePurgaResult,
      });
    });

    it('maneja con resiliencia cookies con JSON corrupto y continúa el proceso', async () => {
      mockCookieMap.set('ga4_pending_auth', {
        name: 'ga4_pending_auth',
        value: 'corrupt-non-json-content',
      });

      const fakePurgaResult = {
        success: true,
        auditoriaId: 'aud-corrupt',
        tokensRevocados: false,
        sesionesInvalidadas: true,
        bdTransaccionalPurgada: true,
        dwPurgaDisparada: true,
      };

      vi.mocked(purgeServiceModule.ejecutarPurgaIntegralCliente).mockResolvedValue(fakePurgaResult);

      const result = await solicitarBajaDefinitivaCuentaAction({
        confirmacion: 'ELIMINAR MI CUENTA',
      });

      expect(purgeServiceModule.ejecutarPurgaIntegralCliente).toHaveBeenCalledWith({
        clienteId: DEFAULT_CLIENTE_ID,
        token: null,
        motivo: 'Solicitud voluntaria del titular (Derecho de Supresión)',
      });
      expect(result.success).toBe(true);
    });

    it('extrae refresh_token cuando access_token no está presente en la cookie', async () => {
      mockCookieMap.set('ga4_pending_auth', {
        name: 'ga4_pending_auth',
        value: JSON.stringify({
          tokens: { refresh_token: 'google-refresh-only-token' },
        }),
      });

      vi.mocked(purgeServiceModule.ejecutarPurgaIntegralCliente).mockResolvedValue({
        success: true,
        auditoriaId: 'aud-refresh',
        tokensRevocados: true,
        sesionesInvalidadas: true,
        bdTransaccionalPurgada: true,
        dwPurgaDisparada: true,
      });

      const result = await solicitarBajaDefinitivaCuentaAction({
        confirmacion: 'ELIMINAR MI CUENTA',
      });

      expect(purgeServiceModule.ejecutarPurgaIntegralCliente).toHaveBeenCalledWith({
        clienteId: DEFAULT_CLIENTE_ID,
        token: 'google-refresh-only-token',
        motivo: 'Solicitud voluntaria del titular (Derecho de Supresión)',
      });
      expect(result.success).toBe(true);
    });

    it('retorna mensaje de error si ocurre un fallo durante la purga', async () => {
      vi.mocked(purgeServiceModule.ejecutarPurgaIntegralCliente).mockRejectedValue(
        new Error('Purge orchestrator crashed')
      );

      const result = await solicitarBajaDefinitivaCuentaAction({
        confirmacion: 'ELIMINAR MI CUENTA',
      });

      expect(result).toEqual({
        success: false,
        error: 'Ocurrió un error al procesar la baja de la cuenta. Intente nuevamente.',
      });
    });
  });
});
