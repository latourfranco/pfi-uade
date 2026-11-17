import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  ClienteCuentaRepository,
  type ClientePerfil,
  type AuditoriaSupresion,
  type UpsertClientePerfilDTO,
  type RegistrarAuditoriaSupresionDTO,
} from '../cliente-cuenta.repository';
import * as adminModule from '@/lib/supabase/admin';

vi.mock('@/lib/supabase/admin', () => ({
  getSupabaseAdmin: vi.fn(),
}));

interface MockSupabaseClient {
  from: ReturnType<typeof vi.fn>;
}

describe('ClienteCuentaRepository', () => {
  let mockSupabase: MockSupabaseClient;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('findPerfilByClienteId', () => {
    it('retorna el perfil institucional cuando existe', async () => {
      const fakePerfil: ClientePerfil = {
        id: 'prf-123',
        cliente_id: 'cli-001',
        nombre_organizacion: 'Eureka Fintech S.A.',
        rubro: 'Fintech',
        tamano_equipo: '50-249',
        dominio_url: 'https://eureka.io',
        estado_cuenta: 'activo',
        created_at: '2026-10-24T10:00:00Z',
        updated_at: '2026-10-24T10:00:00Z',
      };

      const maybeSingleMock = vi.fn().mockResolvedValue({ data: fakePerfil, error: null });
      const eqMock = vi.fn().mockReturnValue({ maybeSingle: maybeSingleMock });
      const selectMock = vi.fn().mockReturnValue({ eq: eqMock });

      mockSupabase = {
        from: vi.fn((table: string) => {
          if (table === 'clientes_perfil') {
            return { select: selectMock };
          }
          throw new Error(`Unexpected table ${table}`);
        }),
      };

      vi.mocked(adminModule.getSupabaseAdmin).mockReturnValue(
        mockSupabase as unknown as ReturnType<typeof adminModule.getSupabaseAdmin>
      );

      const result = await ClienteCuentaRepository.findPerfilByClienteId('cli-001');

      expect(mockSupabase.from).toHaveBeenCalledWith('clientes_perfil');
      expect(selectMock).toHaveBeenCalled();
      expect(eqMock).toHaveBeenCalledWith('cliente_id', 'cli-001');
      expect(result).toEqual(fakePerfil);
    });

    it('retorna null si el perfil no existe', async () => {
      const maybeSingleMock = vi.fn().mockResolvedValue({ data: null, error: null });
      const eqMock = vi.fn().mockReturnValue({ maybeSingle: maybeSingleMock });
      const selectMock = vi.fn().mockReturnValue({ eq: eqMock });

      mockSupabase = {
        from: vi.fn().mockReturnValue({ select: selectMock }),
      };

      vi.mocked(adminModule.getSupabaseAdmin).mockReturnValue(
        mockSupabase as unknown as ReturnType<typeof adminModule.getSupabaseAdmin>
      );

      const result = await ClienteCuentaRepository.findPerfilByClienteId('cli-not-found');
      expect(result).toBeNull();
    });

    it('lanza un error si la consulta en Supabase falla', async () => {
      const dbError = new Error('Database read failure');
      const maybeSingleMock = vi.fn().mockResolvedValue({ data: null, error: dbError });
      const eqMock = vi.fn().mockReturnValue({ maybeSingle: maybeSingleMock });
      const selectMock = vi.fn().mockReturnValue({ eq: eqMock });

      mockSupabase = {
        from: vi.fn().mockReturnValue({ select: selectMock }),
      };

      vi.mocked(adminModule.getSupabaseAdmin).mockReturnValue(
        mockSupabase as unknown as ReturnType<typeof adminModule.getSupabaseAdmin>
      );

      await expect(
        ClienteCuentaRepository.findPerfilByClienteId('cli-err')
      ).rejects.toThrow('Database read failure');
    });
  });

  describe('upsertPerfil', () => {
    it('crea o actualiza el perfil con todos los atributos', async () => {
      const fakeUpserted: ClientePerfil = {
        id: 'prf-456',
        cliente_id: 'cli-002',
        nombre_organizacion: 'Acme Corp',
        rubro: 'E-commerce',
        tamano_equipo: '250+',
        dominio_url: 'https://acme.org',
        estado_cuenta: 'activo',
        created_at: '2026-10-24T12:00:00Z',
        updated_at: '2026-10-24T12:00:00Z',
      };

      const singleMock = vi.fn().mockResolvedValue({ data: fakeUpserted, error: null });
      const selectMock = vi.fn().mockReturnValue({ single: singleMock });
      const upsertMock = vi.fn().mockReturnValue({ select: selectMock });

      mockSupabase = {
        from: vi.fn((table: string) => {
          if (table === 'clientes_perfil') {
            return { upsert: upsertMock };
          }
          throw new Error(`Unexpected table ${table}`);
        }),
      };

      vi.mocked(adminModule.getSupabaseAdmin).mockReturnValue(
        mockSupabase as unknown as ReturnType<typeof adminModule.getSupabaseAdmin>
      );

      const dto: UpsertClientePerfilDTO = {
        clienteId: 'cli-002',
        nombreOrganizacion: 'Acme Corp',
        rubro: 'E-commerce',
        tamanoEquipo: '250+',
        dominioUrl: 'https://acme.org',
      };

      const result = await ClienteCuentaRepository.upsertPerfil(dto);

      expect(mockSupabase.from).toHaveBeenCalledWith('clientes_perfil');
      expect(upsertMock).toHaveBeenCalledWith(
        expect.objectContaining({
          cliente_id: 'cli-002',
          nombre_organizacion: 'Acme Corp',
          rubro: 'E-commerce',
          tamano_equipo: '250+',
          dominio_url: 'https://acme.org',
          updated_at: expect.any(String),
        }),
        { onConflict: 'cliente_id' }
      );
      expect(result).toEqual(fakeUpserted);
    });

    it('crea o actualiza el perfil omitiendo atributos opcionales no definidos', async () => {
      const fakeUpserted: ClientePerfil = {
        id: 'prf-789',
        cliente_id: 'cli-003',
        nombre_organizacion: 'Minimal Org',
        rubro: 'E-commerce',
        tamano_equipo: '50-249',
        dominio_url: null,
        estado_cuenta: 'activo',
        created_at: '2026-10-24T12:00:00Z',
        updated_at: '2026-10-24T12:00:00Z',
      };

      const singleMock = vi.fn().mockResolvedValue({ data: fakeUpserted, error: null });
      const selectMock = vi.fn().mockReturnValue({ single: singleMock });
      const upsertMock = vi.fn().mockReturnValue({ select: selectMock });

      mockSupabase = {
        from: vi.fn().mockReturnValue({ upsert: upsertMock }),
      };

      vi.mocked(adminModule.getSupabaseAdmin).mockReturnValue(
        mockSupabase as unknown as ReturnType<typeof adminModule.getSupabaseAdmin>
      );

      const dto: UpsertClientePerfilDTO = {
        clienteId: 'cli-003',
        nombreOrganizacion: 'Minimal Org',
      };

      const result = await ClienteCuentaRepository.upsertPerfil(dto);

      expect(upsertMock).toHaveBeenCalledWith(
        {
          cliente_id: 'cli-003',
          nombre_organizacion: 'Minimal Org',
          updated_at: expect.any(String),
        },
        { onConflict: 'cliente_id' }
      );
      expect(result).toEqual(fakeUpserted);
    });

    it('lanza un error si el upsert falla en la base de datos', async () => {
      const dbError = new Error('Constraint violation');
      const singleMock = vi.fn().mockResolvedValue({ data: null, error: dbError });
      const selectMock = vi.fn().mockReturnValue({ single: singleMock });
      const upsertMock = vi.fn().mockReturnValue({ select: selectMock });

      mockSupabase = {
        from: vi.fn().mockReturnValue({ upsert: upsertMock }),
      };

      vi.mocked(adminModule.getSupabaseAdmin).mockReturnValue(
        mockSupabase as unknown as ReturnType<typeof adminModule.getSupabaseAdmin>
      );

      await expect(
        ClienteCuentaRepository.upsertPerfil({
          clienteId: 'cli-err',
          nombreOrganizacion: 'Error Org',
        })
      ).rejects.toThrow('Constraint violation');
    });
  });

  describe('marcarBajaCuenta', () => {
    it('actualiza el estado de la cuenta a baja_solicitada', async () => {
      const fakeUpdated: ClientePerfil = {
        id: 'prf-001',
        cliente_id: 'cli-baja',
        nombre_organizacion: 'Closing Org',
        rubro: 'Fintech',
        tamano_equipo: '11-49',
        dominio_url: null,
        estado_cuenta: 'baja_solicitada',
        created_at: '2026-10-20T10:00:00Z',
        updated_at: '2026-10-24T12:00:00Z',
      };

      const maybeSingleMock = vi.fn().mockResolvedValue({ data: fakeUpdated, error: null });
      const selectMock = vi.fn().mockReturnValue({ maybeSingle: maybeSingleMock });
      const eqMock = vi.fn().mockReturnValue({ select: selectMock });
      const updateMock = vi.fn().mockReturnValue({ eq: eqMock });

      mockSupabase = {
        from: vi.fn((table: string) => {
          if (table === 'clientes_perfil') {
            return { update: updateMock };
          }
          throw new Error(`Unexpected table ${table}`);
        }),
      };

      vi.mocked(adminModule.getSupabaseAdmin).mockReturnValue(
        mockSupabase as unknown as ReturnType<typeof adminModule.getSupabaseAdmin>
      );

      const result = await ClienteCuentaRepository.marcarBajaCuenta('cli-baja');

      expect(mockSupabase.from).toHaveBeenCalledWith('clientes_perfil');
      expect(updateMock).toHaveBeenCalledWith(
        expect.objectContaining({
          estado_cuenta: 'baja_solicitada',
          updated_at: expect.any(String),
        })
      );
      expect(eqMock).toHaveBeenCalledWith('cliente_id', 'cli-baja');
      expect(result).toEqual(fakeUpdated);
    });

    it('lanza un error si el update de baja falla', async () => {
      const dbError = new Error('Failed to update status');
      const maybeSingleMock = vi.fn().mockResolvedValue({ data: null, error: dbError });
      const selectMock = vi.fn().mockReturnValue({ maybeSingle: maybeSingleMock });
      const eqMock = vi.fn().mockReturnValue({ select: selectMock });
      const updateMock = vi.fn().mockReturnValue({ eq: eqMock });

      mockSupabase = {
        from: vi.fn().mockReturnValue({ update: updateMock }),
      };

      vi.mocked(adminModule.getSupabaseAdmin).mockReturnValue(
        mockSupabase as unknown as ReturnType<typeof adminModule.getSupabaseAdmin>
      );

      await expect(
        ClienteCuentaRepository.marcarBajaCuenta('cli-err')
      ).rejects.toThrow('Failed to update status');
    });
  });

  describe('registrarAuditoriaSupresion', () => {
    it('inserta un registro completo de auditoría de supresión', async () => {
      const fakeAuditoria: AuditoriaSupresion = {
        id: 'aud-123',
        cliente_id: 'cli-999',
        fecha_solicitud: '2026-10-24T12:00:00Z',
        motivo: 'Cierre voluntario de operaciones',
        tokens_revocados: true,
        sesiones_invalidadas: true,
        bd_transaccional_purgada: true,
        dw_purga_disparada: true,
        estado_purga: 'en_proceso',
        metadata: { ip: '127.0.0.1' },
      };

      const singleMock = vi.fn().mockResolvedValue({ data: fakeAuditoria, error: null });
      const selectMock = vi.fn().mockReturnValue({ single: singleMock });
      const insertMock = vi.fn().mockReturnValue({ select: selectMock });

      mockSupabase = {
        from: vi.fn((table: string) => {
          if (table === 'auditoria_supresion_datos') {
            return { insert: insertMock };
          }
          throw new Error(`Unexpected table ${table}`);
        }),
      };

      vi.mocked(adminModule.getSupabaseAdmin).mockReturnValue(
        mockSupabase as unknown as ReturnType<typeof adminModule.getSupabaseAdmin>
      );

      const dto: RegistrarAuditoriaSupresionDTO = {
        clienteId: 'cli-999',
        motivo: 'Cierre voluntario de operaciones',
        tokensRevocados: true,
        sesionesInvalidadas: true,
        bdTransaccionalPurgada: true,
        dwPurgaDisparada: true,
        estadoPurga: 'en_proceso',
        metadata: { ip: '127.0.0.1' },
      };

      const result = await ClienteCuentaRepository.registrarAuditoriaSupresion(dto);

      expect(mockSupabase.from).toHaveBeenCalledWith('auditoria_supresion_datos');
      expect(insertMock).toHaveBeenCalledWith({
        cliente_id: 'cli-999',
        motivo: 'Cierre voluntario de operaciones',
        tokens_revocados: true,
        sesiones_invalidadas: true,
        bd_transaccional_purgada: true,
        dw_purga_disparada: true,
        estado_purga: 'en_proceso',
        metadata: { ip: '127.0.0.1' },
      });
      expect(result).toEqual(fakeAuditoria);
    });

    it('aplica valores por defecto cuando los campos opcionales no son provistos', async () => {
      const fakeAuditoria: AuditoriaSupresion = {
        id: 'aud-456',
        cliente_id: 'cli-default',
        fecha_solicitud: '2026-10-24T12:00:00Z',
        motivo: 'Solicitud voluntaria del titular (Derecho de Supresión)',
        tokens_revocados: false,
        sesiones_invalidadas: false,
        bd_transaccional_purgada: false,
        dw_purga_disparada: false,
        estado_purga: 'en_proceso',
        metadata: {},
      };

      const singleMock = vi.fn().mockResolvedValue({ data: fakeAuditoria, error: null });
      const selectMock = vi.fn().mockReturnValue({ single: singleMock });
      const insertMock = vi.fn().mockReturnValue({ select: selectMock });

      mockSupabase = {
        from: vi.fn().mockReturnValue({ insert: insertMock }),
      };

      vi.mocked(adminModule.getSupabaseAdmin).mockReturnValue(
        mockSupabase as unknown as ReturnType<typeof adminModule.getSupabaseAdmin>
      );

      const result = await ClienteCuentaRepository.registrarAuditoriaSupresion({
        clienteId: 'cli-default',
      });

      expect(insertMock).toHaveBeenCalledWith({
        cliente_id: 'cli-default',
        motivo: 'Solicitud voluntaria del titular (Derecho de Supresión)',
        tokens_revocados: false,
        sesiones_invalidadas: false,
        bd_transaccional_purgada: false,
        dw_purga_disparada: false,
        estado_purga: 'en_proceso',
        metadata: {},
      });
      expect(result).toEqual(fakeAuditoria);
    });

    it('lanza un error si la inserción en auditoría falla', async () => {
      const dbError = new Error('Insert audit failed');
      const singleMock = vi.fn().mockResolvedValue({ data: null, error: dbError });
      const selectMock = vi.fn().mockReturnValue({ single: singleMock });
      const insertMock = vi.fn().mockReturnValue({ select: selectMock });

      mockSupabase = {
        from: vi.fn().mockReturnValue({ insert: insertMock }),
      };

      vi.mocked(adminModule.getSupabaseAdmin).mockReturnValue(
        mockSupabase as unknown as ReturnType<typeof adminModule.getSupabaseAdmin>
      );

      await expect(
        ClienteCuentaRepository.registrarAuditoriaSupresion({ clienteId: 'cli-err' })
      ).rejects.toThrow('Insert audit failed');
    });
  });

  describe('actualizarEstadoAuditoria', () => {
    it('actualiza el estado de la purga y el metadata', async () => {
      const fakeUpdated: AuditoriaSupresion = {
        id: 'aud-789',
        cliente_id: 'cli-123',
        fecha_solicitud: '2026-10-24T12:00:00Z',
        motivo: 'Supresión',
        tokens_revocados: true,
        sesiones_invalidadas: true,
        bd_transaccional_purgada: true,
        dw_purga_disparada: true,
        estado_purga: 'completada',
        metadata: { durationMs: 140 },
      };

      const singleMock = vi.fn().mockResolvedValue({ data: fakeUpdated, error: null });
      const selectMock = vi.fn().mockReturnValue({ single: singleMock });
      const eqMock = vi.fn().mockReturnValue({ select: selectMock });
      const updateMock = vi.fn().mockReturnValue({ eq: eqMock });

      mockSupabase = {
        from: vi.fn((table: string) => {
          if (table === 'auditoria_supresion_datos') {
            return { update: updateMock };
          }
          throw new Error(`Unexpected table ${table}`);
        }),
      };

      vi.mocked(adminModule.getSupabaseAdmin).mockReturnValue(
        mockSupabase as unknown as ReturnType<typeof adminModule.getSupabaseAdmin>
      );

      const result = await ClienteCuentaRepository.actualizarEstadoAuditoria(
        'aud-789',
        'completada',
        { durationMs: 140 }
      );

      expect(mockSupabase.from).toHaveBeenCalledWith('auditoria_supresion_datos');
      expect(updateMock).toHaveBeenCalledWith({
        estado_purga: 'completada',
        metadata: { durationMs: 140 },
      });
      expect(eqMock).toHaveBeenCalledWith('id', 'aud-789');
      expect(result).toEqual(fakeUpdated);
    });

    it('actualiza el estado sin sobreescribir metadata si no es provisto', async () => {
      const fakeUpdated: AuditoriaSupresion = {
        id: 'aud-999',
        cliente_id: 'cli-123',
        fecha_solicitud: '2026-10-24T12:00:00Z',
        motivo: 'Supresión',
        tokens_revocados: true,
        sesiones_invalidadas: true,
        bd_transaccional_purgada: true,
        dw_purga_disparada: true,
        estado_purga: 'fallida',
      };

      const singleMock = vi.fn().mockResolvedValue({ data: fakeUpdated, error: null });
      const selectMock = vi.fn().mockReturnValue({ single: singleMock });
      const eqMock = vi.fn().mockReturnValue({ select: selectMock });
      const updateMock = vi.fn().mockReturnValue({ eq: eqMock });

      mockSupabase = {
        from: vi.fn().mockReturnValue({ update: updateMock }),
      };

      vi.mocked(adminModule.getSupabaseAdmin).mockReturnValue(
        mockSupabase as unknown as ReturnType<typeof adminModule.getSupabaseAdmin>
      );

      const result = await ClienteCuentaRepository.actualizarEstadoAuditoria(
        'aud-999',
        'fallida'
      );

      expect(updateMock).toHaveBeenCalledWith({
        estado_purga: 'fallida',
      });
      expect(result).toEqual(fakeUpdated);
    });

    it('lanza un error si el update en auditoría falla', async () => {
      const dbError = new Error('Update audit failed');
      const singleMock = vi.fn().mockResolvedValue({ data: null, error: dbError });
      const selectMock = vi.fn().mockReturnValue({ single: singleMock });
      const eqMock = vi.fn().mockReturnValue({ select: selectMock });
      const updateMock = vi.fn().mockReturnValue({ eq: eqMock });

      mockSupabase = {
        from: vi.fn().mockReturnValue({ update: updateMock }),
      };

      vi.mocked(adminModule.getSupabaseAdmin).mockReturnValue(
        mockSupabase as unknown as ReturnType<typeof adminModule.getSupabaseAdmin>
      );

      await expect(
        ClienteCuentaRepository.actualizarEstadoAuditoria('aud-err', 'fallida')
      ).rejects.toThrow('Update audit failed');
    });
  });

  describe('upsertAdminMember', () => {
    it('inserta al miembro administrador cuando no existe en organizacion_miembros', async () => {
      const maybeSingleMock = vi.fn().mockResolvedValue({ data: null, error: null });
      const eqEmailMock = vi.fn().mockReturnValue({ maybeSingle: maybeSingleMock });
      const eqClienteMock = vi.fn().mockReturnValue({ eq: eqEmailMock });
      const selectMock = vi.fn().mockReturnValue({ eq: eqClienteMock });
      const insertMock = vi.fn().mockResolvedValue({ error: null });

      mockSupabase = {
        from: vi.fn().mockReturnValue({
          select: selectMock,
          insert: insertMock,
        }),
      };
      vi.mocked(adminModule.getSupabaseAdmin).mockReturnValue(
        mockSupabase as unknown as ReturnType<typeof adminModule.getSupabaseAdmin>
      );

      await ClienteCuentaRepository.upsertAdminMember({
        clienteId: 'cli-1',
        email: 'admin@acme.com',
        nombre: 'Acme',
      });

      expect(mockSupabase.from).toHaveBeenCalledWith('organizacion_miembros');
      expect(insertMock).toHaveBeenCalledWith(
        expect.objectContaining({
          cliente_id: 'cli-1',
          email: 'admin@acme.com',
          nombre: 'Acme',
          rol: 'admin',
          activo: true,
        })
      );
    });

    it('actualiza al miembro administrador cuando ya existe en organizacion_miembros', async () => {
      const maybeSingleMock = vi.fn().mockResolvedValue({ data: { id: 'mem-1' }, error: null });
      const eqEmailMock = vi.fn().mockReturnValue({ maybeSingle: maybeSingleMock });
      const eqClienteMock = vi.fn().mockReturnValue({ eq: eqEmailMock });
      const selectMock = vi.fn().mockReturnValue({ eq: eqClienteMock });
      const eqIdMock = vi.fn().mockResolvedValue({ error: null });
      const updateMock = vi.fn().mockReturnValue({ eq: eqIdMock });

      mockSupabase = {
        from: vi.fn().mockReturnValue({
          select: selectMock,
          update: updateMock,
        }),
      };
      vi.mocked(adminModule.getSupabaseAdmin).mockReturnValue(
        mockSupabase as unknown as ReturnType<typeof adminModule.getSupabaseAdmin>
      );

      await ClienteCuentaRepository.upsertAdminMember({
        clienteId: 'cli-1',
        email: 'admin@acme.com',
        nombre: 'Acme Renovado',
      });

      expect(updateMock).toHaveBeenCalledWith(
        expect.objectContaining({
          nombre: 'Acme Renovado',
          rol: 'admin',
          activo: true,
        })
      );
      expect(eqIdMock).toHaveBeenCalledWith('id', 'mem-1');
    });

    it('lanza error si falla upsertAdminMember', async () => {
      const maybeSingleMock = vi.fn().mockResolvedValue({
        data: null,
        error: new Error('member fail'),
      });
      const eqEmailMock = vi.fn().mockReturnValue({ maybeSingle: maybeSingleMock });
      const eqClienteMock = vi.fn().mockReturnValue({ eq: eqEmailMock });
      const selectMock = vi.fn().mockReturnValue({ eq: eqClienteMock });

      mockSupabase = {
        from: vi.fn().mockReturnValue({ select: selectMock }),
      };
      vi.mocked(adminModule.getSupabaseAdmin).mockReturnValue(
        mockSupabase as unknown as ReturnType<typeof adminModule.getSupabaseAdmin>
      );

      await expect(
        ClienteCuentaRepository.upsertAdminMember({
          clienteId: 'cli-1',
          email: 'admin@acme.com',
          nombre: 'Acme',
        })
      ).rejects.toThrow('member fail');
    });
  });
});
