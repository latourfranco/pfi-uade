"use client";

import Link from "next/link";
import { ArrowLeft, LogOut, UserCog } from "lucide-react";
import { EurekaLogo } from "@/components/brand/eureka-logo";
import { signOutAction } from "@/app/actions/auth";
import { PerfilInstitucionalCard } from "./perfil-institucional-card";
import { DerechoSupresionCard } from "./derecho-supresion-card";
import { DangerZoneCard } from "./danger-zone-card";
import type { ClientePerfil } from "@/repositories/cliente-cuenta.repository";
import type { ClienteIntegracionFuente } from "@/repositories/cliente-integracion.repository";

interface CuentaViewProps {
  perfil: ClientePerfil | null;
  integracion: ClienteIntegracionFuente | null;
  clienteId?: string;
}

export function CuentaView({ perfil, integracion, clienteId }: CuentaViewProps) {
  return (
    <div className="min-h-screen w-full bg-[#FAF9F5] flex flex-col p-6 sm:p-10 md:p-12 lg:p-14 selection:bg-eureka-primary/20 selection:text-[#4F46E5] animate-in fade-in duration-500 ease-out">
      {/* Header con Logo y Navegación hacia Dashboard */}
      <header className="w-full max-w-5xl mx-auto mb-8 flex items-center justify-between">
        <Link href="/dashboard" className="cursor-pointer">
          <EurekaLogo size="md" />
        </Link>
        <div className="flex items-center gap-2">
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-neutral-200/90 bg-white/80 text-xs sm:text-sm font-medium text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100/80 transition-all cursor-pointer shadow-xs"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Volver al Radar</span>
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

      {/* Contenedor Principal */}
      <main className="w-full max-w-5xl mx-auto flex flex-col flex-1 space-y-6">
        {/* Título de la Sección */}
        <section className="mb-2">
          <div className="inline-flex items-center gap-2 text-xs font-semibold text-eureka-primary uppercase tracking-wider mb-2">
            <UserCog className="w-4 h-4" />
            <span>Configuración Institucional</span>
          </div>
          <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-eureka-dark tracking-tight leading-tight">
            Administración y Configuración de Cuenta
          </h1>
          <p className="text-sm text-neutral-500 mt-1 max-w-2xl">
            Gestioná los datos corporativos de tu organización y exercé de forma
            transparente los derechos de privacidad y supresión de datos.
          </p>
        </section>

        {/* 1. Perfil Institucional */}
        <PerfilInstitucionalCard
          perfil={perfil}
          integracion={integracion}
          clienteId={clienteId}
        />

        {/* 2. Ejercicio del Derecho de Supresión de Datos */}
        <DerechoSupresionCard />

        {/* 3. Zona de Peligro */}
        <DangerZoneCard clienteId={clienteId} />
      </main>
    </div>
  );
}
