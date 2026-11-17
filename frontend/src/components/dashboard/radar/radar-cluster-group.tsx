"use client";

import type { FrictionCluster } from "../dashboard-radar-canvas";

interface RadarClusterGroupProps {
  cluster: FrictionCluster;
  onSelect: (cluster: FrictionCluster) => void;
}

export function RadarClusterGroup({ cluster, onSelect }: RadarClusterGroupProps) {
  return (
    <g
      className="cursor-pointer group pointer-events-auto outline-none"
      onClick={() => onSelect(cluster)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(cluster);
        }
      }}
      aria-label={`Ver patrón de fricción: ${cluster.name}`}
    >
      {/* 1. Aura difusa pulsante */}
      <g
        style={{
          transformOrigin: `${cluster.x}px ${cluster.y}px`,
          animationDelay: cluster.pulseDelay || "0s",
        }}
        className="animate-aura-pulse transition-transform duration-300 group-hover:scale-110"
      >
        {/* Resplandor exterior difuso */}
        <circle
          cx={cluster.x}
          cy={cluster.y}
          r={cluster.radius * 1.35}
          fill={`url(#grad-${cluster.id})`}
          filter="url(#heatBlur)"
        />
        {/* Núcleo térmico interior */}
        <circle
          cx={cluster.x}
          cy={cluster.y}
          r={cluster.radius * 0.85}
          fill={`url(#grad-${cluster.id})`}
          filter="url(#subtleBlur)"
        />
      </g>

      {/* 2. Punto focal único pulsante según escala cromática */}
      <g
        style={{
          transformOrigin: `${cluster.x}px ${cluster.y}px`,
          animationDelay: cluster.pulseDelay || "0s",
          color: cluster.coreColor,
        }}
        className="animate-core-pulse transition-transform duration-200 group-hover:scale-125"
      >
        {/* Halo puntual */}
        <circle
          cx={cluster.x}
          cy={cluster.y}
          r="7.5"
          fill={cluster.coreColor}
          opacity="0.32"
        />
        {/* Punto único de fricción */}
        <circle
          cx={cluster.x}
          cy={cluster.y}
          r="4.8"
          fill={cluster.coreColor}
          opacity="0.95"
        />
      </g>

      {/* 3. Área de impacto interactiva que cubre el foco y su aura */}
      <circle
        cx={cluster.x}
        cy={cluster.y}
        r={Math.max(cluster.radius * 1.4, 48)}
        fill="transparent"
        className="cursor-pointer"
      />

      <title>{cluster.name}</title>
    </g>
  );
}
