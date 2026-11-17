"use client";

import { AudienceBreakdownCard } from "./audience/audience-breakdown-card";
import type { FrictionDetail } from "@/lib/friction-data";

interface FrictionTabAudienceProps {
  data: FrictionDetail;
}

export function FrictionTabAudience({ data }: FrictionTabAudienceProps) {
  const categories = data.audience?.categories ?? [];

  if (categories.length === 0) {
    return (
      <div className="w-full bg-white rounded-2xl sm:rounded-[24px] border border-neutral-200/70 p-8 text-center text-neutral-500">
        No hay datos de audiencia registrados para esta fricción.
      </div>
    );
  }

  return (
    <div className="w-full flex flex-col gap-5 sm:gap-6 animate-in fade-in duration-300">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
        {categories.map((category) => (
          <AudienceBreakdownCard key={category.title} category={category} />
        ))}
      </div>
    </div>
  );
}
