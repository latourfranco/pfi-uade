import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  ClienteIntegracionRepository,
  type CreateClienteIntegracionDTO,
  type ClienteIntegracionFuente,
} from '../cliente-integracion.repository';
import * as adminModule from '@/lib/supabase/admin';

vi.mock('@/lib/supabase/admin', () => ({
  getSupabaseAdmin: vi.fn(),
}));

interface MockSupabaseClient {
  from: ReturnType<typeof vi.fn>;
}

describe('ClienteIntegracionRepository', () => {
  let mockSupabase: MockSupabaseClient;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('create', () => {
    it('desactiva integraciones previas e inserta una nueva integración activa', async () => {
      const updateEq2 = vi.fn().mockResolvedValue({ error: null });
      const updateEq1 = vi.fn().mockReturnValue({ eq: updateEq2 });
      const updateMock = vi.fn().mockReturnValue({ eq: updateEq1 });

      const fakeInserted: ClienteIntegracionFuente = {
        id: 'int-123',
        cliente_id: 'cli-456',
        ga4_property_id: '998877',
        client_gcp_project_id: 'my-gcp-proj',
        gcp_region: 'us-central1',
        activo: true,
        ultimo_lote_sincronizado: null,
        created_at: '2026-10-21T12:00:00Z',
        updated_at: '2026-10-21T12:00:00Z',
      };

      const singleMock = vi.fn().mockResolvedValue({ data: fakeInserted, error: null });
      const selectMock = vi.fn().mockReturnValue({ single: singleMock });
      const insertMock = vi.fn().mockReturnValue({ select: selectMock });

      mockSupabase = {
        from: vi.fn((table: string) => {
          if (table === 'clientes_integracion_fuente') {
            return {
              update: updateMock,
              insert: insertMock,
            };
          }
          throw new Error(`Unexpected table ${table}`);
        }),
      };

      vi.mocked(adminModule.getSupabaseAdmin).mockReturnValue(
        mockSupabase as unknown as ReturnType<typeof adminModule.getSupabaseAdmin>
      );

      const dto: CreateClienteIntegracionDTO = {
        clienteId: 'cli-456',
        ga4PropertyId: '998877',
        clientGcpProjectId: 'my-gcp-proj',
        gcpRegion: 'us-central1',
      };

      const result = await ClienteIntegracionRepository.create(dto);

      expect(mockSupabase.from).toHaveBeenCalledWith('clientes_integracion_fuente');
      expect(updateMock).toHaveBeenCalledWith(
        expect.objectContaining({ activo: false, updated_at: expect.any(String) })
      );
      expect(updateEq1).toHaveBeenCalledWith('cliente_id', 'cli-456');
      expect(updateEq2).toHaveBeenCalledWith('activo', true);

      expect(insertMock).toHaveBeenCalledWith({
        cliente_id: 'cli-456',
        ga4_property_id: '998877',
        client_gcp_project_id: 'my-gcp-proj',
        gcp_region: 'us-central1',
        activo: true,
      });
      expect(result).toEqual(fakeInserted);
    });

    it('lanza un error si la inserción en Supabase falla', async () => {
      const updateEq2 = vi.fn().mockResolvedValue({ error: null });
      const updateEq1 = vi.fn().mockReturnValue({ eq: updateEq2 });
      const updateMock = vi.fn().mockReturnValue({ eq: updateEq1 });

      const dbError = new Error('Database connection failed');
      const singleMock = vi.fn().mockResolvedValue({ data: null, error: dbError });
      const selectMock = vi.fn().mockReturnValue({ single: singleMock });
      const insertMock = vi.fn().mockReturnValue({ select: selectMock });

      mockSupabase = {
        from: vi.fn().mockReturnValue({
          update: updateMock,
          insert: insertMock,
        }),
      };

      vi.mocked(adminModule.getSupabaseAdmin).mockReturnValue(
        mockSupabase as unknown as ReturnType<typeof adminModule.getSupabaseAdmin>
      );

      const dto: CreateClienteIntegracionDTO = {
        clienteId: 'cli-err',
        ga4PropertyId: '123',
        clientGcpProjectId: 'proj-err',
        gcpRegion: 'us-east1',
      };

      await expect(ClienteIntegracionRepository.create(dto)).rejects.toThrow('Database connection failed');
    });
  });

  describe('findActiveByClienteId', () => {
    it('retorna la integración activa más reciente cuando existe', async () => {
      const fakeRecord: ClienteIntegracionFuente = {
        id: 'rec-1',
        cliente_id: 'cli-abc',
        ga4_property_id: '333444',
        client_gcp_project_id: 'proj-abc',
        gcp_region: 'us-central1',
        activo: true,
        ultimo_lote_sincronizado: '2026-10-20',
        created_at: '2026-10-21T10:00:00Z',
        updated_at: '2026-10-21T10:00:00Z',
      };

      const maybeSingleMock = vi.fn().mockResolvedValue({ data: fakeRecord, error: null });
      const limitMock = vi.fn().mockReturnValue({ maybeSingle: maybeSingleMock });
      const orderMock = vi.fn().mockReturnValue({ limit: limitMock });
      const eqActivoMock = vi.fn().mockReturnValue({ order: orderMock });
      const eqClienteMock = vi.fn().mockReturnValue({ eq: eqActivoMock });
      const selectMock = vi.fn().mockReturnValue({ eq: eqClienteMock });

      mockSupabase = {
        from: vi.fn().mockReturnValue({
          select: selectMock,
        }),
      };

      vi.mocked(adminModule.getSupabaseAdmin).mockReturnValue(
        mockSupabase as unknown as ReturnType<typeof adminModule.getSupabaseAdmin>
      );

      const result = await ClienteIntegracionRepository.findActiveByClienteId('cli-abc');

      expect(mockSupabase.from).toHaveBeenCalledWith('clientes_integracion_fuente');
      expect(selectMock).toHaveBeenCalled();
      expect(eqClienteMock).toHaveBeenCalledWith('cliente_id', 'cli-abc');
      expect(eqActivoMock).toHaveBeenCalledWith('activo', true);
      expect(orderMock).toHaveBeenCalledWith('created_at', { ascending: false });
      expect(limitMock).toHaveBeenCalledWith(1);
      expect(result).toEqual(fakeRecord);
    });

    it('retorna null si el cliente no posee ninguna integración activa', async () => {
      const maybeSingleMock = vi.fn().mockResolvedValue({ data: null, error: null });
      const limitMock = vi.fn().mockReturnValue({ maybeSingle: maybeSingleMock });
      const orderMock = vi.fn().mockReturnValue({ limit: limitMock });
      const eqActivoMock = vi.fn().mockReturnValue({ order: orderMock });
      const eqClienteMock = vi.fn().mockReturnValue({ eq: eqActivoMock });
      const selectMock = vi.fn().mockReturnValue({ eq: eqClienteMock });

      mockSupabase = {
        from: vi.fn().mockReturnValue({
          select: selectMock,
        }),
      };

      vi.mocked(adminModule.getSupabaseAdmin).mockReturnValue(
        mockSupabase as unknown as ReturnType<typeof adminModule.getSupabaseAdmin>
      );

      const result = await ClienteIntegracionRepository.findActiveByClienteId('cli-nonexistent');
      expect(result).toBeNull();
    });

    it('lanza un error si la consulta a Supabase retorna error', async () => {
      const queryError = new Error('Query timed out');
      const maybeSingleMock = vi.fn().mockResolvedValue({ data: null, error: queryError });
      const limitMock = vi.fn().mockReturnValue({ maybeSingle: maybeSingleMock });
      const orderMock = vi.fn().mockReturnValue({ limit: limitMock });
      const eqActivoMock = vi.fn().mockReturnValue({ order: orderMock });
      const eqClienteMock = vi.fn().mockReturnValue({ eq: eqActivoMock });
      const selectMock = vi.fn().mockReturnValue({ eq: eqClienteMock });

      mockSupabase = {
        from: vi.fn().mockReturnValue({
          select: selectMock,
        }),
      };

      vi.mocked(adminModule.getSupabaseAdmin).mockReturnValue(
        mockSupabase as unknown as ReturnType<typeof adminModule.getSupabaseAdmin>
      );

      await expect(
        ClienteIntegracionRepository.findActiveByClienteId('cli-err')
      ).rejects.toThrow('Query timed out');
    });
  });

  describe('desactivarPorClienteId', () => {
    it('desactiva correctamente todas las integraciones activas del cliente', async () => {
      const eqActivoMock = vi.fn().mockResolvedValue({ error: null });
      const eqClienteMock = vi.fn().mockReturnValue({ eq: eqActivoMock });
      const updateMock = vi.fn().mockReturnValue({ eq: eqClienteMock });

      mockSupabase = {
        from: vi.fn((table: string) => {
          if (table === 'clientes_integracion_fuente') {
            return {
              update: updateMock,
            };
          }
          throw new Error(`Unexpected table ${table}`);
        }),
      };

      vi.mocked(adminModule.getSupabaseAdmin).mockReturnValue(
        mockSupabase as unknown as ReturnType<typeof adminModule.getSupabaseAdmin>
      );

      await ClienteIntegracionRepository.desactivarPorClienteId('cli-to-deactivate');

      expect(mockSupabase.from).toHaveBeenCalledWith('clientes_integracion_fuente');
      expect(updateMock).toHaveBeenCalledWith(
        expect.objectContaining({
          activo: false,
          updated_at: expect.any(String),
        })
      );
      expect(eqClienteMock).toHaveBeenCalledWith('cliente_id', 'cli-to-deactivate');
      expect(eqActivoMock).toHaveBeenCalledWith('activo', true);
    });

    it('lanza un error si el update de desactivación falla en Supabase', async () => {
      const dbError = new Error('Database update failure');
      const eqActivoMock = vi.fn().mockResolvedValue({ error: dbError });
      const eqClienteMock = vi.fn().mockReturnValue({ eq: eqActivoMock });
      const updateMock = vi.fn().mockReturnValue({ eq: eqClienteMock });

      mockSupabase = {
        from: vi.fn().mockReturnValue({
          update: updateMock,
        }),
      };

      vi.mocked(adminModule.getSupabaseAdmin).mockReturnValue(
        mockSupabase as unknown as ReturnType<typeof adminModule.getSupabaseAdmin>
      );

      await expect(
        ClienteIntegracionRepository.desactivarPorClienteId('cli-fail')
      ).rejects.toThrow('Database update failure');
    });
  });

  describe('reassignClienteId', () => {
    it('omite la consulta si los ids son vacíos o iguales', async () => {
      mockSupabase = { from: vi.fn() };
      vi.mocked(adminModule.getSupabaseAdmin).mockReturnValue(
        mockSupabase as unknown as ReturnType<typeof adminModule.getSupabaseAdmin>
      );

      await ClienteIntegracionRepository.reassignClienteId('', 'cli-2');
      await ClienteIntegracionRepository.reassignClienteId('cli-1', 'cli-1');

      expect(mockSupabase.from).not.toHaveBeenCalled();
    });

    it('reasigna integraciones activas de un cliente temporal al nuevo usuario', async () => {
      const eqActivo = vi.fn().mockResolvedValue({ error: null });
      const eqCliente = vi.fn().mockReturnValue({ eq: eqActivo });
      const updateMock = vi.fn().mockReturnValue({ eq: eqCliente });

      mockSupabase = {
        from: vi.fn().mockReturnValue({ update: updateMock }),
      };
      vi.mocked(adminModule.getSupabaseAdmin).mockReturnValue(
        mockSupabase as unknown as ReturnType<typeof adminModule.getSupabaseAdmin>
      );

      await ClienteIntegracionRepository.reassignClienteId('temp-1', 'user-1');

      expect(updateMock).toHaveBeenCalledWith(
        expect.objectContaining({ cliente_id: 'user-1', updated_at: expect.any(String) })
      );
      expect(eqCliente).toHaveBeenCalledWith('cliente_id', 'temp-1');
      expect(eqActivo).toHaveBeenCalledWith('activo', true);
    });

    it('lanza error si falla la reasignación', async () => {
      const eqActivo = vi.fn().mockResolvedValue({ error: new Error('reassign fail') });
      const eqCliente = vi.fn().mockReturnValue({ eq: eqActivo });
      const updateMock = vi.fn().mockReturnValue({ eq: eqCliente });

      mockSupabase = {
        from: vi.fn().mockReturnValue({ update: updateMock }),
      };
      vi.mocked(adminModule.getSupabaseAdmin).mockReturnValue(
        mockSupabase as unknown as ReturnType<typeof adminModule.getSupabaseAdmin>
      );

      await expect(
        ClienteIntegracionRepository.reassignClienteId('temp-1', 'user-1')
      ).rejects.toThrow('reassign fail');
    });
  });

  describe('upsertOnboardingConfig', () => {
    it('actualiza la integración existente cuando ya existe una activa', async () => {
      const existing: ClienteIntegracionFuente = {
        id: 'int-existing',
        cliente_id: 'user-1',
        ga4_property_id: '555',
        client_gcp_project_id: 'proj-1',
        gcp_region: 'us-central1',
        activo: true,
        ultimo_lote_sincronizado: null,
        created_at: '2026-11-17T00:00:00Z',
        updated_at: '2026-11-17T00:00:00Z',
      };

      vi.spyOn(ClienteIntegracionRepository, 'findActiveByClienteId').mockResolvedValueOnce(existing);

      const updatedRow = { ...existing, base_url: 'https://miapp.com', requires_authentication: true };
      const singleMock = vi.fn().mockResolvedValue({ data: updatedRow, error: null });
      const selectMock = vi.fn().mockReturnValue({ single: singleMock });
      const eqMock = vi.fn().mockReturnValue({ select: selectMock });
      const updateMock = vi.fn().mockReturnValue({ eq: eqMock });

      mockSupabase = {
        from: vi.fn().mockReturnValue({ update: updateMock }),
      };
      vi.mocked(adminModule.getSupabaseAdmin).mockReturnValue(
        mockSupabase as unknown as ReturnType<typeof adminModule.getSupabaseAdmin>
      );

      const res = await ClienteIntegracionRepository.upsertOnboardingConfig({
        clienteId: 'user-1',
        baseUrl: 'https://miapp.com',
        requiresAuthentication: true,
        loginUrl: 'https://miapp.com/login',
        testUsername: 'qa@miapp.com',
        testPasswordEncrypted: 'enc-pwd',
        storageStateEncrypted: null,
        ga4PropertyId: '555',
        clientGcpProjectId: 'proj-1',
        gcpRegion: 'us-central1',
      });

      expect(eqMock).toHaveBeenCalledWith('id', 'int-existing');
      expect(res).toEqual(updatedRow);
    });

    it('inserta una nueva integración cuando no existe ninguna activa', async () => {
      vi.spyOn(ClienteIntegracionRepository, 'findActiveByClienteId').mockResolvedValueOnce(null);

      const insertedRow: ClienteIntegracionFuente = {
        id: 'int-new',
        cliente_id: 'user-2',
        ga4_property_id: null,
        client_gcp_project_id: null,
        gcp_region: null,
        base_url: 'https://shop.com',
        requires_authentication: false,
        activo: true,
        ultimo_lote_sincronizado: null,
        created_at: '2026-11-17T00:00:00Z',
        updated_at: '2026-11-17T00:00:00Z',
      };

      const singleMock = vi.fn().mockResolvedValue({ data: insertedRow, error: null });
      const selectMock = vi.fn().mockReturnValue({ single: singleMock });
      const insertMock = vi.fn().mockReturnValue({ select: selectMock });

      mockSupabase = {
        from: vi.fn().mockReturnValue({ insert: insertMock }),
      };
      vi.mocked(adminModule.getSupabaseAdmin).mockReturnValue(
        mockSupabase as unknown as ReturnType<typeof adminModule.getSupabaseAdmin>
      );

      const res = await ClienteIntegracionRepository.upsertOnboardingConfig({
        clienteId: 'user-2',
        baseUrl: 'https://shop.com',
        requiresAuthentication: false,
      });

      expect(insertMock).toHaveBeenCalledWith(
        expect.objectContaining({
          cliente_id: 'user-2',
          activo: true,
          base_url: 'https://shop.com',
          requires_authentication: false,
        })
      );
      expect(res).toEqual(insertedRow);
    });
  });
});
