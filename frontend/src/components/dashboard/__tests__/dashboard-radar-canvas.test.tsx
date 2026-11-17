import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { DashboardRadarCanvas } from "../dashboard-radar-canvas";
import { HEAT_PALETTES, type EventConfig } from "@/lib/radar-constants";

const SAMPLE_EVENTS_CONFIG: Record<string, EventConfig> = {
  begin_checkout: {
    id: "begin_checkout",
    label: "INICIO DE CHECKOUT",
    technicalName: "begin_checkout",
    nodeX: 500,
    nodeY: 275,
    clusters: [
      {
        id: "pat-101",
        x: 578,
        y: 197,
        radius: 48,
        tier: "alta",
        ...HEAT_PALETTES.alta,
        name: "Modal de Login en Checkout",
        severity: "alta",
        impact: "-30.4 pp en avance · 379 sesiones perdidas",
        sessions: "1.156 ses",
        users: "890",
        sessionsCount: "1.156",
        diagnosis: "El modal de login impide continuar sin cuenta.",
        proximityLabel: "Criticidad alta",
        pulseDelay: "0s",
      },
    ],
  },
};

const SAMPLE_DISPLAY_NAMES: Record<string, string> = {
  begin_checkout: "Inicio de checkout",
};

describe("DashboardRadarCanvas Component", () => {
  it("renderiza el estado vacío cuando no hay evento seleccionado", async () => {
    const handleSelect = vi.fn();
    await act(async () => {
      render(
        <DashboardRadarCanvas
          selectedEventId={null}
          onSelectEvent={handleSelect}
          eventsConfig={SAMPLE_EVENTS_CONFIG}
          eventDisplayNames={SAMPLE_DISPLAY_NAMES}
        />
      );
    });

    expect(screen.getByText(/seleccioná un/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /cerrar/i })).not.toBeInTheDocument();
  });

  it("renderiza el radar interactivo cuando se selecciona un evento válido", async () => {
    const handleSelect = vi.fn();
    await act(async () => {
      render(
        <DashboardRadarCanvas
          selectedEventId="begin_checkout"
          onSelectEvent={handleSelect}
          eventsConfig={SAMPLE_EVENTS_CONFIG}
          eventDisplayNames={SAMPLE_DISPLAY_NAMES}
        />
      );
    });

    expect(screen.getByText("INICIO DE CHECKOUT")).toBeInTheDocument();

    const closeBtn = screen.getByRole("button", { name: /cerrar/i });
    expect(closeBtn).toBeInTheDocument();

    const clusterBtn = screen.getByRole("button", {
      name: /ver patrón de fricción: modal de login en checkout/i,
    });
    expect(clusterBtn).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(clusterBtn);
    });

    expect(screen.getByText("Diagnóstico del agente")).toBeInTheDocument();
    expect(screen.getByText("-30.4 pp en avance · 379 sesiones perdidas")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /explorar detalle/i })).toHaveAttribute(
      "href",
      "/dashboard/friccion/pat-101?event=begin_checkout"
    );

    const backBtn = screen.getByRole("button", { name: /volver/i });
    await act(async () => {
      fireEvent.click(backBtn);
    });

    expect(screen.queryByText("Diagnóstico del agente")).not.toBeInTheDocument();

    await act(async () => {
      fireEvent.click(closeBtn);
    });
    expect(handleSelect).toHaveBeenCalledWith(null);
  });

  it("maneja eventos desconocidos recurriendo al estado vacío", async () => {
    const handleSelect = vi.fn();
    await act(async () => {
      render(
        <DashboardRadarCanvas
          selectedEventId="inexistente"
          onSelectEvent={handleSelect}
          eventsConfig={SAMPLE_EVENTS_CONFIG}
          eventDisplayNames={SAMPLE_DISPLAY_NAMES}
        />
      );
    });

    expect(screen.getByText(/seleccioná un/i)).toBeInTheDocument();
  });
});
