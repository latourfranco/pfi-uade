import { google, type Auth, type bigquery_v2 } from "googleapis";
import { ClienteIntegracionRepository } from "@/repositories/cliente-integracion.repository";

export type OAuth2Client = Auth.OAuth2Client;

export interface Ga4PropertyInfo {
  propertyId: string;
  propertyName: string;
  accountName: string;
}

export interface ProvisioningResult {
  propertyId: string;
  projectId: string;
  gcpRegion: string;
  clienteId: string;
}

/**
 * Función auxiliar para reintentar operaciones que puedan experimentar latencia de propagación en GCP.
 */
async function withRetry<T>(
  fn: () => Promise<T>,
  retries = 4,
  baseDelayMs = 2000
): Promise<T> {
  let lastError: unknown;
  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      return await fn();
    } catch (error: unknown) {
      lastError = error;
      const err = error as { message?: string; code?: number; status?: number };
      const isPropagationError =
        err?.message?.includes("has not enabled BigQuery") ||
        err?.message?.includes("API has not been used") ||
        err?.code === 400 ||
        err?.code === 403 ||
        err?.status === 400 ||
        err?.status === 403;

      if (isPropagationError && attempt < retries - 1) {
        console.warn(
          `[GCP Orchestrator] Reintentando operación (intento ${attempt + 1}/${retries}) tras latencia de propagación de API...`
        );
        await new Promise((resolve) =>
          setTimeout(resolve, baseDelayMs * (attempt + 1))
        );
        continue;
      }
      throw error;
    }
  }
  throw lastError;
}

/**
 * 1. Consulta y retorna los proyectos de Google Cloud que se encuentren en estado 'ACTIVE'.
 */
export async function getActiveGcpProjects(
  auth: OAuth2Client
): Promise<Array<{ projectId: string; name?: string }>> {
  const resourceManager = google.cloudresourcemanager({
    version: "v1",
    auth,
  });

  const { data } = await resourceManager.projects.list();
  const active =
    data.projects?.filter(
      (p) => p.lifecycleState === "ACTIVE" && p.projectId
    ) || [];

  return active.map((p) => ({
    projectId: p.projectId!,
    name: p.name || p.projectId!,
  }));
}

/**
 * 2. Crea un nuevo proyecto en Google Cloud con el ID proporcionado.
 */
export async function createGcpProject(
  auth: OAuth2Client,
  projectId: string,
  projectName = "Analytics Data Warehouse"
): Promise<{ projectId: string }> {
  const resourceManager = google.cloudresourcemanager({
    version: "v1",
    auth,
  });

  await resourceManager.projects.create({
    requestBody: {
      projectId,
      name: projectName,
    },
  });

  return { projectId };
}

/**
 * 3. Habilita la API de BigQuery en el proyecto de GCP indicado y espera a que la operación concluya.
 */
export async function enableBigQueryApi(
  auth: OAuth2Client,
  projectId: string
): Promise<void> {
  const serviceUsage = google.serviceusage({ version: "v1", auth });

  try {
    const { data: service } = await serviceUsage.services.get({
      name: `projects/${projectId}/services/bigquery.googleapis.com`,
    });

    if (service.state === "ENABLED") {
      return;
    }
  } catch {
    // Si no está habilitado o falla la consulta, procedemos a habilitarlo
  }

  const { data: operation } = await serviceUsage.services.enable({
    name: `projects/${projectId}/services/bigquery.googleapis.com`,
  });

  // Si devuelve una operación de larga duración (LRO), esperamos a que termine
  if (operation.name && !operation.done) {
    let attempts = 0;
    while (attempts < 15) {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      try {
        const { data: opStatus } = await serviceUsage.operations.get({
          name: operation.name,
        });
        if (opStatus.done) {
          break;
        }
      } catch {
        // Continuar esperando si la consulta intermedia falla
      }
      attempts++;
    }
  }

  // Pausa de 2 segundos para permitir que la propagación en los endpoints de BigQuery se asiente
  await new Promise((resolve) => setTimeout(resolve, 2000));
}

/**
 * 4. Consulta y estructura la lista de cuentas y propiedades de GA4 accesibles.
 */
