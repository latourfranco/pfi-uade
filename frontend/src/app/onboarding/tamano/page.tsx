"use client";

import { useState, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { EurekaLogo } from "@/components/brand/eureka-logo";
import { OnboardingProgressBar } from "@/components/onboarding/onboarding-progress-bar";
import { TamanoPyramidGraphic } from "@/components/onboarding/tamano-pyramid-graphic";
import { cn } from "@/lib/utils";

const TAMANO_OPTIONS = ["1-49", "50-249", "250-999", "+1000"];

function TamanoContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const rubroParam = searchParams.get("rubro") || "E-commerce";
  const tamanoParam = searchParams.get("tamano");

  const [selectedTamano, setSelectedTamano] = useState<string>(() => {
    if (tamanoParam && TAMANO_OPTIONS.includes(tamanoParam)) {
      return tamanoParam;
    }
    return "1-49";
  });

  const handleSelect = (option: string) => {
    setSelectedTamano(option);
  };

  const handleNext = () => {
    if (typeof window !== "undefined") {
      sessionStorage.setItem("eureka_onboarding_tamano", selectedTamano);
      localStorage.setItem("eureka_onboarding_tamano", selectedTamano);
    }

    router.push(
      `/onboarding/interfaz?rubro=${encodeURIComponent(
        rubroParam
      )}&tamano=${encodeURIComponent(selectedTamano)}`
    );
  };

  return (
    <div className="min-h-screen w-full flex flex-col lg:flex-row bg-white">
      {/* Columna Izquierda: Información y Selección */}
      <div className="w-full lg:w-1/2 min-h-screen flex flex-col justify-between p-8 sm:p-12 md:p-14 lg:p-16 xl:p-20 bg-white">
        {/* Header fijo superior con Logo y Barra de Progreso */}
        <header className="w-full shrink-0">
          <EurekaLogo size="md" />
          <div className="mt-7 sm:mt-8">
            <OnboardingProgressBar currentStep={2} totalSteps={4} />
          </div>
        </header>

        {/* Contenido Principal */}
        <main className="w-full max-w-xl my-auto py-8">
          <div className="mb-4">
            <Link
              href={`/onboarding/rubro?rubro=${encodeURIComponent(rubroParam)}`}
              className="inline-flex items-center gap-1.5 text-sm font-medium text-eureka-primary hover:text-eureka-brand transition-colors duration-150 group"
            >
              <ArrowLeft className="w-3.5 h-3.5 transition-transform duration-200 ease-out group-hover:-translate-x-1" />
              <span>Volver</span>
            </Link>
          </div>

          {/* Título Principal */}
          <h1 className="text-4xl sm:text-5xl font-bold text-neutral-950 tracking-tight leading-[1.12] mb-4 font-heading">
            ¿Cuántas personas{" "}
            <br className="hidden sm:inline" />
            trabajan con vos?
          </h1>

          {/* Bajada explicativa */}
          <p className="text-sm sm:text-base text-neutral-600 leading-relaxed max-w-md sm:max-w-lg mb-8 sm:mb-9">
            Define el volumen de datos que esperamos y cuánto detalle técnico
            incluimos en cada reporte.
          </p>

          {/* Opciones de Tamaño (Pills) */}
          <div
            className="flex flex-wrap gap-2.5 sm:gap-3 mb-6"
            role="radiogroup"
            aria-label="Selección de tamaño de equipo"
          >
            {TAMANO_OPTIONS.map((option) => {
              const isSelected = selectedTamano === option;
              return (
                <button
                  key={option}
                  type="button"
                  role="radio"
                  aria-checked={isSelected}
                  onClick={() => handleSelect(option)}
                  className={cn(
                    "px-5 sm:px-6 py-2.5 sm:py-3 rounded-full text-sm sm:text-base font-medium transition-all duration-200 cursor-pointer select-none border",
                    "focus:outline-none focus-visible:ring-2 focus-visible:ring-eureka-primary/40 focus-visible:ring-offset-2",
                    isSelected
                      ? "bg-eureka-dark text-white border-eureka-dark shadow-xs"
                      : "bg-white text-neutral-800 border-neutral-300 hover:border-neutral-400 hover:bg-neutral-50/80"
                  )}
                >
                  {option}
                </button>
              );
            })}
          </div>

          {/* Botón de Acción Avanzar */}
          <div className="mt-8 sm:mt-10">
            <button
              type="button"
              onClick={handleNext}
              disabled={!selectedTamano}
              className="group relative inline-flex items-center justify-center gap-2.5 px-8 py-3.5 rounded-xl bg-eureka-primary hover:bg-eureka-primary/90 text-white font-medium text-sm sm:text-base shadow-[0_4px_16px_rgba(82,86,232,0.35)] hover:shadow-[0_8px_24px_rgba(82,86,232,0.45)] hover:-translate-y-0.5 active:translate-y-0 active:scale-[0.98] transition-all duration-300 ease-out cursor-pointer overflow-hidden disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {/* Efecto de brillo / shimmer dinámico */}
              <div
                className="absolute inset-0 -translate-x-full group-hover:translate-x-full transition-transform duration-700 ease-out pointer-events-none"
                style={{
                  background:
                    "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.28) 50%, transparent 100%)",
                }}
              />

              <span className="relative z-10 font-medium">Avanzar</span>
              <ArrowRight className="relative z-10 w-4 h-4 transition-transform duration-300 ease-out group-hover:translate-x-1" />
            </button>
          </div>
        </main>

        {/* Footer vacío para mantener balance visual */}
        <footer className="hidden lg:block h-4" />
      </div>

      {/* Columna Derecha: Fondo #EFEFE8 con Pirámide Invertida (oculta en mobile) */}
      <div className="hidden lg:flex lg:w-1/2 min-h-screen bg-eureka-cream items-center justify-center p-8 sm:p-12 relative overflow-hidden">
        <TamanoPyramidGraphic selectedTamano={selectedTamano} />
      </div>
    </div>
  );
}

export default function OnboardingTamanoPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-white" />}>
      <TamanoContent />
    </Suspense>
  );
}
