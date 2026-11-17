import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { FrictionTabAudience } from "../friction-tab-audience";
import { createMockFrictionDetail } from "./test-fixtures";

describe("FrictionTabAudience Component", () => {
  it("renderiza las tarjetas de distribución sin la tarjeta de resumen", async () => {
    const detail = createMockFrictionDetail();
    await act(async () => {
      render(<FrictionTabAudience data={detail} />);
    });

    expect(screen.queryByText(detail.audience.summary)).not.toBeInTheDocument();
    expect(screen.getByText("DISPOSITIVO")).toBeInTheDocument();
    expect(screen.getByText("UBICACIÓN")).toBeInTheDocument();
  });

  it("muestra estado vacío cuando no hay categorías de audiencia", async () => {
    const detail = createMockFrictionDetail({
      audience: { summary: "Resumen ignorado", categories: [] },
    });
    await act(async () => {
      render(<FrictionTabAudience data={detail} />);
    });

    expect(
      screen.getByText(/no hay datos de audiencia registrados para esta fricción/i)
    ).toBeInTheDocument();
  });

  it("muestra estado vacío cuando audience es undefined", async () => {
    const detail = createMockFrictionDetail();
    const withoutAudience = { ...detail, audience: undefined } as unknown as typeof detail;

    await act(async () => {
      render(<FrictionTabAudience data={withoutAudience} />);
    });

    expect(
      screen.getByText(/no hay datos de audiencia registrados para esta fricción/i)
    ).toBeInTheDocument();
  });
});
