"use client";

import { cn } from "@/lib/utils";
import { Check } from "lucide-react";

interface StageGraphicProps {
  status: "pending" | "active" | "completed";
}

export function StageExtractionGraphic({ status }: StageGraphicProps) {
  const isPending = status === "pending";
  const isActive = status === "active";
  const isCompleted = status === "completed";

  return (
    <div className="relative w-24 h-24 sm:w-28 sm:h-28 flex items-center justify-center select-none">
      {/* Halo de fondo cuando está activo */}
      {isActive && (
        <div
          className="absolute inset-0 rounded-2xl bg-eureka-primary/15 animate-ping"
          style={{ animationDuration: "2.8s" }}
        />
      )}

      {/* Tarjeta contenedor del gráfico */}
      <div
        className={cn(
          "relative w-full h-full rounded-2xl border flex flex-col items-center justify-center p-2.5 transition-all duration-500",
          isPending && "bg-neutral-100/60 border-neutral-200/80 text-neutral-400",
          isActive && "bg-white border-eureka-primary shadow-lg shadow-indigo-500/10 text-eureka-primary",
          isCompleted && "bg-[#EEF2FF] border-eureka-primary/50 text-eureka-primary shadow-xs"
        )}
      >
        {/* Badge de completado */}
        {isCompleted && (
          <div className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-eureka-primary text-white flex items-center justify-center shadow-xs animate-in zoom-in-50 duration-300">
            <Check className="w-3 h-3 stroke-[3]" />
          </div>
        )}

        {/* Ilustración SVG de Ingesta / Stream de Datos */}
        <svg
          viewBox="0 0 80 80"
          className="w-14 h-14 sm:w-16 sm:h-16"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          {/* Base / Recipiente de Almacenamiento & Buffer */}
          <rect
            x="20"
            y="48"
            width="40"
            height="18"
            rx="5"
            className={cn(
              "transition-colors duration-500",
              isPending ? "fill-neutral-200/90 stroke-neutral-300" : "fill-eureka-primary/10 stroke-eureka-primary"
            )}
            strokeWidth="1.5"
          />

          {/* Ranura/Indicador de base */}
          <line
            x1="28"
            y1="57"
            x2="52"
            y2="57"
            className={cn(
              "transition-colors duration-500",
              isPending ? "stroke-neutral-300" : "stroke-eureka-primary"
            )}
            strokeWidth="2"
            strokeLinecap="round"
          />

          {/* Líneas guía de flujo descendente */}
          <line
            x1="26"
            y1="14"
            x2="26"
            y2="42"
            className={cn(
              "transition-colors duration-500 stroke-dashed",
              isPending ? "stroke-neutral-300" : "stroke-eureka-primary/30"
            )}
            strokeWidth="1.2"
            strokeDasharray="2 3"
          />
          <line
            x1="40"
            y1="10"
            x2="40"
            y2="42"
            className={cn(
              "transition-colors duration-500 stroke-dashed",
              isPending ? "stroke-neutral-300" : "stroke-eureka-primary/40"
            )}
            strokeWidth="1.2"
            strokeDasharray="2 3"
          />
          <line
            x1="54"
            y1="14"
            x2="54"
            y2="42"
            className={cn(
              "transition-colors duration-500 stroke-dashed",
              isPending ? "stroke-neutral-300" : "stroke-eureka-primary/30"
            )}
            strokeWidth="1.2"
            strokeDasharray="2 3"
          />

          {/* Paquetes / Nodos de datos en movimiento */}
          {isActive ? (
            <>
              {/* Paquete 1 */}
              <g className="animate-pipeline-packet-1">
                <circle cx="26" cy="18" r="3.5" className="fill-eureka-primary" />
              </g>

              {/* Paquete 2 (Central con halo) */}
              <g className="animate-pipeline-packet-2">
                <circle cx="40" cy="14" r="4.5" className="fill-eureka-primary" />
                <circle cx="40" cy="14" r="7" className="fill-eureka-primary/20" />
              </g>

              {/* Paquete 3 */}
              <g className="animate-pipeline-packet-3">
                <circle cx="54" cy="18" r="3.5" className="fill-eureka-primary" />
              </g>
            </>
          ) : isCompleted ? (
            <>
              <circle cx="26" cy="38" r="3" className="fill-eureka-primary" />
              <circle cx="40" cy="38" r="4" className="fill-eureka-primary" />
              <circle cx="54" cy="38" r="3" className="fill-eureka-primary" />
            </>
          ) : (
            <>
              <circle cx="26" cy="18" r="3" className="fill-neutral-300" />
              <circle cx="40" cy="14" r="3.5" className="fill-neutral-350" />
              <circle cx="54" cy="18" r="3" className="fill-neutral-300" />
            </>
          )}
        </svg>
      </div>
    </div>
  );
}
