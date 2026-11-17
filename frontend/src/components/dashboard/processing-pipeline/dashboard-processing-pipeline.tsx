"use client";

import React, { useState, useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import { StageExtractionGraphic } from "./stage-extraction-graphic";
import { StageFrictionGraphic } from "./stage-friction-graphic";
import { StagePathsGraphic } from "./stage-paths-graphic";
import { StageDiagnosticsGraphic } from "./stage-diagnostics-graphic";
import { PipelineArrowConnector } from "./pipeline-arrow-connector";
import { CheckCircle2 } from "lucide-react";

interface PipelineStageConfig {
  id: string;
  title: string;
  graphic: React.ComponentType<{ status: "pending" | "active" | "completed" }>;
}

const STAGES: PipelineStageConfig[] = [
  {
    id: "extraction",
    title: "Extracción de datos de navegación",
    graphic: StageExtractionGraphic,
  },
  {
    id: "friction",
    title: "Detección de patrones de fricción",
    graphic: StageFrictionGraphic,
  },
  {
    id: "paths",
    title: "Exploración de rutas",
    graphic: StagePathsGraphic,
  },
  {
    id: "diagnostics",
    title: "Generación de diagnósticos",
    graphic: StageDiagnosticsGraphic,
  },
];

interface StageNodeProps {
  stage: PipelineStageConfig;
  index: number;
  status: "pending" | "active" | "completed";
}

function StageNode({ stage, index, status }: StageNodeProps) {
  const GraphicComponent = stage.graphic;
  const isCurrent = status === "active";
  const isDone = status === "completed";
  const isPending = status === "pending";

  return (
    <div className="flex flex-col items-center text-center w-40 sm:w-44 lg:w-48 shrink-0 group">
      {/* Elemento Gráfico (Box) */}
      <div className="mb-3 transition-transform duration-300 group-hover:scale-105">
        <GraphicComponent status={status} />
      </div>

      {/* Número y Título de Etapa */}
      <div className="flex flex-col items-center px-1 w-full">
        <span
          className={cn(
            "text-sm uppercase tracking-wider font-bold mb-1 transition-colors duration-300",
            isDone && "text-eureka-primary font-semibold",
            isCurrent && "text-eureka-primary font-bold",
            isPending && "text-neutral-400 font-medium"
          )}
        >
          Etapa {index + 1}
        </span>
        <p
          className={cn(
            "text-xs sm:text-sm leading-snug font-medium transition-colors duration-300",
            isDone && "text-neutral-900 font-semibold",
            isCurrent && "text-eureka-dark font-bold",
            isPending && "text-neutral-400 font-normal"
          )}
        >
          {stage.title}
        </p>
      </div>
    </div>
  );
}

interface DashboardProcessingPipelineProps {
  stageDurationMs?: number;
  onComplete?: () => void;
  className?: string;
}

export function DashboardProcessingPipeline({
  stageDurationMs = 2000,
  onComplete,
  className = "",
}: DashboardProcessingPipelineProps) {
  const [currentStageIndex, setCurrentStageIndex] = useState<number>(0);
  const [progress, setProgress] = useState<number>(0);
  const onCompleteRef = useRef(onComplete);
  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);
  const isFinishedRef = useRef(false);

  const totalDuration = stageDurationMs * STAGES.length;

  useEffect(() => {
    if (isFinishedRef.current) return;
    const startTime = Date.now();

    const interval = setInterval(() => {
      if (isFinishedRef.current) {
        clearInterval(interval);
        return;
      }

      const elapsed = Date.now() - startTime;
      const currentPct = Math.min(100, Math.floor((elapsed / totalDuration) * 100));
      setProgress(currentPct);

      const calculatedStage = Math.min(
        STAGES.length,
        Math.floor(elapsed / stageDurationMs)
      );
      setCurrentStageIndex(calculatedStage);

      if (elapsed >= totalDuration) {
        clearInterval(interval);
        isFinishedRef.current = true;
        setCurrentStageIndex(STAGES.length);
        setProgress(100);

        // Retardo de 2 segundos al finalizar para apreciar el estado completo al 100%
        const completeTimeout = setTimeout(() => {
          onCompleteRef.current?.();
        }, 2000);

        return () => clearTimeout(completeTimeout);
      }
    }, 60);

    return () => clearInterval(interval);
  }, [stageDurationMs, totalDuration]);

  const isAllCompleted = currentStageIndex >= STAGES.length;
  const activeStage = isAllCompleted
    ? {
      title: "Análisis completado con éxito",
      subtitle: "Cargando tu panorama de fricción...",
    }
    : STAGES[currentStageIndex];

  const getStageStatus = (index: number): "pending" | "active" | "completed" => {
    if (index < currentStageIndex || isAllCompleted) {
      return "completed";
    }
    if (index === currentStageIndex) {
      return "active";
    }
    return "pending";
  };

  const mobileStageIndex = Math.min(currentStageIndex, STAGES.length - 1);

  return (
    <div
      className={cn(
        "w-full max-w-5xl mx-auto flex flex-col items-center select-none",
        className
      )}
    >
      {/* Badge de Etapa / Estado Superior */}
      <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-neutral-100 border border-eureka-primary transition-all duration-300">
        {!isAllCompleted ? (
          <>
            <span className="w-2 h-2 rounded-full bg-eureka-primary animate-pulse" />
            <span className="text-xs sm:text-sm font-semibold text-eureka-primary">
              Etapa {currentStageIndex + 1} de {STAGES.length}
            </span>
          </>
        ) : (
          <>
            <CheckCircle2 className="w-4 h-4 text-eureka-primary" />
            <span className="text-xs sm:text-sm font-bold text-eureka-primary">
              Procesamiento finalizado (100%)
            </span>
          </>
        )}
      </div>

      {/* Titular Dinámico de la Etapa */}
      <div className="text-center max-w-2xl px-4 mb-10 min-h-20 sm:min-h-24 flex flex-col justify-center">
        <h2 className="text-2xl sm:text-3xl md:text-4xl font-bold text-eureka-dark tracking-tight leading-tight mb-2 transition-all duration-300">
          {activeStage.title}
        </h2>
      </div>

      {/* 1. Disposición para Pantallas Grandes (Desktop lg+: 4 etapas con flechas perfectamente centradas vertical y horizontalmente) */}
      <div className="hidden lg:flex flex-row items-start justify-center px-4 mb-10 sm:mb-12 w-full">
        {STAGES.map((stage, index) => (
          <React.Fragment key={stage.id}>
            <StageNode
              stage={stage}
              index={index}
              status={getStageStatus(index)}
            />

            {index < STAGES.length - 1 && (
              <div className="h-24 sm:h-28 flex items-center justify-center flex-1 max-w-16 min-w-8 px-1">
                <PipelineArrowConnector
                  status={
                    index < currentStageIndex
                      ? "completed"
                      : index === currentStageIndex
                        ? "active"
                        : "pending"
                  }
                />
              </div>
            )}
          </React.Fragment>
        ))}
      </div>

      {/* 2. Disposición para Pantallas Intermedias (Tablet md a lg: 2 columnas, 2 filas con flechas centradas) */}
      <div className="hidden md:flex lg:hidden flex-col items-center gap-8 mb-10 w-full max-w-lg">
        {/* Fila 1: Etapa 1 -> Etapa 2 */}
        <div className="flex flex-row items-start justify-between w-full">
          <StageNode
            stage={STAGES[0]}
            index={0}
            status={getStageStatus(0)}
          />
          <div className="h-24 sm:h-28 flex items-center justify-center flex-1 px-3">
            <PipelineArrowConnector
              status={
                currentStageIndex > 0
                  ? "completed"
                  : currentStageIndex === 0
                    ? "active"
                    : "pending"
              }
            />
          </div>
          <StageNode
            stage={STAGES[1]}
            index={1}
            status={getStageStatus(1)}
          />
        </div>

        {/* Fila 2: Etapa 3 -> Etapa 4 */}
        <div className="flex flex-row items-start justify-between w-full">
          <StageNode
            stage={STAGES[2]}
            index={2}
            status={getStageStatus(2)}
          />
          <div className="h-24 sm:h-28 flex items-center justify-center flex-1 px-3">
            <PipelineArrowConnector
              status={
                currentStageIndex > 2
                  ? "completed"
                  : currentStageIndex === 2
                    ? "active"
                    : "pending"
              }
            />
          </div>
          <StageNode
            stage={STAGES[3]}
            index={3}
            status={getStageStatus(3)}
          />
        </div>
      </div>

      {/* 3. Disposición para Pantallas Pequeñas (Mobile < md: 1 sola etapa centrada que se reemplaza dinámicamente) */}
      <div className="flex md:hidden flex-col items-center justify-center mb-10 w-full px-4">
        <div
          key={mobileStageIndex}
          className="flex flex-col items-center text-center animate-in fade-in zoom-in-95 duration-400 slide-in-from-bottom-2"
        >
          <StageNode
            stage={STAGES[mobileStageIndex]}
            index={mobileStageIndex}
            status={getStageStatus(mobileStageIndex)}
          />
        </div>

        {/* Indicador de pasos tipo pills para mobile */}
        <div className="flex items-center gap-2 mt-5">
          {STAGES.map((_, i) => (
            <div
              key={i}
              className={cn(
                "h-1.5 rounded-full transition-all duration-300",
                i === mobileStageIndex
                  ? "w-6 bg-eureka-primary"
                  : i < mobileStageIndex || isAllCompleted
                    ? "w-2 bg-eureka-primary/60"
                    : "w-2 bg-neutral-300"
              )}
            />
          ))}
        </div>
      </div>

      {/* Barra de Progreso General con Porcentaje */}
      <div className="w-full max-w-md px-4 flex flex-col items-center">
        <div className="w-full flex items-center justify-between text-xs font-semibold text-neutral-500 mb-2">
          <span>Progreso global</span>
          <span className="text-eureka-primary font-bold">{progress}%</span>
        </div>

        <div
          className="w-full h-2 rounded-full bg-neutral-200/80 overflow-hidden relative"
          role="progressbar"
          aria-valuenow={progress}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div
            className="h-full bg-eureka-primary rounded-full transition-all duration-300 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
    </div>
  );
}
