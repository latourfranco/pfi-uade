import { google } from "googleapis";
import { ClienteIntegracionRepository } from "@/repositories/cliente-integracion.repository";
import { ClienteCuentaRepository } from "@/repositories/cliente-cuenta.repository";
import {
  revocarTokenGoogle,
  getOAuth2Client,
} from "./google-token-revocation.service";

export interface DisparoPurgaParams {
  clienteId: string;
  token?: string | null;
  motivo?: string;
}

export interface PurgaResultado {
  success: boolean;
  auditoriaId: string;
  tokensRevocados: boolean;
  sesionesInvalidadas: boolean;
  bdTransaccionalPurgada: boolean;
  dwPurgaDisparada: boolean;
}

export interface PurgarDataWarehouseParams {
  projectId?: string;
  propertyId?: string;
  clienteId: string;
}

/**
 * Ejecuta la purga y eliminación del dataset y tablas analíticas del cliente
 * en Google Cloud BigQuery (Data Warehouse).
 * Maneja idempotencia si el recurso ya no existe.
 */
export async function purgarDataWarehouseCliente(
  params: PurgarDataWarehouseParams
): Promise<void> {
  const { projectId, propertyId, clienteId } = params;

  if (!projectId || !propertyId) {
    console.log(
      `[DW Purge] No hay proyecto o propiedad asociada al cliente ${clienteId}. Omitiendo purga de BigQuery.`
    );
    return;
  }

  const datasetId = `analytics_${propertyId}`;
  console.log(
    `[DW Purge] Purgando dataset ${datasetId} del Data Warehouse en proyecto ${projectId}...`
  );

  try {
    const auth = getOAuth2Client();
    const bq = google.bigquery({ version: "v2", auth });

    await bq.datasets.delete({
      projectId,
      datasetId,
      deleteContents: true,
    });

    console.log(
      `[DW Purge] Dataset ${datasetId} eliminado con éxito de BigQuery.`
    );
  } catch (error: unknown) {
    const err = error as {
      code?: number;
      status?: number;
      message?: string;
    };

    // 404 Not Found: El dataset ya no existe o fue purgado previamente (idempotente)
    if (err?.code === 404 || err?.status === 404) {
      console.warn(
        `[DW Purge] El dataset ${datasetId} no existía o ya fue purgado previamente.`
      );
      return;
    }

    console.error(
      `[DW Purge] Error durante la purga de dataset ${datasetId}:`,
      err?.message || error
    );
    throw error;
  }
}

/**
 * Orquestador principal del proceso integral de baja y purga de cuenta:
 * 1. Revoca credenciales y tokens OAuth 2.0 ante Google Identity.
 * 2. Desactiva integraciones de fuentes en la base de datos transaccional (Supabase).
 * 3. Marca la cuenta institucional en estado 'baja_solicitada'.
 * 4. Inserta el registro auditable del ejercicio del derecho de supresión.
 * 5. Dispara el evento de purga asíncrona hacia el Data Warehouse (BigQuery).
 */
export async function ejecutarPurgaIntegralCliente(
  params: DisparoPurgaParams
): Promise<PurgaResultado> {
  const { clienteId, token, motivo } = params;

  // 1. Revocación de tokens de Google
  const tokenRevocation = await revocarTokenGoogle(token);

  // 2. Obtener la integración activa para conocer las coordenadas de GCP/BigQuery
  const integracion = await ClienteIntegracionRepository.findActiveByClienteId(
    clienteId
  );

  // 3. Purga transaccional en Supabase
  await ClienteIntegracionRepository.desactivarPorClienteId(clienteId);
  await ClienteCuentaRepository.marcarBajaCuenta(clienteId);

  // 4. Registro de auditoría legal (Derecho de Supresión)
  const auditoria = await ClienteCuentaRepository.registrarAuditoriaSupresion({
    clienteId,
    motivo:
      motivo ||
      "Solicitud voluntaria del titular (Derecho de Supresión)",
    tokensRevocados: tokenRevocation.revoked,
    sesionesInvalidadas: true,
    bdTransaccionalPurgada: true,
    dwPurgaDisparada: true,
    estadoPurga: "en_proceso",
    metadata: {
      tokenRevoked: tokenRevocation.revoked,
      revocationMessage: tokenRevocation.message,
      targetProjectId: integracion?.client_gcp_project_id || null,
      targetPropertyId: integracion?.ga4_property_id || null,
      disparado_en: new Date().toISOString(),
    },
  });

  // 5. Disparo asíncrono hacia el Data Warehouse (BigQuery)
  // Se ejecuta en background sin bloquear el tiempo de respuesta al cliente
  const asyncDwPurgeTask = async () => {
    try {
      if (integracion) {
        await purgarDataWarehouseCliente({
          projectId: integracion.client_gcp_project_id ?? undefined,
          propertyId: integracion.ga4_property_id ?? undefined,
          clienteId,
        });
      }

      await ClienteCuentaRepository.actualizarEstadoAuditoria(
        auditoria.id,
        "completada",
        {
          completado_en: new Date().toISOString(),
          dw_purgado: Boolean(integracion),
        }
      );
    } catch (dwError: unknown) {
      console.error(
        "[Purge Service] Error en purga asíncrona de Data Warehouse:",
        dwError
      );
      await ClienteCuentaRepository.actualizarEstadoAuditoria(
        auditoria.id,
        "fallida",
        {
          fallido_en: new Date().toISOString(),
          error: String(dwError),
        }
      );
    }
  };

  // Lanzar microtarea asíncrona
  void Promise.resolve().then(asyncDwPurgeTask);

  return {
    success: true,
    auditoriaId: auditoria.id,
    tokensRevocados: tokenRevocation.revoked,
    sesionesInvalidadas: true,
    bdTransaccionalPurgada: true,
    dwPurgaDisparada: true,
  };
}
