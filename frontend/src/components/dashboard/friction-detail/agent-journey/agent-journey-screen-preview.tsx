"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { cn } from "@/lib/utils";
import type { AgentJourneyStep } from "@/lib/friction-data";
import { ZoomIn, X } from "lucide-react";
import { AgentJourneyAgentNote } from "./agent-journey-agent-note";

interface AgentJourneyScreenPreviewProps {
  steps: AgentJourneyStep[];
  selectedStepIndex: number;
  onSelectStep?: (index: number) => void;
  isMobile?: boolean;
}

function ScreenCaptureItem({
  step,
  onOpenFullscreen,
}: {
  step: AgentJourneyStep;
  onOpenFullscreen: () => void;
}) {
  const [imageError, setImageError] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);

  if (step.imageSrc && !imageError) {
    return (
      <div
        onClick={onOpenFullscreen}
        className="w-full h-full relative cursor-zoom-in group/capture"
        title="Clic para ver en pantalla completa"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={step.imageSrc}
          alt={step.caption || step.title}
          onLoad={() => setImageLoaded(true)}
          onError={() => setImageError(true)}
          className={cn(
            "w-full h-full object-cover object-top transition-all duration-500 group-hover/capture:scale-[1.01]",
            imageLoaded ? "opacity-100" : "opacity-0"
          )}
        />

        {/* Overlay sutil al hover indicando zoom */}
        <div className="absolute inset-0 bg-black/0 group-hover/capture:bg-black/10 transition-colors pointer-events-none flex items-center justify-center">
          <div className="opacity-0 group-hover/capture:opacity-100 transition-opacity bg-black/60 backdrop-blur-xs text-white text-xs px-3 py-1.5 rounded-full flex items-center gap-1.5 font-mono shadow-md">
            <ZoomIn className="w-3.5 h-3.5 text-white" />
            <span>Ver pantalla completa</span>
          </div>
        </div>

        {!imageLoaded && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#18191E]">
            <div className="z-10 flex flex-col items-center justify-center border border-dashed border-sky-400/60 bg-sky-950/25 text-sky-400 px-4 py-2 rounded-md font-mono text-xs tracking-tight select-none shadow-xs">
              <span>{step.captureName}</span>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div
      onClick={onOpenFullscreen}
      className="w-full h-full relative flex items-center justify-center cursor-zoom-in"
    >
      {/* Grilla sutil de fondo para sensación de canvas */}
      <div className="absolute inset-0 bg-[radial-gradient(#27272A_1px,transparent_1px)] bg-size-[16px_16px] opacity-40 pointer-events-none" />

      {/* Bounding Box Centrado con Identificador */}
      <div className="z-10 m-auto flex flex-col items-center justify-center border border-dashed border-sky-400/60 bg-sky-950/25 text-sky-400 px-4 py-2 rounded-md font-mono text-xs tracking-tight select-none shadow-xs">
        <span>{step.captureName}</span>
      </div>
    </div>
  );
}

export function AgentJourneyScreenPreview({
  steps,
  selectedStepIndex,
  onSelectStep,
  isMobile: propIsMobile,
}: AgentJourneyScreenPreviewProps) {
  const currentStep = steps[selectedStepIndex] || steps[0];
  const isMobile =
    propIsMobile ??
    (currentStep?.resolution?.includes("390") ||
      currentStep?.resolution?.includes("844") ||
      steps.some((s) => s.resolution?.includes("390")));

  const frameRef = useRef<HTMLDivElement | null>(null);
  const touchStartY = useRef<number | null>(null);
  const [isFullscreenOpen, setIsFullscreenOpen] = useState(false);

  const handleOpenFullscreen = useCallback(() => {
    setIsFullscreenOpen(true);
  }, []);

  const handleCloseFullscreen = useCallback(() => {
    setIsFullscreenOpen(false);
  }, []);

  // Bloquear el scroll del body cuando el modal de pantalla completa está abierto
  useEffect(() => {
    if (isFullscreenOpen) {
      document.body.style.overflow = "hidden";
      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === "Escape") {
          handleCloseFullscreen();
        }
      };
      window.addEventListener("keydown", handleKeyDown);
      return () => {
        document.body.style.overflow = "unset";
        window.removeEventListener("keydown", handleKeyDown);
      };
    } else {
      document.body.style.overflow = "unset";
    }
  }, [isFullscreenOpen, handleCloseFullscreen]);

  // Intercepción nativa y aislada del scroll sobre la ventana del navegador
  useEffect(() => {
    const el = frameRef.current;
    if (!el || !onSelectStep) return;

    let isCooldown = false;
    let accumulatedDelta = 0;
    let resetTimer: NodeJS.Timeout | null = null;
    const SCROLL_THRESHOLD = 50;
    const COOLDOWN_MS = 450;

    const handleWheel = (e: WheelEvent) => {
      if (isFullscreenOpen) return;

      e.preventDefault();

      if (isCooldown) return;

      accumulatedDelta += e.deltaY;

      if (resetTimer) clearTimeout(resetTimer);
      resetTimer = setTimeout(() => {
        accumulatedDelta = 0;
      }, 200);

      if (accumulatedDelta >= SCROLL_THRESHOLD) {
        if (selectedStepIndex < steps.length - 1) {
          isCooldown = true;
          accumulatedDelta = 0;
          onSelectStep(selectedStepIndex + 1);
          setTimeout(() => {
            isCooldown = false;
          }, COOLDOWN_MS);
        }
      } else if (accumulatedDelta <= -SCROLL_THRESHOLD) {
        if (selectedStepIndex > 0) {
          isCooldown = true;
          accumulatedDelta = 0;
          onSelectStep(selectedStepIndex - 1);
          setTimeout(() => {
            isCooldown = false;
          }, COOLDOWN_MS);
        }
      }
    };

    const handleTouchStart = (e: TouchEvent) => {
      touchStartY.current = e.touches[0].clientY;
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (isFullscreenOpen || touchStartY.current === null || isCooldown) return;
      const deltaY = touchStartY.current - e.touches[0].clientY;
      const TOUCH_THRESHOLD = 55;

      if (Math.abs(deltaY) > TOUCH_THRESHOLD) {
        e.preventDefault();
        if (deltaY > 0 && selectedStepIndex < steps.length - 1) {
          isCooldown = true;
          onSelectStep(selectedStepIndex + 1);
          touchStartY.current = null;
          setTimeout(() => {
            isCooldown = false;
          }, COOLDOWN_MS);
        } else if (deltaY < 0 && selectedStepIndex > 0) {
          isCooldown = true;
          onSelectStep(selectedStepIndex - 1);
          touchStartY.current = null;
          setTimeout(() => {
            isCooldown = false;
          }, COOLDOWN_MS);
        }
      }
    };

    el.addEventListener("wheel", handleWheel, { passive: false });
    el.addEventListener("touchstart", handleTouchStart, { passive: true });
    el.addEventListener("touchmove", handleTouchMove, { passive: false });

    return () => {
      el.removeEventListener("wheel", handleWheel);
      el.removeEventListener("touchstart", handleTouchStart);
      el.removeEventListener("touchmove", handleTouchMove);
    };
  }, [selectedStepIndex, steps.length, onSelectStep, isFullscreenOpen]);

  return (
    <>
      <div className="w-full flex flex-col items-center">
        {/* Marco de Pantalla / Ventana de Navegador */}
        <div
          ref={frameRef}
          className={cn(
            "bg-[#18191E] flex flex-col items-center justify-start relative overflow-hidden transition-all duration-300 group cursor-ns-resize",
            isMobile
              ? "w-full max-w-[315px] sm:max-w-[340px] md:max-w-[350px] aspect-[390/844] rounded-[2.5rem] border-[3px] border-neutral-300 sm:border-neutral-400 shadow-[0_12px_36px_rgba(0,0,0,0.12)] ring-1 ring-black/10"
              : "w-full aspect-16/10 min-h-80 sm:min-h-95 rounded-2xl border-2 border-neutral-300 shadow-[0_4px_24px_rgba(0,0,0,0.08)]"
          )}
        >
          {/* Barra superior de navegador adaptativa */}
          {isMobile ? (
            <div className="w-full bg-[#111216] px-3.5 pt-2 pb-1.5 border-b border-neutral-800/90 flex flex-col items-center z-30 text-[10px] font-mono text-neutral-400 select-none shrink-0 gap-1.5">
              {/* Notch / Dynamic Island sutil */}
              <div className="w-20 h-3.5 bg-black rounded-full flex items-center justify-center">
                <span className="w-1.5 h-1.5 rounded-full bg-neutral-900 inline-block mr-2" />
                <span className="w-2 h-2 rounded-full bg-[#0d0d0f] inline-block border border-neutral-800" />
              </div>

              {/* Fila URL móvil con botón de Zoom */}
              <div className="w-full flex items-center justify-between gap-1.5 px-0.5">
                <span className="text-[9px] font-mono text-neutral-500 tracking-tight shrink-0">
                  390×844
                </span>

                <div className="flex-1 min-w-0 max-w-[195px] bg-[#1A1B20] border border-neutral-700/50 rounded-full px-2.5 py-0.5 text-center truncate text-neutral-400 text-[10px] leading-tight">
                  {currentStep?.url || "https://your.merch.google/"}
                </div>

                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleOpenFullscreen();
                  }}
                  className="p-1 rounded text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors cursor-pointer shrink-0"
                  title="Ver captura en pantalla completa"
                  aria-label="Ver captura en pantalla completa"
                >
                  <ZoomIn className="size-3.5 text-neutral-300 hover:text-white" />
                </button>
              </div>
            </div>
          ) : (
            <div className="w-full bg-[#111216] px-3 py-1.5 border-b border-neutral-800 flex items-center justify-between z-30 text-[10px] font-mono text-neutral-400 select-none shrink-0 gap-2">
              <div className="flex items-center gap-1.5 w-14 shrink-0">
                <span className="w-2 h-2 rounded-full bg-red-500/70 inline-block" />
                <span className="w-2 h-2 rounded-full bg-amber-500/70 inline-block" />
                <span className="w-2 h-2 rounded-full bg-emerald-500/70 inline-block" />
              </div>

              {/* Barra de dirección URL con transición suave */}
              <div className="flex-1 min-w-0 max-w-xs sm:max-w-sm mx-auto bg-[#1A1B20] border border-neutral-700/50 rounded px-2.5 py-0.5 text-center truncate text-neutral-400 text-[10.5px] leading-tight transition-colors duration-300">
                {currentStep?.url || "https://your.merch.google/"}
              </div>

              {/* Botón de Zoom In / Pantalla Completa */}
              <div className="w-14 flex justify-end shrink-0">
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleOpenFullscreen();
                  }}
                  className="p-1 rounded text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors cursor-pointer flex items-center gap-1"
                  title="Ver captura en pantalla completa"
                  aria-label="Ver captura en pantalla completa"
                >
                  <ZoomIn className="size-3.5 text-neutral-300 hover:text-white" />
                </button>
              </div>
            </div>
          )}

          {/* Contenedor de Capturas Vertical */}
          <div className="w-full flex-1 relative overflow-hidden bg-[#18191E]">
            {steps.map((stepItem, index) => {
              const isCurrent = index === selectedStepIndex;
              const isPast = index < selectedStepIndex;
              const isFuture = index > selectedStepIndex;

              return (
                <div
                  key={stepItem.stepNumber}
                  className={cn(
                    "absolute inset-0 w-full h-full transition-all duration-700 ease-[cubic-bezier(0.16,1,0.3,1)] will-change-transform",
                    isCurrent && "translate-y-0 opacity-100 scale-100 z-10 pointer-events-auto",
                    isPast && "-translate-y-full opacity-0 scale-95 pointer-events-none z-0",
                    isFuture && "translate-y-full opacity-0 scale-95 pointer-events-none z-0"
                  )}
                >
                  <ScreenCaptureItem
                    step={stepItem}
                    onOpenFullscreen={handleOpenFullscreen}
                  />
                </div>
              );
            })}
          </div>

          {/* Barra de Inicio (Home Indicator) en móvil */}
          {isMobile && (
            <div className="w-full bg-[#111216] py-1.5 flex justify-center shrink-0 border-t border-neutral-800/40 z-20">
              <div className="w-24 h-1 bg-neutral-600/70 rounded-full" />
            </div>
          )}
        </div>
      </div>

      {/* Modal / Lightbox de Pantalla Completa con fondo color arena/crema (#FAF9F5) */}
      {isFullscreenOpen && (
        <div
          className="fixed inset-0 z-50 bg-[#FAF9F5]/95 backdrop-blur-md flex flex-col justify-between p-4 sm:p-8 animate-in fade-in duration-200 overflow-y-auto selection:bg-eureka-primary/20 selection:text-[#4F46E5]"
          onClick={handleCloseFullscreen}
        >
          {/* Header del Lightbox */}
          <div
            className="w-full max-w-7xl mx-auto flex items-center justify-between z-10 pb-4 gap-3 sm:gap-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex flex-col min-w-0 flex-1">
              <span
                className="text-sm font-mono text-eureka-primary font-bold tracking-wider uppercase md:text-base truncate block"
                title={`Paso ${selectedStepIndex + 1} de ${steps.length} · ${currentStep.title}`}
              >
                Paso {selectedStepIndex + 1} de {steps.length} · {currentStep.title}
              </span>
              <span
                className="text-xs sm:text-sm font-mono text-neutral-600 mt-0.5 truncate md:text-base block"
                title={currentStep.url}
              >
                {currentStep.url}
              </span>
            </div>

            <button
              type="button"
              onClick={handleCloseFullscreen}
              className="shrink-0 p-2 rounded-full bg-neutral-200/80 hover:bg-neutral-300/90 text-neutral-700 hover:text-neutral-900 border border-neutral-300/70 shadow-2xs transition-colors cursor-pointer"
              title="Cerrar (Esc)"
              aria-label="Cerrar pantalla completa"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Cuerpo Principal del Lightbox: Navegador Ampliado a la Izquierda + Nota del Agente a la Derecha */}
          <div
            className="w-full max-w-7xl mx-auto flex-1 grid grid-cols-1 lg:grid-cols-[1fr_360px] xl:grid-cols-[1fr_400px] gap-8 items-start justify-center py-2 sm:py-4 my-auto"
            onClick={handleCloseFullscreen}
          >
            {/* Columna Izquierda: Ventana de Navegador Ampliada con Borde Pronunciado y Sombra Completa */}
            <div
              className="w-full flex items-start justify-center p-1"
              onClick={handleCloseFullscreen}
            >
              {currentStep.imageSrc ? (
                <div
                  onClick={(e) => e.stopPropagation()}
                  className={cn(
                    "bg-[#18191E] border-2 border-neutral-300 shadow-[0_12px_40px_rgba(0,0,0,0.16)] flex flex-col overflow-hidden animate-in zoom-in-95 duration-200",
                    isMobile
                      ? "w-full max-w-[340px] sm:max-w-[365px] max-h-[82vh] aspect-[390/844] rounded-[2.5rem] border-[3px]"
                      : "w-full max-h-[78vh] rounded-2xl"
                  )}
                >
                  {/* Barra superior de navegador en modal */}
                  {isMobile ? (
                    <div className="w-full bg-[#111216] px-4 py-2 border-b border-neutral-800 flex items-center justify-between text-[11px] font-mono text-neutral-400 select-none shrink-0 gap-2">
                      <span className="text-[10px] text-neutral-500 font-mono">Mobile (390×844)</span>
                      <div className="flex-1 min-w-0 max-w-[200px] mx-auto bg-[#1A1B20] border border-neutral-700/50 rounded-full px-2.5 py-0.5 text-center truncate text-neutral-400 text-[10.5px] leading-tight">
                        {currentStep.url || "https://your.merch.google/"}
                      </div>
                    </div>
                  ) : (
                    <div className="w-full bg-[#111216] px-3.5 py-2 border-b border-neutral-800 flex items-center justify-between text-[11px] font-mono text-neutral-400 select-none shrink-0 gap-2">
                      <div className="flex items-center gap-1.5 w-14 shrink-0">
                        <span className="w-2.5 h-2.5 rounded-full bg-red-500/70 inline-block" />
                        <span className="w-2.5 h-2.5 rounded-full bg-amber-500/70 inline-block" />
                        <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/70 inline-block" />
                      </div>
                      <div className="flex-1 min-w-0 max-w-sm mx-auto bg-[#1A1B20] border border-neutral-700/50 rounded px-3 py-0.5 text-center truncate text-neutral-400 text-xs leading-tight">
                        {currentStep.url || "https://your.merch.google/"}
                      </div>
                      <div className="w-14 shrink-0" />
                    </div>
                  )}

                  {/* Imagen de la captura */}
                  <div className="flex-1 overflow-auto flex items-center justify-center bg-[#18191E]">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={currentStep.imageSrc}
                      alt={currentStep.caption || currentStep.title}
                      className={cn(
                        "select-none",
                        isMobile
                          ? "w-full h-full object-cover object-top"
                          : "max-w-full max-h-[70vh] object-contain object-top"
                      )}
                    />
                  </div>

                  {/* Barra Home indicator modal */}
                  {isMobile && (
                    <div className="w-full bg-[#111216] py-1.5 flex justify-center shrink-0 border-t border-neutral-800/40 z-20">
                      <div className="w-24 h-1 bg-neutral-600/70 rounded-full" />
                    </div>
                  )}
                </div>
              ) : (
                <div
                  onClick={(e) => e.stopPropagation()}
                  className={cn(
                    "w-full bg-[#18191E] border-2 border-dashed border-sky-400/60 flex items-center justify-center text-sky-400 font-mono text-sm p-8 shadow-[0_12px_40px_rgba(0,0,0,0.16)]",
                    isMobile
                      ? "max-w-[340px] aspect-[390/844] rounded-[2.5rem]"
                      : "max-w-3xl aspect-16/10 rounded-2xl"
                  )}
                >
                  <span>{currentStep.captureName}</span>
                </div>
              )}
            </div>

            {/* Columna Derecha: Tarjeta de Nota del Agente con Borde Pronunciado y Sombra Completa */}
            <div
              className="w-full max-w-md mx-auto self-start p-1"
              onClick={(e) => e.stopPropagation()}
            >
              <AgentJourneyAgentNote
                step={currentStep}
                className="border-2 border-neutral-300 shadow-[0_8px_30px_rgba(0,0,0,0.06)]"
              />
            </div>
          </div>

          {/* Footer del Lightbox */}
          <div
            className="w-full max-w-7xl mx-auto hidden md:flex items-center justify-center text-sm font-mono text-neutral-500 pt-4 md:text-base"
            onClick={(e) => e.stopPropagation()}
          >
            <span>Presioná Esc o hacé clic afuera para cerrar</span>
          </div>
        </div>
      )}
    </>
  );
}