export async function getGa4AccountProperties(
  auth: OAuth2Client
): Promise<Ga4PropertyInfo[]> {
  const analyticsAdmin = google.analyticsadmin({
    version: "v1beta",
    auth,
  });

  const { data } = await analyticsAdmin.accountSummaries.list();
  const properties: Ga4PropertyInfo[] = [];

  if (data.accountSummaries && data.accountSummaries.length > 0) {
    for (const account of data.accountSummaries) {
      const accountDisplayName = account.displayName || "Cuenta GA4";
      if (account.propertySummaries && account.propertySummaries.length > 0) {
        for (const prop of account.propertySummaries) {
          // El formato de property es 'properties/123456789'
          const propertyId = prop.property?.split("/")[1] || "";
          if (propertyId) {
            properties.push({
              propertyId,
              propertyName: prop.displayName || `Propiedad ${propertyId}`,
              accountName: accountDisplayName,
            });
          }
        }
      }
    }
  }

  return properties;
}

/**
 * 5. Crea el BigQuery Link en GA4 con la configuración estricta requerida.
 * Utiliza analyticsadmin v1alpha donde se encuentra expuesto el recurso bigQueryLinks.
 * - dailyExportEnabled: true
 * - streamingExportEnabled: false
 * - datasetLocation: US (o región configurada)
 * 
 * Es idempotente: si la propiedad ya tiene un BigQuery Link activo (límite de cuota en GA4 estándar),
 * lo detecta y continúa sin arrojar error.
 */
export async function createGa4BigQueryLink(
  auth: OAuth2Client,
  propertyId: string,
  projectId: string,
  datasetLocation = "US"
): Promise<void> {
  const analyticsAdmin = google.analyticsadmin({
    version: "v1alpha",
    auth,
  });

  await withRetry(async () => {
    try {
      // 1. Verificar si la propiedad ya tiene enlaces de BigQuery existentes
      const { data: existingLinks } =
        await analyticsAdmin.properties.bigQueryLinks.list({
          parent: `properties/${propertyId}`,
        });

      if (
        existingLinks.bigqueryLinks &&
        existingLinks.bigqueryLinks.length > 0
      ) {
        console.log(
          `[GA4] La propiedad ${propertyId} ya tiene un BigQuery Link configurado (${existingLinks.bigqueryLinks[0].name || existingLinks.bigqueryLinks[0].project}). Omitiendo creación.`
        );
        return;
      }

      console.log(
        `[GA4] Creando BigQuery Link para propiedad ${propertyId} en proyecto ${projectId}...`
      );
      const res = await analyticsAdmin.properties.bigQueryLinks.create({
        parent: `properties/${propertyId}`,
        requestBody: {
          project: `projects/${projectId}`,
          dailyExportEnabled: true,
          streamingExportEnabled: false,
          datasetLocation,
        },
      });
      console.log(`[GA4] BigQuery Link creado exitosamente:`, res.data?.name);
    } catch (error: unknown) {
      const err = error as {
        code?: number;
        status?: number;
        message?: string;
        cause?: { status?: string; message?: string };
      };

      // Si ya existía el enlace a este proyecto (409 Conflict o 429 Cuota de links por propiedad alcanzada)
      const isAlreadyLinked =
        err?.code === 409 ||
        err?.status === 409 ||
        err?.code === 429 ||
        err?.status === 429 ||
        err?.cause?.status === "RESOURCE_EXHAUSTED" ||
        err?.message?.includes("Resource has been exhausted");

      if (isAlreadyLinked) {
        console.warn(
          "[GA4] BigQuery Link ya existía previamente o la propiedad alcanzó la cuota de enlaces. Continuando..."
        );
        return;
      }

      console.error("[GA4] Error al crear BigQuery Link:", err?.message || error);
      throw error;
    }
  });
}

type DatasetAccessEntry = NonNullable<bigquery_v2.Schema$Dataset["access"]>[number];

/**
 * 6. Configura el dataset en BigQuery:
 * - Aplica caducidad de 60 días (5.184.000.000 ms) para asegurar costo cero de almacenamiento.
 * - Concede rol READER / roles/bigquery.dataViewer a la Service Account central.
 */
