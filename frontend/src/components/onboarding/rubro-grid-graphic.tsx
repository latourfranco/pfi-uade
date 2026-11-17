"use client";

import { useMemo } from "react";
import { cn } from "@/lib/utils";

interface RubroGridGraphicProps {
  selectedRubro?: string | null;
  className?: string;
}

// Mapa de baldosas coloreadas según el rubro seleccionado
const RUBRO_PATTERNS: Record<string, [number, number][]> = {
  // Centro clásico (coincide exactamente con el diseño inicial)
  "E-commerce": [
    [1, 1],
    [1, 2],
  ],
  // Flujo dinámico
  Fintech: [
    [0, 1],
    [1, 1],
    [1, 2],
    [2, 2],
  ],
  // Doble columna / solidez
  Banca: [
    [0, 1],
    [1, 1],
    [2, 1],
    [0, 2],
    [1, 2],
    [2, 2],
  ],
  // Alas / horizonte de vuelo
  Viajes: [
    [0, 1],
    [0, 2],
    [1, 0],
    [1, 1],
    [1, 2],
    [1, 3],
  ],
  // Símbolo de reproducción / multimedia
  Entretenimiento: [
    [0, 1],
    [1, 1],
    [2, 1],
    [1, 2],
  ],
  // Plataforma / stack en capas
  SaaS: [
    [0, 1],
    [0, 2],
    [1, 1],
    [1, 2],
    [2, 1],
    [2, 2],
  ],
  // Cruz central
  Salud: [
    [0, 1],
    [1, 0],
    [1, 1],
    [1, 2],
    [2, 1],
  ],
  // Bloque superior
  Educación: [
    [0, 1],
    [0, 2],
    [1, 1],
    [1, 2],
  ],
  // Marco protector / escudo
  Seguros: [
    [0, 1],
    [0, 2],
    [1, 0],
    [1, 1],
    [1, 2],
    [1, 3],
    [2, 1],
    [2, 2],
  ],
  // Traza de ruta y despacho
  Logística: [
    [0, 0],
    [1, 1],
    [1, 2],
    [2, 3],
  ],
  // Haz horizontal
  Otro: [
    [1, 0],
    [1, 1],
    [1, 2],
    [1, 3],
  ],
};

export function RubroGridGraphic({
  selectedRubro = "E-commerce",
  className = "",
}: RubroGridGraphicProps) {
  // Las baldosas coloreadas cambian únicamente cuando el usuario selecciona otro rubro
  const activeCells = useMemo(() => {
    if (!selectedRubro || !RUBRO_PATTERNS[selectedRubro]) {
      return RUBRO_PATTERNS["E-commerce"];
    }
    return RUBRO_PATTERNS[selectedRubro];
  }, [selectedRubro]);

  const isCellActive = (row: number, col: number) => {
    return activeCells.some(([r, c]) => r === row && c === col);
  };

  return (
    <div
      className={cn(
        "relative flex items-center justify-center select-none w-full",
        className
      )}
      aria-hidden="true"
    >
      {/* Grilla 4x3 de baldosas redondeadas con transición al cambiar de selección */}
      <div className="grid grid-cols-4 gap-3 sm:gap-4 md:gap-4.5 p-4">
        {[0, 1, 2].map((rowIndex) =>
          [0, 1, 2, 3].map((colIndex) => {
            const active = isCellActive(rowIndex, colIndex);
            return (
              <div
                key={`${rowIndex}-${colIndex}`}
                className={cn(
                  "w-13 h-13 sm:w-16 sm:h-16 md:w-20 md:h-20 lg:w-20 lg:h-20 xl:w-22 xl:h-22",
                  "rounded-2xl sm:rounded-[20px] md:rounded-[22px]",
                  "transition-all duration-700 ease-in-out transform",
                  active
                    ? "bg-[#787DF6] shadow-[0_6px_22px_rgba(120,125,246,0.4)] scale-[1.03]"
                    : "bg-white shadow-[0_1px_3px_rgba(0,0,0,0.03)] scale-100 hover:bg-white/95"
                )}
              />
            );
          })
        )}
      </div>
    </div>
  );
}
