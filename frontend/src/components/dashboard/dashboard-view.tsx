"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { LogOut, Settings, Sparkles } from "lucide-react";
import { EurekaLogo } from "@/components/brand/eureka-logo";
import { DashboardEventFilters } from "./dashboard-event-filters";
import { DashboardRadarCanvas } from "./dashboard-radar-canvas";
import { getDashboardRadarDataAction } from "@/app/actions/fricciones";
import { signOutAction } from "@/app/actions/auth";
import type { RadarDataResult } from "@/repositories/friccion.repository";

const numberFormatter = new Intl.NumberFormat("es-AR");

export function DashboardView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const eventParam = searchParams.get("event");

  const [selectedEventIdOverride, setSelectedEventIdOverride] = useState<string | null | undefined>(undefined);
  const [radarData, setRadarData] = useState<RadarDataResult | null>(null);

  useEffect(() => {
    let isMounted = true;
    getDashboardRadarDataAction()
      .then((data) => {
        if (isMounted && data) {
          setRadarData(data);
        }
      })
      .catch((err) => {
        console.warn("[DashboardView] Error cargando radar data:", err);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const selectedEventId = selectedEventIdOverride !== undefined ? selectedEventIdOverride : (eventParam || null);

  const handleSelectEvent = (id: string | null) => {
    setSelectedEventIdOverride(id);
    const params = new URLSearchParams(searchParams.toString());
    if (id) {
      params.set("event", id);
    } else {
      params.delete("event");
    }
    const query = params.toString();
    router.replace(query ? `/dashboard?${query}` : "/dashboard", { scroll: false });
  };

  const detectedEvents = radarData?.detectedEvents ?? [];
  const eventsCount = detectedEvents.length;
  const frictionsCount = detectedEvents.reduce((acc, ev) => acc + ev.count, 0);
  const totalAffectedSessions = radarData?.totalAffectedSessions ?? 0;
  const sessionsAffected = numberFormatter.format(totalAffectedSessions);

  const totalLostSessions = Object.values(radarData?.eventsConfig ?? {}).reduce(
    (acc, eventConfig) =>
      acc +
      eventConfig.clusters.reduce(
        (clusterAcc, cluster) => clusterAcc + (cluster.sesionesPerdidas ?? 0),
        0
      ),
    0
  );

  const conversionLossPct =
    totalAffectedSessions > 0 && totalLostSessions > 0
      ? ((totalLostSessions / totalAffectedSessions) * 100).toFixed(1).replace(".", ",")
      : null;
  const lostSessionsFormatted = numberFormatter.format(Math.round(totalLostSessions));

  return (
    <div className="min-h-screen w-full bg-[#FAF9F5] flex flex-col p-6 sm:p-10 md:p-12 lg:p-14 selection:bg-eureka-primary/20 selection:text-[#4F46E5] animate-in fade-in duration-700 ease-out">
      {/* Header con Logo y Acceso a Configuración de Cuenta */}
      <header className="w-full max-w-7xl mx-auto mb-6 sm:mb-8 flex items-center justify-between gap-3">
        <EurekaLogo size="md" />
        <div className="flex items-center gap-2">
          <Link
            href="/dashboard/cuenta"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-neutral-200/90 bg-white/80 text-xs sm:text-sm font-medium text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100/80 transition-all cursor-pointer shadow-xs"
          >
            <Settings className="w-4 h-4" />
            <span>Configuración</span>
          </Link>
          <button
            type="button"
            onClick={() => signOutAction()}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-neutral-200/90 bg-white/80 text-xs sm:text-sm font-medium text-neutral-600 hover:text-red-600 hover:border-red-200 hover:bg-red-50/70 transition-all cursor-pointer shadow-xs"
          >
            <LogOut className="w-4 h-4" />
            <span>Cerrar sesión</span>
          </button>
        </div>
      </header>

      {/* Contenido Principal */}
      <main className="w-full max-w-7xl mx-auto flex flex-col flex-1">
        {/* Encabezado y Selector de Lente */}
        <section className="mb-5">
          <h1 className="text-3xl sm:text-4xl lg:text-[42px] font-bold text-eureka-dark tracking-tight leading-[1.12] mb-5">
            Explorá dónde tu producto
            <br />
            <span className="text-eureka-primary">pierde a sus usuarios</span>
          </h1>
        </section>

        {/* Resumen llamativo de hallazgos y beneficio */}
        <section className="mb-5">
          <div className="w-full bg-white/85 backdrop-blur-md border border-eureka-primary/20 rounded-2xl px-5 py-4 shadow-[0_2px_10px_rgba(82,86,232,0.05)] flex items-start sm:items-center gap-3.5">
            <div className="w-9 h-9 rounded-xl bg-[#EEF2FF] text-eureka-primary flex items-center justify-center shrink-0">
              <Sparkles className="w-4 h-4" />
            </div>
            {frictionsCount > 0 ? (
              <p className="text-sm sm:text-base text-eureka-dark leading-relaxed">
                Detectamos{" "}
                <span className="font-bold text-eureka-primary">
                  {frictionsCount} {frictionsCount === 1 ? "fricción" : "fricciones"}
                </span>{" "}
                en{" "}
                <span className="font-bold text-eureka-primary">
                  {eventsCount} {eventsCount === 1 ? "flujo clave" : "flujos clave"}
                </span>{" "}
                que afectan{" "}
                <span className="font-bold text-eureka-primary">
                  {sessionsAffected} sesiones/mes
                </span>
                .{" "}
                {conversionLossPct ? (
                  <>
                    Resolverlas permite recuperar hasta un{" "}
                    <span className="font-bold text-eureka-primary">
                      {conversionLossPct}% de conversión
                    </span>{" "}
                    ({lostSessionsFormatted} sesiones perdidas).
                  </>
                ) : (
                  <>
                    Resolverlas te permite recuperar usuarios antes del abandono y mejorar la conversión.
                  </>
                )}
              </p>
            ) : (
              <p className="text-sm sm:text-base text-neutral-600 leading-relaxed">
                Aún no detectamos fricciones activas en tus flujos clave. Cuando aparezcan bloqueos, los vas a ver acá para priorizar mejoras de conversión.
              </p>
            )}
          </div>
        </section>

        {/* Texto explicativo bajo las métricas */}
        <p className="text-sm sm:text-base text-neutral-600 mb-3 leading-normal">
          Los focos de <span className="font-bold text-eureka-primary">fricción</span> se ubican según el camino del usuario. <span className="font-bold text-eureka-primary">Seleccioná un flujo clave</span> para ver el detalle.
        </p>

        {/* Barra de Filtro de Eventos */}
        <section className="mb-4">
          <DashboardEventFilters
            selectedEventId={selectedEventId}
            onSelectEvent={handleSelectEvent}
            events={detectedEvents}
          />
        </section>

        {/* Canvas Principal de Exploración */}
        <section className="w-full flex-1">
          <DashboardRadarCanvas
            selectedEventId={selectedEventId}
            onSelectEvent={handleSelectEvent}
            eventsConfig={radarData?.eventsConfig}
            eventDisplayNames={radarData?.eventDisplayNames}
          />
        </section>
      </main>
    </div>
  );
}
