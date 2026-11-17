"use client";

import { cn } from "@/lib/utils";

export function RadarListeningGraphic({ className = "" }: { className?: string }) {
  // Duración total de un giro completo de 360° (segundos)
  const SWEEP_DURATION = 6.5;

  return (
    <div
      className={cn("relative flex items-center justify-center select-none", className)}
      aria-hidden="true"
    >
      {/* Escenario de Radar (400x400 relativo) */}
      <div className="relative w-85 h-85 sm:w-100 sm:h-100 md:w-112.5 md:h-112.5">
        {/* 5 Anillos concéntricos estáticos */}
        <svg
          viewBox="0 0 400 400"
          className="absolute inset-0 w-full h-full pointer-events-none z-0"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <circle cx="200" cy="200" r="26" stroke="#D6D6CC" strokeWidth="1.2" />
          <circle cx="200" cy="200" r="54" stroke="#D6D6CC" strokeWidth="1.2" />
          <circle cx="200" cy="200" r="88" stroke="#D6D6CC" strokeWidth="1.2" />
          <circle cx="200" cy="200" r="124" stroke="#D6D6CC" strokeWidth="1.2" />
          <circle cx="200" cy="200" r="164" stroke="#D6D6CC" strokeWidth="1.2" />
        </svg>

        {/* Haz de barrido rotatorio (conic-gradient + aguja a las 12 en punto) */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-10">
          <div
            className="w-82 h-82 sm:w-96.5 sm:h-96.5 md:w-107 md:h-107 rounded-full"
            style={{
              animation: `radarMasterSweep ${SWEEP_DURATION}s linear infinite`,
              background:
                "conic-gradient(from -75deg at 50% 50%, rgba(129, 140, 248, 0) 0deg, rgba(129, 140, 248, 0.02) 20deg, rgba(129, 140, 248, 0.1) 48deg, rgba(129, 140, 248, 0.28) 75deg, transparent 75.2deg)",
            }}
          >
            {/* Aguja frontal del radar: ubicada exactamente a 0° (arriba / 12 en punto) */}
            <div
              className="absolute top-0 left-1/2 w-[1.5px] h-1/2 bg-eureka-primary origin-bottom transform -translate-x-1/2 opacity-90 shadow-[0_0_8px_rgba(129,140,248,0.7)]"
            />
          </div>
        </div>

        {/* Punto Central (Estación de escucha constante) */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 flex items-center justify-center pointer-events-none z-20">
          <div className="w-6 h-6 rounded-full bg-eureka-primary/25 animate-pulse absolute" />
          <div className="w-3.5 h-3.5 rounded-full bg-eureka-dark relative z-10" />
        </div>

        {/* --- DOT 1: Arriba-Derecha (theta = 58°, r = 142px -> top: 31.2%, left: 80.1%) --- */}
        <div
          className="absolute -translate-x-1/2 -translate-y-1/2 flex items-center justify-center pointer-events-none z-20"
          style={{ top: "31.2%", left: "80.1%" }}
        >
          {/* Onda Ping */}
          <div
            className="w-4 h-4 rounded-full bg-eureka-dark absolute"
            style={{
              animation: `dot1PingAnim ${SWEEP_DURATION}s linear infinite`,
            }}
          />
          {/* Punto Núcleo con desvanecimiento fosforescente */}
          <div
            className="w-3 h-3 rounded-full bg-eureka-dark relative z-10"
            style={{
              animation: `dot1PhosphorAnim ${SWEEP_DURATION}s ease-out infinite`,
            }}
          />
        </div>

        {/* --- DOT 2: Abajo-Derecha (theta = 135°, r = 88px -> top: 65.6%, left: 65.6%) --- */}
        <div
          className="absolute -translate-x-1/2 -translate-y-1/2 flex items-center justify-center pointer-events-none z-20"
          style={{ top: "65.6%", left: "65.6%" }}
        >
          {/* Onda Ping */}
          <div
            className="w-4 h-4 rounded-full bg-eureka-primary absolute"
            style={{
              animation: `dot2PingAnim ${SWEEP_DURATION}s linear infinite`,
            }}
          />
          {/* Punto Núcleo con halo integrado y desvanecimiento */}
          <div
            className="w-2.5 h-2.5 rounded-full bg-eureka-primary shadow-[0_0_12px_rgba(129,140,248,0.7)] relative z-10"
            style={{
              animation: `dot2PhosphorAnim ${SWEEP_DURATION}s ease-out infinite`,
            }}
          />
        </div>

        {/* --- DOT 3: Abajo-Izquierda (theta = 215°, r = 124px -> top: 75.4%, left: 32.2%) --- */}
        <div
          className="absolute -translate-x-1/2 -translate-y-1/2 flex items-center justify-center pointer-events-none z-20"
          style={{ top: "75.4%", left: "32.2%" }}
        >
          {/* Onda Ping */}
          <div
            className="w-4 h-4 rounded-full bg-eureka-dark absolute"
            style={{
              animation: `dot3PingAnim ${SWEEP_DURATION}s linear infinite`,
            }}
          />
          {/* Punto Núcleo */}
          <div
            className="w-2.5 h-2.5 rounded-full bg-eureka-dark relative z-10"
            style={{
              animation: `dot3PhosphorAnim ${SWEEP_DURATION}s ease-out infinite`,
            }}
          />
        </div>

        {/* --- DOT 4: Izquierda Principal (theta = 275°, r = 124px -> top: 47.3%, left: 19.1%) --- */}
        <div
          className="absolute -translate-x-1/2 -translate-y-1/2 flex items-center justify-center pointer-events-none z-20"
          style={{ top: "47.3%", left: "19.1%" }}
        >
          {/* Onda Ping */}
          <div
            className="w-5 h-5 rounded-full bg-eureka-primary absolute"
            style={{
              animation: `dot4PingAnim ${SWEEP_DURATION}s linear infinite`,
            }}
          />
          {/* Punto Núcleo con halo y desvanecimiento */}
          <div
            className="w-3.5 h-3.5 rounded-full bg-eureka-primary shadow-[0_0_16px_rgba(129,140,248,0.85)] relative z-10"
            style={{
              animation: `dot4PhosphorAnim ${SWEEP_DURATION}s ease-out infinite`,
            }}
          />
        </div>

        {/* --- DOT 5: Noroeste (theta = 325°, r = 96px -> top: 30.3%, left: 36.2%) --- */}
        <div
          className="absolute -translate-x-1/2 -translate-y-1/2 flex items-center justify-center pointer-events-none z-20"
          style={{ top: "30.3%", left: "36.2%" }}
        >
          {/* Onda Ping */}
          <div
            className="w-4 h-4 rounded-full bg-eureka-primary absolute"
            style={{
              animation: `dot5PingAnim ${SWEEP_DURATION}s linear infinite`,
            }}
          />
          {/* Punto Núcleo con halo y desvanecimiento */}
          <div
            className="w-2.5 h-2.5 rounded-full bg-eureka-primary shadow-[0_0_10px_rgba(129,140,248,0.7)] relative z-10"
            style={{
              animation: `dot5PhosphorAnim ${SWEEP_DURATION}s ease-out infinite`,
            }}
          />
        </div>
      </div>
    </div>
  );
}
