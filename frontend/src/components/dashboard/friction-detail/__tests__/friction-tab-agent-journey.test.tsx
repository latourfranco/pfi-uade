import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { FrictionTabAgentJourney } from "../friction-tab-agent-journey";
import { createMockFrictionDetail } from "./test-fixtures";

describe("FrictionTabAgentJourney Component", () => {
  it("renderiza los pasos del recorrido y permite navegar con botones y teclado", async () => {
    const detail = createMockFrictionDetail();
    await act(async () => {
      render(<FrictionTabAgentJourney data={detail} />);
    });

    expect(screen.getByText(/paso 1 de 2/i)).toBeInTheDocument();
    expect(screen.getByTestId("agent-journey-sticky-preview")).toHaveClass("lg:sticky", "lg:top-6");
    expect(screen.getByTestId("agent-journey-sticky-note")).toHaveClass("lg:sticky", "lg:top-6");
    expect(screen.getByText("Paso de contexto")).toBeInTheDocument();

    const nextBtn = screen.getByRole("button", { name: /paso siguiente/i });
    await act(async () => {
      fireEvent.click(nextBtn);
    });
    expect(screen.getByText(/paso 2 de 2/i)).toBeInTheDocument();
    expect(screen.getByText("Bloqueo en modal de login")).toBeInTheDocument();

    const prevBtn = screen.getByRole("button", { name: /paso anterior/i });
    await act(async () => {
      fireEvent.click(prevBtn);
    });
    expect(screen.getByText(/paso 1 de 2/i)).toBeInTheDocument();

    await act(async () => {
      fireEvent.keyDown(window, { key: "ArrowRight" });
    });
    expect(screen.getByText(/paso 2 de 2/i)).toBeInTheDocument();

    await act(async () => {
      fireEvent.keyDown(window, { key: "ArrowLeft" });
    });
    expect(screen.getByText(/paso 1 de 2/i)).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /ir al paso 2/i }));
    });
    expect(screen.getByText(/paso 2 de 2/i)).toBeInTheDocument();
  });

  it("ignora eventos de teclado cuando el foco está en un input", async () => {
    const detail = createMockFrictionDetail();
    await act(async () => {
      render(
        <div>
          <input aria-label="campo" />
          <FrictionTabAgentJourney data={detail} />
        </div>
      );
    });

    const input = screen.getByLabelText("campo");
    await act(async () => {
      fireEvent.keyDown(input, { key: "ArrowRight" });
    });
    expect(screen.getByText(/paso 1 de 2/i)).toBeInTheDocument();
  });

  it("muestra estado vacío cuando no hay pasos registrados", async () => {
    const detail = createMockFrictionDetail({
      agentJourney: { steps: [] },
    });
    await act(async () => {
      render(<FrictionTabAgentJourney data={detail} />);
    });

    expect(screen.getByText(/no hay pasos registrados para esta fricción/i)).toBeInTheDocument();
  });

  it("detecta vista mobile desde tipoDispositivo", async () => {
    const detail = createMockFrictionDetail({ tipoDispositivo: "mobile" });
    await act(async () => {
      render(<FrictionTabAgentJourney data={detail} />);
    });
    expect(screen.getByText(/paso 1 de 2/i)).toBeInTheDocument();
  });
});
