"use client";

import { cn } from "@/lib/utils";

interface AnalyticsConnectionGraphicProps {
  className?: string;
  isConnected?: boolean;
}

export function AnalyticsConnectionGraphic({
  className = "",
  isConnected = false,
}: AnalyticsConnectionGraphicProps) {
  return (
    <div
      className={cn(
        "relative flex items-center justify-center select-none",
        className
      )}
      aria-hidden="true"
    >
      <style>{`
        @keyframes streamPacketHorizontal {
          0% {
            left: 32%;
            opacity: 0;
            transform: scale(0.5);
          }
          20% {
            opacity: 1;
            transform: scale(1);
          }
          80% {
            opacity: 1;
            transform: scale(1);
          }
          100% {
            left: 68%;
            opacity: 0;
            transform: scale(0.5);
          }
        }

        @keyframes beaconGlow {
          0%, 100% {
            transform: scale(0.96);
            filter: drop-shadow(0 0 6px rgba(82, 86, 232, 0.45));
          }
          50% {
            transform: scale(1.08);
            filter: drop-shadow(0 0 14px rgba(82, 86, 232, 0.85));
          }
        }
      `}</style>

      {/* Escenario relativo 400x400 (misma escala y proporción que el radar) */}
      <div className="relative w-85 h-85 sm:w-100 sm:h-100 md:w-112.5 md:h-112.5">
        {/* Geometría vectorial estática con trazos finos #D6D6CC */}
        <svg
          viewBox="0 0 400 400"
          className="absolute inset-0 w-full h-full pointer-events-none z-0"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          {/* Eje central con segmento punteado sutil */}
          <line
            x1="70"
            y1="200"
            x2="330"
            y2="200"
            stroke="#D6D6CC"
            strokeWidth="1.2"
            strokeDasharray="3 3"
          />

          {/* --- NODO IZQUIERDO: Origen (Google Analytics 4) --- */}
          {/* Anillos concéntricos de origen */}
          <circle cx="120" cy="200" r="18" stroke="#D6D6CC" strokeWidth="1.2" />
          <circle cx="120" cy="200" r="38" stroke="#D6D6CC" strokeWidth="1.2" />
          <circle cx="120" cy="200" r="62" stroke="#D6D6CC" strokeWidth="1.2" />

          {/* --- NODO DERECHO: Destino (Eureka Friction Core) --- */}
          {/* Anillos concéntricos de destino */}
          <circle cx="280" cy="200" r="18" stroke="#D6D6CC" strokeWidth="1.2" />
          <circle cx="280" cy="200" r="38" stroke="#D6D6CC" strokeWidth="1.2" />
          <circle cx="280" cy="200" r="62" stroke="#D6D6CC" strokeWidth="1.2" />

          {/* --- UNIÓN CENTRAL: Gateway de enlace seguro --- */}
          <circle cx="200" cy="200" r="12" stroke="#D6D6CC" strokeWidth="1.2" />
          <circle
            cx="200"
            cy="200"
            r="28"
            stroke="#D6D6CC"
            strokeWidth="1"
            strokeDasharray="2 4"
          />
        </svg>

        {/* Núcleo Nodo Origen (Izquierda: 30%, 50%) */}
        <div className="absolute top-1/2 left-[30%] -translate-x-1/2 -translate-y-1/2 flex items-center justify-center pointer-events-none z-20">
          <div className="w-5 h-5 rounded-full bg-neutral-300/40 animate-ping absolute" />
          <div className="w-3.5 h-3.5 rounded-full bg-eureka-dark relative z-10" />
        </div>

        {/* Núcleo Nodo Destino (Derecha: 70%, 50%) */}
        <div className="absolute top-1/2 left-[70%] -translate-x-1/2 -translate-y-1/2 flex items-center justify-center pointer-events-none z-20">
          <div
            className={cn(
              "rounded-full animate-ping absolute",
              isConnected
                ? "w-9 h-9 bg-emerald-500/25"
                : "w-7 h-7 bg-eureka-primary/20"
            )}
            style={{ animationDuration: "2.8s" }}
          />
          <div
            className={cn(
              "w-3.5 h-3.5 rounded-full relative z-10 transition-colors duration-500",
              isConnected
                ? "bg-emerald-600 shadow-[0_0_14px_rgba(16,185,129,0.8)]"
                : "bg-eureka-primary"
            )}
            style={{ animation: "beaconGlow 3s ease-in-out infinite" }}
          />
        </div>

        {/* Nodo Pasarela Central (50%, 50%) */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 flex items-center justify-center pointer-events-none z-20">
          <div className="w-2 h-2 rounded-full bg-neutral-400" />
        </div>

        {/* Partícula de flujo de datos en el eje central */}
        <div
          className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none z-20 opacity-0"
          style={{
            animation:
              "streamPacketHorizontal 3s cubic-bezier(0.4, 0, 0.2, 1) infinite",
          }}
        >
          <div className="w-2.5 h-2.5 rounded-full bg-eureka-primary shadow-[0_0_12px_rgba(82,86,232,0.85)]" />
        </div>
      </div>
    </div>
  );
}
