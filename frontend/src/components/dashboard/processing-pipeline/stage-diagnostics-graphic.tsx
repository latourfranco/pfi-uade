"use client";

import { cn } from "@/lib/utils";
import { Check, Sparkles } from "lucide-react";

interface StageGraphicProps {
  status: "pending" | "active" | "completed";
}

export function StageDiagnosticsGraphic({ status }: StageGraphicProps) {
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

        {/* Ilustración SVG de Reporte / Diagnóstico y Síntesis de Datos */}
        <div className="relative w-14 h-14 sm:w-16 sm:h-16 flex items-center justify-center">
          <svg
            viewBox="0 0 80 80"
            className="w-full h-full absolute inset-0"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            {/* Hoja / Tarjeta de Diagnóstico */}
            <rect
              x="18"
              y="12"
              width="44"
              height="56"
              rx="6"
              className={cn(
                "transition-colors duration-500",
                isPending
                  ? "fill-neutral-200/80 stroke-neutral-300"
                  : isCompleted
                  ? "fill-eureka-primary/15 stroke-eureka-primary"
                  : "fill-white stroke-eureka-primary shadow-xs"
              )}
              strokeWidth="1.5"
            />

            {/* Cabecera / Pestaña del reporte */}
            <rect
              x="26"
              y="20"
              width="18"
              height="4"
              rx="2"
              className={cn(
                "transition-colors duration-500",
                isPending ? "fill-neutral-400" : "fill-eureka-primary"
              )}
            />

            {/* Línea de métrica 1 */}
            <rect
              x="26"
              y="29"
              width="28"
              height="3"
              rx="1.5"
              className={cn(
                "transition-colors duration-500",
                isPending ? "fill-neutral-300" : "fill-eureka-primary/80"
              )}
            />

            {/* Barra de progreso / valor de métrica 2 */}
            <rect
              x="26"
              y="37"
              width="22"
              height="3"
              rx="1.5"
              className={cn(
                "transition-colors duration-500",
                isPending ? "fill-neutral-300" : "fill-eureka-primary/60"
              )}
            />

            {/* Barra de métrica 3 */}
            <rect
              x="26"
              y="45"
              width="26"
              height="3"
              rx="1.5"
              className={cn(
                "transition-colors duration-500",
                isPending ? "fill-neutral-300" : "fill-eureka-primary/40"
              )}
            />

            {/* Fila de síntesis / score */}
            <circle
              cx="30"
              cy="56"
              r="3"
              className={cn(
                "transition-colors duration-500",
                isPending ? "fill-neutral-350" : "fill-eureka-primary"
              )}
            />
            <line
              x1="36"
              y1="56"
              x2="52"
              y2="56"
              className={cn(
                "transition-colors duration-500",
                isPending ? "stroke-neutral-300" : "stroke-eureka-primary/80"
              )}
              strokeWidth="2.5"
              strokeLinecap="round"
            />
          </svg>

          {/* Chispa / Destello de IA e Insights */}
          {isActive && (
            <div className="absolute top-2 right-2 animate-pipeline-sparkle">
              <Sparkles className="w-4 h-4 text-eureka-primary filter drop-shadow-[0_0_4px_rgba(82,86,232,0.6)]" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
