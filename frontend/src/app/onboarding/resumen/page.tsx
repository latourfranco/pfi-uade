"use client";

import { useState, useEffect, useMemo, useSyncExternalStore, useCallback, useRef, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Building2,
  CheckCircle2,
  ChevronRight,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  formatOnboardingAuthSummary,
  getStoredOnboardingAuthSnapshot,
} from "@/lib/onboarding-auth";
import {
  completeOnboardingAction,
  getAuthSessionSummaryAction,
  signInWithGoogleAction,
} from "@/app/actions/auth";
import { EurekaLogo } from "@/components/brand/eureka-logo";
import { RadarListeningGraphic } from "@/components/onboarding/radar-listening-graphic";

interface SummaryItem {
  label: string;
  value: string;
  href: string;
}

function subscribeToStorage(callback: () => void) {
  window.addEventListener("storage", callback);
  return () => window.removeEventListener("storage", callback);
}

function getStoredRubroSnapshot() {
  if (typeof window === "undefined") return null;
  return (
    sessionStorage.getItem("eureka_onboarding_rubro") ||
    localStorage.getItem("eureka_onboarding_rubro")
  );
}

function getStoredTamanoSnapshot() {
  if (typeof window === "undefined") return null;
  return (
    sessionStorage.getItem("eureka_onboarding_tamano") ||
    localStorage.getItem("eureka_onboarding_tamano")
  );
}

function getStoredUrlSnapshot() {
  if (typeof window === "undefined") return null;
  return (
    sessionStorage.getItem("eureka_onboarding_url") ||
    localStorage.getItem("eureka_onboarding_url")
  );
}

function getServerSnapshot() {
  return null;
}

function ResumenContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const propertyName = searchParams.get("propertyName");
  const propertyId = searchParams.get("propertyId");
  const projectId = searchParams.get("projectId");
  const region = searchParams.get("region");
  const rubroParam = searchParams.get("rubro");
  const tamanoParam = searchParams.get("tamano");

  const storedRubro = useSyncExternalStore(
    subscribeToStorage,
    getStoredRubroSnapshot,
    getServerSnapshot
  );

  const storedTamano = useSyncExternalStore(
    subscribeToStorage,
    getStoredTamanoSnapshot,
    getServerSnapshot
  );

  const storedUrl = useSyncExternalStore(
    subscribeToStorage,
    getStoredUrlSnapshot,
    getServerSnapshot
  );

  const storedAuthRaw = useSyncExternalStore(
    subscribeToStorage,
    getStoredOnboardingAuthSnapshot,
    getServerSnapshot
  );
  const authSummary = formatOnboardingAuthSummary(storedAuthRaw);

  const rubro = rubroParam || storedRubro || "E-commerce";
  const rawTamano = tamanoParam || storedTamano || "50-249";
  const equipoFormatted = `${rawTamano} personas`;
  const siteUrl = storedUrl || propertyName || "";

  const summaryItems: SummaryItem[] = useMemo(() => {
    const encodedRubro = encodeURIComponent(rubro);
    const encodedTamano = encodeURIComponent(rawTamano);
    const encodedSite = encodeURIComponent(siteUrl);

    return [
      {
        label: "Rubro",
        value: rubro,
        href: `/onboarding/rubro?rubro=${encodedRubro}`,
      },
      {
        label: "Equipo",
        value: equipoFormatted,
        href: `/onboarding/tamano?rubro=${encodedRubro}&tamano=${encodedTamano}`,
      },
      {
        label: "Sitio web",
        value: siteUrl || "No configurado",
        href: `/onboarding/interfaz?rubro=${encodedRubro}&tamano=${encodedTamano}&propertyName=${encodedSite}`,
      },
      {
        label: "Autenticación del sitio",
        value: authSummary,
        href: `/onboarding/interfaz?rubro=${encodedRubro}&tamano=${encodedTamano}&propertyName=${encodedSite}`,
      },
      {
        label: "Conexión con Google Analytics",
        value: "Configurada",
        href: `/onboarding/fuente?rubro=${encodedRubro}&tamano=${encodedTamano}&propertyName=${encodedSite}`,
      },
    ];
  }, [siteUrl, rubro, rawTamano, equipoFormatted, authSummary]);

  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [sessionEmail, setSessionEmail] = useState<string | null>(null);
  const [nombreOrganizacion, setNombreOrganizacion] = useState(() =>
    typeof window !== "undefined"
      ? sessionStorage.getItem("eureka_onboarding_org") || ""
      : ""
  );
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const autoCompleteTriggeredRef = useRef(false);
  const shouldAutoComplete = searchParams.get("complete") === "1";

  const finalizeAuthenticatedOnboarding = useCallback(
    async (orgNameOverride?: string) => {
      setSubmitError(null);
      setIsSubmitting(true);

      const resolvedOrg =
        (orgNameOverride ?? nombreOrganizacion).trim() || undefined;

      const result = await completeOnboardingAction({
        rubro,
        tamano: rawTamano,
        baseUrl: siteUrl,
        authPayloadRaw: storedAuthRaw,
        propertyId,
        projectId,
        region,
        nombreOrganizacion: resolvedOrg,
      });

      if (!result.success) {
        setSubmitError(
          result.error ||
            "No pudimos finalizar tu configuración. Intentá nuevamente."
        );
        setIsSubmitting(false);
        return;
      }

      if (typeof window !== "undefined") {
        sessionStorage.removeItem("eureka_onboarding_org");
      }

      router.push(result.redirectUrl || "/dashboard?onboarding=true");
      router.refresh();
    },
    [
      nombreOrganizacion,
      rubro,
      rawTamano,
      siteUrl,
      storedAuthRaw,
      propertyId,
      projectId,
      region,
      router,
    ]
  );

  useEffect(() => {
    let active = true;
    getAuthSessionSummaryAction()
      .then((summary) => {
        if (!active) return;
        setIsAuthenticated(summary.authenticated);
        setSessionEmail(summary.email);
        const savedOrg =
          typeof window !== "undefined"
            ? sessionStorage.getItem("eureka_onboarding_org") || ""
            : "";
        const resolvedOrg = savedOrg || summary.nombreOrganizacion || "";
        if (resolvedOrg) {
          setNombreOrganizacion(resolvedOrg);
        }

        if (
          summary.authenticated &&
          shouldAutoComplete &&
          !autoCompleteTriggeredRef.current
        ) {
          autoCompleteTriggeredRef.current = true;
          void finalizeAuthenticatedOnboarding(resolvedOrg);
        }
      })
      .catch(() => {
        // Ignorar si no hay sesión previa
      });
    return () => {
      active = false;
    };
  }, [shouldAutoComplete, finalizeAuthenticatedOnboarding]);

  const handleCompleteOnboarding = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);

    if (!isAuthenticated) {
      if (nombreOrganizacion.trim().length < 2) {
        setSubmitError(
          "Ingresá el nombre de tu organización (mínimo 2 caracteres)."
        );
        return;
      }
      if (typeof window !== "undefined") {
        sessionStorage.setItem(
          "eureka_onboarding_org",
          nombreOrganizacion.trim()
        );
      }
      setIsSubmitting(true);
      const oauthResult = await signInWithGoogleAction(
        "/onboarding/resumen?complete=1"
      );
      if (oauthResult && !oauthResult.success) {
        setSubmitError(
          oauthResult.error ||
            "No pudimos iniciar la autenticación con Google."
        );
        setIsSubmitting(false);
      }
      return;
    }

    await finalizeAuthenticatedOnboarding();
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }

      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => {
          if (prev === null) return 0;
          return (prev + 1) % summaryItems.length;
        });
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => {
          if (prev === null) return summaryItems.length - 1;
          return (prev - 1 + summaryItems.length) % summaryItems.length;
        });
      } else if (e.key === "Escape") {
        setSelectedIndex(null);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [summaryItems.length]);

  return (
    <div className="min-h-screen w-full flex flex-col lg:flex-row bg-white">
      {/* Columna Izquierda: Información y Resumen */}
      <div className="w-full lg:w-1/2 min-h-screen flex flex-col justify-between p-8 sm:p-12 md:p-14 lg:p-16 xl:p-20 bg-white">
        {/* Header con Logo */}
        <header className="w-full">
          <EurekaLogo size="md" />
        </header>

        {/* Contenido Principal */}
        <main className="w-full max-w-xl my-auto py-8">
          <div className="mb-4">
            <Link
              href={`/onboarding/fuente?rubro=${encodeURIComponent(rubro)}&tamano=${encodeURIComponent(rawTamano)}&propertyName=${encodeURIComponent(propertyName || storedUrl || "")}`}
              className="inline-flex items-center gap-1.5 text-sm font-medium text-eureka-primary hover:text-eureka-brand transition-colors duration-150 group"
            >
              <ArrowLeft className="w-3.5 h-3.5 transition-transform duration-200 ease-out group-hover:-translate-x-1" />
              <span>Volver</span>
            </Link>
          </div>

          {/* Título Principal */}
          <h1 className="text-4xl sm:text-5xl font-bold text-neutral-950 tracking-tight leading-[1.12] mb-8">
            Listo. Ya estamos{" "}
            <br />
            escuchando.
          </h1>

          {/* Tabla de Resumen (clickeable para editar cada paso) */}
          <div className="w-full border-t border-b border-neutral-200/90 divide-y mb-10">
            {summaryItems.map((item, index) => {
              const isSelected = selectedIndex === index;
              return (
                <Link
                  key={item.label}
                  href={item.href}
                  onClick={() => setSelectedIndex(index)}
                  onMouseEnter={() => setSelectedIndex(index)}
                  className={cn(
                    "group py-3.5 px-3.5 -mx-3.5 flex items-center justify-between gap-4 rounded-xl transition-all duration-500 ease-out border cursor-pointer",
                    isSelected
                      ? "bg-[#EEF2FF] border-eureka-primary/40 shadow-md shadow-indigo-500/5 scale-[1.02] translate-x-1.5 z-10"
                      : "border-transparent hover:bg-neutral-100/60 hover:translate-x-1"
                  )}
                >
                  <div className="flex items-center">
                    <div
                      className={cn(
                        "h-4.5 rounded-full bg-[#6366F1] transition-all duration-500 ease-out",
                        isSelected
                          ? "w-1.5 opacity-100 scale-100 mr-2.5"
                          : "w-0 opacity-0 scale-0 mr-0"
                      )}
                    />
                    <span
                      className={cn(
                        "transition-all duration-500 ease-out",
                        isSelected
                          ? "text-neutral-950 font-semibold text-sm sm:text-base"
                          : "text-neutral-500 group-hover:text-neutral-900 font-normal text-sm sm:text-base"
                      )}
                    >
                      {item.label}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span
                      className={cn(
                        "transition-all duration-500 ease-out text-right",
                        isSelected
                          ? "text-[#4338CA] font-bold text-base sm:text-lg"
                          : "text-neutral-900 group-hover:text-[#4F46E5] font-semibold text-sm sm:text-base"
                      )}
                    >
                      {item.value}
                    </span>
                    <ChevronRight
                      className={cn(
                        "w-4 h-4 transition-all duration-300",
                        isSelected
                          ? "text-[#4338CA] translate-x-0.5 opacity-100"
                          : "text-neutral-400 opacity-60 group-hover:opacity-100 group-hover:translate-x-0.5"
                      )}
                    />
                  </div>
                </Link>
              );
            })}
          </div>

          {/* Formulario de Creación de Cuenta con Google + Botón CTA */}
          <form onSubmit={handleCompleteOnboarding} className="space-y-6">
            {isAuthenticated ? (
              <div className="rounded-xl border border-emerald-200/90 bg-emerald-50/70 px-4 py-3 flex items-center gap-2.5 text-xs sm:text-sm text-emerald-800">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>
                  Sesión de Google activa como{" "}
                  <strong className="font-semibold">{sessionEmail}</strong>
                </span>
              </div>
            ) : (
              <div className="rounded-2xl border border-neutral-200/90 bg-neutral-50/70 p-5 space-y-3.5">
                <div>
                  <h2 className="text-sm font-semibold text-neutral-900">
                    Creá tu cuenta con Google para activar tu radar
                  </h2>
                  <p className="text-xs text-neutral-500 mt-0.5">
                    Guardaremos tu configuración de sitio, credenciales y perfil asociados a tu cuenta de Google.
                  </p>
                </div>

                <div>
                  <label
                    htmlFor="resumen-org"
                    className="block text-xs font-medium text-neutral-700 mb-1"
                  >
                    Nombre de la organización
                  </label>
                  <div className="relative">
                    <Building2 className="w-4 h-4 text-neutral-400 absolute left-3 top-1/2 -translate-y-1/2" />
                    <input
                      id="resumen-org"
                      type="text"
                      required
                      value={nombreOrganizacion}
                      onChange={(e) => setNombreOrganizacion(e.target.value)}
                      placeholder="Ej. Tienda Norte S.A."
                      className="w-full rounded-xl border border-neutral-200 bg-white pl-9 pr-3 py-2 text-sm text-neutral-900 placeholder:text-neutral-400 focus:outline-none focus:ring-2 focus:ring-eureka-primary/25 focus:border-eureka-primary"
                    />
                  </div>
                </div>
              </div>
            )}

            {submitError && (
              <div
                role="alert"
                className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50/80 px-3.5 py-2.5 text-xs sm:text-sm text-red-700"
              >
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{submitError}</span>
              </div>
            )}

            <div>
              <button
                type="submit"
                disabled={isSubmitting}
                className="group relative inline-flex items-center justify-center gap-2.5 px-8 py-3.5 rounded-xl bg-eureka-primary hover:bg-eureka-primary/90 disabled:opacity-60 text-white font-medium text-sm sm:text-base shadow-[0_4px_16px_rgba(82,86,232,0.35)] hover:shadow-[0_8px_24px_rgba(82,86,232,0.45)] hover:-translate-y-0.5 active:translate-y-0 active:scale-[0.98] transition-all duration-300 ease-out cursor-pointer overflow-hidden"
              >
                {/* Efecto de brillo / shimmer dinámico */}
                <div
                  className="absolute inset-0 -translate-x-full group-hover:translate-x-full transition-transform duration-700 ease-out pointer-events-none"
                  style={{
                    background:
                      "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.28) 50%, transparent 100%)",
                  }}
                />

                {isSubmitting ? (
                  <>
                    <Loader2 className="relative z-10 w-4 h-4 animate-spin" />
                    <span className="relative z-10 font-medium">
                      Activando tu cuenta...
                    </span>
                  </>
                ) : (
                  <>
                    <span className="relative z-10 font-medium">
                      {isAuthenticated
                        ? "Ver mi panorama de fricción"
                        : "Continuar con Google y activar radar"}
                    </span>
                    <ArrowRight className="relative z-10 w-4 h-4 transition-transform duration-300 ease-out group-hover:translate-x-1" />
                  </>
                )}
              </button>
            </div>
          </form>
        </main>

        {/* Footer vacío para mantener balance visual */}
        <footer className="hidden lg:block h-4" />
      </div>

      {/* Columna Derecha: Fondo #EFEFE8 con Ilustración de Radar (oculta en mobile) */}
      <div className="hidden lg:flex lg:w-1/2 min-h-screen bg-eureka-cream items-center justify-center p-8 sm:p-12 relative overflow-hidden">
        <RadarListeningGraphic />
      </div>
    </div>
  );
}

export default function OnboardingResumenPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-white" />}>
      <ResumenContent />
    </Suspense>
  );
}
