import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import * as navigation from "next/navigation";
import { FrictionDetailView } from "../friction-detail-view";
import { createMockFrictionDetail } from "./test-fixtures";

describe("FrictionDetailView Component", () => {
  beforeEach(() => {
    vi.spyOn(navigation, "useSearchParams").mockReturnValue(
      new URLSearchParams() as unknown as ReturnType<typeof navigation.useSearchParams>
    );
  });

  it("renderiza el recorrido por defecto y permite alternar entre las 3 pestañas", async () => {
    const detail = createMockFrictionDetail();
    await act(async () => {
      render(<FrictionDetailView data={detail} eventId="begin_checkout" />);
    });

    expect(screen.getByText("Línea temporal · 2 pasos")).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /diagnóstico/i }));
    });
    expect(screen.getByText(detail.diagnosis.paragraphs[0])).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /quiénes son/i }));
    });
    expect(screen.getByText("DISPOSITIVO")).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /recorrido del agente/i }));
    });
    expect(screen.getByText("Línea temporal · 2 pasos")).toBeInTheDocument();
  });
});
