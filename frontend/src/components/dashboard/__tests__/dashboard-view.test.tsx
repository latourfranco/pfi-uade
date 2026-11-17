import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { HEAT_PALETTES } from "@/lib/radar-constants";

const { mockGetDashboardRadarDataAction, mockUseSearchParams, mockReplace } = vi.hoisted(() => ({
  mockGetDashboardRadarDataAction: vi.fn(),
  mockUseSearchParams: vi.fn(),
  mockReplace: vi.fn(),
}));

vi.mock("@/app/actions/fricciones", () => ({
  getDashboardRadarDataAction: mockGetDashboardRadarDataAction,
}));

vi.mock("next/navigation", () => ({
  useSearchParams: mockUseSearchParams,
  useRouter: () => ({ replace: mockReplace }),
}));

import { DashboardView } from "../dashboard-view";

const MOCK_RADAR_RESPONSE = {
  detectedEvents: [{ id: "begin_checkout", name: "Inicio de checkout", count: 1 }],
  eventsConfig: {
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
          tier: "alta" as const,
          ...HEAT_PALETTES.alta,
          name: "Modal de Login en Checkout",
          severity: "alta" as const,
          impact: "-30.4 pp",
          sessions: "1.156 ses",
          users: "890",
          sessionsCount: "1.156",
          diagnosis: "Bloqueo en checkout.",
          proximityLabel: "Criticidad alta",
          pulseDelay: "0s",
          sesionesPerdidas: 289,
        },
      ],
    },
  },
  eventDisplayNames: {
    begin_checkout: "Inicio de checkout",
  },
  totalAffectedSessions: 1156,
};

describe("DashboardView Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseSearchParams.mockReturnValue(new URLSearchParams());
    mockGetDashboardRadarDataAction.mockResolvedValue(MOCK_RADAR_RESPONSE);
  });

  it("renderiza la vista principal con datos reales de la server action", async () => {
    render(<DashboardView />);

    expect(
      await screen.findByRole("heading", { name: /explorá dónde tu producto/i })
    ).toBeInTheDocument();

    expect(await screen.findByText("1 fricción")).toBeInTheDocument();
    expect(screen.getByText("1 flujo clave")).toBeInTheDocument();
    expect(screen.getByText("1.156 sesiones/mes")).toBeInTheDocument();
    expect(screen.getByText("25,0% de conversión")).toBeInTheDocument();
    expect(screen.getByText(/289 sesiones perdidas/i)).toBeInTheDocument();
    expect(screen.getByText(/para descubrir sus focos de/i)).toBeInTheDocument();
  });

  it("permite seleccionar y deseleccionar un evento mediante los filtros", async () => {
    render(<DashboardView />);

    const filterButton = await screen.findByRole("button", { name: /inicio de checkout/i });
    fireEvent.click(filterButton);

    expect(await screen.findByText("INICIO DE CHECKOUT")).toBeInTheDocument();
    expect(mockReplace).toHaveBeenCalledWith("/dashboard?event=begin_checkout", { scroll: false });

    fireEvent.click(filterButton);

    await waitFor(() => {
      expect(screen.queryByText("INICIO DE CHECKOUT")).not.toBeInTheDocument();
    });
    expect(mockReplace).toHaveBeenLastCalledWith("/dashboard", { scroll: false });
  });

  it("lee el parámetro de evento desde la URL inicial (?event=begin_checkout)", async () => {
    mockUseSearchParams.mockReturnValue(new URLSearchParams("event=begin_checkout"));

    render(<DashboardView />);

    expect(await screen.findByText("INICIO DE CHECKOUT")).toBeInTheDocument();
  });

  it("maneja fallo al cargar radar data sin romper la vista", async () => {
    mockGetDashboardRadarDataAction.mockRejectedValueOnce(new Error("Network error"));

    render(<DashboardView />);

    await waitFor(() => {
      expect(mockGetDashboardRadarDataAction).toHaveBeenCalledTimes(1);
    });
    expect(
      screen.getByText(/aún no detectamos fricciones activas en tus flujos clave/i)
    ).toBeInTheDocument();
  });

  it("pluraliza correctamente y hace fallback si no hay sesionesPerdidas", async () => {
    mockGetDashboardRadarDataAction.mockResolvedValueOnce({
      ...MOCK_RADAR_RESPONSE,
      detectedEvents: [
        { id: "begin_checkout", name: "Inicio de checkout", count: 2 },
        { id: "add_to_cart", name: "Agregar al carrito", count: 1 },
      ],
      eventsConfig: {},
      totalAffectedSessions: 2400,
    });

    render(<DashboardView />);

    expect(await screen.findByText("3 fricciones")).toBeInTheDocument();
    expect(screen.getByText("2 flujos clave")).toBeInTheDocument();
    expect(screen.getByText("2.400 sesiones/mes")).toBeInTheDocument();
    expect(screen.getByText(/recuperar usuarios antes del abandono/i)).toBeInTheDocument();
  });
});
