import { getSupabaseAdmin } from "@/lib/supabase/admin";
import { DEFAULT_CLIENTE_ID } from "@/lib/constants";
import { getSignedCaptureUrl } from "@/services/gcp/storage.service";
import {
  buildAudienceCategories,
  calculateFunnelDropPp,
  calculateSiteSharePercent,
  formatPercentFromRatio,
  mergeStepsWithNotes,
  normalizeDiagnostico,
  type AgentJourneyStep,
  type FrictionDetail,
  type FriccionDetailRow,
  type FriccionRadarRow,
} from "@/lib/friction-data";
import {
  RADIAL_DISTANCES,
  HEAT_PALETTES,
  getRadialCoord,
  type FrictionCluster,
  type EventConfig,
  type HeatTier,
  type EventItem,
} from "@/lib/radar-constants";

const DB_TIMEOUT_MS = 3500;
const numberFormatter = new Intl.NumberFormat("es-AR");

function withTimeout<T>(promise: Promise<T>, ms: number, fallbackValue: T): Promise<T> {
  let timer: NodeJS.Timeout;
  const timeoutPromise = new Promise<T>((resolve) => {
    timer = setTimeout(() => {
      console.warn(`[FriccionRepository] Consulta excedió el timeout de ${ms}ms.`);
      resolve(fallbackValue);
    }, ms);
  });

  return Promise.race([
    promise.then((res) => {
      clearTimeout(timer);
      return res;
    }),
    timeoutPromise,
  ]);
}

function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return numberFormatter.format(value);
}

function formatDropRate(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "0,0%";
  const num = Number(value);
  if (Number.isNaN(num)) return "0,0%";
  return `${num.toFixed(1).replace(".", ",")}%`;
}

function getResolutionForDevice(deviceType: string | null | undefined): string {
  if (deviceType === "mobile") return "390 × 844";
  if (deviceType === "tablet") return "768 × 1024";
  return "1440 × 900";
}

export interface RadarDataResult {
  detectedEvents: EventItem[];
  eventsConfig: Record<string, EventConfig>;
  eventDisplayNames: Record<string, string>;
  totalAffectedSessions: number;
}

const EMPTY_RADAR_DATA: RadarDataResult = {
  detectedEvents: [],
  eventsConfig: {},
  eventDisplayNames: {},
  totalAffectedSessions: 0,
};

