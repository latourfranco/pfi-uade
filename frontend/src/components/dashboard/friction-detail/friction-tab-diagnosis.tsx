"use client";

import type { FrictionDetail } from "@/lib/friction-data";

interface FrictionTabDiagnosisProps {
  data: FrictionDetail;
}

export function FrictionTabDiagnosis({ data }: FrictionTabDiagnosisProps) {
  const paragraphs = data.diagnosis?.paragraphs ?? [];
  const evidence = data.evidence ?? [];
  const recommendations = data.recommendations ?? [];

  return (
    <div className="w-full bg-white rounded-2xl sm:rounded-[24px] border border-neutral-200/70 p-6 sm:p-8 md:p-10 shadow-[0_2px_12px_rgba(0,0,0,0.02)]">
      {/* Sección 1: Diagnóstico del Agente */}
      <div className="flex flex-col">
        <span className="text-sm font-mono font-bold tracking-widest text-eureka-primary uppercase mb-4 select-none">
          Diagnóstico del agente
        </span>

        {paragraphs.length > 0 ? (
          <div className="space-y-4 text-neutral-700 text-sm sm:text-base leading-relaxed font-normal">
            {paragraphs.map((paragraph, index) => (
              <p key={index} className="leading-relaxed">
                {paragraph}
              </p>
            ))}
          </div>
        ) : (
          <p className="text-sm text-neutral-500">Sin párrafos de diagnóstico registrados.</p>
        )}
      </div>

      {/* Separador Horizontal */}
      <div className="border-t border-neutral-100 my-6 sm:my-8" />

      {/* Sección 2: Evidencia */}
      <div className="flex flex-col">
        <span className="text-sm font-mono font-bold tracking-widest text-eureka-primary uppercase mb-4 select-none">
          Evidencia
        </span>

        {evidence.length > 0 ? (
          <ul className="space-y-3 text-neutral-700 text-sm sm:text-base leading-relaxed">
            {evidence.map((item, index) => (
              <li key={index} className="flex items-start gap-3">
                <span className="w-1.5 h-1.5 rounded-full bg-eureka-primary shrink-0 mt-2.5" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-neutral-500">Sin evidencias registradas.</p>
        )}
      </div>

      {/* Sección 3: Recomendaciones */}
      {recommendations.length > 0 && (
        <>
          <div className="border-t border-neutral-100 my-6 sm:my-8" />
          <div className="flex flex-col">
            <span className="text-sm font-mono font-bold tracking-widest text-eureka-primary uppercase mb-4 select-none">
              Recomendaciones
            </span>
            <ol className="space-y-3 text-neutral-700 text-sm sm:text-base leading-relaxed list-decimal list-inside">
              {recommendations.map((rec, index) => (
                <li key={index} className="leading-relaxed">
                  {rec}
                </li>
              ))}
            </ol>
          </div>
        </>
      )}
    </div>
  );
}
