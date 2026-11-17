import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { AgentJourneyTimeline } from "../agent-journey-timeline";
import { createMockFrictionDetail } from "../../__tests__/test-fixtures";

describe("AgentJourneyTimeline Component", () => {
  it("renderiza pasos diferenciando contexto y punto de fricción y permite seleccionarlos", async () => {
    const detail = createMockFrictionDetail();
    const steps = [
      ...detail.agentJourney.steps,
      {
        ...detail.agentJourney.steps[1],
        stepNumber: 3,
        title: "Paso en patrón sin fricción",
        status: "warning" as const,
        enPatron: true,
        friccionDetectada: false,
      },
      {
        ...detail.agentJourney.steps[1],
        stepNumber: 4,
        title: "Paso fuera de patrón",
        status: "success" as const,
        enPatron: false,
        friccionDetectada: false,
      },
    ];
    const onSelectStep = vi.fn();

    await act(async () => {
      render(
        <AgentJourneyTimeline
          steps={steps}
          selectedStepIndex={0}
          onSelectStep={onSelectStep}
        />
      );
    });

    expect(screen.getByText("Línea temporal · 4 pasos")).toBeInTheDocument();
    expect(screen.getAllByText("Contexto")).toHaveLength(2);
    expect(screen.getByText("Fricción")).toBeInTheDocument();

    // Paso 1 (contexto, seleccionado): gris/oscuro
    expect(screen.getByText("1").className).toContain("bg-neutral-700");
    // Paso 2 (mayor fricción, no seleccionado): rojo destacado
    expect(screen.getByText("2").className).toContain("bg-red-600");
    expect(screen.getByText("2").className).toContain("ring-red-200");
    // Paso 3 (en_patron === true, no seleccionado): rojo suave
    expect(screen.getByText("3").className).toContain("bg-red-50");
    expect(screen.getByText("3").className).toContain("text-red-600");
    // Paso 4 (fuera de patrón, no seleccionado): blanco/gris (sin verde)
    expect(screen.getByText("4").className).toContain("bg-white");
    expect(screen.getByText("4").className).toContain("text-neutral-400");

    await act(async () => {
      fireEvent.click(screen.getByText("Paso en patrón sin fricción"));
    });
    expect(onSelectStep).toHaveBeenCalledWith(2);
  });

  it("aplica colores activos para paso en patrón y paso con fricción seleccionada", async () => {
    const detail = createMockFrictionDetail();
    const steps = [
      {
        ...detail.agentJourney.steps[1],
        stepNumber: 1,
        enPatron: true,
        friccionDetectada: false,
      },
      {
        ...detail.agentJourney.steps[1],
        stepNumber: 2,
        enPatron: true,
        friccionDetectada: true,
      },
    ];

    let rerender!: (ui: React.ReactElement) => void;
    await act(async () => {
      const res = render(
        <AgentJourneyTimeline
          steps={steps}
          selectedStepIndex={0}
          onSelectStep={vi.fn()}
        />
      );
      rerender = res.rerender;
    });

    expect(screen.getByText("1").className).toContain("bg-red-500");

    await act(async () => {
      rerender(
        <AgentJourneyTimeline
          steps={steps}
          selectedStepIndex={1}
          onSelectStep={vi.fn()}
        />
      );
    });

    expect(screen.getByText("2").className).toContain("bg-red-600");
    expect(screen.getByText("2").className).toContain("ring-4");
  });
});
