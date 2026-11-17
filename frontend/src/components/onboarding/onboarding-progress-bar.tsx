"use client";

import { cn } from "@/lib/utils";

interface OnboardingProgressBarProps {
  currentStep: number;
  totalSteps?: number;
  className?: string;
}

export function OnboardingProgressBar({
  currentStep,
  totalSteps = 4,
  className = "",
}: OnboardingProgressBarProps) {
  const percentage = Math.round(
    Math.min(Math.max((currentStep / totalSteps) * 100, 0), 100)
  );

  return (
    <div
      className={cn("inline-flex items-center gap-3.5 select-none", className)}
      role="progressbar"
      aria-valuenow={currentStep}
      aria-valuemin={1}
      aria-valuemax={totalSteps}
      aria-label={`Paso ${currentStep} de ${totalSteps}`}
    >
      <div className="w-28 sm:w-32 md:w-36 h-1 bg-neutral-200/90 rounded-full overflow-hidden flex">
        <div
          className="h-full bg-eureka-primary rounded-full transition-all duration-500 ease-out"
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className="text-sm sm:text-[15px] font-medium text-neutral-600 tracking-tight whitespace-nowrap">
        Paso {currentStep} de {totalSteps}
      </span>
    </div>
  );
}
