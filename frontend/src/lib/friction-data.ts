export type FriccionSeverity = "alta" | "media" | "baja";
export type PasoEstado = "success" | "warning" | "error";
export type CoincidenciaCluster = "baja" | "media" | "alta" | "muy alta" | "crítica";
export type DeviceType = "desktop" | "mobile" | "tablet";

export interface DistributionItem {
  label: string;
  percentage: number;
}

/** Fila de la tabla `public.fricciones` */
export interface FriccionRow {
  id: string;
  client_id: string;
  nombre: string | null;
  evento_clave: string | null;
  evento_clave_nombre: string | null;
  tasa_abandono: number | string | null;
  llegada_grupo: number | string | null;
  llegada_referencia: number | string | null;
  sesiones: number | null;
  usuarios: number | null;
  sesiones_perdidas: number | string | null;
  total_sesiones_modelo: number | null;
  secuencia: string[] | null;
  secuencia_nombres: string[] | null;
  id_modelo: string | null;
  id_sesion: string | null;
  primera_deteccion: string | null;
  ultima_deteccion: string | null;
  fecha_exploracion: string | null;
  hash_exploracion: string | null;
  tipo_dispositivo: DeviceType | string | null;
  navegador: string | null;
  sistema_operativo: string | null;
  distribucion_dispositivos: DistributionItem[] | null;
  distribucion_navegadores: DistributionItem[] | null;
  distribucion_sistemas: DistributionItem[] | null;
  distribucion_paises: DistributionItem[] | null;
  created_at?: string | null;
  updated_at?: string | null;
}

