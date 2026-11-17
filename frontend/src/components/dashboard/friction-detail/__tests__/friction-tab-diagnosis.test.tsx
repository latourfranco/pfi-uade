import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { FrictionTabDiagnosis } from "../friction-tab-diagnosis";
import { createMockFrictionDetail } from "./test-fixtures";

describe("FrictionTabDiagnosis Component", () => {
  it("renderiza párrafos de diagnóstico, evidencias y recomendaciones", async () => {
    const detail = createMockFrictionDetail();
    await act(async () => {
      render(<FrictionTabDiagnosis data={detail} />);
    });

    expect(screen.getByText(detail.diagnosis.paragraphs[0])).toBeInTheDocument();
    expect(screen.getByText(detail.evidence[0])).toBeInTheDocument();
    expect(screen.getByText("Recomendaciones")).toBeInTheDocument();
    expect(screen.getByText(detail.recommendations![0])).toBeInTheDocument();
  });

  it("muestra fallbacks vacíos cuando no hay párrafos ni evidencias ni recomendaciones", async () => {
    const detail = createMockFrictionDetail({
      diagnosis: { paragraphs: [] },
      evidence: [],
      recommendations: [],
    });
    await act(async () => {
      render(<FrictionTabDiagnosis data={detail} />);
    });

    expect(screen.getByText(/sin párrafos de diagnóstico registrados/i)).toBeInTheDocument();
    expect(screen.getByText(/sin evidencias registradas/i)).toBeInTheDocument();
    expect(screen.queryByText("Recomendaciones")).not.toBeInTheDocument();
  });

  it("maneja propiedades diagnosis, evidence y recommendations indefinidas", async () => {
    const detail = createMockFrictionDetail({
      diagnosis: undefined as unknown as ReturnType<typeof createMockFrictionDetail>["diagnosis"],
      evidence: undefined as unknown as string[],
      recommendations: undefined,
    });
    await act(async () => {
      render(<FrictionTabDiagnosis data={detail} />);
    });

    expect(screen.getByText(/sin párrafos de diagnóstico registrados/i)).toBeInTheDocument();
    expect(screen.getByText(/sin evidencias registradas/i)).toBeInTheDocument();
  });
});
