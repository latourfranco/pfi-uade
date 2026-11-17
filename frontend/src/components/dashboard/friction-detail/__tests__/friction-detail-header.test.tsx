import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";
import * as navigation from "next/navigation";
import { FrictionDetailHeader } from "../friction-detail-header";
import { createMockFrictionDetail } from "./test-fixtures";
import * as exportUtils from "@/lib/export-friction-findings";

describe("FrictionDetailHeader Component", () => {
  beforeEach(() => {
    vi.spyOn(navigation, "useSearchParams").mockReturnValue(
      new URLSearchParams() as unknown as ReturnType<typeof navigation.useSearchParams>
    );
  });

  it("renderiza título, bajada, pérdida de conversión destacada y métricas reales", async () => {
    const detail = createMockFrictionDetail({
      caidaPuntosPorcentuales: 30.4,
      sesionesPerdidas: 379.4,
    });
    await act(async () => {
      render(<FrictionDetailHeader data={detail} eventId="begin_checkout" />);
    });

    expect(screen.getByText(detail.title)).toBeInTheDocument();
    expect(screen.getByText(detail.subtitle)).toBeInTheDocument();
    expect(
      screen.getByText("-30,4 pp de conversión · 379 sesiones perdidas")
    ).toBeInTheDocument();
    expect(screen.queryByText("Vista de página")).not.toBeInTheDocument();
    expect(screen.queryByText("Inicio de checkout")).not.toBeInTheDocument();
    expect(screen.getByText("32,7%")).toBeInTheDocument();
    expect(screen.getByText("890")).toBeInTheDocument();
    expect(screen.getByText("1.156")).toBeInTheDocument();

    const backLink = screen.getByRole("link", { name: /volver/i });
    expect(backLink).toHaveAttribute("href", "/dashboard?event=begin_checkout");
  });

  it("usa impactoResumen como respaldo cuando no hay caidaPuntosPorcentuales", async () => {
    const detail = createMockFrictionDetail({
      caidaPuntosPorcentuales: null,
      impactoResumen: "-15,2 pp de conversión",
    });
    await act(async () => {
      render(<FrictionDetailHeader data={detail} eventId="begin_checkout" />);
    });

    expect(screen.getByText("-15,2 pp de conversión")).toBeInTheDocument();
  });

  it("muestra conversión sin sesiones perdidas si sesionesPerdidas es null", async () => {
    const detail = createMockFrictionDetail({
      caidaPuntosPorcentuales: 12.5,
      sesionesPerdidas: null,
    });
    await act(async () => {
      render(<FrictionDetailHeader data={detail} eventId="begin_checkout" />);
    });

    expect(screen.getByText("-12,5 pp de conversión")).toBeInTheDocument();
  });

  it("usa eventoClave del modelo cuando no se pasa eventId ni query param", async () => {
    const detail = createMockFrictionDetail({
      eventoClave: "add_to_cart",
      impactoResumen: null,
      secuenciaNombres: [],
    });
    await act(async () => {
      render(<FrictionDetailHeader data={detail} />);
    });

    expect(screen.getByRole("link", { name: /volver/i })).toHaveAttribute(
      "href",
      "/dashboard?event=add_to_cart"
    );
  });

  it("vuelve a /dashboard si no hay evento en props, query ni modelo", async () => {
    const detail = createMockFrictionDetail({
      eventoClave: null,
      impactoResumen: null,
      secuenciaNombres: [],
    });
    await act(async () => {
      render(<FrictionDetailHeader data={detail} />);
    });

    expect(screen.getByRole("link", { name: /volver/i })).toHaveAttribute("href", "/dashboard");
  });

  it("permite exportar los hallazgos desde el botón del encabezado", async () => {
    const downloadSpy = vi
      .spyOn(exportUtils, "downloadFrictionFindings")
      .mockResolvedValue(undefined);
    const detail = createMockFrictionDetail();

    await act(async () => {
      render(<FrictionDetailHeader data={detail} />);
    });

    const exportBtn = screen.getByRole("button", { name: /exportar hallazgos/i });
    await act(async () => {
      fireEvent.click(exportBtn);
    });

    expect(downloadSpy).toHaveBeenCalledWith(detail);
    downloadSpy.mockRestore();
  });
});
