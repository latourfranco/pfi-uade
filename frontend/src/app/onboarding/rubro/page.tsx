"use client";

import { useState, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { EurekaLogo } from "@/components/brand/eureka-logo";
import { OnboardingProgressBar } from "@/components/onboarding/onboarding-progress-bar";
import { RubroGridGraphic } from "@/components/onboarding/rubro-grid-graphic";
import { cn } from "@/lib/utils";

const RUBRO_OPTIONS = [
  "E-commerce",
  "Fintech",
  "Banca",
  "Viajes",
  "Entretenimiento",
  "SaaS",
  "Salud",
  "Educación",
  "Seguros",
  "Logística",
  "Otro",
];

function RubroContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const rubroParam = searchParams.get("rubro");

  const [selectedRubro, setSelectedRubro] = useState<string>(() => {
    if (!rubroParam) return "E-commerce";
    if (RUBRO_OPTIONS.includes(rubroParam)) return rubroParam;
    return "Otro";
  });

  const [customRubro, setCustomRubro] = useState<string>(() => {
    if (rubroParam && !RUBRO_OPTIONS.includes(rubroParam)) {
      return rubroParam;
    }
    return "";
  });

  const handleSelect = (option: string) => {
    setSelectedRubro(option);
  };

  const handleNext = () => {
    const finalRubro =
      selectedRubro === "Otro" && customRubro.trim()
        ? customRubro.trim()
        : selectedRubro;

    if (typeof window !== "undefined") {
      sessionStorage.setItem("eureka_onboarding_rubro", finalRubro);
      localStorage.setItem("eureka_onboarding_rubro", finalRubro);
    }

    router.push(`/onboarding/tamano?rubro=${encodeURIComponent(finalRubro)}`);
  };

  return (
    <div className="min-h-screen w-full flex flex-col lg:flex-row bg-white">
      {/* Columna Izquierda: Información y Selección */}
      <div className="w-full lg:w-1/2 min-h-screen flex flex-col justify-between p-8 sm:p-12 md:p-14 lg:p-16 xl:p-20 bg-white">
        {/* Header fijo superior con Logo y Barra de Progreso */}
        <header className="w-full shrink-0">
          <div className="flex items-center justify-between gap-4">
            <EurekaLogo size="md" />
            <Link
              href="/login"
              className="text-xs sm:text-sm font-medium text-neutral-500 hover:text-eureka-primary transition-colors"
            >
              ¿Ya tenés cuenta? Iniciar sesión
            </Link>
          </div>
          <div className="mt-7 sm:mt-8">
            <OnboardingProgressBar currentStep={1} totalSteps={4} />
          </div>
        </header>

        {/* Contenido Principal */}
        <main className="w-full max-w-xl my-auto py-8">
          {/* Título Principal */}
          <h1 className="text-4xl sm:text-5xl font-bold text-neutral-950 tracking-tight leading-[1.12] mb-4 font-heading">
            ¿A qué se dedica tu{" "}
            <br className="hidden sm:inline" />
            empresa?
          </h1>

          {/* Bajada explicativa */}
          <p className="text-sm sm:text-base text-neutral-600 leading-relaxed max-w-md sm:max-w-lg mb-8 sm:mb-9">
            Usamos el rubro para interpretar los flujos críticos y escribir los
            reportes en el vocabulario de tu negocio.
          </p>

          {/* Opciones de Rubros (Pills) */}
          <div
            className="flex flex-wrap gap-2.5 sm:gap-3 mb-6"
            role="radiogroup"
            aria-label="Selección de rubro de tu empresa"
          >
            {RUBRO_OPTIONS.map((option) => {
              const isSelected = selectedRubro === option;
              return (
                <button
                  key={option}
                  type="button"
                  role="radio"
                  aria-checked={isSelected}
                  onClick={() => handleSelect(option)}
                  className={cn(
                    "px-4.5 sm:px-5 py-2 sm:py-2.5 rounded-full text-sm sm:text-base font-medium transition-all duration-200 cursor-pointer select-none border",
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

          {/* Campo extra si seleccionó "Otro" */}
          {selectedRubro === "Otro" && (
            <div className="mb-6 animate-in fade-in slide-in-from-top-2 duration-300">
              <label
                htmlFor="custom-rubro-input"
                className="block text-xs sm:text-sm font-medium text-neutral-600 mb-1.5"
              >
                Especifica tu rubro
              </label>
              <input
                id="custom-rubro-input"
                type="text"
                value={customRubro}
                onChange={(e) => setCustomRubro(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && customRubro.trim()) {
                    e.preventDefault();
                    handleNext();
                  }
                }}
                placeholder="Ej. Logística, Inmobiliaria, SaaS..."
                className="w-full max-w-md px-4 py-2.5 rounded-xl border border-neutral-300 bg-white text-neutral-900 placeholder:text-neutral-400 text-sm focus:border-eureka-primary focus:ring-2 focus:ring-eureka-primary/20 outline-none transition-all"
                autoFocus
              />
            </div>
          )}

          {/* Botón de Acción Avanzar */}
          <div className="mt-8 sm:mt-10">
            <button
              type="button"
              onClick={handleNext}
              disabled={
                !selectedRubro ||
                (selectedRubro === "Otro" && !customRubro.trim())
              }
              className="group relative inline-flex items-center justify-center gap-2.5 px-8 py-3.5 rounded-xl bg-eureka-primary hover:bg-eureka-primary/90 text-white font-medium text-sm sm:text-base shadow-[0_4px_16px_rgba(82,86,232,0.35)] hover:shadow-[0_8px_24px_rgba(82,86,232,0.45)] hover:-translate-y-0.5 active:translate-y-0 active:scale-[0.98] transition-all duration-300 ease-out cursor-pointer overflow-hidden disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:translate-y-0 disabled:hover:shadow-[0_4px_16px_rgba(82,86,232,0.35)] disabled:active:scale-100"
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

      {/* Columna Derecha: Fondo #EFEFE8 con Gráfico de Grilla (oculto en mobile) */}
      <div className="hidden lg:flex lg:w-1/2 min-h-screen bg-eureka-cream items-center justify-center p-8 sm:p-12 relative overflow-hidden">
        <RubroGridGraphic selectedRubro={selectedRubro} />
      </div>
    </div>
  );
}

export default function OnboardingRubroPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-white" />}>
      <RubroContent />
    </Suspense>
  );
}