export async function configureBigQueryDataset(
  auth: OAuth2Client,
  projectId: string,
  propertyId: string,
  serviceAccountEmail: string
): Promise<{ gcpRegion: string }> {
  const bq = google.bigquery({ version: "v2", auth });
  const datasetId = `analytics_${propertyId}`;

  return await withRetry(async () => {
    let existingDataset: bigquery_v2.Schema$Dataset | null = null;

    try {
      const res = await bq.datasets.get({
        projectId,
        datasetId,
      });
      existingDataset = res.data;
    } catch (err: unknown) {
      const errorObj = err as { code?: number; status?: number };
      if (errorObj?.code !== 404 && errorObj?.status !== 404) {
        throw err;
      }
    }

    const gcpRegion = existingDataset?.location || "US";

    if (!existingDataset) {
      console.log(
        `[BigQuery] Creando dataset ${datasetId} en proyecto ${projectId}...`
      );
      const accessEntries: DatasetAccessEntry[] = [
        {
          role: "OWNER",
          specialGroup: "projectOwners",
        },
        {
          role: "WRITER",
          specialGroup: "projectWriters",
        },
        {
          role: "READER",
          specialGroup: "projectReaders",
        },
      ];

      if (serviceAccountEmail) {
        accessEntries.push({
          role: "READER",
          userByEmail: serviceAccountEmail,
        });
      }

      await bq.datasets.insert({
        projectId,
        requestBody: {
          datasetReference: {
            projectId,
            datasetId,
          },
          location: gcpRegion,
          defaultTableExpirationMs: "5184000000",
          access: accessEntries,
        },
      });
      console.log(`[BigQuery] Dataset ${datasetId} creado con éxito.`);
    } else {
      console.log(
        `[BigQuery] Actualizando dataset ${datasetId} en proyecto ${projectId}...`
      );
      const accessEntries: DatasetAccessEntry[] = Array.isArray(
        existingDataset.access
      )
        ? [...existingDataset.access]
        : [];

      if (serviceAccountEmail) {
        const alreadyHasAccess = accessEntries.some(
          (entry) =>
            entry.userByEmail?.toLowerCase() ===
            serviceAccountEmail.toLowerCase()
        );

        if (!alreadyHasAccess) {
          accessEntries.push({
            role: "READER",
            userByEmail: serviceAccountEmail,
          });
        }
      }

      await bq.datasets.patch({
        projectId,
        datasetId,
        requestBody: {
          defaultTableExpirationMs: "5184000000",
          access: accessEntries,
        },
      });
      console.log(`[BigQuery] Dataset ${datasetId} actualizado con éxito.`);
    }

    return { gcpRegion };
  });
}

/**
 * 7. Persiste el registro de la integración a través del repositorio correspondiente.
 */
export async function persistIntegrationRecord(data: {
  clienteId: string;
  ga4PropertyId: string;
  clientGcpProjectId: string;
  gcpRegion: string;
}): Promise<void> {
  await ClienteIntegracionRepository.create({
    clienteId: data.clienteId,
    ga4PropertyId: data.ga4PropertyId,
    clientGcpProjectId: data.clientGcpProjectId,
    gcpRegion: data.gcpRegion,
  });
}

/**
 * Orquestador principal que ejecuta la secuencia completa de aprovisionamiento.
 */
export async function orchestrateGa4Provisioning(params: {
  auth: OAuth2Client;
  propertyId: string;
  clienteId: string;
  platformServiceAccountEmail: string;
}): Promise<ProvisioningResult> {
  const { auth, propertyId, clienteId, platformServiceAccountEmail } = params;

  // 1. Obtener proyectos activos o crear uno nuevo
  const activeProjects = await getActiveGcpProjects(auth);
  let targetProjectId = "";

  if (activeProjects.length > 0 && activeProjects[0].projectId) {
    targetProjectId = activeProjects[0].projectId;
  } else {
    targetProjectId = `dw-client-${Date.now().toString().slice(-6)}`;
    await createGcpProject(auth, targetProjectId);
  }

  console.log(
    `[GCP Orchestrator] Proyecto GCP destino seleccionado: ${targetProjectId}`
  );

  // 2. Habilitar API de BigQuery y esperar a que esté completamente lista
  await enableBigQueryApi(auth, targetProjectId);

  // 3. Crear el BigQuery Link en GA4
  await createGa4BigQueryLink(auth, propertyId, targetProjectId);

  // 4. Configurar Dataset BigQuery (TTL 60 días e IAM para la SA central)
  const { gcpRegion } = await configureBigQueryDataset(
    auth,
    targetProjectId,
    propertyId,
    platformServiceAccountEmail
  );

  // 5. Persistir en Supabase mediante el repositorio
  await persistIntegrationRecord({
    clienteId,
    ga4PropertyId: propertyId,
    clientGcpProjectId: targetProjectId,
    gcpRegion,
  });

  return {
    propertyId,
    projectId: targetProjectId,
    gcpRegion,
    clienteId,
  };
}
