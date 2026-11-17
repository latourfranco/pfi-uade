"use client";

export function RadarEmptyState() {
  return (
    <div className="relative z-10 flex flex-col items-center text-center max-w-sm px-4 animate-in fade-in duration-300 pointer-events-none">
      {/* Ícono de Radar / Sonar en círculo con halo */}
      <div className="relative flex items-center justify-center mb-5">
        {/* Ondas expansivas de sonar lentas y continuas */}
        <div
          className="w-12 h-12 rounded-full bg-eureka-primary/25 absolute pointer-events-none"
          style={{ animation: "sonarPulseSlow 3.6s cubic-bezier(0.16, 1, 0.3, 1) infinite" }}
        />
        <div
          className="w-12 h-12 rounded-full bg-eureka-primary/20 absolute pointer-events-none"
          style={{ animation: "sonarPulseSlow 3.6s cubic-bezier(0.16, 1, 0.3, 1) infinite 1.8s" }}
        />
        <div
          className="w-12 h-12 rounded-full bg-eureka-primary/15 flex items-center justify-center relative z-10"
          style={{ animation: "sonarCoreGlow 3.6s ease-in-out infinite" }}
        >
          {/* Ícono de Sonar / Diana */}
          <svg
            viewBox="0 0 32 32"
            className="w-7 h-7 text-eureka-primary"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <circle
              cx="16"
              cy="16"
              r="13"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeDasharray="3 3"
              opacity="0.6"
            />
            <circle
              cx="16"
              cy="16"
              r="8.5"
              stroke="currentColor"
              strokeWidth="1.75"
            />
            <circle
              cx="16"
              cy="16"
              r="3.5"
              stroke="currentColor"
              strokeWidth="1.75"
              fill="currentColor"
              fillOpacity="0.3"
            />
            <path
              d="M16 3V7M16 25V29M3 16H7M25 16H29"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
        </div>
      </div>

      {/* Texto de instrucción */}
      <p className="text-xs sm:text-sm text-neutral-600 font-normal leading-relaxed">
        Seleccioná un <span className="font-bold text-eureka-primary">flujo clave</span> para descubrir sus focos de{" "}
        <span className="font-bold text-eureka-primary">fricción</span>.
      </p>
    </div>
  );
}
