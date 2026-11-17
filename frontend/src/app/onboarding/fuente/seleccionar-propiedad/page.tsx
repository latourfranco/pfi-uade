import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { EurekaLogo } from "@/components/brand/eureka-logo";
import { RadarListeningGraphic } from "@/components/onboarding/radar-listening-graphic";
import { completeSelectedPropertyIntegration } from "@/app/actions/google-auth";
import type { Ga4PropertyInfo } from "@/services/gcp/orchestrator";
import { ArrowRight, BarChart3 } from "lucide-react";

export default async function SeleccionarPropiedadPage() {
  const cookieStore = await cookies();
  const pendingAuthCookie = cookieStore.get("ga4_pending_auth");

  if (!pendingAuthCookie?.value) {
    redirect("/onboarding/fuente?error=sesion_expirada");
  }

  let properties: Ga4PropertyInfo[] = [];

  try {
    const parsed = JSON.parse(pendingAuthCookie.value);
    properties = parsed.properties || [];
  } catch {
    redirect("/onboarding/fuente?error=sesion_invalida");
  }

  if (properties.length === 0) {
    redirect("/onboarding/fuente?error=no_ga4_property_found");
  }

  return (
    <div className="min-h-screen w-full flex flex-col lg:flex-row bg-white">
      {/* Columna Izquierda: Lista de Selección de Propiedades */}
      <div className="w-full lg:w-1/2 min-h-screen flex flex-col justify-between p-8 sm:p-12 md:p-14 lg:p-16 xl:p-20 bg-white">
        {/* Header con Logo */}
        <header className="w-full">
          <EurekaLogo size="md" />
        </header>

        {/* Contenido Principal */}
        <main className="w-full max-w-xl my-auto py-8">
          {/* Badge de paso */}
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-100 text-eureka-primary text-xs font-medium mb-6">
            <span className="w-1.5 h-1.5 rounded-full bg-eureka-primary animate-pulse" />
            Paso 1.5: Selección de Propiedad
          </div>

          <h1 className="text-3xl sm:text-4xl font-bold text-neutral-950 tracking-tight leading-[1.15] mb-3">
            Selecciona la propiedad de GA4 a vincular.
          </h1>

          <p className="text-sm sm:text-base text-neutral-600 font-normal leading-relaxed mb-6">
            Detectamos múltiples propiedades en tu cuenta de Google. Elige cuál de ellas deseas conectar con BigQuery para el análisis de fricción.
          </p>

          <form action={completeSelectedPropertyIntegration} className="space-y-6">
            <div className="space-y-3 max-h-80 overflow-y-auto pr-1">
              {properties.map((prop, idx) => (
                <label
                  key={prop.propertyId}
                  className="group relative flex items-center justify-between p-4 rounded-xl border border-neutral-200/90 bg-white hover:border-eureka-primary/60 hover:bg-indigo-50/20 cursor-pointer transition-all duration-200 shadow-xs has-checked:border-eureka-primary has-checked:bg-indigo-50/40 has-checked:shadow-sm"
                >
                  <div className="flex items-center gap-3.5">
                    <div className="p-2.5 rounded-lg bg-neutral-100 group-hover:bg-indigo-100/70 group-has-checked:bg-indigo-100 text-neutral-700 group-has-checked:text-eureka-primary transition-colors">
                      <BarChart3 className="w-5 h-5" />
                    </div>
                    <div>
                      <h4 className="text-sm sm:text-base font-semibold text-neutral-900 group-has-checked:text-eureka-primary transition-colors">
                        {prop.propertyName}
                      </h4>
                      <p className="text-xs text-neutral-500 mt-0.5">
                        Cuenta: {prop.accountName} • ID: {prop.propertyId}
                      </p>
                    </div>
                  </div>

                  <input
                    type="radio"
                    name="propertyId"
                    value={prop.propertyId}
                    defaultChecked={idx === 0}
                    className="w-4 h-4 text-eureka-primary focus:ring-eureka-primary accent-eureka-primary cursor-pointer"
                  />
                </label>
              ))}
            </div>

            <div>
              <button
                type="submit"
                className="group relative w-full sm:w-auto inline-flex items-center justify-center gap-2.5 px-8 py-3.5 rounded-xl bg-eureka-primary hover:bg-eureka-primary/90 text-white font-medium text-sm sm:text-base shadow-[0_4px_16px_rgba(82,86,232,0.35)] hover:shadow-[0_8px_24px_rgba(82,86,232,0.45)] hover:-translate-y-0.5 active:translate-y-0 active:scale-[0.98] transition-all duration-300 ease-out cursor-pointer overflow-hidden"
              >
                <span>Confirmar e Integrar Propiedad</span>
                <ArrowRight className="w-4 h-4 transition-transform duration-300 ease-out group-hover:translate-x-1" />
              </button>
            </div>
          </form>
        </main>

        {/* Footer */}
        <footer className="text-xs text-neutral-400 font-normal">
          Podrás modificar o agregar más propiedades posteriormente desde la configuración de integraciones.
        </footer>
      </div>

      {/* Columna Derecha: Radar Graphic */}
      <div className="w-full lg:w-1/2 min-h-90 lg:min-h-screen bg-eureka-cream flex items-center justify-center p-8 sm:p-12 relative overflow-hidden">
        <RadarListeningGraphic />
      </div>
    </div>
  );
}
