import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { google } from 'googleapis';
import { ClienteIntegracionRepository } from '@/repositories/cliente-integracion.repository';
import {
  getActiveGcpProjects,
  createGcpProject,
  enableBigQueryApi,
  getGa4AccountProperties,
  createGa4BigQueryLink,
  configureBigQueryDataset,
  persistIntegrationRecord,
  orchestrateGa4Provisioning,
  type OAuth2Client,
} from '../orchestrator';

vi.mock('@/repositories/cliente-integracion.repository', () => ({
  ClienteIntegracionRepository: {
    create: vi.fn(),
  },
}));

vi.mock('googleapis', () => {
  return {
    google: {
      cloudresourcemanager: vi.fn(),
      serviceusage: vi.fn(),
      analyticsadmin: vi.fn(),
      bigquery: vi.fn(),
    },
  };
});

describe('GCP Orchestrator', () => {
  const mockAuth = {} as OAuth2Client;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('getActiveGcpProjects', () => {
    it('filtra y retorna solo los proyectos con lifecycleState ACTIVE y projectId válido', async () => {
      const mockList = vi.fn().mockResolvedValue({
        data: {
          projects: [
            { projectId: 'proj-active-1', name: 'Active Project 1', lifecycleState: 'ACTIVE' },
            { projectId: 'proj-deleted', name: 'Deleted Project', lifecycleState: 'DELETE_REQUESTED' },
            { projectId: 'proj-active-2', lifecycleState: 'ACTIVE' }, // sin name -> fallback a projectId
            { lifecycleState: 'ACTIVE' }, // sin projectId -> descartado
          ],
        },
      });

      vi.mocked(google.cloudresourcemanager).mockReturnValue({
        projects: { list: mockList },
      } as unknown as ReturnType<typeof google.cloudresourcemanager>);

      const projects = await getActiveGcpProjects(mockAuth);

      expect(google.cloudresourcemanager).toHaveBeenCalledWith({ version: 'v1', auth: mockAuth });
      expect(projects).toEqual([
        { projectId: 'proj-active-1', name: 'Active Project 1' },
        { projectId: 'proj-active-2', name: 'proj-active-2' },
      ]);
    });

    it('retorna array vacío si data.projects es undefined o nulo', async () => {
      const mockList = vi.fn().mockResolvedValue({ data: {} });

      vi.mocked(google.cloudresourcemanager).mockReturnValue({
        projects: { list: mockList },
      } as unknown as ReturnType<typeof google.cloudresourcemanager>);

      const projects = await getActiveGcpProjects(mockAuth);
      expect(projects).toEqual([]);
    });
  });

  describe('createGcpProject', () => {
    it('crea un proyecto con el nombre personalizado proporcionado', async () => {
      const mockCreate = vi.fn().mockResolvedValue({ data: {} });
      vi.mocked(google.cloudresourcemanager).mockReturnValue({
        projects: { create: mockCreate },
      } as unknown as ReturnType<typeof google.cloudresourcemanager>);

      const result = await createGcpProject(mockAuth, 'my-new-proj', 'Custom Warehouse');

      expect(mockCreate).toHaveBeenCalledWith({
        requestBody: {
          projectId: 'my-new-proj',
          name: 'Custom Warehouse',
        },
      });
      expect(result).toEqual({ projectId: 'my-new-proj' });
    });

    it('crea un proyecto con el nombre por defecto si no se especifica', async () => {
      const mockCreate = vi.fn().mockResolvedValue({ data: {} });
      vi.mocked(google.cloudresourcemanager).mockReturnValue({
        projects: { create: mockCreate },
      } as unknown as ReturnType<typeof google.cloudresourcemanager>);

      const result = await createGcpProject(mockAuth, 'my-default-proj');

      expect(mockCreate).toHaveBeenCalledWith({
        requestBody: {
          projectId: 'my-default-proj',
          name: 'Analytics Data Warehouse',
        },
      });
      expect(result).toEqual({ projectId: 'my-default-proj' });
    });
  });

  describe('enableBigQueryApi', () => {
    it('retorna inmediatamente si la API de BigQuery ya se encuentra en estado ENABLED', async () => {
      const mockServicesGet = vi.fn().mockResolvedValue({
        data: { state: 'ENABLED' },
      });
      const mockServicesEnable = vi.fn();

      vi.mocked(google.serviceusage).mockReturnValue({
        services: {
          get: mockServicesGet,
          enable: mockServicesEnable,
        },
      } as unknown as ReturnType<typeof google.serviceusage>);

      await enableBigQueryApi(mockAuth, 'proj-123');

      expect(mockServicesGet).toHaveBeenCalledWith({
        name: 'projects/proj-123/services/bigquery.googleapis.com',
      });
      expect(mockServicesEnable).not.toHaveBeenCalled();
    });

    it('habilita la API y espera si no está habilitada y devuelve una operación completada', async () => {
      const mockServicesGet = vi.fn().mockResolvedValue({
        data: { state: 'DISABLED' },
      });
      const mockServicesEnable = vi.fn().mockResolvedValue({
        data: { name: 'operations/op-1', done: true },
      });

      vi.mocked(google.serviceusage).mockReturnValue({
        services: {
          get: mockServicesGet,
          enable: mockServicesEnable,
        },
      } as unknown as ReturnType<typeof google.serviceusage>);

      const promise = enableBigQueryApi(mockAuth, 'proj-123');
      await vi.advanceTimersByTimeAsync(2000);
      await promise;

      expect(mockServicesEnable).toHaveBeenCalledWith({
        name: 'projects/proj-123/services/bigquery.googleapis.com',
      });
    });

    it('habilita la API cuando services.get arroja un error y espera la resolución de LRO pendiente', async () => {
      const mockServicesGet = vi.fn().mockRejectedValue(new Error('Service not found'));
      const mockServicesEnable = vi.fn().mockResolvedValue({
        data: { name: 'operations/op-lro-99', done: false },
      });
      const mockOperationsGet = vi
        .fn()
        .mockRejectedValueOnce(new Error('Network glitch'))
        .mockResolvedValueOnce({ data: { done: false } })
        .mockResolvedValueOnce({ data: { done: true } });

      vi.mocked(google.serviceusage).mockReturnValue({
        services: {
          get: mockServicesGet,
          enable: mockServicesEnable,
        },
        operations: {
          get: mockOperationsGet,
        },
      } as unknown as ReturnType<typeof google.serviceusage>);

      const promise = enableBigQueryApi(mockAuth, 'proj-lro');

      // Avanzar los intervalos de polling (1500ms c/u) y el settling final (2000ms)
      await vi.advanceTimersByTimeAsync(1500);
      await vi.advanceTimersByTimeAsync(1500);
      await vi.advanceTimersByTimeAsync(1500);
      await vi.advanceTimersByTimeAsync(2000);

      await promise;

      expect(mockServicesEnable).toHaveBeenCalled();
      expect(mockOperationsGet).toHaveBeenCalledTimes(3);
    });

    it('termina de esperar si el loop de polling alcanza el límite de 15 intentos', async () => {
      const mockServicesGet = vi.fn().mockResolvedValue({ data: { state: 'DISABLED' } });
      const mockServicesEnable = vi.fn().mockResolvedValue({
        data: { name: 'operations/op-slow', done: false },
      });
      const mockOperationsGet = vi.fn().mockResolvedValue({ data: { done: false } });

      vi.mocked(google.serviceusage).mockReturnValue({
        services: {
          get: mockServicesGet,
          enable: mockServicesEnable,
        },
        operations: {
          get: mockOperationsGet,
        },
      } as unknown as ReturnType<typeof google.serviceusage>);

      const promise = enableBigQueryApi(mockAuth, 'proj-slow');

      // Avanzar 15 veces 1500ms + 2000ms
      for (let i = 0; i < 15; i++) {
        await vi.advanceTimersByTimeAsync(1500);
      }
      await vi.advanceTimersByTimeAsync(2000);

      await promise;
      expect(mockOperationsGet).toHaveBeenCalledTimes(15);
    });
  });

  describe('getGa4AccountProperties', () => {
    it('retorna la lista de propiedades extrayendo ID y nombres formateados', async () => {
      const mockList = vi.fn().mockResolvedValue({
        data: {
          accountSummaries: [
            {
              displayName: 'Mi Empresa',
              propertySummaries: [
                { property: 'properties/12345', displayName: 'Web Principal' },
                { property: 'properties/67890' }, // sin displayName -> fallback a Propiedad 67890
                { property: 'malformed_property' }, // sin / -> split da "" -> ignorada
              ],
            },
            {
              // sin displayName -> fallback a Cuenta GA4
              propertySummaries: [
                { property: 'properties/112233', displayName: 'App Móvil' },
              ],
            },
            {
              displayName: 'Cuenta Vacía',
              propertySummaries: [],
            },
          ],
        },
      });

      vi.mocked(google.analyticsadmin).mockReturnValue({
        accountSummaries: { list: mockList },
      } as unknown as ReturnType<typeof google.analyticsadmin>);

      const result = await getGa4AccountProperties(mockAuth);

      expect(result).toEqual([
        {
          propertyId: '12345',
          propertyName: 'Web Principal',
          accountName: 'Mi Empresa',
        },
        {
          propertyId: '67890',
          propertyName: 'Propiedad 67890',
          accountName: 'Mi Empresa',
        },
        {
          propertyId: '112233',
          propertyName: 'App Móvil',
          accountName: 'Cuenta GA4',
        },
      ]);
    });

    it('retorna array vacío si accountSummaries es undefined o está vacío', async () => {
      const mockList = vi.fn().mockResolvedValue({ data: {} });
      vi.mocked(google.analyticsadmin).mockReturnValue({
        accountSummaries: { list: mockList },
      } as unknown as ReturnType<typeof google.analyticsadmin>);

      const result = await getGa4AccountProperties(mockAuth);
      expect(result).toEqual([]);
    });
  });

  describe('createGa4BigQueryLink', () => {
    it('omite la creación si la propiedad ya tiene un BigQuery Link activo', async () => {
      const mockList = vi.fn().mockResolvedValue({
        data: {
          bigqueryLinks: [{ name: 'properties/123/bigQueryLinks/456', project: 'projects/already-linked' }],
        },
      });
      const mockCreate = vi.fn();

      vi.mocked(google.analyticsadmin).mockReturnValue({
        properties: {
          bigQueryLinks: {
            list: mockList,
            create: mockCreate,
          },
        },
      } as unknown as ReturnType<typeof google.analyticsadmin>);

      await createGa4BigQueryLink(mockAuth, '123', 'my-proj');

      expect(mockList).toHaveBeenCalledWith({ parent: 'properties/123' });
      expect(mockCreate).not.toHaveBeenCalled();
    });

    it('crea el BigQuery Link con la configuración esperada cuando no existen links previos', async () => {
      const mockList = vi.fn().mockResolvedValue({
        data: { bigqueryLinks: [] },
      });
      const mockCreate = vi.fn().mockResolvedValue({
        data: { name: 'properties/123/bigQueryLinks/created-link' },
      });

      vi.mocked(google.analyticsadmin).mockReturnValue({
        properties: {
          bigQueryLinks: {
            list: mockList,
            create: mockCreate,
          },
        },
      } as unknown as ReturnType<typeof google.analyticsadmin>);

      await createGa4BigQueryLink(mockAuth, '123', 'my-proj', 'EU');

      expect(mockCreate).toHaveBeenCalledWith({
        parent: 'properties/123',
        requestBody: {
          project: 'projects/my-proj',
          dailyExportEnabled: true,
          streamingExportEnabled: false,
          datasetLocation: 'EU',
        },
      });
    });

    it('maneja de forma idempotente errores de conflicto 409 o cuota excedida 429', async () => {
      const mockList = vi.fn().mockResolvedValue({ data: { bigqueryLinks: [] } });
      const mockCreate = vi.fn().mockRejectedValue({ code: 409, message: 'Already exists' });

      vi.mocked(google.analyticsadmin).mockReturnValue({
        properties: {
          bigQueryLinks: {
            list: mockList,
            create: mockCreate,
          },
        },
      } as unknown as ReturnType<typeof google.analyticsadmin>);

      await expect(createGa4BigQueryLink(mockAuth, '123', 'my-proj')).resolves.toBeUndefined();
    });

    it('maneja error status 429 o mensaje "Resource has been exhausted"', async () => {
      const mockList = vi.fn().mockResolvedValue({ data: { bigqueryLinks: [] } });
      const mockCreate = vi.fn().mockRejectedValue({
        status: 429,
        cause: { status: 'RESOURCE_EXHAUSTED' },
        message: 'Resource has been exhausted',
      });

      vi.mocked(google.analyticsadmin).mockReturnValue({
        properties: {
          bigQueryLinks: {
            list: mockList,
            create: mockCreate,
          },
        },
      } as unknown as ReturnType<typeof google.analyticsadmin>);

      await expect(createGa4BigQueryLink(mockAuth, '123', 'my-proj')).resolves.toBeUndefined();
    });

    it('reintenta ante error de propagación (código 400 o 403) y tiene éxito en el siguiente intento', async () => {
      const mockList = vi.fn().mockResolvedValue({ data: { bigqueryLinks: [] } });
      const propagationError = {
        code: 400,
        message: 'The project has not enabled BigQuery API',
      };
      const mockCreate = vi
        .fn()
        .mockRejectedValueOnce(propagationError)
        .mockResolvedValueOnce({ data: { name: 'link-ok' } });

      vi.mocked(google.analyticsadmin).mockReturnValue({
        properties: {
          bigQueryLinks: {
            list: mockList,
            create: mockCreate,
          },
        },
      } as unknown as ReturnType<typeof google.analyticsadmin>);

      const promise = createGa4BigQueryLink(mockAuth, '123', 'my-proj');

      // withRetry espera baseDelayMs * (attempt + 1) = 2000 * 1 = 2000ms
      await vi.advanceTimersByTimeAsync(2000);
      await promise;

      expect(mockCreate).toHaveBeenCalledTimes(2);
    });

    it('lanza el error original inmediatamente si no es un error de propagación', async () => {
      const mockList = vi.fn().mockResolvedValue({ data: { bigqueryLinks: [] } });
      const fatalError = new Error('Fatal backend failure');
      const mockCreate = vi.fn().mockRejectedValue(fatalError);

      vi.mocked(google.analyticsadmin).mockReturnValue({
        properties: {
          bigQueryLinks: {
            list: mockList,
            create: mockCreate,
          },
        },
      } as unknown as ReturnType<typeof google.analyticsadmin>);

      await expect(createGa4BigQueryLink(mockAuth, '123', 'my-proj')).rejects.toThrow('Fatal backend failure');
      expect(mockCreate).toHaveBeenCalledTimes(1);
    });

    it('agota los reintentos y lanza el último error si el error de propagación persiste', async () => {
      const mockList = vi.fn().mockResolvedValue({ data: { bigqueryLinks: [] } });
      const persistentError = {
        status: 403,
        message: 'API has not been used in project before or it is disabled',
      };
      const mockCreate = vi.fn().mockRejectedValue(persistentError);

      vi.mocked(google.analyticsadmin).mockReturnValue({
        properties: {
          bigQueryLinks: {
            list: mockList,
            create: mockCreate,
          },
        },
      } as unknown as ReturnType<typeof google.analyticsadmin>);

      const assertion = expect(
        createGa4BigQueryLink(mockAuth, '123', 'my-proj')
      ).rejects.toEqual(persistentError);

      await vi.advanceTimersByTimeAsync(2000);
      await vi.advanceTimersByTimeAsync(4000);
      await vi.advanceTimersByTimeAsync(6000);

      await assertion;
      expect(mockCreate).toHaveBeenCalledTimes(4);
    });
  });

  describe('configureBigQueryDataset', () => {
    it('crea un nuevo dataset con caducidad de 60 días y permisos de la SA si el dataset no existe (404)', async () => {
      const notFoundError = { code: 404, message: 'Not found' };
      const mockDatasetsGet = vi.fn().mockRejectedValue(notFoundError);
      const mockDatasetsInsert = vi.fn().mockResolvedValue({ data: {} });
      const mockDatasetsPatch = vi.fn();

      vi.mocked(google.bigquery).mockReturnValue({
        datasets: {
          get: mockDatasetsGet,
          insert: mockDatasetsInsert,
          patch: mockDatasetsPatch,
        },
      } as unknown as ReturnType<typeof google.bigquery>);

      const result = await configureBigQueryDataset(
        mockAuth,
        'proj-bq',
        'prop-888',
        'central-sa@platform.iam.gserviceaccount.com'
      );

      expect(mockDatasetsGet).toHaveBeenCalledWith({
        projectId: 'proj-bq',
        datasetId: 'analytics_prop-888',
      });
      expect(mockDatasetsInsert).toHaveBeenCalledWith({
        projectId: 'proj-bq',
        requestBody: {
          datasetReference: {
            projectId: 'proj-bq',
            datasetId: 'analytics_prop-888',
          },
          location: 'US',
          defaultTableExpirationMs: '5184000000',
          access: [
            { role: 'OWNER', specialGroup: 'projectOwners' },
            { role: 'WRITER', specialGroup: 'projectWriters' },
            { role: 'READER', specialGroup: 'projectReaders' },
            { role: 'READER', userByEmail: 'central-sa@platform.iam.gserviceaccount.com' },
          ],
        },
      });
      expect(mockDatasetsPatch).not.toHaveBeenCalled();
      expect(result).toEqual({ gcpRegion: 'US' });
    });

    it('crea el dataset sin entrada para SA si serviceAccountEmail está vacío', async () => {
      const notFoundError = { status: 404, message: 'Not found' };
      const mockDatasetsGet = vi.fn().mockRejectedValue(notFoundError);
      const mockDatasetsInsert = vi.fn().mockResolvedValue({ data: {} });

      vi.mocked(google.bigquery).mockReturnValue({
        datasets: {
          get: mockDatasetsGet,
          insert: mockDatasetsInsert,
          patch: vi.fn(),
        },
      } as unknown as ReturnType<typeof google.bigquery>);

      const result = await configureBigQueryDataset(mockAuth, 'proj-bq', 'prop-888', '');

      expect(mockDatasetsInsert).toHaveBeenCalledWith(
        expect.objectContaining({
          requestBody: expect.objectContaining({
            access: [
              { role: 'OWNER', specialGroup: 'projectOwners' },
              { role: 'WRITER', specialGroup: 'projectWriters' },
              { role: 'READER', specialGroup: 'projectReaders' },
            ],
          }),
        })
      );
      expect(result).toEqual({ gcpRegion: 'US' });
    });

    it('actualiza un dataset existente agregando la SA central si aún no tenía permisos', async () => {
      const mockDatasetsGet = vi.fn().mockResolvedValue({
        data: {
          location: 'southamerica-west1',
          access: [{ role: 'OWNER', specialGroup: 'projectOwners' }],
        },
      });
      const mockDatasetsPatch = vi.fn().mockResolvedValue({ data: {} });

      vi.mocked(google.bigquery).mockReturnValue({
        datasets: {
          get: mockDatasetsGet,
          insert: vi.fn(),
          patch: mockDatasetsPatch,
        },
      } as unknown as ReturnType<typeof google.bigquery>);

      const result = await configureBigQueryDataset(
        mockAuth,
        'proj-bq',
        'prop-888',
        'sa@central.com'
      );

      expect(mockDatasetsPatch).toHaveBeenCalledWith({
        projectId: 'proj-bq',
        datasetId: 'analytics_prop-888',
        requestBody: {
          defaultTableExpirationMs: '5184000000',
          access: [
            { role: 'OWNER', specialGroup: 'projectOwners' },
            { role: 'READER', userByEmail: 'sa@central.com' },
          ],
        },
      });
      expect(result).toEqual({ gcpRegion: 'southamerica-west1' });
    });

    it('no duplica permisos si la SA ya figuraba en el dataset existente (case-insensitive)', async () => {
      const mockDatasetsGet = vi.fn().mockResolvedValue({
        data: {
          location: 'US',
          access: [
            { role: 'OWNER', specialGroup: 'projectOwners' },
            { role: 'READER', userByEmail: 'SA@CENTRAL.COM' },
          ],
        },
      });
      const mockDatasetsPatch = vi.fn().mockResolvedValue({ data: {} });

      vi.mocked(google.bigquery).mockReturnValue({
        datasets: {
          get: mockDatasetsGet,
          insert: vi.fn(),
          patch: mockDatasetsPatch,
        },
      } as unknown as ReturnType<typeof google.bigquery>);

      await configureBigQueryDataset(mockAuth, 'proj-bq', 'prop-888', 'sa@central.com');

      expect(mockDatasetsPatch).toHaveBeenCalledWith({
        projectId: 'proj-bq',
        datasetId: 'analytics_prop-888',
        requestBody: {
          defaultTableExpirationMs: '5184000000',
          access: [
            { role: 'OWNER', specialGroup: 'projectOwners' },
            { role: 'READER', userByEmail: 'SA@CENTRAL.COM' },
          ],
        },
      });
    });

    it('maneja dataset existente cuyo campo access no es array (null o undefined)', async () => {
      const mockDatasetsGet = vi.fn().mockResolvedValue({
        data: {
          location: 'US',
          access: null,
        },
      });
      const mockDatasetsPatch = vi.fn().mockResolvedValue({ data: {} });

      vi.mocked(google.bigquery).mockReturnValue({
        datasets: {
          get: mockDatasetsGet,
          insert: vi.fn(),
          patch: mockDatasetsPatch,
        },
      } as unknown as ReturnType<typeof google.bigquery>);

      await configureBigQueryDataset(mockAuth, 'proj-bq', 'prop-888', 'sa@central.com');

      expect(mockDatasetsPatch).toHaveBeenCalledWith(
        expect.objectContaining({
          requestBody: expect.objectContaining({
            access: [{ role: 'READER', userByEmail: 'sa@central.com' }],
          }),
        })
      );
    });

    it('relanza cualquier error de datasets.get que sea diferente de 404', async () => {
      const serverError = { code: 500, message: 'Internal Server Error' };
      const mockDatasetsGet = vi.fn().mockRejectedValue(serverError);

      vi.mocked(google.bigquery).mockReturnValue({
        datasets: {
          get: mockDatasetsGet,
          insert: vi.fn(),
          patch: vi.fn(),
        },
      } as unknown as ReturnType<typeof google.bigquery>);

      await expect(
        configureBigQueryDataset(mockAuth, 'proj-bq', 'prop-888', 'sa@central.com')
      ).rejects.toEqual(serverError);
    });
  });

  describe('persistIntegrationRecord', () => {
    it('llama a ClienteIntegracionRepository.create con el DTO mapeado', async () => {
      vi.mocked(ClienteIntegracionRepository.create).mockResolvedValue({} as never);

      await persistIntegrationRecord({
        clienteId: 'cli-001',
        ga4PropertyId: 'prop-002',
        clientGcpProjectId: 'proj-003',
        gcpRegion: 'us-central1',
      });

      expect(ClienteIntegracionRepository.create).toHaveBeenCalledWith({
        clienteId: 'cli-001',
        ga4PropertyId: 'prop-002',
        clientGcpProjectId: 'proj-003',
        gcpRegion: 'us-central1',
      });
    });
  });

  describe('orchestrateGa4Provisioning', () => {
    it('ejecuta el flujo completo reutilizando el primer proyecto GCP activo existente', async () => {
      const mockProjectsList = vi.fn().mockResolvedValue({
        data: {
          projects: [{ projectId: 'existing-active-proj', lifecycleState: 'ACTIVE' }],
        },
      });
      vi.mocked(google.cloudresourcemanager).mockReturnValue({
        projects: { list: mockProjectsList },
      } as unknown as ReturnType<typeof google.cloudresourcemanager>);

      const mockServicesGet = vi.fn().mockResolvedValue({ data: { state: 'ENABLED' } });
      vi.mocked(google.serviceusage).mockReturnValue({
        services: { get: mockServicesGet },
      } as unknown as ReturnType<typeof google.serviceusage>);

      const mockLinksList = vi.fn().mockResolvedValue({ data: { bigqueryLinks: [] } });
      const mockLinksCreate = vi.fn().mockResolvedValue({ data: { name: 'link-1' } });
      vi.mocked(google.analyticsadmin).mockReturnValue({
        properties: {
          bigQueryLinks: {
            list: mockLinksList,
            create: mockLinksCreate,
          },
        },
      } as unknown as ReturnType<typeof google.analyticsadmin>);

      const mockDatasetsGet = vi.fn().mockResolvedValue({
        data: { location: 'us-east1', access: [] },
      });
      const mockDatasetsPatch = vi.fn().mockResolvedValue({ data: {} });
      vi.mocked(google.bigquery).mockReturnValue({
        datasets: {
          get: mockDatasetsGet,
          patch: mockDatasetsPatch,
        },
      } as unknown as ReturnType<typeof google.bigquery>);

      vi.mocked(ClienteIntegracionRepository.create).mockResolvedValue({} as never);

      const result = await orchestrateGa4Provisioning({
        auth: mockAuth,
        propertyId: 'ga4-prop-99',
        clienteId: 'client-11',
        platformServiceAccountEmail: 'sa@central.com',
      });

      expect(result).toEqual({
        propertyId: 'ga4-prop-99',
        projectId: 'existing-active-proj',
        gcpRegion: 'us-east1',
        clienteId: 'client-11',
      });
      expect(ClienteIntegracionRepository.create).toHaveBeenCalledWith({
        clienteId: 'client-11',
        ga4PropertyId: 'ga4-prop-99',
        clientGcpProjectId: 'existing-active-proj',
        gcpRegion: 'us-east1',
      });
    });

    it('crea un nuevo proyecto si no se encuentran proyectos activos disponibles', async () => {
      const mockProjectsList = vi.fn().mockResolvedValue({ data: { projects: [] } });
      const mockProjectsCreate = vi.fn().mockResolvedValue({ data: {} });
      vi.mocked(google.cloudresourcemanager).mockReturnValue({
        projects: {
          list: mockProjectsList,
          create: mockProjectsCreate,
        },
      } as unknown as ReturnType<typeof google.cloudresourcemanager>);

      const mockServicesGet = vi.fn().mockResolvedValue({ data: { state: 'ENABLED' } });
      vi.mocked(google.serviceusage).mockReturnValue({
        services: { get: mockServicesGet },
      } as unknown as ReturnType<typeof google.serviceusage>);

      const mockLinksList = vi.fn().mockResolvedValue({ data: { bigqueryLinks: [] } });
      const mockLinksCreate = vi.fn().mockResolvedValue({ data: { name: 'link-1' } });
      vi.mocked(google.analyticsadmin).mockReturnValue({
        properties: {
          bigQueryLinks: {
            list: mockLinksList,
            create: mockLinksCreate,
          },
        },
      } as unknown as ReturnType<typeof google.analyticsadmin>);

      const mockDatasetsGet = vi.fn().mockResolvedValue({
        data: { location: 'US', access: [] },
      });
      const mockDatasetsPatch = vi.fn().mockResolvedValue({ data: {} });
      vi.mocked(google.bigquery).mockReturnValue({
        datasets: {
          get: mockDatasetsGet,
          patch: mockDatasetsPatch,
        },
      } as unknown as ReturnType<typeof google.bigquery>);

      vi.mocked(ClienteIntegracionRepository.create).mockResolvedValue({} as never);

      const result = await orchestrateGa4Provisioning({
        auth: mockAuth,
        propertyId: 'ga4-prop-fresh',
        clienteId: 'client-22',
        platformServiceAccountEmail: 'sa@central.com',
      });

      expect(mockProjectsCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          requestBody: expect.objectContaining({
            projectId: expect.stringMatching(/^dw-client-\d+$/),
          }),
        })
      );
      expect(result.projectId).toMatch(/^dw-client-\d+$/);
    });
  });
});
