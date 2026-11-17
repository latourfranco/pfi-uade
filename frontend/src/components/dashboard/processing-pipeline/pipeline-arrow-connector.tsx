"use client";

import { cn } from "@/lib/utils";

interface PipelineArrowConnectorProps {
  status: "pending" | "active" | "completed";
  className?: string;
}

export function PipelineArrowConnector({
  status,
  className = "",
}: PipelineArrowConnectorProps) {
  const isPending = status === "pending";
  const isActive = status === "active";

  return (
    <div
      className={cn(
        "relative flex items-center justify-center select-none w-full",
        className
      )}
      aria-hidden="true"
    >
      {/* Flecha Horizontal con centrado geométrico perfecto */}
      <div className="relative w-10 sm:w-14 md:w-16 h-6 flex items-center justify-center overflow-visible">
        <svg
          viewBox="0 0 60 20"
          className="w-full h-full overflow-visible"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            <linearGradient id="activeFlowGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#5256E8" stopOpacity="0.2" />
              <stop offset="50%" stopColor="#5256E8" stopOpacity="1" />
              <stop offset="100%" stopColor="#5256E8" stopOpacity="0.2" />
            </linearGradient>
          </defs>

          {/* Línea Base */}
          <line
            x1="4"
            y1="10"
            x2="50"
            y2="10"
            className={cn(
              "transition-colors duration-500",
              isPending ? "stroke-neutral-300" : "stroke-eureka-primary"
            )}
            strokeWidth="2"
            strokeLinecap="round"
          />

          {/* Cabeza de la Flecha (centrada en margen simétrico x=4 a x=56) */}
          <path
            d="M 46 4 L 56 10 L 46 16"
            className={cn(
              "transition-colors duration-500",
              isPending ? "stroke-neutral-300" : "stroke-eureka-primary"
            )}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Efecto de flujo de pulso activo */}
          {isActive && (
            <line
              x1="6"
              y1="10"
              x2="52"
              y2="10"
              stroke="url(#activeFlowGradient)"
              strokeWidth="3.5"
              strokeLinecap="round"
              className="animate-connector-flow"
            />
          )}
        </svg>
      </div>
    </div>
  );
}
