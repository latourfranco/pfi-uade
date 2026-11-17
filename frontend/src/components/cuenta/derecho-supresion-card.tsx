import { ShieldCheck, Database, KeyRound, Clock, FileText } from "lucide-react";

export function DerechoSupresionCard() {
  return (
    <section className="rounded-2xl border border-neutral-200/90 bg-white p-6 sm:p-7 shadow-xs">
      <div className="flex items-center gap-2.5 mb-3">
        <div className="p-2 rounded-xl bg-indigo-50 text-eureka-primary shrink-0">
          <ShieldCheck className="w-5 h-5 text-eureka-primary" />
        </div>
        <div>
          <span className="text-xs font-semibold text-eureka-primary tracking-wider uppercase">
            Marco Normativo de Privacidad
          </span>
          <h2 className="text-lg sm:text-xl font-bold text-neutral-900 tracking-tight">
            Ejercicio del Derecho de Supresión de Datos
          </h2>
        </div>
      </div>

      <p className="text-xs sm:text-sm text-neutral-600 leading-relaxed mb-5">
        En cumplimiento con los estándares internacionales de protección de datos personales, cualquier titular o
        administrador institucional tiene la potestad de exigir la eliminación completa de su información
        y el cese absoluto del tratamiento de sus métricas de usuario.
      </p>

      {/* Grid de 3 pilares de la supresión */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-left">
        <div className="rounded-xl border border-neutral-200/80 bg-neutral-50/60 p-4 space-y-1.5">
          <div className="flex items-center gap-2 text-neutral-800 font-semibold text-xs sm:text-sm">
            <KeyRound className="w-4 h-4 text-eureka-primary shrink-0" />
            <span>1. Revocación de Tokens</span>
          </div>
          <p className="text-xs text-neutral-500 leading-relaxed">
            Se envían instrucciones a Google Identity para anular las credenciales de lectura
            y aprovisionamiento de GA4 y Google Cloud.
          </p>
        </div>

        <div className="rounded-xl border border-neutral-200/80 bg-neutral-50/60 p-4 space-y-1.5">
          <div className="flex items-center gap-2 text-neutral-800 font-semibold text-xs sm:text-sm">
            <Database className="w-4 h-4 text-eureka-primary shrink-0" />
            <span>2. Purga Transaccional & DW</span>
          </div>
          <p className="text-xs text-neutral-500 leading-relaxed">
            Se desvincula el enlace de BigQuery y se programa la eliminación del dataset
            analítico y los perfiles en la base transaccional.
          </p>
        </div>

        <div className="rounded-xl border border-neutral-200/80 bg-neutral-50/60 p-4 space-y-1.5">
          <div className="flex items-center gap-2 text-neutral-800 font-semibold text-xs sm:text-sm">
            <FileText className="w-4 h-4 text-eureka-primary shrink-0" />
            <span>3. Trazabilidad Legal</span>
          </div>
          <p className="text-xs text-neutral-500 leading-relaxed">
            Se asienta una constancia en la tabla de auditoría para certificar la solicitud
            y el estado de la purga ante organismos de control.
          </p>
        </div>
      </div>

      <div className="mt-4 pt-3 border-t border-neutral-100 flex items-center gap-2 text-[11px] text-neutral-400">
        <Clock className="w-3.5 h-3.5" />
        <span>
          El disparo de la purga técnica es inmediato. La propagación y liberación de almacenamiento en BigQuery puede demorar unos minutos.
        </span>
      </div>
    </section>
  );
}
