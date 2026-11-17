"use client";

import { cn } from "@/lib/utils";
import type { AudienceBreakdownCategory } from "@/lib/friction-data";

interface AudienceBreakdownCardProps {
  category: AudienceBreakdownCategory;
}

export function AudienceBreakdownCard({ category }: AudienceBreakdownCardProps) {
  const visibleItems = [...category.items]
    .filter((item) => item.percentage > 0)
    .sort((a, b) => b.percentage - a.percentage)
    .slice(0, 5);

  return (
    <div className="w-full bg-white rounded-2xl border border-neutral-200/70 p-5 sm:p-6 shadow-[0_2px_12px_rgba(0,0,0,0.02)] flex flex-col justify-start">
      {/* Título de Categoría en Formato Mono */}
      <span className="text-sm font-mono font-bold tracking-widest text-eureka-primary uppercase mb-4 select-none">
        {category.title}
      </span>

      {/* Lista de Items con Barra de Progreso */}
      <div className="flex flex-col space-y-3.5">
        {visibleItems.map((item, index) => {
          const isPrimary = index === 0;

          return (
            <div key={item.label} className="flex flex-col">
              {/* Fila con Nombre y Porcentaje */}
              <div className="flex items-center justify-between text-xs sm:text-sm mb-1.5 leading-none">
                <span className="font-bold text-neutral-900 select-none">
                  {item.label}
                </span>
                <span className="font-mono font-medium text-xs sm:text-sm text-neutral-600 select-none">
                  {item.percentage}%
                </span>
              </div>

              {/* Barra de Progreso */}
              <div className="w-full h-1 bg-neutral-200/80 rounded-full overflow-hidden">
                <div
                  className={cn(
                    "h-full rounded-full transition-all duration-500 ease-out",
                    isPrimary ? "bg-eureka-primary" : "bg-eureka-primary/50"
                  )}
                  style={{ width: `${Math.min(100, Math.max(0, item.percentage))}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
