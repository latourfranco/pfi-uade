"use server";

import { FriccionRepository, type RadarDataResult } from "@/repositories/friccion.repository";
import { getEffectiveClienteId } from "@/lib/auth/session";

export async function getDashboardRadarDataAction(
  clienteId?: string
): Promise<RadarDataResult> {
  try {
    const effectiveClienteId = await getEffectiveClienteId(clienteId);
    return await FriccionRepository.getRadarData(effectiveClienteId);
  } catch (error) {
    console.error("[getDashboardRadarDataAction] Error al obtener datos:", error);
    return {
      detectedEvents: [],
      eventsConfig: {},
      eventDisplayNames: {},
      totalAffectedSessions: 0,
    };
  }
}
