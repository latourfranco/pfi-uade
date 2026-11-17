"use client";

interface RadarEventNodeProps {
  label: string;
}

export function RadarEventNode({ label }: RadarEventNodeProps) {
  return (
    <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-20 flex flex-col items-center pointer-events-none transition-all duration-500 ease-out">
      {/* Punto Azul con Halo de Luz */}
      <div className="relative flex items-center justify-center mb-2">
        {/* Halo suave con pulso */}
        <div className="w-7 h-7 rounded-full bg-eureka-primary/25 blur-xs absolute animate-halo-pulse" />
        {/* Punto azul central */}
        <div className="w-3.5 h-3.5 rounded-full bg-eureka-primary shadow-[0_0_10px_rgba(82,86,232,0.85)] relative z-10" />
      </div>

      {/* Tarjeta Pastilla: Nombre de Evento */}
      <div className="bg-white backdrop-blur-xs border border-eureka-primary/60 rounded-[14px] px-4 py-1.5 shadow-[0_2px_10px_rgba(82,86,232,0.06)] flex flex-col items-center justify-center text-center pointer-events-auto">
        <span className="text-[11px] font-bold font-mono tracking-[0.14em] text-eureka-primary uppercase leading-tight">
          {label}
        </span>
      </div>
    </div>
  );
}
