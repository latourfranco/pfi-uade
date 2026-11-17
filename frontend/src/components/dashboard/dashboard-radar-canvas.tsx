"use client";

import { useState } from "react";
import { useRadarMatrix } from "./radar/use-radar-matrix";
import { RadarEmptyState } from "./radar/radar-empty-state";
import { RadarClusterGroup } from "./radar/radar-cluster-group";
import { RadarEventNode } from "./radar/radar-event-node";
import { RadarFrictionDialog } from "./radar/radar-friction-dialog";
import type {
  FrictionCluster,
  EventConfig,
} from "@/lib/radar-constants";

export {
  RADIAL_DISTANCES,
  HEAT_PALETTES,
  type HeatTier,
  type MatrixDot,
  type FrictionCluster,
  type EventConfig,
} from "@/lib/radar-constants";

export interface DashboardRadarCanvasProps {
  selectedEventId: string | null;
  onSelectEvent: (id: string | null) => void;
  eventsConfig?: Record<string, EventConfig>;
  eventDisplayNames?: Record<string, string>;
}

const VIEWBOX_W = 1000;
const VIEWBOX_H = 550;

export function DashboardRadarCanvas({
  selectedEventId,
  onSelectEvent,
  eventsConfig = {},
  eventDisplayNames = {},
}: DashboardRadarCanvasProps) {
  const activeEventsConfig = eventsConfig;
  const activeDisplayNames = eventDisplayNames;
  const currentEvent = selectedEventId ? activeEventsConfig[selectedEventId] : null;
  const [selectedCluster, setSelectedCluster] = useState<FrictionCluster | null>(null);

  // Hook desacoplado para cálculo matricial del mapa de calor
  const matrixDots = useRadarMatrix(currentEvent, 28, VIEWBOX_W, VIEWBOX_H);

  return (
    <div className="w-full rounded-3xl border border-neutral-300/80 bg-[#ECEAE2] relative overflow-hidden min-h-115 flex items-center justify-center shadow-inner select-none transition-colors duration-500">
      {/* Capa Gráfica SVG */}
      <svg
        viewBox={`0 0 ${VIEWBOX_W} ${VIEWBOX_H}`}
        className="w-full h-full absolute inset-0"
        preserveAspectRatio="xMidYMid slice"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <filter id="heatBlur" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="18" />
          </filter>
          <filter id="subtleBlur" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="10" />
          </filter>

          {currentEvent?.clusters.map((cluster) => (
            <radialGradient
              key={`grad-${cluster.id}`}
              id={`grad-${cluster.id}`}
              cx="50%"
              cy="50%"
              r="50%"
            >
              <stop offset="0%" stopColor={cluster.auraGradientColor} stopOpacity="1" />
              <stop offset="45%" stopColor={cluster.auraGradientColor} stopOpacity="0.75" />
              <stop offset="80%" stopColor={cluster.auraGradientColor} stopOpacity="0.2" />
              <stop offset="100%" stopColor={cluster.auraGradientColor} stopOpacity="0" />
            </radialGradient>
          ))}
        </defs>

        {/* Matriz de Puntos de Fondo */}
        <g className="transition-all duration-700 pointer-events-none">
          {matrixDots.map((dot, idx) => (
            <circle
              key={idx}
              cx={dot.x}
              cy={dot.y}
              r={dot.radius}
              fill={dot.fill}
              opacity={dot.opacity}
            />
          ))}
        </g>

        {/* Focos de Fricción Interactivos */}
        {currentEvent?.clusters.map((cluster) => (
          <RadarClusterGroup
            key={`cluster-interactive-${cluster.id}`}
            cluster={cluster}
            onSelect={setSelectedCluster}
          />
        ))}
      </svg>

      {/* Capas de Interfaz (HTML) */}
      {!currentEvent ? (
        <RadarEmptyState />
      ) : (
        <>
          {/* Botón de cierre en esquina superior derecha */}
          <div className="absolute top-4 right-5 z-30">
            <button
              type="button"
              onClick={() => {
                setSelectedCluster(null);
                onSelectEvent(null);
              }}
              className="text-xs font-mono text-neutral-500 hover:text-neutral-900 bg-white/80 hover:bg-white px-3 py-1.5 rounded-full transition-all cursor-pointer border border-neutral-300/80 shadow-2xs backdrop-blur-xs flex items-center gap-1.5"
            >
              <span>Cerrar</span>
              <span className="text-neutral-400 font-bold">×</span>
            </button>
          </div>

          {/* Nodo central de evento */}
          <RadarEventNode label={currentEvent.label} />
        </>
      )}

      {/* Modal Dialog de detalle */}
      <RadarFrictionDialog
        cluster={selectedCluster}
        eventId={selectedEventId}
        eventName={
          activeDisplayNames[selectedEventId || ""] ||
          currentEvent?.label ||
          "Evento"
        }
        onClose={() => setSelectedCluster(null)}
      />
    </div>
  );
}
