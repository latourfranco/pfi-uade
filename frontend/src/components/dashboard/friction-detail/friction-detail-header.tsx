"use client";

import { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowLeft, Download, TrendingDown } from "lucide-react";
import { downloadFrictionFindings } from "@/lib/export-friction-findings";
import type { FrictionDetail } from "@/lib/friction-data";

const integerFormatter = new Intl.NumberFormat("es-AR");

function formatConversionImpact(data: FrictionDetail): string | null {
  if (
    data.caidaPuntosPorcentuales !== null &&
    data.caidaPuntosPorcentuales !== undefined &&
    !Number.isNaN(data.caidaPuntosPorcentuales)
  ) {
    const ppFormatted = Math.abs(data.caidaPuntosPorcentuales).toFixed(1).replace(".", ",");
    const parts = [`-${ppFormatted} pp de conversión`];
    if (
      data.sesionesPerdidas !== null &&
      data.sesionesPerdidas !== undefined &&
      !Number.isNaN(data.sesionesPerdidas)
    ) {
      parts.push(`${integerFormatter.format(Math.round(data.sesionesPerdidas))} sesiones perdidas`);
    }
    return parts.join(" · ");
  }

  return data.impactoResumen ?? null;
}

interface FrictionDetailHeaderProps {
  data: FrictionDetail;
  eventId?: string | null;
}

export function FrictionDetailHeader({ data, eventId }: FrictionDetailHeaderProps) {
  const [isExporting, setIsExporting] = useState(false);
  const searchParams = useSearchParams();
  const currentEvent =
    eventId ||
    searchParams.get("event") ||
    data.eventoClave ||
    null;

  const backUrl = currentEvent ? `/dashboard?event=${currentEvent}` : "/dashboard";
  const conversionImpact = formatConversionImpact(data);

  const handleExport = async () => {
    setIsExporting(true);
    try {
      await downloadFrictionFindings(data);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="w-full flex flex-col gap-4">
      {/* Barra superior: Volver y Exportar hallazgos */}
      <div className="flex items-center justify-between gap-4">
        <Link
          href={backUrl}
          className="inline-flex items-center gap-1.5 text-sm sm:text-base font-medium text-eureka-primary hover:text-eureka-brand transition-colors duration-150 group"
        >
          <ArrowLeft className="w-3.5 h-3.5 transition-transform duration-200 ease-out group-hover:-translate-x-1" />
          <span>Volver</span>
        </Link>

        <button
          type="button"
          onClick={handleExport}
          disabled={isExporting}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-neutral-200 bg-white text-xs sm:text-sm font-medium text-neutral-700 hover:bg-neutral-50 hover:text-neutral-900 disabled:opacity-60 disabled:cursor-wait transition-colors cursor-pointer shadow-2xs"
        >
          <Download className="w-3.5 h-3.5 text-neutral-500" />
          <span>{isExporting ? "Exportando..." : "Exportar hallazgos"}</span>
        </button>
      </div>

      {/* Contenido Principal del Encabezado */}
      <div className="w-full flex flex-col lg:flex-row lg:items-start lg:justify-between gap-6 lg:gap-10">
        {/* Lado Izquierdo: Título y Bajada */}
        <div className="flex-1 max-w-3xl">
          {/* Título Principal */}
          <h1 className="text-2xl sm:text-3xl lg:text-[32px] font-bold text-neutral-900 tracking-tight leading-[1.18] mb-3">
            {data.title}
          </h1>

          {/* Bajada Descriptiva */}
          <p className="text-sm sm:text-base text-neutral-600 leading-relaxed max-w-2xl font-normal">
            {data.subtitle}
          </p>

          {/* Callout destacado de pérdida de conversión */}
          {conversionImpact && (
            <div className="mt-4 inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-red-50 border border-red-200/90 text-red-700 shadow-xs">
              <TrendingDown className="w-4 h-4 shrink-0 text-red-600" />
              <span className="text-xs sm:text-sm font-mono font-semibold tracking-tight">
                {conversionImpact}
              </span>
            </div>
          )}
        </div>

        {/* Lado Derecho: KPIs / Métricas Clave */}
        <div className="flex flex-wrap items-center gap-6 sm:gap-10 shrink-0 self-start pt-1 lg:pt-3">
          {/* Métrica 1: Tasa de sesiones */}
          <div className="flex flex-col">
            <span className="text-2xl sm:text-3xl font-bold text-eureka-primary tracking-tight leading-none">
              {data.metrics.sessionRate.value}
            </span>
            <span className="text-xs sm:text-sm text-neutral-600 font-normal mt-1.5 whitespace-nowrap">
              {data.metrics.sessionRate.label}
            </span>
          </div>

          {/* Métrica 2: Clientes afectados */}
          <div className="flex flex-col">
            <span className="text-2xl sm:text-3xl font-bold text-eureka-primary tracking-tight leading-none">
              {data.metrics.affectedUsers.value}
            </span>
            <span className="text-xs sm:text-sm text-neutral-600 font-normal mt-1.5 whitespace-nowrap">
              {data.metrics.affectedUsers.label}
            </span>
          </div>

          {/* Métrica 3: Sesiones totales */}
          <div className="flex flex-col">
            <span className="text-2xl sm:text-3xl font-bold text-eureka-primary tracking-tight leading-none">
              {data.metrics.totalSessions.value}
            </span>
            <span className="text-xs sm:text-sm text-neutral-600 font-normal mt-1.5 whitespace-nowrap">
              {data.metrics.totalSessions.label}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