export class FriccionRepository {
  /**
   * Obtiene el detalle completo de una fricción desde Supabase,
   * enriqueciendo las capturas privadas de GCS con Signed URLs.
   * Retorna `null` si la fricción no existe o falla la consulta.
   */
  static async getDetailById(id: string): Promise<FrictionDetail | null> {
    const fetchFromSupabase = async (): Promise<FrictionDetail | null> => {
      try {
        const supabase = getSupabaseAdmin();

        const { data: rawFriccion, error } = await supabase
          .from("fricciones")
          .select(
            `
            *,
            fricciones_diagnosticos (*),
            friccion_recorrido_pasos (
              *,
              friccion_recorrido_notas (*)
            )
          `
          )
          .eq("id", id)
          .maybeSingle();

        if (error || !rawFriccion) {
          if (error) {
            console.warn(`[FriccionRepository] Error al consultar fricción ${id}:`, error.message);
          }
          return null;
        }

        const friccion = rawFriccion as unknown as FriccionDetailRow;
        const diagnostico = normalizeDiagnostico(friccion.fricciones_diagnosticos);
        const pasosConNotas = mergeStepsWithNotes(friccion.friccion_recorrido_pasos ?? []);
        const resolution = getResolutionForDevice(friccion.tipo_dispositivo);

        const steps: AgentJourneyStep[] = await Promise.all(
          pasosConNotas.map(async ({ paso, nota }) => {
            const signedImageUrl = await getSignedCaptureUrl(paso.captura_gcs_url);
            const pathSegment = paso.ruta_pagina
              ? paso.ruta_pagina.split("?")[0].split("/").filter(Boolean).pop()
              : null;
            const captureName = pathSegment
              ? `captura · ${pathSegment}`
              : `captura · paso_${paso.numero_paso}`;

            const stepTitle =
              nota?.nota_titulo ||
              paso.evento_nombre ||
              pathSegment ||
              `Paso ${paso.numero_paso}`;

            const notasContexto = Array.isArray(paso.notas_contexto) ? paso.notas_contexto : [];
            const contextDescription =
              notasContexto.length > 0
                ? notasContexto.join(" ")
                : "Paso de contexto capturado en el recorrido.";

            return {
              id: paso.id,
              stepNumber: paso.numero_paso,
              title: stepTitle,
              actionSubtitle:
                paso.evento_nombre ||
                nota?.insignias?.[0] ||
                paso.nombre_evento ||
                "Navegación",
              captureName,
              resolution,
              caption: `${stepTitle}${pathSegment ? ` · ${pathSegment}` : ""}`,
              noteTitle: nota?.nota_titulo || paso.evento_nombre || `Paso ${paso.numero_paso}`,
              noteDescription: nota?.nota_descripcion || contextDescription,
              badges: Array.isArray(nota?.insignias) ? nota.insignias : [],
              screenTime: "",
              clusterMatch: nota?.coincidencia_cluster || "",
              status: nota?.estado ?? (paso.friccion_detectada ? "error" : undefined),
              url: paso.ruta_pagina || undefined,
              imageSrc: signedImageUrl,
              nombreEvento: paso.nombre_evento,
              eventoNombre: paso.evento_nombre,
              items: paso.items,
              scroll: paso.scroll,
              enPatron: Boolean(paso.en_patron),
              friccionDetectada: Boolean(paso.friccion_detectada),
              notasContexto,
              hasLlmNote: Boolean(nota),
            };
          })
        );

        const dropRateFormatted = formatDropRate(friccion.tasa_abandono);
        const llegadaGrupo = formatPercentFromRatio(friccion.llegada_grupo);
        const llegadaReferencia = formatPercentFromRatio(friccion.llegada_referencia);
        const caidaPuntosPorcentuales = calculateFunnelDropPp(
          friccion.llegada_referencia,
          friccion.llegada_grupo
        );
        const porcentajeSitio = calculateSiteSharePercent(
          friccion.sesiones,
          friccion.total_sesiones_modelo
        );
        const sesionesPerdidas =
          friccion.sesiones_perdidas !== null && friccion.sesiones_perdidas !== undefined
            ? Number(friccion.sesiones_perdidas)
            : null;

        const eventoVisible = friccion.evento_clave_nombre || friccion.evento_clave || "";

        return {
          id: friccion.id,
          indexBadge: 1,
          title: diagnostico?.titulo || friccion.nombre || "Patrón de fricción detectado",
          subtitle:
            diagnostico?.subtitulo ||
            (eventoVisible
              ? `Tasa de abandono de ${dropRateFormatted} asociada a ${eventoVisible}.`
              : `Tasa de abandono de ${dropRateFormatted} en el flujo analizado.`),
          eventoClave: friccion.evento_clave,
          eventoClaveNombre: friccion.evento_clave_nombre,
          severidad: diagnostico?.severidad ?? null,
          impactoResumen: diagnostico?.impacto_resumen ?? null,
          secuencia: Array.isArray(friccion.secuencia) ? friccion.secuencia : [],
          secuenciaNombres: Array.isArray(friccion.secuencia_nombres)
            ? friccion.secuencia_nombres
            : [],
          tipoDispositivo: friccion.tipo_dispositivo,
          navegador: friccion.navegador,
          sistemaOperativo: friccion.sistema_operativo,
          llegadaGrupo,
          llegadaReferencia,
          caidaPuntosPorcentuales,
          sesionesPerdidas: Number.isNaN(sesionesPerdidas as number) ? null : sesionesPerdidas,
          totalSesionesModelo: friccion.total_sesiones_modelo,
          porcentajeSitio,
          ultimaDeteccion: friccion.ultima_deteccion,
          metrics: {
            sessionRate: {
              value: dropRateFormatted,
              label: "tasa de abandono",
            },
            affectedUsers: {
              value: formatCount(friccion.usuarios),
              label: "usuarios afectados",
            },
            totalSessions: {
              value: formatCount(friccion.sesiones),
              label: "sesiones analizadas",
            },
          },
          diagnosis: {
            paragraphs:
              Array.isArray(diagnostico?.diagnostico_parrafos) &&
              diagnostico.diagnostico_parrafos.length > 0
                ? diagnostico.diagnostico_parrafos
                : diagnostico?.diagnostico_corto
                  ? [diagnostico.diagnostico_corto]
                  : [],
          },
          evidence: Array.isArray(diagnostico?.evidencias) ? diagnostico.evidencias : [],
          recommendations: Array.isArray(diagnostico?.recomendaciones)
            ? diagnostico.recomendaciones
            : [],
          agentJourney: {
            steps,
          },
          audience: {
            summary: diagnostico?.audiencia_resumen || "",
            categories: buildAudienceCategories(friccion),
          },
        };
      } catch (err) {
        console.error(`[FriccionRepository] Fallo general al consultar ${id} en Supabase:`, err);
        return null;
      }
    };

    return withTimeout(fetchFromSupabase(), DB_TIMEOUT_MS, null);
  }

