"use client";

import { useState, useEffect, useCallback } from "react";
import { cn } from "@/lib/utils";
import { EurekaLogo } from "@/components/brand/eureka-logo";
import { DashboardProcessingPipeline } from "./processing-pipeline/dashboard-processing-pipeline";

interface DashboardIntroProps {
  stageDurationMs?: number;
  headlineDurationMs?: number;
  onComplete?: () => void;
}

export function DashboardIntro({
  stageDurationMs = 2000,
  headlineDurationMs = 1500,
  onComplete,
}: DashboardIntroProps) {
  // Subfase interna: "pipeline" | "transitioning" | "headline"
  const [introStep, setIntroStep] = useState<"pipeline" | "transitioning" | "headline">("pipeline");

  const handlePipelineComplete = useCallback(() => {
    // 1. Desvanece suavemente el pipeline
    setIntroStep("transitioning");

    // 2. Muestra el gran titular con animación de entrada
    setTimeout(() => {
      setIntroStep("headline");
    }, 350);
  }, []);

  useEffect(() => {
    if (introStep !== "headline") return;

    // Duración de permanencia del titular antes de salir al dashboard
    const finishTimer = setTimeout(() => {
      onComplete?.();
    }, headlineDurationMs);

    return () => {
      clearTimeout(finishTimer);
    };
  }, [introStep, headlineDurationMs, onComplete]);

  return (
    <div className="h-dvh w-full bg-[#FAF9F5] flex flex-col justify-between p-6 sm:p-10 md:p-12 lg:p-14 relative overflow-y-auto selection:bg-eureka-primary/20 selection:text-[#4F46E5]">
      {/* Background subtle warm radial glow */}
      <div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-200 h-200 bg-linear-to-br from-eureka-cream/70 via-transparent to-transparent rounded-full pointer-events-none blur-3xl -z-10"
        aria-hidden="true"
      />

      {/* Header con Logo */}
      <header className="w-full max-w-6xl mx-auto">
        <EurekaLogo size="md" />
      </header>

      {/* Contenido Central */}
      <main className="w-full max-w-5xl mx-auto flex flex-col items-center justify-center my-auto py-6">
        {introStep === "pipeline" || introStep === "transitioning" ? (
          <div
            className={cn(
              "w-full transition-all duration-350 ease-out",
              introStep === "transitioning"
                ? "opacity-0 -translate-y-2 blur-[2px] scale-[0.99] pointer-events-none"
                : "opacity-100 translate-y-0 filter-none scale-100"
            )}
          >
            <DashboardProcessingPipeline
              stageDurationMs={stageDurationMs}
              onComplete={handlePipelineComplete}
            />
          </div>
        ) : (
          <div className="w-full max-w-4xl flex flex-col items-center text-center animate-headline-enter">
            {/* Titular Principal de Impacto */}
            <h1 className="text-4xl sm:text-6xl md:text-7xl lg:text-[76px] font-bold text-eureka-dark tracking-tight leading-[1.06] max-w-3xl">
              Descubrí lo que
              <br />
              tus usuarios no
              <br />
              pueden decirte
            </h1>
          </div>
        )}
      </main>

      {/* Footer balanceador */}
      <footer className="w-full h-4" />
    </div>
  );
}
