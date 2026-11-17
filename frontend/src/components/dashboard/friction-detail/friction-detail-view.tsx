"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { EurekaLogo } from "@/components/brand/eureka-logo";
import { FrictionDetailHeader } from "./friction-detail-header";
import { FrictionTabDiagnosis } from "./friction-tab-diagnosis";
import { FrictionTabAgentJourney } from "./friction-tab-agent-journey";
import { FrictionTabAudience } from "./friction-tab-audience";
import type { FrictionDetail } from "@/lib/friction-data";

export type FrictionTabType = "diagnostico" | "recorrido" | "quienes-son";

interface FrictionDetailViewProps {
  data: FrictionDetail;
  eventId?: string | null;
}

export function FrictionDetailView({ data, eventId }: FrictionDetailViewProps) {
  const [activeTab, setActiveTab] = useState<FrictionTabType>("recorrido");

  return (
    <div className="min-h-screen w-full bg-[#FAF9F5] flex flex-col p-6 sm:p-10 md:p-12 lg:p-14 selection:bg-eureka-primary/20 selection:text-[#4F46E5] animate-in fade-in duration-500 ease-out">
      {/* Header con Logo Eureka */}
      <header className="w-full max-w-7xl mx-auto mb-6 sm:mb-8">
        <EurekaLogo size="md" />
      </header>

      {/* Contenedor Principal */}
      <main className="w-full max-w-7xl mx-auto flex flex-col flex-1">
        {/* Encabezado: Volver, Título, Subtítulo y KPIs */}
        <section className="mb-6">
          <FrictionDetailHeader data={data} eventId={eventId} />
        </section>

        {/* Barra de Pestañas (Tabs) */}
        <section className="w-full border-b border-neutral-200/80 mb-6">
          <nav className="flex items-center gap-6 sm:gap-8 -mb-px" aria-label="Pestañas de detalle">
            {/* Pestaña: Recorrido del agente */}
            <button
              type="button"
              onClick={() => setActiveTab("recorrido")}
              className={cn(
                "pb-3 text-sm sm:text-base transition-colors duration-150 cursor-pointer border-b-2",
                activeTab === "recorrido"
                  ? "font-semibold text-neutral-900 border-eureka-primary"
                  : "font-normal text-neutral-600 hover:text-neutral-900 border-transparent"
              )}
            >
              Recorrido del agente
            </button>

            {/* Pestaña: Diagnóstico */}
            <button
              type="button"
              onClick={() => setActiveTab("diagnostico")}
              className={cn(
                "pb-3 text-sm sm:text-base transition-colors duration-150 cursor-pointer border-b-2",
                activeTab === "diagnostico"
                  ? "font-semibold text-neutral-900 border-eureka-primary"
                  : "font-normal text-neutral-600 hover:text-neutral-900 border-transparent"
              )}
            >
              Diagnóstico
            </button>

            {/* Pestaña: Quiénes son */}
            <button
              type="button"
              onClick={() => setActiveTab("quienes-son")}
              className={cn(
                "pb-3 text-sm sm:text-base transition-colors duration-150 cursor-pointer border-b-2",
                activeTab === "quienes-son"
                  ? "font-semibold text-neutral-900 border-eureka-primary"
                  : "font-normal text-neutral-600 hover:text-neutral-900 border-transparent"
              )}
            >
              Quiénes son
            </button>
          </nav>
        </section>

        {/* Contenido de la Pestaña Activa */}
        <section className="w-full">
          {activeTab === "diagnostico" && <FrictionTabDiagnosis data={data} />}
          {activeTab === "recorrido" && <FrictionTabAgentJourney data={data} />}
          {activeTab === "quienes-son" && <FrictionTabAudience data={data} />}
        </section>
      </main>
    </div>
  );
}
