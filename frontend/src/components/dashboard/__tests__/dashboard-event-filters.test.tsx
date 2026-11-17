import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { DashboardEventFilters } from "../dashboard-event-filters";
import type { EventItem } from "@/lib/radar-constants";

const SAMPLE_EVENTS: EventItem[] = [
  { id: "begin_checkout", name: "Inicio de checkout", count: 2 },
  { id: "add_to_cart", name: "Agregar al carrito", count: 1 },
];

describe("DashboardEventFilters Component", () => {
  it("renderiza estado vacío cuando no hay eventos detectados", async () => {
    const handleSelect = vi.fn();
    await act(async () => {
      render(<DashboardEventFilters selectedEventId={null} onSelectEvent={handleSelect} />);
    });

    expect(screen.getByText("FLUJOS CLAVE")).toBeInTheDocument();
    expect(
      screen.getByText(/no hay flujos clave con fricciones detectadas todavía/i)
    ).toBeInTheDocument();
  });

  it("renderiza la etiqueta de eventos y el botón no seleccionado", async () => {
    const handleSelect = vi.fn();
    await act(async () => {
      render(
        <DashboardEventFilters
          selectedEventId={null}
          onSelectEvent={handleSelect}
          events={SAMPLE_EVENTS}
        />
      );
    });

    const button = screen.getByRole("button", { name: /inicio de checkout/i });
    expect(button).toBeInTheDocument();
    expect(button.className).toContain("bg-[#EAEAF4]/80");
    expect(screen.getAllByTestId("flow-chip-pulse")).toHaveLength(2);

    fireEvent.click(button);
    expect(handleSelect).toHaveBeenCalledWith("begin_checkout");
  });

  it("renderiza el botón seleccionado y lo deselecciona al hacer click", async () => {
    const handleSelect = vi.fn();
    await act(async () => {
      render(
        <DashboardEventFilters
          selectedEventId="begin_checkout"
          onSelectEvent={handleSelect}
          events={SAMPLE_EVENTS}
        />
      );
    });

    const button = screen.getByRole("button", { name: /inicio de checkout/i });
    expect(button.className).toContain("bg-[#EEF2FF]");
    expect(screen.queryByTestId("flow-chip-pulse")).not.toBeInTheDocument();

    fireEvent.click(button);
    expect(handleSelect).toHaveBeenCalledWith(null);
  });
});