/** Fila de la tabla `public.fricciones_diagnosticos` (1:1 con `fricciones`) */
export interface FriccionDiagnosticoRow {
  id: string;
  friccion_id: string;
  nombre_corto: string | null;
  titulo: string | null;
  subtitulo: string | null;
  severidad: FriccionSeverity | null;
  impacto_resumen: string | null;
  diagnostico_corto: string | null;
  diagnostico_parrafos: string[];
  evidencias: string[];
  recomendaciones: string[];
  audiencia_resumen: string | null;
  modelo_llm: string | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  fecha_ejecucion: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

/** Fila de la tabla `public.friccion_recorrido_pasos` (1:N pasos completos) */
export interface FriccionPasoRow {
  id: string;
  friccion_id: string;
  numero_paso: number;
  nombre_evento: string | null;
  evento_nombre: string | null;
  ruta_pagina: string | null;
  items: string | null;
  scroll: boolean | null;
  en_patron: boolean | null;
  friccion_detectada: boolean | null;
  notas_contexto: string[] | null;
  captura_gcs_url: string | null;
  created_at?: string | null;
}

/** Fila de la tabla `public.friccion_recorrido_notas` (solo pasos con `en_patron = true`) */
export interface FriccionNotaRow {
  id: string;
  friccion_id: string;
  paso_id: string | null;
  numero_paso: number;
  nota_titulo: string;
  nota_descripcion: string;
  insignias: string[];
  estado: PasoEstado | null;
  coincidencia_cluster: CoincidenciaCluster | string | null;
  created_at?: string | null;
}

export interface FriccionPasoWithNotasRow extends FriccionPasoRow {
  friccion_recorrido_notas?: FriccionNotaRow[] | FriccionNotaRow | null;
}

export interface FriccionDetailRow extends FriccionRow {
  fricciones_diagnosticos?: FriccionDiagnosticoRow[] | FriccionDiagnosticoRow | null;
  friccion_recorrido_pasos?: FriccionPasoWithNotasRow[] | null;
}

export interface FriccionRadarRow {
  id: string;
  nombre: string | null;
  evento_clave: string | null;
  evento_clave_nombre: string | null;
  tasa_abandono: number | string | null;
  llegada_grupo: number | string | null;
  llegada_referencia: number | string | null;
  sesiones: number | null;
  usuarios: number | null;
  sesiones_perdidas: number | string | null;
  total_sesiones_modelo: number | null;
  secuencia: string[] | null;
  secuencia_nombres: string[] | null;
  ultima_deteccion: string | null;
  fricciones_diagnosticos?:
    | Pick<FriccionDiagnosticoRow, "nombre_corto" | "titulo" | "subtitulo" | "severidad" | "impacto_resumen" | "diagnostico_corto">
    | Array<Pick<FriccionDiagnosticoRow, "nombre_corto" | "titulo" | "subtitulo" | "severidad" | "impacto_resumen" | "diagnostico_corto">>
    | null;
}

export interface FrictionMetric {
  value: string;
  label: string;
}

export interface AgentJourneyStep {
  id?: string;
  stepNumber: number;
  title: string;
  actionSubtitle: string;
  captureName: string;
  resolution: string;
  caption: string;
  noteTitle: string;
  noteDescription: string;
  badges: string[];
  screenTime: string;
  interactiveElementsCount?: number;
  clusterMatch: string;
  status?: PasoEstado;
  duration?: string;
  url?: string;
  imageSrc?: string;
  nombreEvento?: string | null;
  eventoNombre?: string | null;
  items?: string | null;
  scroll?: boolean | null;
  enPatron?: boolean;
  friccionDetectada?: boolean;
  notasContexto?: string[];
  hasLlmNote?: boolean;
}

export interface AudienceBreakdownItem {
  label: string;
  percentage: number;
}

export interface AudienceBreakdownCategory {
  title: string;
  items: AudienceBreakdownItem[];
}

export interface AudienceData {
  summary: string;
  categories: AudienceBreakdownCategory[];
}

export interface FrictionDetail {
  id: string;
  indexBadge: number;
  title: string;
  subtitle: string;
  eventoClave?: string | null;
  eventoClaveNombre?: string | null;
  severidad?: FriccionSeverity | null;
  impactoResumen?: string | null;
  secuencia?: string[];
  secuenciaNombres?: string[];
  tipoDispositivo?: DeviceType | string | null;
  navegador?: string | null;
  sistemaOperativo?: string | null;
  llegadaGrupo?: number | null;
  llegadaReferencia?: number | null;
  caidaPuntosPorcentuales?: number | null;
  sesionesPerdidas?: number | null;
  totalSesionesModelo?: number | null;
  porcentajeSitio?: number | null;
  ultimaDeteccion?: string | null;
  metrics: {
    sessionRate: FrictionMetric;
    affectedUsers: FrictionMetric;
    totalSessions: FrictionMetric;
  };
  diagnosis: {
    paragraphs: string[];
  };
  evidence: string[];
  recommendations?: string[];
  agentJourney: {
    totalRuns?: number;
    failedRuns?: number;
    averageDuration?: string;
    steps: AgentJourneyStep[];
  };
  audience: AudienceData;
}

/**
 * Normaliza la relación 1:1 `fricciones_diagnosticos` que PostgREST puede
 * retornar como objeto único o array de 1 elemento.
 */
export function normalizeDiagnostico<T>(raw: T | T[] | null | undefined): T | null {
  if (!raw) return null;
  return Array.isArray(raw) ? (raw[0] ?? null) : raw;
}

/**
 * Convierte una proporción `0..1` (ej. `0.6728`) a porcentaje `0..100` (`67.28`).
 */
export function formatPercentFromRatio(ratio: number | string | null | undefined): number | null {
  if (ratio === null || ratio === undefined || ratio === "") return null;
  const num = Number(ratio);
  if (Number.isNaN(num)) return null;
  return num * 100;
}

/**
 * Calcula la caída en puntos porcentuales: `(llegada_referencia - llegada_grupo) * 100`.
 */
export function calculateFunnelDropPp(
  referencia: number | string | null | undefined,
  grupo: number | string | null | undefined
): number | null {
  const refPct = formatPercentFromRatio(referencia);
  const grpPct = formatPercentFromRatio(grupo);
  if (refPct === null || grpPct === null) return null;
  return refPct - grpPct;
}

/**
 * Calcula el porcentaje de sesiones afectadas sobre el total analizado en el modelo.
 */
export function calculateSiteSharePercent(
  sesiones: number | null | undefined,
  totalModelo: number | null | undefined
): number | null {
  if (!sesiones || !totalModelo || totalModelo <= 0) return null;
  return (sesiones / totalModelo) * 100;
}

/**
 * Construye las categorías de audiencia desde las columnas JSONB de `public.fricciones`.
 * Omite categorías sin ítems para no mostrar tarjetas vacías.
 */
export function buildAudienceCategories(
  friccion: Pick<
    FriccionRow,
    | "distribucion_dispositivos"
    | "distribucion_paises"
    | "distribucion_navegadores"
    | "distribucion_sistemas"
  >
): AudienceBreakdownCategory[] {
  const mapping: Array<{ title: string; items: DistributionItem[] | null | undefined }> = [
    { title: "DISPOSITIVO", items: friccion.distribucion_dispositivos },
    { title: "UBICACIÓN", items: friccion.distribucion_paises },
    { title: "NAVEGADOR", items: friccion.distribucion_navegadores },
    { title: "SISTEMA", items: friccion.distribucion_sistemas },
  ];

  return mapping
    .filter((entry) => Array.isArray(entry.items) && entry.items.length > 0)
    .map((entry) => ({
      title: entry.title,
      items: entry.items!,
    }));
}

/**
 * Ordena pasos por `numero_paso` ascendente y vincula cada paso con su nota LLM
 * haciendo match por `paso.id === nota.paso_id` (con fallback a `numero_paso` o relación anidada).
 */
export function mergeStepsWithNotes(
  pasos: FriccionPasoWithNotasRow[],
  notas: FriccionNotaRow[] = []
): Array<{ paso: FriccionPasoWithNotasRow; nota: FriccionNotaRow | null }> {
  const sortedPasos = [...pasos].sort((a, b) => a.numero_paso - b.numero_paso);
  const notasByPasoId = new Map<string, FriccionNotaRow>();
  const notasByNumero = new Map<number, FriccionNotaRow>();

  for (const nota of notas) {
    if (nota.paso_id) notasByPasoId.set(nota.paso_id, nota);
    notasByNumero.set(nota.numero_paso, nota);
  }

  return sortedPasos.map((paso) => {
    const nestedNota = normalizeDiagnostico(paso.friccion_recorrido_notas);
    const matchedNota =
      nestedNota ??
      notasByPasoId.get(paso.id) ??
      notasByNumero.get(paso.numero_paso) ??
      null;
    return { paso, nota: matchedNota };
  });
}

