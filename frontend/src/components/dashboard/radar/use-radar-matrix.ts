import { useMemo } from "react";
import type { EventConfig, FrictionCluster, MatrixDot } from "../dashboard-radar-canvas";

const DEFAULT_GRID_STEP = 28;
const DEFAULT_VIEWBOX_W = 1000;
const DEFAULT_VIEWBOX_H = 550;

export function calculateRadarMatrix(
  currentEvent: EventConfig | null,
  gridStep = DEFAULT_GRID_STEP,
  viewBoxW = DEFAULT_VIEWBOX_W,
  viewBoxH = DEFAULT_VIEWBOX_H
): MatrixDot[] {
  const dots: MatrixDot[] = [];

  // Retícula base limpia cuando no hay evento seleccionado
  if (!currentEvent) {
    for (let x = gridStep; x < viewBoxW; x += gridStep) {
      for (let y = gridStep; y < viewBoxH; y += gridStep) {
        dots.push({
          x,
          y,
          radius: 1.05,
          fill: "#C4C3B8",
          opacity: 0.35,
        });
      }
    }
    return dots;
  }

  const clusters = currentEvent.clusters;

  // Retícula sensible al calor de los focos con evento activo
  for (let x = gridStep; x < viewBoxW; x += gridStep) {
    for (let y = gridStep; y < viewBoxH; y += gridStep) {
      // Área despejada detrás del nodo central
      if (Math.hypot(x - currentEvent.nodeX, y - currentEvent.nodeY) < 18) {
        continue;
      }

      let nearestCluster: FrictionCluster | null = null;
      let minDistance = Infinity;

      for (const cluster of clusters) {
        const dist = Math.hypot(x - cluster.x, y - cluster.y);
        if (dist < minDistance) {
          minDistance = dist;
          nearestCluster = cluster;
        }
      }

      if (nearestCluster) {
        const influenceRadius = nearestCluster.radius * 2.5;

        if (minDistance < influenceRadius) {
          const heatRatio = 1 - minDistance / influenceRadius;
          const palette = nearestCluster.dotPalettes || {
            hot: "#DC2626",
            mid: "#EF4444",
            warm: "#F87171",
            soft: "#FCA5A5",
          };

          let fill = palette.soft;
          let opacity = 0.38;
          let radius = 1.15;

          if (heatRatio > 0.65) {
            fill = palette.hot;
            opacity = 0.95;
            radius = 1.95;
          } else if (heatRatio > 0.4) {
            fill = palette.mid;
            opacity = 0.85;
            radius = 1.6;
          } else if (heatRatio > 0.2) {
            fill = palette.warm;
            opacity = 0.65;
            radius = 1.35;
          } else if (heatRatio > 0.05) {
            fill = palette.soft;
            opacity = 0.45;
            radius = 1.2;
          }

          dots.push({ x, y, radius, fill, opacity });
          continue;
        }
      }

      // Puntos base generales
      dots.push({
        x,
        y,
        radius: 1.05,
        fill: "#C4C3B8",
        opacity: 0.35,
      });
    }
  }

  return dots;
}

export function useRadarMatrix(
  currentEvent: EventConfig | null,
  gridStep = DEFAULT_GRID_STEP,
  viewBoxW = DEFAULT_VIEWBOX_W,
  viewBoxH = DEFAULT_VIEWBOX_H
): MatrixDot[] {
  return useMemo(
    () => calculateRadarMatrix(currentEvent, gridStep, viewBoxW, viewBoxH),
    [currentEvent, gridStep, viewBoxW, viewBoxH]
  );
}
