"use client";

import { useMemo } from "react";
import { cn } from "@/lib/utils";

interface TamanoPyramidGraphicProps {
  selectedTamano?: string | null;
  className?: string;
}

// Mapeo de opción de tamaño a la fila activa de la pirámide invertida:
// Fila 0 (arriba de todo): 4 boxes -> +1000
// Fila 1 (siguiente): 3 boxes      -> 250-999
// Fila 2 (siguiente): 2 boxes      -> 50-249
// Fila 3 (abajo de todo): 1 box    -> 1-49
const TAMANO_ROW_MAP: Record<string, number> = {
  "+1000": 0,
  "250-999": 1,
  "50-249": 2,
  "1-49": 3,
};

// Estructura de la pirámide invertida: cantidad de boxes por fila (de arriba a abajo)
const PYRAMID_ROWS = [4, 3, 2, 1];

export function TamanoPyramidGraphic({
  selectedTamano = "1-49",
  className = "",
}: TamanoPyramidGraphicProps) {
  const activeRow = useMemo(() => {
    if (!selectedTamano || TAMANO_ROW_MAP[selectedTamano] === undefined) {
      return TAMANO_ROW_MAP["1-49"];
    }
    return TAMANO_ROW_MAP[selectedTamano];
  }, [selectedTamano]);

  return (
    <div
      className={cn(
        "relative flex items-center justify-center select-none w-full",
        className
      )}
      aria-hidden="true"
    >
      {/* Pirámide Invertida: 4 arriba, 3, 2, 1 abajo */}
      <div className="flex flex-col gap-3 sm:gap-4 md:gap-4.5 items-center p-4">
        {PYRAMID_ROWS.map((boxCount, rowIndex) => {
          const isRowActive = activeRow === rowIndex;
          return (
            <div
              key={rowIndex}
              className="flex justify-center gap-3 sm:gap-4 md:gap-4.5"
            >
              {Array.from({ length: boxCount }).map((_, boxIndex) => (
                <div
                  key={`${rowIndex}-${boxIndex}`}
                  className={cn(
                    "w-13 h-13 sm:w-16 sm:h-16 md:w-20 md:h-20 lg:w-20 lg:h-20 xl:w-22 xl:h-22",
                    "rounded-2xl sm:rounded-[20px] md:rounded-[22px]",
                    "transition-all duration-700 ease-in-out transform",
                    isRowActive
                      ? "bg-[#787DF6] shadow-[0_6px_22px_rgba(120,125,246,0.4)] scale-[1.03]"
                      : "bg-white shadow-[0_1px_3px_rgba(0,0,0,0.03)] scale-100 hover:bg-white/95"
                  )}
                />
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}
