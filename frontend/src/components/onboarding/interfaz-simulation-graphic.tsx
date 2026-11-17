"use client";

import { MousePointer2, Lock } from "lucide-react";
import { cn } from "@/lib/utils";

interface InterfazSimulationGraphicProps {
  className?: string;
}

export function InterfazSimulationGraphic({
  className = "",
}: InterfazSimulationGraphicProps) {
  return (
    <div
      className={cn(
        "relative flex flex-col items-center justify-center select-none w-full max-w-md mx-auto p-4",
        className
      )}
      aria-hidden="true"
    >
      <style>{`
        @keyframes ripplePulse {
          0% {
            transform: scale(0.6);
            opacity: 0.8;
          }
          100% {
            transform: scale(2.2);
            opacity: 0;
          }
        }

        @keyframes cursorHover {
          0%, 100% {
            transform: translate(0, 0);
          }
          50% {
            transform: translate(10px, -12px);
          }
        }
      `}</style>

      {/* Ventana de Navegador */}
      <div className="relative w-full rounded-2xl bg-white border border-neutral-200/90 shadow-[0_16px_40px_rgba(0,0,0,0.06)] overflow-hidden">
        {/* Barra Superior del Navegador */}
        <div className="bg-neutral-50/90 border-b border-neutral-200/80 px-4 py-3 flex items-center gap-3">
          {/* Controles de Ventana (Mac Style) */}
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="w-2.5 h-2.5 rounded-full bg-[#FF5F56]/80" />
            <span className="w-2.5 h-2.5 rounded-full bg-[#FFBD2E]/80" />
            <span className="w-2.5 h-2.5 rounded-full bg-[#27C93F]/80" />
          </div>

          {/* Barra de URL del Navegador */}
          <div className="flex-1 flex items-center justify-center gap-2 px-3 py-1.5 rounded-lg bg-white border border-neutral-200/90 text-xs text-neutral-700 font-mono shadow-2xs">
            <Lock className="w-3 h-3 text-emerald-600 shrink-0" />
            <span className="truncate">https://your.merch.google</span>
          </div>
        </div>

        {/* Contenido Mockeado con Skeletons */}
        <div className="p-5 sm:p-6 bg-white relative">
          {/* Barra de Navegación Skeleton */}
          <div className="flex items-center justify-between pb-3.5 mb-5 border-b border-neutral-100">
            {/* Logo skeleton */}
            <div className="w-24 h-4 rounded-md bg-neutral-200/80 animate-pulse" />

            {/* Links de navegación skeleton */}
            <div className="flex items-center gap-2.5">
              <div className="w-12 h-3 rounded bg-neutral-200/60" />
              <div className="w-14 h-3 rounded bg-neutral-200/60" />
              <div className="w-5 h-5 rounded-md bg-neutral-200/60" />
            </div>
          </div>

          {/* Ficha de Interfaz / Producto Skeleton */}
          <div className="flex gap-4 sm:gap-5 items-start">
            {/* Placeholder de Imagen */}
            <div className="w-28 sm:w-32 h-32 sm:h-36 rounded-xl bg-gradient-to-br from-neutral-100 via-neutral-50 to-neutral-200/60 border border-neutral-200/80 flex items-center justify-center shrink-0">
              <div className="w-10 h-10 rounded-lg bg-neutral-200/70" />
            </div>

            {/* Skeletons de Labels y Botón */}
            <div className="flex-1 min-w-0 pt-0.5">
              {/* Título skeleton (2 líneas) */}
              <div className="w-full h-3.5 rounded-md bg-neutral-200/90 mb-2" />
              <div className="w-3/5 h-3 rounded-md bg-neutral-200/60 mb-3" />

              {/* Precio / Label secundario skeleton */}
              <div className="w-16 h-4 rounded-md bg-neutral-300/80 mb-3.5" />

              {/* Selector de opciones skeleton */}
              <div className="flex items-center gap-1.5 mb-4">
                <span className="w-6 h-6 rounded-md bg-neutral-100 border border-neutral-200/80" />
                <span className="w-6 h-6 rounded-md bg-eureka-primary/15 border border-eureka-primary/30" />
                <span className="w-6 h-6 rounded-md bg-neutral-100 border border-neutral-200/80" />
                <span className="w-6 h-6 rounded-md bg-neutral-100 border border-neutral-200/80" />
              </div>

              {/* Botón de Acción skeleton */}
              <div className="w-full h-8 rounded-lg bg-eureka-primary shadow-xs flex items-center justify-center">
                <div className="w-20 h-2.5 rounded bg-white/70" />
              </div>
            </div>
          </div>

          {/* Elemento de Cursor de Mouse Flotante */}
          <div
            className="absolute bottom-10 right-14 z-30 pointer-events-none"
            style={{ animation: "cursorHover 3.5s ease-in-out infinite" }}
          >
            <div className="relative">
              {/* Anillos de Radar sutiles */}
              <span
                className="absolute -top-3 -left-3 w-8 h-8 rounded-full bg-eureka-primary/25"
                style={{ animation: "ripplePulse 2s cubic-bezier(0, 0.2, 0.8, 1) infinite" }}
              />
              <span
                className="absolute -top-3 -left-3 w-8 h-8 rounded-full bg-eureka-primary/15"
                style={{
                  animation: "ripplePulse 2s cubic-bezier(0, 0.2, 0.8, 1) infinite",
                  animationDelay: "0.6s",
                }}
              />

              {/* Icono de Cursor */}
              <div className="relative z-10 text-eureka-primary">
                <MousePointer2 className="w-8 h-8 fill-white -rotate-12 translate-x-0.5 -translate-y-0.5" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
