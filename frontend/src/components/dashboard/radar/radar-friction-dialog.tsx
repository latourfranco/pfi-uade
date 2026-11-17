"use client";

import Link from "next/link";
import { Users, MousePointer2, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import type { FrictionCluster } from "../dashboard-radar-canvas";

interface RadarFrictionDialogProps {
  cluster: FrictionCluster | null;
  eventId?: string | null;
  eventName: string;
  onClose: () => void;
}

export function RadarFrictionDialog({
  cluster,
  eventId,
  eventName,
  onClose,
}: RadarFrictionDialogProps) {
  return (
    <Dialog
      open={Boolean(cluster)}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      {cluster && (
        <DialogContent
          showCloseButton={false}
          className="sm:max-w-115 w-full h-[min(700px,calc(100dvh-2rem))] max-h-[calc(100dvh-2rem)] flex flex-col p-0 rounded-[26px] bg-white border border-neutral-200/80 shadow-[0_22px_60px_rgba(0,0,0,0.16)] outline-none font-sans overflow-hidden gap-0"
        >
          {/* Contenido scrolleable en Y */}
          <div className="flex-1 min-h-0 overflow-y-auto scrollbar-thin p-6 sm:p-7 pb-4 flex flex-col gap-4.5">
            {/* Encabezado con Indicador de Patrón, Criticidad y Título */}
            <DialogHeader className="gap-2 text-left shrink-0">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-eureka-primary shrink-0" />
                  <span className="text-xs font-bold font-mono tracking-wider text-eureka-primary uppercase">
                    Patrón seleccionado
                  </span>
                </div>

                {/* Badge de Criticidad */}
                <span
                  className={cn(
                    "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium font-mono border shadow-2xs",
                    cluster.severity === "alta" && "bg-red-100 text-red-800 border-red-400",
                    cluster.severity === "media" && "bg-orange-100 text-orange-800 border-orange-400",
                    cluster.severity === "baja" && "bg-amber-100 text-amber-900 border-amber-400"
                  )}
                >
                  <span
                    className={cn(
                      "w-1.5 h-1.5 rounded-full",
                      cluster.severity === "alta" && "bg-red-600 animate-pulse",
                      cluster.severity === "media" && "bg-orange-600",
                      cluster.severity === "baja" && "bg-amber-600"
                    )}
                  />
                  Criticidad {cluster.severity}
                </span>
              </div>

              <DialogTitle className="text-xl sm:text-2xl font-bold text-neutral-900 tracking-tight leading-snug">
                {cluster.name}
              </DialogTitle>
            </DialogHeader>

            {/* Tarjeta 1: Impacto en Evento Clave */}
            <div className="rounded-2xl bg-[#EEF2FF]/70 border border-indigo-100/90 p-3.5 px-4 shrink-0">
              <span className="text-[11px] font-bold font-mono tracking-wider text-eureka-primary uppercase block mb-1">
                Impacta en el evento clave
              </span>
              <p className="text-base sm:text-lg font-bold text-neutral-900 leading-snug">
                {eventName}
              </p>
              {cluster.impact && (
                <p className="text-xs font-mono font-medium text-eureka-primary mt-1">
                  {cluster.impact}
                </p>
              )}
            </div>

            {/* Tarjeta 2: Métricas de Usuarios y Sesiones */}
            <div className="grid grid-cols-2 gap-4 rounded-2xl bg-[#EEF2FF]/70 border border-indigo-100/90 p-4 items-center shrink-0">
              <div className="flex flex-col gap-0.5">
                <Users className="w-5 h-5 text-neutral-600 mb-1" />
                <span className="text-xl font-bold text-eureka-primary tracking-tight leading-tight">
                  {cluster.users}
                </span>
                <span className="text-xs sm:text-sm text-neutral-500 font-medium">Usuarios</span>
              </div>
              <div className="flex flex-col gap-0.5 border-l border-indigo-200/70 pl-4">
                <MousePointer2 className="w-5 h-5 text-neutral-600 mb-1" />
                <span className="text-xl font-bold text-eureka-primary tracking-tight leading-tight">
                  {cluster.sessionsCount}
                </span>
                <span className="text-xs sm:text-sm text-neutral-500 font-medium">Sesiones/mes</span>
              </div>
            </div>

            {/* Sección 3: Diagnóstico del Agente */}
            <div className="flex flex-col gap-1.5 pt-1 text-left shrink-0">
              <h3 className="text-base sm:text-lg font-bold text-neutral-900 tracking-tight">
                Diagnóstico del agente
              </h3>
              <DialogDescription className="text-sm sm:text-base text-neutral-600 leading-relaxed font-normal">
                {cluster.diagnosis}
              </DialogDescription>
            </div>
          </div>

          {/* Botones de Acción (Siempre visibles al fondo) */}
          <div className="p-6 sm:p-7 pt-3.5 shrink-0 bg-white border-t border-neutral-100/90 flex flex-col gap-2.5 shadow-[0_-8px_20px_rgba(0,0,0,0.03)] z-10">
            {/* Botón Principal: Navegar al detalle */}
            <Link
              href={`/dashboard/friccion/${cluster.id}${eventId ? `?event=${eventId}` : ""}`}
              className="group inline-flex w-full items-center justify-center gap-2 px-6 py-3 rounded-xl bg-eureka-primary hover:bg-eureka-primary/90 text-white font-medium text-sm sm:text-base transition-colors duration-200 cursor-pointer shadow-xs"
            >
              <span>Explorar detalle</span>
              <ArrowRight className="w-4 h-4 transition-transform duration-300 ease-out group-hover:translate-x-1" />
            </Link>

            {/* Botón Secundario: Volver */}
            <button
              type="button"
              onClick={onClose}
              className="w-full inline-flex items-center justify-center px-6 py-2.5 rounded-xl bg-white hover:bg-neutral-50 text-neutral-800 hover:text-black font-medium text-sm border border-neutral-300 hover:border-neutral-400 shadow-2xs active:scale-[0.98] transition-all duration-200 cursor-pointer"
            >
              Volver
            </button>
          </div>
        </DialogContent>
      )}
    </Dialog>
  );
}
