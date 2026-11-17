"use client";

import { cn } from "@/lib/utils";

interface MetricItem {
  value: string;
  label: string;
}

export interface DashboardMetricsBarProps {
  frictionsCount?: number;
  sessionsAffected?: string;
  eventsCount?: number;
}

export function DashboardMetricsBar({
  frictionsCount = 0,
  sessionsAffected = "0",
  eventsCount = 0,
}: DashboardMetricsBarProps) {
  const metrics: MetricItem[] = [
    { value: `${frictionsCount}`, label: frictionsCount === 1 ? "fricción identificada" : "fricciones identificadas" },
    { value: sessionsAffected, label: "sesiones/mes afectadas" },
    { value: `${eventsCount}`, label: eventsCount === 1 ? "evento clave involucrado" : "eventos clave involucrados" },
  ];

  return (
    <div className="w-full bg-white/70 backdrop-blur-md border border-neutral-200/80 rounded-2xl p-3 sm:py-3.5 sm:px-6 grid grid-cols-1 sm:grid-cols-3 gap-2.5 sm:gap-0 items-center justify-center shadow-[0_1px_4px_rgba(0,0,0,0.02)]">
      {metrics.map((metric, idx) => (
        <div
          key={idx}
          className={cn(
            "flex items-center justify-center gap-2 px-2 py-1 sm:py-0",
            idx < metrics.length - 1 &&
              "border-b border-neutral-200/70 pb-2.5 sm:pb-0 sm:border-b-0 sm:border-r sm:border-neutral-200"
          )}
        >
          <span className="font-mono font-bold text-base sm:text-lg text-eureka-primary shrink-0">
            {metric.value}
          </span>
          <span className="font-mono font-medium text-xs sm:text-sm text-eureka-dark leading-tight">
            {metric.label}
          </span>
        </div>
      ))}
    </div>
  );
}
