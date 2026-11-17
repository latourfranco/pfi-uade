"use client";

import { useState, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, ArrowRight, Globe, KeyRound, Lock } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  saveOnboardingAuth,
  validateStorageStateJson,
  type OnboardingAuthMode,
} from "@/lib/onboarding-auth";
import { EurekaLogo } from "@/components/brand/eureka-logo";
import { OnboardingProgressBar } from "@/components/onboarding/onboarding-progress-bar";
import { InterfazSimulationGraphic } from "@/components/onboarding/interfaz-simulation-graphic";

function normalizeWebsiteUrl(raw: string): string | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  const withScheme = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
  try {
    const parsed = new URL(withScheme);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return null;
    if (!parsed.hostname.includes(".") && parsed.hostname !== "localhost") return null;
    return parsed.origin + (parsed.pathname === "/" ? "" : parsed.pathname);
  } catch {
    return null;
  }
}

function InterfazContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const rubro = searchParams.get("rubro") || "E-commerce";
  const tamano = searchParams.get("tamano") || "50-249";
  const propertyNameParam = searchParams.get("propertyName") || searchParams.get("url");

  const [siteUrl, setSiteUrl] = useState<string>(() => {
    if (propertyNameParam) return propertyNameParam;
    if (typeof window !== "undefined") {
      return (
        sessionStorage.getItem("eureka_onboarding_url") ||
        localStorage.getItem("eureka_onboarding_url") ||
        ""
      );
    }
    return "";
  });
  const [authMode, setAuthMode] = useState<OnboardingAuthMode>("none");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [storageStateJson, setStorageStateJson] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const normalizedUrl = normalizeWebsiteUrl(siteUrl);
  const isAuthValid =
    authMode === "none" ||
    (authMode === "credentials" && username.trim().length > 0 && password.length > 0) ||
    (authMode === "storage_state" && validateStorageStateJson(storageStateJson));

  const canAdvance = Boolean(normalizedUrl) && isAuthValid && !isSaving;

  const handleNext = async () => {
    if (!normalizedUrl || !isAuthValid || isSaving) return;
    setIsSaving(true);
    try {
      sessionStorage.setItem("eureka_onboarding_interfaz", normalizedUrl);
      localStorage.setItem("eureka_onboarding_interfaz", normalizedUrl);
      sessionStorage.setItem("eureka_onboarding_url", normalizedUrl);
      localStorage.setItem("eureka_onboarding_url", normalizedUrl);

      await saveOnboardingAuth({
        mode: authMode,
        username,
        password,
        storageStateJson,
      });

      router.push(
        `/onboarding/fuente?rubro=${encodeURIComponent(
          rubro
        )}&tamano=${encodeURIComponent(
          tamano
        )}&propertyName=${encodeURIComponent(normalizedUrl)}`
      );
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex flex-col lg:flex-row bg-white">
      {/* Columna Izquierda: Información y Acción */}
      <div className="w-full lg:w-1/2 min-h-screen flex flex-col justify-between p-8 sm:p-12 md:p-14 lg:p-16 xl:p-20 bg-white">
        {/* Header fijo superior con Logo y Barra de Progreso */}
        <header className="w-full shrink-0">
          <EurekaLogo size="md" />
          <div className="mt-7 sm:mt-8">
            <OnboardingProgressBar currentStep={3} totalSteps={4} />
          </div>
        </header>

        {/* Contenido Principal */}
        <main className="w-full max-w-xl my-auto py-8">
          <div className="mb-4">
            <Link
              href={`/onboarding/tamano?rubro=${encodeURIComponent(rubro)}&tamano=${encodeURIComponent(tamano)}`}
              className="inline-flex items-center gap-1.5 text-sm font-medium text-eureka-primary hover:text-eureka-brand transition-colors duration-150 group"
            >
              <ArrowLeft className="w-3.5 h-3.5 transition-transform duration-200 ease-out group-hover:-translate-x-1" />
              <span>Volver</span>
            </Link>
          </div>

          {/* Título Principal */}
          <h1 className="text-4xl sm:text-5xl font-bold text-neutral-950 tracking-tight leading-[1.12] mb-4 font-heading">
            ¿Qué sitio web{" "}
            <br className="hidden sm:inline" />
            vamos a analizar?
          </h1>

          {/* Bajada explicativa sencilla */}
          <p className="text-sm sm:text-base text-neutral-600 leading-relaxed max-w-md sm:max-w-lg mb-8 sm:mb-9">
            Ingresá la URL de tu sitio web para que nuestro agente analice la
            experiencia real de tus usuarios.
          </p>

          {/* Tarjeta de Input de URL del Sitio */}
          <div className="w-full max-w-md sm:max-w-lg rounded-2xl border border-neutral-200/90 bg-white p-5 sm:p-6 shadow-xs mb-8">
            <label
              htmlFor="onboarding-site-url"
              className="block text-xs font-semibold uppercase tracking-wider text-neutral-500 mb-3.5"
            >
              URL de tu sitio web
            </label>

            {/* Input de dirección URL */}
            <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-neutral-50 border border-neutral-200 text-neutral-900 focus-within:border-eureka-primary focus-within:bg-white transition-colors">
              <Globe className="w-4 h-4 text-eureka-primary shrink-0" />
              <input
                id="onboarding-site-url"
                type="url"
                value={siteUrl}
                onChange={(e) => setSiteUrl(e.target.value)}
                placeholder="https://tu-tienda.com"
                className="w-full bg-transparent font-mono text-sm sm:text-base font-medium tracking-tight text-neutral-900 placeholder:text-neutral-400 focus:outline-none"
              />
            </div>

            {siteUrl.trim() && !normalizedUrl && (
              <p className="mt-2 text-xs text-red-600 font-medium">
                Ingresá una URL válida (ej. https://tu-sitio.com)
              </p>
            )}
          </div>

          {/* Configuración de Acceso Autenticado (Opcional) */}
          <div className="w-full max-w-md sm:max-w-lg rounded-2xl border border-neutral-200/90 bg-white p-5 sm:p-6 shadow-xs mb-8">
            <div className="flex items-center justify-between gap-2 mb-3.5">
              <span className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-neutral-500">
                <Lock className="w-3.5 h-3.5 text-eureka-primary" />
                Acceso autenticado (opcional)
              </span>
            </div>

            <div className="flex flex-wrap gap-2 mb-4" role="radiogroup" aria-label="Tipo de autenticación">
              {[
                { id: "none" as const, label: "Sin autenticación" },
                { id: "credentials" as const, label: "Usuario y contraseña" },
                { id: "storage_state" as const, label: "Sesión pre-autenticada" },
              ].map((opt) => {
                const active = authMode === opt.id;
                return (
                  <button
                    key={opt.id}
                    type="button"
                    role="radio"
                    aria-checked={active}
                    onClick={() => setAuthMode(opt.id)}
                    className={cn(
                      "px-3.5 py-1.5 rounded-full text-xs sm:text-sm font-medium border transition-all cursor-pointer",
                      active
                        ? "bg-eureka-dark text-white border-eureka-dark shadow-xs"
                        : "bg-neutral-50 text-neutral-700 border-neutral-200 hover:border-neutral-300"
                    )}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>

            {authMode === "credentials" && (
              <div className="space-y-3 pt-1">
                <div>
                  <label htmlFor="onboarding-auth-user" className="block text-xs font-medium text-neutral-600 mb-1">
                    Usuario o email
                  </label>
                  <input
                    id="onboarding-auth-user"
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="usuario@tu-empresa.com"
                    className="w-full px-3.5 py-2.5 rounded-xl bg-neutral-50 border border-neutral-200 text-sm text-neutral-900 focus:outline-none focus:border-eureka-primary focus:bg-white"
                  />
                </div>
                <div>
                  <label htmlFor="onboarding-auth-pass" className="block text-xs font-medium text-neutral-600 mb-1">
                    Contraseña
                  </label>
                  <input
                    id="onboarding-auth-pass"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full px-3.5 py-2.5 rounded-xl bg-neutral-50 border border-neutral-200 text-sm text-neutral-900 focus:outline-none focus:border-eureka-primary focus:bg-white"
                  />
                </div>
                <p className="inline-flex items-center gap-1.5 text-xs text-neutral-500">
                  <KeyRound className="w-3.5 h-3.5 text-eureka-primary shrink-0" />
                  <span>Se encripta antes de guardarse en la sesión.</span>
                </p>
              </div>
            )}

            {authMode === "storage_state" && (
              <div className="space-y-2 pt-1">
                <label htmlFor="onboarding-storage-state" className="block text-xs font-medium text-neutral-600">
                  Datos de sesión (JSON)
                </label>
                <textarea
                  id="onboarding-storage-state"
                  rows={4}
                  value={storageStateJson}
                  onChange={(e) => setStorageStateJson(e.target.value)}
                  placeholder='{"cookies": [], "origins": []}'
                  className="w-full px-3.5 py-2.5 rounded-xl bg-neutral-50 border border-neutral-200 font-mono text-xs text-neutral-900 focus:outline-none focus:border-eureka-primary focus:bg-white"
                />
                {storageStateJson.trim() && !validateStorageStateJson(storageStateJson) && (
                  <p className="text-xs text-red-600 font-medium">
                    Ingresá un objeto JSON válido.
                  </p>
                )}
                <p className="inline-flex items-center gap-1.5 text-xs text-neutral-500">
                  <KeyRound className="w-3.5 h-3.5 text-eureka-primary shrink-0" />
                  <span>La información se encripta antes de guardarse en la sesión.</span>
                </p>
              </div>
            )}
          </div>

          {/* Botón de Acción Avanzar */}
          <div className="mt-8 sm:mt-10">
            <button
              type="button"
              onClick={handleNext}
              disabled={!canAdvance}
              className="group relative inline-flex items-center justify-center gap-2.5 px-8 py-3.5 rounded-xl bg-eureka-primary hover:bg-eureka-primary/90 text-white font-medium text-sm sm:text-base shadow-[0_4px_16px_rgba(82,86,232,0.35)] hover:shadow-[0_8px_24px_rgba(82,86,232,0.45)] hover:-translate-y-0.5 active:translate-y-0 active:scale-[0.98] transition-all duration-300 ease-out cursor-pointer overflow-hidden disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:translate-y-0"
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

      {/* Columna Derecha: Fondo #EFEFE8 con Gráfico de Simulación (oculto en mobile) */}
      <div className="hidden lg:flex lg:w-1/2 min-h-screen bg-eureka-cream items-center justify-center p-8 sm:p-12 relative overflow-hidden">
        <InterfazSimulationGraphic />
      </div>
    </div>
  );
}

export default function OnboardingInterfazPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-white" />}>
      <InterfazContent />
    </Suspense>
  );
}
