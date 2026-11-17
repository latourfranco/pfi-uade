"use client";

import { cn } from "@/lib/utils";
import type { AgentJourneyStep } from "@/lib/friction-data";

interface AgentJourneyTimelineProps {
  steps: AgentJourneyStep[];
  selectedStepIndex: number;
  onSelectStep: (index: number) => void;
}

export function AgentJourneyTimeline({
  steps,
  selectedStepIndex,
  onSelectStep,
}: AgentJourneyTimelineProps) {
  return (
    <div className="w-full flex flex-col select-none">
      {/* Encabezado de la línea temporal */}
      <span className="text-sm font-mono font-bold tracking-widest text-eureka-primary uppercase mb-6">
        Línea temporal · {steps.length} pasos
      </span>

      {/* Lista de pasos verticales */}
      <div className="relative flex flex-col space-y-6">
        {/* Línea vertical conectora */}
        <div className="absolute left-3.5 top-3.5 bottom-3.5 w-[1.5px] bg-neutral-200/90 -translate-x-1/2 pointer-events-none" />

        {steps.map((step, index) => {
          const isActive = selectedStepIndex === index;
          const isContext = step.enPatron === false;
          const isInPattern = step.enPatron === true;
          const isFrictionPoint = step.friccionDetectada === true;

          return (
            <button
              key={step.stepNumber}
              type="button"
              onClick={() => onSelectStep(index)}
              className={cn(
                "relative flex items-start gap-3.5 text-left group cursor-pointer focus:outline-none transition-all",
                isContext && !isActive && "opacity-65 hover:opacity-100"
              )}
            >
              {/* Círculo indicador de número */}
              <div
                className={cn(
                  "w-7 h-7 rounded-full flex items-center justify-center text-xs font-mono shrink-0 z-10 transition-all duration-200",
                  isActive
                    ? isFrictionPoint
                      ? "bg-red-600 text-white font-bold shadow-sm ring-4 ring-red-200 scale-105"
                      : isInPattern
                        ? "bg-red-500 text-white font-bold shadow-xs scale-105"
                        : "bg-neutral-700 text-white font-bold shadow-xs scale-105"
                    : isFrictionPoint
                      ? "bg-red-600 border-2 border-red-700 text-white font-bold shadow-xs ring-2 ring-red-200"
                      : isInPattern
                        ? "bg-red-50 border border-red-300 text-red-600 font-medium group-hover:border-red-400 group-hover:text-red-700"
                        : "bg-white border border-neutral-300 text-neutral-400 font-medium group-hover:border-neutral-400 group-hover:text-neutral-600"
                )}
              >
                {step.stepNumber}
              </div>

              {/* Textos del paso */}
              <div className="flex flex-col pt-0.5 min-w-0">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span
                    className={cn(
                      "text-sm sm:text-base transition-colors duration-150 leading-tight",
                      isActive
                        ? "font-bold text-neutral-900"
                        : "font-medium text-neutral-600 group-hover:text-neutral-900"
                    )}
                  >
                    {step.title}
                  </span>
                  {isFrictionPoint && (
                    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold bg-red-100 text-red-700 border border-red-200">
                      Fricción
                    </span>
                  )}
                  {isContext && (
                    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono text-neutral-500 bg-neutral-100 border border-neutral-200">
                      Contexto
                    </span>
                  )}
                </div>
                <span className="text-sm font-mono text-neutral-600 tracking-tight mt-0.5 truncate">
                  {step.eventoNombre || step.actionSubtitle}
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
