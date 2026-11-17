"use client";

import { useState, useEffect, useCallback } from "react";
import { AgentJourneyTimeline } from "./agent-journey/agent-journey-timeline";
import { AgentJourneyScreenPreview } from "./agent-journey/agent-journey-screen-preview";
import { AgentJourneyAgentNote } from "./agent-journey/agent-journey-agent-note";
import type { FrictionDetail } from "@/lib/friction-data";
import { ChevronLeft, ChevronRight } from "lucide-react";

interface FrictionTabAgentJourneyProps {
  data: FrictionDetail;
}

export function FrictionTabAgentJourney({ data }: FrictionTabAgentJourneyProps) {
  const [selectedStepIndex, setSelectedStepIndex] = useState(0);

  const steps = data.agentJourney?.steps ?? [];
  const currentStep = steps[selectedStepIndex] || steps[0];

  const handleNext = useCallback(() => {
    setSelectedStepIndex((prev) => Math.min(steps.length - 1, prev + 1));
  }, [steps.length]);

  const handlePrev = useCallback(() => {
    setSelectedStepIndex((prev) => Math.max(0, prev - 1));
  }, []);

  // Navegación con teclado (Flechas Arriba / Abajo / Izquierda / Derecha)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignorar si el usuario está escribiendo en inputs
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }

      if (e.key === "ArrowDown" || e.key === "ArrowRight") {
        e.preventDefault();
        handleNext();
      } else if (e.key === "ArrowUp" || e.key === "ArrowLeft") {
        e.preventDefault();
        handlePrev();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleNext, handlePrev]);

  if (steps.length === 0 || !currentStep) {
    return (
      <div className="w-full bg-white rounded-2xl sm:rounded-[24px] border border-neutral-200/70 p-8 text-center text-neutral-500">
        No hay pasos registrados para esta fricción.
      </div>
    );
  }

  return (
    <div className="w-full relative pb-4 animate-in fade-in duration-300">
      {/* Grilla con mayor protagonismo al navegador central y reducción proporcional en laterales */}
      <div className="w-full grid grid-cols-1 lg:grid-cols-[250px_1fr_250px] xl:grid-cols-[270px_1fr_270px] gap-6 lg:gap-8 items-start">
        {/* Columna Izquierda: Línea Temporal de Pasos */}
        <div className="w-full">
          <AgentJourneyTimeline
            steps={steps}
            selectedStepIndex={selectedStepIndex}
            onSelectStep={setSelectedStepIndex}
          />
        </div>

        {/* Columna Central: Ventana de Navegador con Mayor Ancho (sticky para patrones largos) */}
        <div
          data-testid="agent-journey-sticky-preview"
          className="w-full flex flex-col items-center lg:sticky lg:top-6"
        >
          <AgentJourneyScreenPreview
            steps={steps}
            selectedStepIndex={selectedStepIndex}
            onSelectStep={setSelectedStepIndex}
            isMobile={
              data.tipoDispositivo === "mobile" ||
              steps.some((s) => s.resolution?.includes("390"))
            }
          />

          {/* Pastilla de Control de Pasos con Indicadores y Botones */}
          <div className="mt-3.5 inline-flex items-center gap-3 p-2 rounded-full bg-white border border-neutral-200 shadow-2xs text-xs font-mono text-neutral-600 select-none">
            <button
              type="button"
              onClick={handlePrev}
              disabled={selectedStepIndex === 0}
              className="p-1 rounded-full hover:bg-neutral-100 disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors"
              aria-label="Paso anterior"
            >
              <ChevronLeft className="size-5 text-neutral-700" />
            </button>

            {/* Puntos interactivos de paso */}
            <div className="flex items-center gap-1.5">
              {steps.map((_, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setSelectedStepIndex(idx)}
                  className={`h-1.5 rounded-full transition-all duration-300 cursor-pointer ${
                    idx === selectedStepIndex
                      ? "w-4 bg-eureka-primary"
                      : "w-1.5 bg-neutral-300 hover:bg-neutral-400"
                  }`}
                  aria-label={`Ir al paso ${idx + 1}`}
                />
              ))}
            </div>

            <span className="text-sm text-neutral-500 font-medium pl-0.5">
              Paso {selectedStepIndex + 1} de {steps.length}
            </span>

            <button
              type="button"
              onClick={handleNext}
              disabled={selectedStepIndex === steps.length - 1}
              className="p-1 rounded-full hover:bg-neutral-100 disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors"
              aria-label="Paso siguiente"
            >
              <ChevronRight className="size-5 text-neutral-700" />
            </button>
          </div>
        </div>

        {/* Columna Derecha: Tarjeta de Nota del Agente */}
        <div
          data-testid="agent-journey-sticky-note"
          className="w-full lg:sticky lg:top-6"
        >
          <AgentJourneyAgentNote step={currentStep} />
        </div>
      </div>
    </div>
  );
}
