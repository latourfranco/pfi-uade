"use client";

import { cn } from "@/lib/utils";
import { Check } from "lucide-react";

interface StageGraphicProps {
  status: "pending" | "active" | "completed";
}

export function StagePathsGraphic({ status }: StageGraphicProps) {
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

        {/* Ilustración SVG de Secuencia de Navegación en Interfaces Web */}
        <div className="relative w-14 h-14 sm:w-16 sm:h-16 flex items-center justify-center">
          <svg
            viewBox="0 0 80 80"
            className="w-full h-full absolute inset-0"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            {/* --- PANTALLA 1 (Interfaz Web Origen / Izquierda) --- */}
            <g>
              {/* Marco de ventana de navegador */}
              <rect
                x="8"
                y="22"
                width="34"
                height="44"
                rx="4"
                className={cn(
                  "transition-colors duration-500",
                  isPending
                    ? "fill-neutral-200/60 stroke-neutral-300"
                    : isCompleted
                    ? "fill-eureka-primary/10 stroke-eureka-primary/50"
                    : "fill-white stroke-neutral-300 shadow-xs"
                )}
                strokeWidth="1.2"
              />

              {/* Barra superior de ventana */}
              <line
                x1="8"
                y1="29"
                x2="42"
                y2="29"
                className={cn(
                  "transition-colors duration-500",
                  isPending ? "stroke-neutral-300" : "stroke-eureka-primary/30"
                )}
                strokeWidth="1"
              />

              {/* 3 puntos de control de ventana */}
              <circle
                cx="12"
                cy="25.5"
                r="1"
                className={isPending ? "fill-neutral-350" : "fill-eureka-primary/60"}
              />
              <circle
                cx="15"
                cy="25.5"
                r="1"
                className={isPending ? "fill-neutral-350" : "fill-eureka-primary/60"}
              />
              <circle
                cx="18"
                cy="25.5"
                r="1"
                className={isPending ? "fill-neutral-350" : "fill-eureka-primary/60"}
              />

              {/* Mini barra de búsqueda/URL */}
              <rect
                x="21"
                y="24"
                width="17"
                height="3"
                rx="1.5"
                className={isPending ? "fill-neutral-300" : "fill-eureka-primary/20"}
              />

              {/* Bloque de contenido Hero */}
              <rect
                x="12"
                y="33"
                width="26"
                height="10"
                rx="2"
                className={isPending ? "fill-neutral-300/80" : "fill-eureka-primary/15"}
              />

              {/* Línea de texto */}
              <line
                x1="12"
                y1="47"
                x2="26"
                y2="47"
                className={isPending ? "stroke-neutral-300" : "stroke-eureka-primary/40"}
                strokeWidth="1.5"
                strokeLinecap="round"
              />

              {/* Botón CTA Interactivo en Pantalla 1 */}
              <rect
                x="12"
                y="51"
                width="14"
                height="8"
                rx="2"
                className={cn(
                  "transition-colors duration-500",
                  isPending
                    ? "fill-neutral-350"
                    : isActive || isCompleted
                    ? "fill-eureka-primary"
                    : "fill-eureka-primary"
                )}
              />
            </g>

            {/* --- PANTALLA 2 (Interfaz Web Destino / Derecha) --- */}
            <g>
              {/* Marco de ventana de navegador */}
              <rect
                x="38"
                y="14"
                width="34"
                height="44"
                rx="4"
                className={cn(
                  "transition-colors duration-500",
                  isPending
                    ? "fill-neutral-100/90 stroke-neutral-300"
                    : isCompleted
                    ? "fill-eureka-primary/15 stroke-eureka-primary"
                    : "fill-white stroke-eureka-primary shadow-md shadow-indigo-500/10"
                )}
                strokeWidth="1.4"
              />

              {/* Barra superior de ventana */}
              <line
                x1="38"
                y1="21"
                x2="72"
                y2="21"
                className={cn(
                  "transition-colors duration-500",
                  isPending ? "stroke-neutral-300" : "stroke-eureka-primary/40"
                )}
                strokeWidth="1"
              />

              {/* 3 puntos de control de ventana */}
              <circle
                cx="42"
                cy="17.5"
                r="1"
                className={isPending ? "fill-neutral-350" : "fill-eureka-primary/60"}
              />
              <circle
                cx="45"
                cy="17.5"
                r="1"
                className={isPending ? "fill-neutral-350" : "fill-eureka-primary/60"}
              />
              <circle
                cx="48"
                cy="17.5"
                r="1"
                className={isPending ? "fill-neutral-350" : "fill-eureka-primary/60"}
              />

              {/* Mini barra de búsqueda/URL */}
              <rect
                x="51"
                y="16"
                width="17"
                height="3"
                rx="1.5"
                className={isPending ? "fill-neutral-300" : "fill-eureka-primary/20"}
              />

              {/* Encabezado / Banner en Pantalla 2 */}
              <rect
                x="42"
                y="25"
                width="26"
                height="6"
                rx="1.5"
                className={isPending ? "fill-neutral-300/80" : "fill-eureka-primary/20"}
              />

              {/* Grid de Cards de navegación */}
              <rect
                x="42"
                y="34"
                width="12"
                height="16"
                rx="2"
                className={cn(
                  "transition-colors duration-500",
                  isPending
                    ? "fill-neutral-300/60 stroke-neutral-300"
                    : isActive || isCompleted
                    ? "fill-eureka-primary/20 stroke-eureka-primary"
                    : "fill-eureka-primary/10 stroke-eureka-primary/40"
                )}
                strokeWidth="1"
              />
              <rect
                x="56"
                y="34"
                width="12"
                height="16"
                rx="2"
                className={isPending ? "fill-neutral-300/50" : "fill-eureka-primary/10"}
              />
            </g>

            {/* --- TRAZA / CURVA DE NAVEGACIÓN ENTRE INTERFACES --- */}
            <path
              d="M 19 55 C 32 55, 30 42, 48 42"
              className={cn(
                "transition-colors duration-500",
                isPending && "stroke-neutral-300 stroke-[1.5] stroke-dashed",
                isActive && "stroke-eureka-primary stroke-[2] animate-pipeline-tracer",
                isCompleted && "stroke-eureka-primary stroke-[2]"
              )}
              strokeDasharray={isPending ? "2 2" : undefined}
            />

            {/* Círculo de origen en CTA */}
            <circle
              cx="19"
              cy="55"
              r="2.5"
              className={isPending ? "fill-neutral-400" : "fill-eureka-primary"}
            />

            {/* Círculo de destino en Card de Pantalla 2 */}
            <circle
              cx="48"
              cy="42"
              r="2.5"
              className={isPending ? "fill-neutral-400" : "fill-eureka-primary"}
            />
          </svg>

          {/* Ondas de Click y Cursor Animado cuando está activo */}
          {isActive && (
            <>
              {/* Onda de click en Pantalla 1 (CTA) */}
              <div
                className="absolute w-4 h-4 rounded-full bg-eureka-primary/40 animate-web-click-1 -translate-x-1/2 -translate-y-1/2 pointer-events-none"
                style={{ top: "68.7%", left: "23.7%" }}
              />

              {/* Onda de click en Pantalla 2 (Card de llegada) */}
              <div
                className="absolute w-4 h-4 rounded-full bg-eureka-primary/40 animate-web-click-2 -translate-x-1/2 -translate-y-1/2 pointer-events-none"
                style={{ top: "52.5%", left: "60%" }}
              />

              {/* Cursor de ratón animado navegando a través de las pantallas */}
              <div
                className="absolute top-0 left-0 w-3.5 h-3.5 text-eureka-primary animate-web-cursor pointer-events-none z-30 filter drop-shadow-[0_1px_3px_rgba(82,86,232,0.6)]"
              >
                <svg
                  viewBox="0 0 24 24"
                  fill="currentColor"
                  stroke="#FFFFFF"
                  strokeWidth="1.5"
                  className="w-full h-full"
                >
                  <path d="M 3 3 L 10 21 L 13 14 L 20 11 Z" />
                </svg>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