  /**
   * Obtiene las fricciones del cliente desde Supabase para construir el Radar
   * y los filtros de eventos clave, ordenadas por `sesiones_perdidas` descendente.
   */
  static async getRadarData(clienteId = DEFAULT_CLIENTE_ID): Promise<RadarDataResult> {
    const fetchFromSupabase = async (): Promise<RadarDataResult | null> => {
      try {
        const supabase = getSupabaseAdmin();
        const { data, error } = await supabase
          .from("fricciones")
          .select(
            `
            id,
            nombre,
            evento_clave,
            evento_clave_nombre,
            tasa_abandono,
            llegada_grupo,
            llegada_referencia,
            sesiones,
            usuarios,
            sesiones_perdidas,
            total_sesiones_modelo,
            secuencia,
            secuencia_nombres,
            ultima_deteccion,
            fricciones_diagnosticos (
              nombre_corto,
              titulo,
              subtitulo,
              severidad,
              impacto_resumen,
              diagnostico_corto
            )
          `
          )
          .eq("client_id", clienteId)
          .order("sesiones_perdidas", { ascending: false });

        if (error) {
          console.error("[FriccionRepository] Error al obtener datos de radar en Supabase:", error.message);
          return null;
        }

        const fricciones = (data || []) as unknown as FriccionRadarRow[];
        if (fricciones.length === 0) {
          return EMPTY_RADAR_DATA;
        }

        const eventsConfig: Record<string, EventConfig> = {};
        const detectedEventsMap = new Map<string, EventItem>();
        const eventDisplayNames: Record<string, string> = {};
        let totalAffectedSessions = 0;

        // Agrupar fricciones dinámicamente por `evento_clave`
        const groupedByEvent = new Map<string, FriccionRadarRow[]>();
        for (const friccion of fricciones) {
          const eventId = friccion.evento_clave || "evento_general";
          const eventName =
            friccion.evento_clave_nombre || friccion.evento_clave || "Evento general";

          eventDisplayNames[eventId] = eventName;

          if (!detectedEventsMap.has(eventId)) {
            detectedEventsMap.set(eventId, { id: eventId, name: eventName, count: 0 });
          }
          detectedEventsMap.get(eventId)!.count++;

          if (!groupedByEvent.has(eventId)) {
            groupedByEvent.set(eventId, []);
          }
          groupedByEvent.get(eventId)!.push(friccion);

          totalAffectedSessions += friccion.sesiones ?? 0;
        }

        // Construir EventConfig y posicionar clusters dinámicamente sin colisiones
        for (const [eventId, eventFricciones] of groupedByEvent.entries()) {
          const eventName = eventDisplayNames[eventId];
          const groupSize = eventFricciones.length;

          const clusters: FrictionCluster[] = eventFricciones.map((friccion, idx) => {
            const diag = normalizeDiagnostico(friccion.fricciones_diagnosticos);
            const tier: HeatTier = (diag?.severidad as HeatTier) || "alta";
            const angle = -45 + (idx * 360) / groupSize;
            const coords = getRadialCoord(RADIAL_DISTANCES[tier] || 110, angle);

            const sessionsFormatted = formatCount(friccion.sesiones);
            const usersFormatted = formatCount(friccion.usuarios);
            const dropRateNum =
              friccion.tasa_abandono !== null && friccion.tasa_abandono !== undefined
                ? Number(friccion.tasa_abandono)
                : undefined;
            const lostSessionsNum =
              friccion.sesiones_perdidas !== null && friccion.sesiones_perdidas !== undefined
                ? Number(friccion.sesiones_perdidas)
                : undefined;

            return {
              id: friccion.id,
              ...coords,
              radius: tier === "alta" ? 48 : tier === "media" ? 40 : 34,
              tier,
              ...HEAT_PALETTES[tier],
              name: diag?.nombre_corto || friccion.nombre || "Fricción detectada",
              severity: tier,
              impact:
                diag?.impacto_resumen ||
                (dropRateNum !== undefined && !Number.isNaN(dropRateNum)
                  ? `-${dropRateNum.toFixed(1)}% Abandono`
                  : "Impacto detectado"),
              sessions: `${sessionsFormatted} ses`,
              users: usersFormatted,
              sessionsCount: sessionsFormatted,
              diagnosis:
                diag?.diagnostico_corto ||
                diag?.subtitulo ||
                "Patrón detectado en análisis.",
              proximityLabel: `Criticidad ${tier}`,
              pulseDelay: `${(idx * 0.4).toFixed(1)}s`,
              eventoClave: eventId,
              eventoClaveNombre: eventName,
              sesionesPerdidas:
                lostSessionsNum !== undefined && !Number.isNaN(lostSessionsNum)
                  ? lostSessionsNum
                  : undefined,
              tasaAbandono:
                dropRateNum !== undefined && !Number.isNaN(dropRateNum)
                  ? dropRateNum
                  : undefined,
              ultimaDeteccion: friccion.ultima_deteccion,
              secuenciaNombres: Array.isArray(friccion.secuencia_nombres)
                ? friccion.secuencia_nombres
                : [],
            };
          });

          eventsConfig[eventId] = {
            id: eventId,
            label: eventName.toUpperCase(),
            technicalName: eventId,
            nodeX: 500,
            nodeY: 275,
            clusters,
          };
        }

        return {
          detectedEvents: Array.from(detectedEventsMap.values()),
          eventsConfig,
          eventDisplayNames,
          totalAffectedSessions,
        };
      } catch (err) {
        console.error("[FriccionRepository] Error inesperado en getRadarData:", err);
        return null;
      }
    };

    const result = await withTimeout(fetchFromSupabase(), DB_TIMEOUT_MS, null);
    return result ?? EMPTY_RADAR_DATA;
  }
}
