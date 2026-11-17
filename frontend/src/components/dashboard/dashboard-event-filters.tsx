"use client";

import { cn } from "@/lib/utils";
import type { EventItem } from "@/lib/radar-constants";

export type { EventItem };

export interface DashboardEventFiltersProps {
  selectedEventId: string | null;
  onSelectEvent: (id: string | null) => void;
  events?: EventItem[];
}

export function DashboardEventFilters({
  selectedEventId,
  onSelectEvent,
  events = [],
}: DashboardEventFiltersProps) {
  const activeEvents = events;
  return (
    <div className="w-full bg-white/70 backdrop-blur-md border border-neutral-200/80 rounded-2xl px-4 py-2.5 flex items-center gap-3 sm:gap-4 flex-wrap shadow-[0_1px_4px_rgba(0,0,0,0.02)]">
      {/* Etiqueta Izquierda con Ícono */}
      <div className="flex items-center gap-2 pr-2 text-neutral-700">
        <svg
          viewBox="0 0 24 24"
          className="w-4 h-4 text-eureka-primary"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="10" strokeDasharray="3 3" opacity="0.6" />
          <circle cx="12" cy="12" r="6" />
          <circle cx="12" cy="12" r="2" fill="currentColor" />
          <path d="M12 2v2M12 20v2M2 12h2M20 12h2" opacity="0.5" />
        </svg>
        <span className="font-mono text-xs sm:text-sm font-semibold tracking-wider text-eureka-dark uppercase select-none">
          FLUJOS CLAVE
        </span>
      </div>

      {/* Chips de Flujos Clave */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        {activeEvents.length === 0 ? (
          <span className="text-xs sm:text-sm text-neutral-500">
            No hay flujos clave con fricciones detectadas todavía.
          </span>
        ) : (
          activeEvents.map((event) => {
            const isSelected = selectedEventId === event.id;
            return (
              <button
                key={event.id}
                type="button"
                onClick={() => onSelectEvent(isSelected ? null : event.id)}
                className={cn(
                  "group inline-flex items-center gap-2.5 px-3.5 py-1.5 rounded-full text-xs transition-all duration-200 cursor-pointer select-none border",
                  isSelected
                    ? "bg-[#EEF2FF] border-eureka-primary/50 text-eureka-primary shadow-xs shadow-indigo-500/10 font-semibold"
                    : !selectedEventId
                      ? "bg-[#EAEAF4]/80 hover:bg-[#EEF2FF]/80 border-eureka-primary/25 hover:border-eureka-primary/50 text-eureka-dark font-medium"
                      : "bg-[#EAEAF4]/80 hover:bg-[#E2E2F0] border-transparent text-eureka-dark font-medium"
                )}
              >
                <span className="relative flex items-center justify-center w-2 h-2 shrink-0">
                  {!selectedEventId && (
                    <span
                      data-testid="flow-chip-pulse"
                      className="absolute inline-flex h-full w-full rounded-full bg-eureka-primary/60 animate-ping"
                    />
                  )}
                  <span
                    className={cn(
                      "relative inline-flex w-1.5 h-1.5 rounded-full transition-colors",
                      isSelected || !selectedEventId
                        ? "bg-eureka-primary"
                        : "bg-neutral-400 group-hover:bg-neutral-600"
                    )}
                  />
                </span>
                <span className="text-xs sm:text-sm">{event.name}</span>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
