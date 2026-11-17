import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  purgarDataWarehouseCliente,
  ejecutarPurgaIntegralCliente,
} from '../purge-service';
import * as googleRevocationModule from '../google-token-revocation.service';
import { ClienteIntegracionRepository } from '@/repositories/cliente-integracion.repository';
import { ClienteCuentaRepository } from '@/repositories/cliente-cuenta.repository';
import { google } from 'googleapis';

vi.mock('@/repositories/cliente-integracion.repository', () => ({
  ClienteIntegracionRepository: {
    findActiveByClienteId: vi.fn(),
    desactivarPorClienteId: vi.fn(),
  },
}));

vi.mock('@/repositories/cliente-cuenta.repository', () => ({
  ClienteCuentaRepository: {
    marcarBajaCuenta: vi.fn(),
    registrarAuditoriaSupresion: vi.fn(),
    actualizarEstadoAuditoria: vi.fn(),
  },
}));

vi.mock('../google-token-revocation.service', async () => {
  const actual = await vi.importActual<typeof googleRevocationModule>(
    '../google-token-revocation.service'
  );
  return {
    ...actual,
    revocarTokenGoogle: vi.fn(),
    getOAuth2Client: vi.fn(),
  };
});

describe('purge-service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('purgarDataWarehouseCliente', () => {
    it('omite la operación si projectId o propertyId no están definidos', async () => {
      const mockDatasetsDelete = vi.fn();
      vi.spyOn(google, 'bigquery').mockReturnValue({
        datasets: { delete: mockDatasetsDelete },
      } as unknown as ReturnType<typeof google.bigquery>);

      await purgarDataWarehouseCliente({
        clienteId: 'cli-empty',
      });

      await purgarDataWarehouseCliente({
        clienteId: 'cli-only-proj',
        projectId: 'gcp-proj',
      });

      await purgarDataWarehouseCliente({
        clienteId: 'cli-only-prop',
        propertyId: '12345',
      });

      expect(mockDatasetsDelete).not.toHaveBeenCalled();
    });

    it('ejecuta la eliminación del dataset analytics_{propertyId} con deleteContents=true', async () => {
      const mockDatasetsDelete = vi.fn().mockResolvedValue({ status: 204 });
      vi.spyOn(google, 'bigquery').mockReturnValue({
        datasets: { delete: mockDatasetsDelete },
      } as unknown as ReturnType<typeof google.bigquery>);

      await purgarDataWarehouseCliente({
        clienteId: 'cli-001',
        projectId: 'gcp-proj-123',
        propertyId: '987654',
      });

      expect(google.bigquery).toHaveBeenCalledWith(
        expect.objectContaining({ version: 'v2' })
      );
      expect(mockDatasetsDelete).toHaveBeenCalledWith({
        projectId: 'gcp-proj-123',
        datasetId: 'analytics_987654',
        deleteContents: true,
      });
    });

    it('maneja con idempotencia errores HTTP 404 (dataset ya eliminado o inexistente)', async () => {
      const notFoundErrorCode = new Error('Dataset not found');
      (notFoundErrorCode as unknown as { code: number }).code = 404;

      const mockDatasetsDelete = vi.fn().mockRejectedValue(notFoundErrorCode);
      vi.spyOn(google, 'bigquery').mockReturnValue({
        datasets: { delete: mockDatasetsDelete },
      } as unknown as ReturnType<typeof google.bigquery>);

      await expect(
        purgarDataWarehouseCliente({
          clienteId: 'cli-001',
          projectId: 'gcp-proj-123',
          propertyId: '987654',
        })
      ).resolves.not.toThrow();

      // Caso status === 404
      const notFoundStatus = { status: 404 };
      mockDatasetsDelete.mockRejectedValueOnce(notFoundStatus);
      await expect(
        purgarDataWarehouseCliente({
          clienteId: 'cli-001',
          projectId: 'gcp-proj-123',
          propertyId: '987654',
        })
      ).resolves.not.toThrow();
    });

    it('relanza errores imprevistos ocurridos durante la purga en BigQuery', async () => {
      const serverError = new Error('BigQuery Service Unavailable');
      (serverError as unknown as { code: number }).code = 503;

      const mockDatasetsDelete = vi.fn().mockRejectedValue(serverError);
      vi.spyOn(google, 'bigquery').mockReturnValue({
        datasets: { delete: mockDatasetsDelete },
      } as unknown as ReturnType<typeof google.bigquery>);

      await expect(
        purgarDataWarehouseCliente({
          clienteId: 'cli-001',
          projectId: 'gcp-proj-123',
          propertyId: '987654',
        })
      ).rejects.toThrow('BigQuery Service Unavailable');

      // Error sin propiedad message
      mockDatasetsDelete.mockRejectedValueOnce('Raw string error');
      await expect(
        purgarDataWarehouseCliente({
          clienteId: 'cli-001',
          projectId: 'gcp-proj-123',
          propertyId: '987654',
        })
      ).rejects.toBe('Raw string error');
    });
  });

  describe('ejecutarPurgaIntegralCliente', () => {
    it('ejecuta la secuencia completa de purga transaccional y dispara purga asíncrona', async () => {
      vi.mocked(googleRevocationModule.revocarTokenGoogle).mockResolvedValue({
        success: true,
        revoked: true,
        message: 'Token revocado exitosamente.',
      });

      vi.mocked(ClienteIntegracionRepository.findActiveByClienteId).mockResolvedValue({
        id: 'int-1',
        cliente_id: 'cli-abc',
        ga4_property_id: 'ga4-111',
        client_gcp_project_id: 'proj-ga4',
        gcp_region: 'us-central1',
        activo: true,
        ultimo_lote_sincronizado: null,
        created_at: '2026-10-24T10:00:00Z',
        updated_at: '2026-10-24T10:00:00Z',
      });

      vi.mocked(ClienteIntegracionRepository.desactivarPorClienteId).mockResolvedValue();

      vi.mocked(ClienteCuentaRepository.marcarBajaCuenta).mockResolvedValue({
        id: 'prf-1',
        cliente_id: 'cli-abc',
        nombre_organizacion: 'Test Org',
        rubro: 'Fintech',
        tamano_equipo: '50-249',
        dominio_url: null,
        estado_cuenta: 'baja_solicitada',
        created_at: '2026-10-24T10:00:00Z',
        updated_at: '2026-10-24T10:00:00Z',
      });

      vi.mocked(ClienteCuentaRepository.registrarAuditoriaSupresion).mockResolvedValue({
        id: 'aud-001',
        cliente_id: 'cli-abc',
        fecha_solicitud: '2026-10-24T12:00:00Z',
        motivo: 'Baja definitiva solicitada por el usuario',
        tokens_revocados: true,
        sesiones_invalidadas: true,
        bd_transaccional_purgada: true,
        dw_purga_disparada: true,
        estado_purga: 'en_proceso',
      });

      const mockDatasetsDelete = vi.fn().mockResolvedValue({ status: 204 });
      vi.spyOn(google, 'bigquery').mockReturnValue({
        datasets: { delete: mockDatasetsDelete },
      } as unknown as ReturnType<typeof google.bigquery>);

      const result = await ejecutarPurgaIntegralCliente({
        clienteId: 'cli-abc',
        token: 'sample-oauth-token',
        motivo: 'Baja definitiva solicitada por el usuario',
      });

      expect(googleRevocationModule.revocarTokenGoogle).toHaveBeenCalledWith(
        'sample-oauth-token'
      );
      expect(ClienteIntegracionRepository.findActiveByClienteId).toHaveBeenCalledWith(
        'cli-abc'
      );
      expect(ClienteIntegracionRepository.desactivarPorClienteId).toHaveBeenCalledWith(
        'cli-abc'
      );
      expect(ClienteCuentaRepository.marcarBajaCuenta).toHaveBeenCalledWith(
        'cli-abc'
      );
      expect(ClienteCuentaRepository.registrarAuditoriaSupresion).toHaveBeenCalledWith(
        expect.objectContaining({
          clienteId: 'cli-abc',
          motivo: 'Baja definitiva solicitada por el usuario',
          tokensRevocados: true,
          sesionesInvalidadas: true,
          bdTransaccionalPurgada: true,
          dwPurgaDisparada: true,
          estadoPurga: 'en_proceso',
        })
      );

      expect(result).toEqual({
        success: true,
        auditoriaId: 'aud-001',
        tokensRevocados: true,
        sesionesInvalidadas: true,
        bdTransaccionalPurgada: true,
        dwPurgaDisparada: true,
      });

      // Esperar microtareas asíncronas para verificar la actualización de auditoría
      await new Promise((resolve) => setTimeout(resolve, 50));

      expect(mockDatasetsDelete).toHaveBeenCalledWith({
        projectId: 'proj-ga4',
        datasetId: 'analytics_ga4-111',
        deleteContents: true,
      });
      expect(ClienteCuentaRepository.actualizarEstadoAuditoria).toHaveBeenCalledWith(
        'aud-001',
        'completada',
        expect.objectContaining({
          dw_purgado: true,
        })
      );
    });

    it('procesa correctamente cuando no hay integración activa y el motivo es omitido', async () => {
      vi.mocked(googleRevocationModule.revocarTokenGoogle).mockResolvedValue({
        success: true,
        revoked: false,
        message: 'No token',
      });

      vi.mocked(ClienteIntegracionRepository.findActiveByClienteId).mockResolvedValue(null);
      vi.mocked(ClienteIntegracionRepository.desactivarPorClienteId).mockResolvedValue();
      vi.mocked(ClienteCuentaRepository.marcarBajaCuenta).mockResolvedValue(null);

      vi.mocked(ClienteCuentaRepository.registrarAuditoriaSupresion).mockResolvedValue({
        id: 'aud-no-int',
        cliente_id: 'cli-no-int',
        fecha_solicitud: '2026-10-24T12:00:00Z',
        motivo: 'Solicitud voluntaria del titular (Derecho de Supresión)',
        tokens_revocados: false,
        sesiones_invalidadas: true,
        bd_transaccional_purgada: true,
        dw_purga_disparada: true,
        estado_purga: 'en_proceso',
      });

      const mockDatasetsDelete = vi.fn();
      vi.spyOn(google, 'bigquery').mockReturnValue({
        datasets: { delete: mockDatasetsDelete },
      } as unknown as ReturnType<typeof google.bigquery>);

      const result = await ejecutarPurgaIntegralCliente({
        clienteId: 'cli-no-int',
      });

      expect(result.success).toBe(true);
      expect(result.auditoriaId).toBe('aud-no-int');
      expect(ClienteCuentaRepository.registrarAuditoriaSupresion).toHaveBeenCalledWith(
        expect.objectContaining({
          motivo: 'Solicitud voluntaria del titular (Derecho de Supresión)',
          metadata: expect.objectContaining({
            targetProjectId: null,
            targetPropertyId: null,
          }),
        })
      );

      // Esperar microtareas asíncronas
      await new Promise((resolve) => setTimeout(resolve, 50));

      expect(mockDatasetsDelete).not.toHaveBeenCalled();
      expect(ClienteCuentaRepository.actualizarEstadoAuditoria).toHaveBeenCalledWith(
        'aud-no-int',
        'completada',
        expect.objectContaining({
          dw_purgado: false,
        })
      );
    });

    it('actualiza el estado de auditoría a fallida si la purga asíncrona de BigQuery falla', async () => {
      vi.mocked(googleRevocationModule.revocarTokenGoogle).mockResolvedValue({
        success: true,
        revoked: false,
        message: 'No token',
      });

      vi.mocked(ClienteIntegracionRepository.findActiveByClienteId).mockResolvedValue({
        id: 'int-2',
        cliente_id: 'cli-err',
        ga4_property_id: 'ga4-err',
        client_gcp_project_id: 'proj-err',
        gcp_region: 'us-central1',
        activo: true,
        ultimo_lote_sincronizado: null,
        created_at: '2026-10-24T10:00:00Z',
        updated_at: '2026-10-24T10:00:00Z',
      });

      vi.mocked(ClienteIntegracionRepository.desactivarPorClienteId).mockResolvedValue();
      vi.mocked(ClienteCuentaRepository.marcarBajaCuenta).mockResolvedValue(null);

      vi.mocked(ClienteCuentaRepository.registrarAuditoriaSupresion).mockResolvedValue({
        id: 'aud-err-1',
        cliente_id: 'cli-err',
        fecha_solicitud: '2026-10-24T12:00:00Z',
        motivo: 'Solicitud voluntaria',
        tokens_revocados: false,
        sesiones_invalidadas: true,
        bd_transaccional_purgada: true,
        dw_purga_disparada: true,
        estado_purga: 'en_proceso',
      });

      const bqError = new Error('Permission denied on BigQuery dataset deletion');
      const mockDatasetsDelete = vi.fn().mockRejectedValue(bqError);
      vi.spyOn(google, 'bigquery').mockReturnValue({
        datasets: { delete: mockDatasetsDelete },
      } as unknown as ReturnType<typeof google.bigquery>);

      const result = await ejecutarPurgaIntegralCliente({
        clienteId: 'cli-err',
      });

      expect(result.success).toBe(true);
      expect(result.auditoriaId).toBe('aud-err-1');

      // Esperar microtareas asíncronas
      await new Promise((resolve) => setTimeout(resolve, 50));

      expect(ClienteCuentaRepository.actualizarEstadoAuditoria).toHaveBeenCalledWith(
        'aud-err-1',
        'fallida',
        expect.objectContaining({
          error: expect.stringContaining('Permission denied'),
        })
      );
    });
  });
});
