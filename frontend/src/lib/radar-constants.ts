export type HeatTier = "alta" | "media" | "baja";

export interface MatrixDot {
  x: number;
  y: number;
  radius: number;
  fill: string;
  opacity: number;
}

export interface FrictionCluster {
  id: string;
  x: number; // ViewBox coord (0-1000)
  y: number; // ViewBox coord (0-550)
  radius: number;
  tier: HeatTier;
  coreColor: string;
  auraGradientColor: string;
  dotPalettes: {
    hot: string;
    mid: string;
    warm: string;
    soft: string;
  };
  name: string;
  severity: "alta" | "media" | "baja";
  impact: string;
  sessions: string;
  users: string;
  sessionsCount: string;
  diagnosis: string;
  proximityLabel: string;
  pulseDelay?: string;
  eventoClave?: string;
  eventoClaveNombre?: string;
  sesionesPerdidas?: number;
  tasaAbandono?: number;
  ultimaDeteccion?: string | null;
  secuenciaNombres?: string[];
}

export interface EventConfig {
  id: string;
  label: string;
  technicalName: string;
  nodeX: number; // ViewBox coord (0-1000)
  nodeY: number; // ViewBox coord (0-550)
  clusters: FrictionCluster[];
}

export interface EventItem {
  id: string;
  name: string;
  count: number;
}

export const RADIAL_DISTANCES: Record<HeatTier, number> = {
  alta: 110,
  media: 160,
  baja: 195,
};

export function getRadialCoord(radius: number, angleDeg: number, centerX = 500, centerY = 275) {
  const rad = (angleDeg * Math.PI) / 180;
  return {
    x: Math.round(centerX + radius * Math.cos(rad)),
    y: Math.round(centerY + radius * Math.sin(rad)),
  };
}

export const HEAT_PALETTES: Record<
  HeatTier,
  {
    coreColor: string;
    auraGradientColor: string;
    dotPalettes: { hot: string; mid: string; warm: string; soft: string };
  }
> = {
  alta: {
    coreColor: "#DC2626",
    auraGradientColor: "rgba(220, 38, 38, 0.55)",
    dotPalettes: {
      hot: "#DC2626",
      mid: "#EF4444",
      warm: "#F87171",
      soft: "#FCA5A5",
    },
  },
  media: {
    coreColor: "#EA580C",
    auraGradientColor: "rgba(234, 88, 12, 0.50)",
    dotPalettes: {
      hot: "#EA580C",
      mid: "#F97316",
      warm: "#FB923C",
      soft: "#FDBA74",
    },
  },
  baja: {
    coreColor: "#CA8A04",
    auraGradientColor: "rgba(202, 138, 4, 0.48)",
    dotPalettes: {
      hot: "#CA8A04",
      mid: "#EAB308",
      warm: "#FACC15",
      soft: "#FEF08A",
    },
  },
};


