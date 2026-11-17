import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { DashboardMetricsBar } from "../dashboard-metrics-bar";

describe("DashboardMetricsBar Component", () => {
  it("renderiza métricas en cero por defecto cuando no hay datos", async () => {
    await act(async () => {
      render(<DashboardMetricsBar />);
    });

    expect(screen.getAllByText("0").length).toBe(3);
    expect(screen.getByText("fricciones identificadas")).toBeInTheDocument();
    expect(screen.getByText("sesiones/mes afectadas")).toBeInTheDocument();
    expect(screen.getByText("eventos clave involucrados")).toBeInTheDocument();
  });

  it("renderiza correctamente etiquetas en singular y valores dinámicos", async () => {
    await act(async () => {
      render(
        <DashboardMetricsBar
          frictionsCount={1}
          sessionsAffected="1.156"
          eventsCount={1}
        />
      );
    });

    expect(screen.getAllByText("1").length).toBe(2);
    expect(screen.getByText("fricción identificada")).toBeInTheDocument();
    expect(screen.getByText("1.156")).toBeInTheDocument();
    expect(screen.getByText("evento clave involucrado")).toBeInTheDocument();
  });

  it("aplica las clases de borde divisor condicional para los elementos intermedios", async () => {
    let container!: HTMLElement;
    await act(async () => {
      const res = render(
        <DashboardMetricsBar frictionsCount={3} sessionsAffected="2.500" eventsCount={2} />
      );
      container = res.container;
    });

    const metricItems = container.querySelectorAll(".font-mono.font-bold");
    expect(metricItems.length).toBe(3);

    const firstWrapper = metricItems[0].parentElement;
    expect(firstWrapper?.className).toContain("border-b");

    const lastWrapper = metricItems[2].parentElement;
    expect(lastWrapper?.className).not.toContain("border-b");
  });
});
