"use client";

import { useState, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  ShieldCheck,
  Lock,
  Coins,
  CheckCircle2,
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Loader2,
} from "lucide-react";
import { EurekaLogo } from "@/components/brand/eureka-logo";
import { OnboardingProgressBar } from "@/components/onboarding/onboarding-progress-bar";
import { AnalyticsConnectionGraphic } from "@/components/onboarding/analytics-connection-graphic";
import { initiateGoogleOAuth } from "@/app/actions/google-auth";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

const ERROR_MESSAGES: Record<string, { title: string; description: string }> = {
  permisos_insuficientes: {
    title: "Permisos insuficientes en Google",
    description:
      "Necesitamos permisos de edición en GA4 y acceso a Cloud Platform para aprovisionar el enlace seguro a BigQuery. Asegúrate de conceder todos los permisos solicitados.",
  },
  no_ga4_property_found: {
    title: "No se encontró ninguna propiedad de GA4",
    description:
      "No detectamos ninguna propiedad de Google Analytics 4 asociada a tu cuenta. Asegúrate de iniciar sesión con la cuenta de Google correcta.",
  },
  acceso_denegado: {
    title: "Autorización cancelada",
    description:
      "Has cancelado el proceso de autorización. Para continuar con el análisis de fricción, es necesario conectar tu propiedad de GA4.",
  },
  sesion_expirada: {
    title: "Sesión de selección expirada",
    description:
      "La sesión de selección de propiedad ha caducado por seguridad. Por favor, inicia la conexión nuevamente.",
  },
  sesion_invalida: {
    title: "Sesión de selección inválida",
    description:
      "No pudimos validar los datos de selección de propiedad. Por favor, inicia la conexión nuevamente.",
  },
  parametro_invalido: {
    title: "Respuesta de autorización incompleta",
    description:
      "No recibimos el código de autorización de Google. Por favor, intenta conectar nuevamente.",
  },
  error_interno: {
    title: "Ocurrió un error en la sincronización",
    description:
      "No pudimos completar la vinculación automática con BigQuery. Por favor, intenta de nuevo.",
  },
};

