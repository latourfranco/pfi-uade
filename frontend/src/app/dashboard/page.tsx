"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { cn } from "@/lib/utils";
import { DashboardIntro } from "@/components/dashboard/dashboard-intro";
import { DashboardView } from "@/components/dashboard/dashboard-view";

type TransitionPhase = "entering" | "visible" | "exiting" | "dashboard";

// 3s por etapa (4 etapas = 12s total)
const STAGE_DURATION_MS = 3000;
const HEADLINE_DURATION_MS = 1500;
const EXIT_TRANSITION_MS = 600;

function DashboardContent() {
  const searchParams = useSearchParams();
  const shouldShowIntro =
    searchParams.get("onboarding") === "true" ||
    searchParams.get("intro") === "true";

  const [phase, setPhase] = useState<TransitionPhase>(() =>
    shouldShowIntro ? "entering" : "dashboard"
  );

  useEffect(() => {
    if (!shouldShowIntro) return;

    // Entrada suave inicial
    const enterTimer = setTimeout(() => {
      setPhase("visible");
    }, 40);

    return () => clearTimeout(enterTimer);
  }, [shouldShowIntro]);

  const handleComplete = useCallback(() => {
    setPhase("exiting");
    setTimeout(() => {
      setPhase("dashboard");
      // Remueve el query param de la barra de direcciones sin recargar la página
      window.history.replaceState(null, "", "/dashboard");
    }, EXIT_TRANSITION_MS);
  }, []);

  return (
    <div className="w-full min-h-screen bg-[#FAF9F5] relative">
      {phase !== "dashboard" ? (
        <div
          className={cn(
            "fixed inset-0 overflow-hidden z-50 transition-all duration-700 ease-in-out",
            phase === "visible" && "opacity-100 scale-100 filter-none",
            phase === "exiting" && "opacity-0 -translate-y-2 blur-[2px] pointer-events-none scale-[0.99]",
            phase === "entering" && "opacity-0 translate-y-2 scale-[0.99]"
          )}
        >
          <DashboardIntro
            stageDurationMs={STAGE_DURATION_MS}
            headlineDurationMs={HEADLINE_DURATION_MS}
            onComplete={handleComplete}
          />
        </div>
      ) : (
        <div className="w-full min-h-screen">
          <DashboardView />
        </div>
      )}
    </div>
  );
}

export default function DashboardPage() {
  return (
    <Suspense fallback={<div className="w-full min-h-screen bg-[#FAF9F5]" />}>
      <DashboardContent />
    </Suspense>
  );
}
