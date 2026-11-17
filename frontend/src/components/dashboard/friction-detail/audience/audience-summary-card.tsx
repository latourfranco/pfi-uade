"use client";

interface AudienceSummaryCardProps {
  summary: string;
}

export function AudienceSummaryCard({ summary }: AudienceSummaryCardProps) {
  return (
    <div className="w-full bg-white rounded-2xl sm:rounded-[24px] border border-neutral-200/70 p-6 sm:p-8 md:p-10 shadow-[0_2px_12px_rgba(0,0,0,0.02)]">
      <span className="text-sm font-mono font-bold tracking-widest text-eureka-primary uppercase block mb-3 select-none">
        Quiénes son
      </span>
      <p className="text-neutral-800 text-sm sm:text-base leading-relaxed max-w-4xl font-normal">
        {summary}
      </p>
    </div>
  );
}
