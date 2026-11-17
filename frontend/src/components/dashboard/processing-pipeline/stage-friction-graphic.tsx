"use client";

import { cn } from "@/lib/utils";
import { Check } from "lucide-react";

interface StageGraphicProps {
  status: "pending" | "active" | "completed";
}

export function StageFrictionGraphic({ status }: StageGraphicProps) {
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

        {/* Ilustración SVG de Radar de Fricción */}
        <div className="relative w-14 h-14 sm:w-16 sm:h-16 flex items-center justify-center">
          <svg
            viewBox="0 0 80 80"
            className="w-full h-full absolute inset-0"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            {/* Anillos concéntricos del radar (r=34 externo, r=22 medio, r=10 interno) */}
            <circle
              cx="40"
              cy="40"
              r="34"
              className={cn(
                "transition-colors duration-500",
                isPending ? "stroke-neutral-300" : "stroke-eureka-primary/30"
              )}
              strokeWidth="1.2"
            />
            <circle
              cx="40"
              cy="40"
              r="22"
              className={cn(
                "transition-colors duration-500",
                isPending ? "stroke-neutral-300" : "stroke-eureka-primary/45"
              )}
              strokeWidth="1.2"
            />
            <circle
              cx="40"
              cy="40"
              r="10"
              className={cn(
                "transition-colors duration-500",
                isPending ? "stroke-neutral-300" : "stroke-eureka-primary/60"
              )}
              strokeWidth="1.2"
            />

            {/* Ejes transversales sutiles */}
            <line
              x1="40"
              y1="6"
              x2="40"
              y2="74"
              className={cn(
                "transition-colors duration-500",
                isPending ? "stroke-neutral-250" : "stroke-eureka-primary/20"
              )}
              strokeWidth="1"
            />
            <line
              x1="6"
              y1="40"
              x2="74"
              y2="40"
              className={cn(
                "transition-colors duration-500",
                isPending ? "stroke-neutral-250" : "stroke-eureka-primary/20"
              )}
              strokeWidth="1"
            />
          </svg>

          {/* Haz de barrido rotatorio con aguja frontal sincronizada */}
          {isActive && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div
                className="w-13 h-13 sm:w-15 sm:h-15 rounded-full animate-pipeline-sweep origin-center relative"
                style={{
                  background:
                    "conic-gradient(from -60deg at 50% 50%, transparent 0deg, rgba(82,86,232,0.02) 20deg, rgba(82,86,232,0.12) 42deg, rgba(82,86,232,0.38) 60deg, transparent 60.5deg)",
                }}
              >
                {/* Aguja frontal del radar a las 12 en punto (0°) */}
                <div className="absolute top-0 left-1/2 w-[1.5px] h-1/2 bg-eureka-primary origin-bottom -translate-x-1/2 opacity-90 shadow-[0_0_6px_rgba(82,86,232,0.8)]" />
              </div>
            </div>
          )}

          {/* Punto central */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 flex items-center justify-center pointer-events-none z-20">
            <div
              className={cn(
                "w-2.5 h-2.5 rounded-full transition-colors duration-500",
                isPending ? "bg-neutral-300" : "bg-eureka-primary"
              )}
            />
          </div>

          {/* Puntos / Focos de Fricción: Uno en aro intermedio (r=22) y otro en aro externo (r=34) */}
          {isActive ? (
            <>
              {/* Foco 1: En el Aro Intermedio (theta = 54°, r = 22px, se ilumina al pasar la aguja en t = 15%) */}
              <div
                className="absolute -translate-x-1/2 -translate-y-1/2 w-6 h-6 flex items-center justify-center pointer-events-none z-20"
                style={{ top: "33.8%", left: "72.3%" }}
              >
                {/* Onda Ping concéntrica */}
                <div className="w-3.5 h-3.5 rounded-full bg-eureka-primary/45 animate-friction-ping-1 absolute" />
                {/* Núcleo con fósforo sostenido */}
                <div className="w-2.5 h-2.5 rounded-full bg-eureka-primary animate-friction-core-1 relative z-10" />
              </div>

              {/* Foco 2: En el Aro Externo (theta = 234°, r = 34px, se ilumina al pasar la aguja en t = 65%) */}
              <div
                className="absolute -translate-x-1/2 -translate-y-1/2 w-6 h-6 flex items-center justify-center pointer-events-none z-20"
                style={{ top: "75.0%", left: "15.6%" }}
              >
                {/* Onda Ping concéntrica */}
                <div className="w-3.5 h-3.5 rounded-full bg-eureka-primary/45 animate-friction-ping-2 absolute" />
                {/* Núcleo con fósforo sostenido */}
                <div className="w-2.5 h-2.5 rounded-full bg-eureka-primary animate-friction-core-2 relative z-10" />
              </div>
            </>
          ) : isCompleted ? (
            <>
              <div
                className="absolute -translate-x-1/2 -translate-y-1/2 w-6 h-6 flex items-center justify-center pointer-events-none z-20"
                style={{ top: "33.8%", left: "72.3%" }}
              >
                <div className="w-2.5 h-2.5 rounded-full bg-eureka-primary" />
              </div>
              <div
                className="absolute -translate-x-1/2 -translate-y-1/2 w-6 h-6 flex items-center justify-center pointer-events-none z-20"
                style={{ top: "75.0%", left: "15.6%" }}
              >
                <div className="w-2.5 h-2.5 rounded-full bg-eureka-primary" />
              </div>
            </>
          ) : (
            <>
              <div
                className="absolute -translate-x-1/2 -translate-y-1/2 w-6 h-6 flex items-center justify-center pointer-events-none z-20"
                style={{ top: "33.8%", left: "72.3%" }}
              >
                <div className="w-2 h-2 rounded-full bg-neutral-300" />
              </div>
              <div
                className="absolute -translate-x-1/2 -translate-y-1/2 w-6 h-6 flex items-center justify-center pointer-events-none z-20"
                style={{ top: "75.0%", left: "15.6%" }}
              >
                <div className="w-2 h-2 rounded-full bg-neutral-300" />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
