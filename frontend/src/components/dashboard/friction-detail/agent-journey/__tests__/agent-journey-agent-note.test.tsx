import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { AgentJourneyAgentNote } from "../agent-journey-agent-note";
import { createMockFrictionDetail } from "../../__tests__/test-fixtures";

describe("AgentJourneyAgentNote Component", () => {
  it("renderiza nota LLM con insignias, coincidencia de cluster e ítems y sin píldora de estado", async () => {
    const detail = createMockFrictionDetail();
    const frictionStep = detail.agentJourney.steps[1];

    await act(async () => {
      render(<AgentJourneyAgentNote step={frictionStep} />);
    });

    expect(screen.getByText("Nota del agente")).toBeInTheDocument();
    expect(screen.queryByText("Fricción")).not.toBeInTheDocument();
    expect(screen.queryByText("Correcto")).not.toBeInTheDocument();
    expect(screen.queryByText("Alerta")).not.toBeInTheDocument();
    expect(screen.getByText(frictionStep.noteTitle)).toBeInTheDocument();
    expect(screen.getByText(frictionStep.noteDescription)).toBeInTheDocument();
    expect(screen.getByText("Bloqueo")).toBeInTheDocument();
    expect(screen.getByText("crítica")).toBeInTheDocument();
    expect(screen.getByText("Hoodie Clásico")).toBeInTheDocument();
    expect(screen.getByText("No")).toBeInTheDocument();
    expect(screen.queryByText("Tiempo en pantalla")).not.toBeInTheDocument();
  });

  it("renderiza etiqueta de contexto cuando enPatron es false", async () => {
    const detail = createMockFrictionDetail();
    const contextStep = detail.agentJourney.steps[0];

    await act(async () => {
      render(<AgentJourneyAgentNote step={contextStep} />);
    });

    expect(screen.getByText("Contexto del paso")).toBeInTheDocument();
    expect(screen.getByText(contextStep.noteTitle)).toBeInTheDocument();
  });
});
