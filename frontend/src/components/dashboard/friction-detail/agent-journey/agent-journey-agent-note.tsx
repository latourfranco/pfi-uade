"use client";

import { cn } from "@/lib/utils";
import type { AgentJourneyStep } from "@/lib/friction-data";

interface AgentJourneyAgentNoteProps {
  step: AgentJourneyStep;
  className?: string;
}

export function AgentJourneyAgentNote({ step, className }: AgentJourneyAgentNoteProps) {
  return (
    <div
      className={cn(
        "w-full bg-white rounded-2xl p-6 border border-neutral-300 shadow-[0_4px_20px_rgba(0,0,0,0.04)] flex flex-col justify-between min-h-70 transition-shadow",
        className
      )}
    >
      <div key={step.stepNumber} className="animate-in fade-in duration-300 slide-in-from-bottom-1">
        {/* Encabezado de la nota */}
        <div className="mb-3">
          <span className="text-sm font-mono font-bold tracking-widest text-eureka-primary uppercase select-none">
            {step.enPatron === false ? "Contexto del paso" : "Nota del agente"}
          </span>
        </div>

        {/* Título de la nota */}
        <h3 className="text-xl font-bold text-neutral-900 tracking-tight leading-snug mb-2.5">
          {step.noteTitle}
        </h3>

        {/* Descripción del agente */}
        <p className="text-sm md:text-base text-neutral-900 leading-relaxed mb-4 font-normal">
          {step.noteDescription}
        </p>

        {/* Insignias */}
        {step.badges && step.badges.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-4">
            {step.badges.map((badge, idx) => (
              <span
                key={`${badge}-${idx}`}
                className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-[#EEF2FF] text-eureka-primary border border-indigo-200/70"
              >
                {badge}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Metadatos Clave */}
      {(step.screenTime || step.clusterMatch || step.items || step.scroll !== undefined && step.scroll !== null) && (
        <div className="border-t border-neutral-200 pt-4 space-y-2.5">
          {step.screenTime && (
            <div className="flex items-center justify-between text-sm md:text-base">
              <span className="text-neutral-600">Tiempo en pantalla</span>
              <span className="font-mono font-bold text-eureka-primary">{step.screenTime}</span>
            </div>
          )}
          {step.clusterMatch && (
            <div className="flex items-center justify-between text-sm">
              <span className="text-neutral-600">Coincidencia cluster</span>
              <span className="font-mono font-semibold text-neutral-900 capitalize">
                {step.clusterMatch}
              </span>
            </div>
          )}
          {step.items && (
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="text-neutral-600 shrink-0">Producto / ítem</span>
              <span className="font-mono text-neutral-800 truncate">{step.items}</span>
            </div>
          )}
          {step.scroll !== undefined && step.scroll !== null && (
            <div className="flex items-center justify-between text-sm">
              <span className="text-neutral-600">Scroll completo</span>
              <span className="font-mono text-neutral-800">{step.scroll ? "Sí" : "No"}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