function FuenteContent() {
  const searchParams = useSearchParams();
  const errorParam = searchParams.get("error");
  const propertyId = searchParams.get("propertyId");
  const propertyName = searchParams.get("propertyName");
  const region = searchParams.get("region");
  const projectId = searchParams.get("projectId");
  const rubroParam = searchParams.get("rubro");
  const tamanoParam = searchParams.get("tamano");
  const isConnected = searchParams.get("status") === "success";

  const [isLoading, setIsLoading] = useState(false);
  const [oauthError, setOauthError] = useState<string | null>(null);
  const [isTermsOpen, setIsTermsOpen] = useState(false);
  const [hasAcceptedTerms, setHasAcceptedTerms] = useState(false);

  const activeErrorKey = oauthError || errorParam;
  const activeError = activeErrorKey
    ? ERROR_MESSAGES[activeErrorKey] || ERROR_MESSAGES.error_interno
    : null;

  const resumenParams = new URLSearchParams({ status: "success" });
  if (propertyId) resumenParams.set("propertyId", propertyId);
  if (propertyName) resumenParams.set("propertyName", propertyName);
  if (region) resumenParams.set("region", region);
  if (projectId) resumenParams.set("projectId", projectId);
  if (rubroParam) resumenParams.set("rubro", rubroParam);
  if (tamanoParam) resumenParams.set("tamano", tamanoParam);
  const resumenHref = `/onboarding/resumen?${resumenParams.toString()}`;

  const backParams = new URLSearchParams();
  if (rubroParam) backParams.set("rubro", rubroParam);
  if (tamanoParam) backParams.set("tamano", tamanoParam);
  if (propertyName) backParams.set("propertyName", propertyName);
  const backQuery = backParams.toString();
  const backHref = backQuery ? `/onboarding/interfaz?${backQuery}` : "/onboarding/interfaz";

  const handleConnect = async () => {
    if (!hasAcceptedTerms || isLoading) return;
    setOauthError(null);
    setIsLoading(true);
    try {
      await initiateGoogleOAuth();
    } catch (error) {
      console.error("[FuenteOnboarding] Error al iniciar OAuth con Google:", error);
      setOauthError("error_interno");
      setIsLoading(false);
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
            <OnboardingProgressBar currentStep={4} totalSteps={4} />
          </div>
        </header>

        {/* Contenido Principal */}
        <main className="w-full max-w-xl my-auto py-8">
          <div className="mb-4">
            <Link
              href={backHref}
              className="inline-flex items-center gap-1.5 text-sm font-medium text-eureka-primary hover:text-eureka-brand transition-colors duration-150 group"
            >
              <ArrowLeft className="w-3.5 h-3.5 transition-transform duration-200 ease-out group-hover:-translate-x-1" />
              <span>Volver</span>
            </Link>
          </div>

          {/* Título Principal */}
          <h1 className="text-4xl sm:text-5xl font-bold text-neutral-950 tracking-tight leading-[1.12] mb-9">
            Conexión con Google Analytics
          </h1>

          {/* Alerta de Error si existe */}
          {activeError && (
            <div className="mb-8 p-4 rounded-xl bg-red-50/90 border border-red-200 flex items-start gap-3.5 text-left animate-in fade-in slide-in-from-top-2 duration-300">
              <AlertCircle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
              <div>
                <h3 className="text-sm font-semibold text-red-950">
                  {activeError.title}
                </h3>
                <p className="text-xs sm:text-sm text-red-700 mt-1 leading-relaxed">
                  {activeError.description}
                </p>
              </div>
            </div>
          )}

          {/* Alerta de Éxito cuando la conexión está activa */}
          {isConnected && (
            <div className="mb-3.5 p-4 rounded-xl bg-emerald-50/90 border border-emerald-500 flex items-start gap-3.5 text-left animate-in fade-in slide-in-from-top-2 duration-300">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
              <div>
                <h3 className="text-sm font-semibold text-emerald-800">
                  Conexión establecida con éxito
                </h3>
                <p className="text-xs sm:text-sm text-emerald-700 mt-0.5 leading-relaxed font-medium">
                  Propiedad vinculada: <span className="font-semibold text-emerald-800">{propertyName}</span>
                </p>
              </div>
            </div>
          )}

          {/* Tarjetas de Beneficios & Seguridad */}
          <div className="space-y-3.5 mb-7">
            <div className="p-4 rounded-xl border bg-indigo-50 border-eureka-primary/50 hover:bg-indigo-100 transition-colors flex items-start gap-3.5">
              <div className="p-2 rounded-lg bg-eureka-primary text-white shrink-0 mt-0.5">
                <Lock className="w-4 h-4" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-neutral-900 md:text-base">
                  Privacidad garantizada
                </h4>
                <p className="text-sm text-neutral-600 mt-0.5 md:text-base">
                  La exportación no incluye datos personales ni información sensible.
                </p>
              </div>
            </div>

            <div className="p-4 rounded-xl border bg-indigo-50 border-eureka-primary/50 hover:bg-indigo-100 transition-colors flex items-start gap-3.5">
              <div className="p-2 rounded-lg bg-eureka-primary text-white shrink-0 mt-0.5">
                <ShieldCheck className="w-4 h-4" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-neutral-900 md:text-base">
                  Permisos de solo lectura
                </h4>
                <p className="text-sm text-neutral-600 mt-0.5 md:text-base">
                  Eureka no puede modificar ni eliminar datos de tu propiedad de Google Analytics.
                </p>
              </div>
            </div>
          </div>

          {/* Checkbox de Términos de la Conexión (solo si aún no está conectado) */}
          {!isConnected && (
            <div className="flex items-start gap-3 mb-6 select-none animate-in fade-in duration-200">
              <input
                id="terms-checkbox"
                type="checkbox"
                checked={hasAcceptedTerms}
                onChange={(e) => setHasAcceptedTerms(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-neutral-300 text-eureka-primary accent-eureka-primary focus:ring-eureka-primary/30 cursor-pointer shrink-0"
              />
              <label
                htmlFor="terms-checkbox"
                className="text-xs sm:text-sm text-neutral-600 leading-normal cursor-pointer"
              >
                Acepto los{" "}
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setIsTermsOpen(true);
                  }}
                  className="text-eureka-primary font-semibold underline underline-offset-3 hover:text-eureka-primary/80 transition-colors cursor-pointer inline"
                >
                  términos de la conexión
                </button>
                .
              </label>
            </div>
          )}

          {/* Botón de Acción: Conectar o Avanzar */}
          <div>
            {isConnected ? (
              <Link
                href={resumenHref}
                className="group relative inline-flex items-center justify-center gap-2.5 px-8 py-3.5 rounded-xl bg-eureka-primary hover:bg-eureka-primary/90 text-white font-medium text-sm sm:text-base shadow-[0_4px_16px_rgba(82,86,232,0.35)] hover:shadow-[0_8px_24px_rgba(82,86,232,0.45)] hover:-translate-y-0.5 active:translate-y-0 active:scale-[0.98] transition-all duration-300 ease-out cursor-pointer overflow-hidden"
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
              </Link>
            ) : (
              <button
                onClick={handleConnect}
                disabled={!hasAcceptedTerms || isLoading}
                className="group relative inline-flex items-center justify-center gap-2.5 px-8 py-3.5 rounded-xl bg-eureka-primary hover:bg-eureka-primary/90 text-white font-medium text-sm sm:text-base shadow-[0_4px_16px_rgba(82,86,232,0.35)] hover:shadow-[0_8px_24px_rgba(82,86,232,0.45)] hover:-translate-y-0.5 active:translate-y-0 active:scale-[0.98] transition-all duration-300 ease-out cursor-pointer overflow-hidden disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0 disabled:hover:shadow-[0_4px_16px_rgba(82,86,232,0.35)] disabled:active:scale-100"
              >
                {/* Efecto de brillo / shimmer dinámico (solo activo cuando está habilitado) */}
                {hasAcceptedTerms && !isLoading && (
                  <div
                    className="absolute inset-0 -translate-x-full group-hover:translate-x-full transition-transform duration-700 ease-out pointer-events-none"
                    style={{
                      background:
                        "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.28) 50%, transparent 100%)",
                    }}
                  />
                )}

                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin text-white relative z-10" />
                    <span className="relative z-10 font-medium">Conectando con Google...</span>
                  </>
                ) : (
                  <>
                    <span className="relative z-10 font-medium">Conectar con Google</span>
                    <ArrowRight className="relative z-10 w-4 h-4 transition-transform duration-300 ease-out group-enabled:group-hover:translate-x-1" />
                  </>
                )}
              </button>
            )}
          </div>
        </main>

        {/* Footer vacío para mantener balance visual */}
        <footer className="hidden lg:block h-4" />
      </div>

      {/* Modal de Términos y Condiciones de la Conexión */}
      <Dialog open={isTermsOpen} onOpenChange={setIsTermsOpen}>
        <DialogContent className="sm:max-w-xl max-h-[88vh] flex flex-col bg-white border border-neutral-200 shadow-2xl p-6 rounded-2xl gap-5 overflow-hidden">
          <DialogHeader className="gap-1.5 text-left shrink-0">
            <DialogTitle className="text-xl font-bold text-neutral-950 font-heading">
              Términos de la conexión
            </DialogTitle>
            <DialogDescription className="text-neutral-600 text-sm md:text-base">
              Transparencia total sobre cómo cuidamos tus datos y tu cuenta.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3.5 my-1 overflow-y-auto pr-1.5 max-h-[56vh]">
            <div className="p-4 rounded-xl border bg-indigo-50 border-eureka-primary/50 hover:bg-indigo-100 transition-colors flex items-start gap-3.5">
              <div className="p-2 rounded-lg bg-eureka-primary text-white shrink-0 mt-0.5">
                <Lock className="w-4 h-4" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-neutral-900 md:text-base">
                  Solo eventos crudos, sin datos personales
                </h4>
                <p className="text-sm text-neutral-600 mt-0.5 md:text-base">
                  Eureka solo lee eventos anónimos de navegación (como clics, scroll y vistas de página). Nunca accedemos a nombres, correos ni identificadores personales de tus usuarios.
                </p>
              </div>
            </div>

            <div className="p-4 rounded-xl border bg-indigo-50 border-eureka-primary/50 hover:bg-indigo-100 transition-colors flex items-start gap-3.5">
              <div className="p-2 rounded-lg bg-eureka-primary text-white shrink-0 mt-0.5">
                <ShieldCheck className="w-4 h-4" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-neutral-900 md:text-base">
                  Permisos de solo lectura
                </h4>
                <p className="text-sm text-neutral-600 mt-0.5 md:text-base">
                  La integración se realiza dentro de tu propio proyecto de Google Cloud. Eureka no tiene permisos para alterar, editar ni borrar datos en tu Google Analytics.
                </p>
              </div>
            </div>

            <div className="p-4 rounded-xl border bg-indigo-50 border-eureka-primary/50 hover:bg-indigo-100 transition-colors flex items-start gap-3.5">
              <div className="p-2 rounded-lg bg-eureka-primary text-white shrink-0 mt-0.5">
                <Coins className="w-4 h-4" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-neutral-900 md:text-base">
                  Cero costo de almacenamiento
                </h4>
                <p className="text-sm text-neutral-600 mt-0.5 md:text-base">
                  Configuramos una política de caducidad automática de 60 días para que el volumen de eventos se mantenga dentro de los 10 GB gratuitos al mes de Google Cloud (suficiente para millones de visitas mensuales).
                  En caso de tráfico masivo que supere dicho límite, el almacenamiento excedente tiene un costo aproximado de USD 0,02 por GB adicional al mes, facturado directamente por Google a cuenta del usuario.
                </p>
              </div>
            </div>

            <div className="p-4 rounded-xl border bg-indigo-50 border-eureka-primary/50 hover:bg-indigo-100 transition-colors flex items-start gap-3.5">
              <div className="p-2 rounded-lg bg-eureka-primary text-white shrink-0 mt-0.5">
                <CheckCircle2 className="w-4 h-4" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-neutral-900 md:text-base">
                  Control y revocación en cualquier momento
                </h4>
                <p className="text-sm text-neutral-600 mt-0.5 md:text-base">
                  Eres dueño de tus datos y puedes desconectar el enlace o revocar los permisos cuando lo desees desde tu consola de Google o desde la plataforma.
                </p>
              </div>
            </div>
          </div>

          <DialogFooter className="shrink-0">
            <Button
              type="button"
              onClick={() => setIsTermsOpen(false)}
              className="w-full sm:w-auto px-6 py-2.5 rounded-xl bg-eureka-primary hover:bg-eureka-primary/90 text-white font-medium cursor-pointer shadow-xs"
            >
              Entendido
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Columna Derecha: Fondo #EFEFE8 con Gráfico de Conexión Analytics (oculto en mobile) */}
      <div className="hidden lg:flex lg:w-1/2 min-h-screen bg-eureka-cream items-center justify-center p-8 sm:p-12 relative overflow-hidden">
        <AnalyticsConnectionGraphic isConnected={isConnected} />
      </div>
    </div>
  );
}

export default function FuenteOnboardingPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-white" />}>
      <FuenteContent />
    </Suspense>
  );
}
