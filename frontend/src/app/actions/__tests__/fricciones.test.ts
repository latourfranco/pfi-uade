import { describe, it, expect, vi, beforeEach } from "vitest";

const { mockGetRadarData } = vi.hoisted(() => ({
  mockGetRadarData: vi.fn(),
}));

vi.mock("@/repositories/friccion.repository", () => ({
  FriccionRepository: {
    getRadarData: mockGetRadarData,
  },
}));

import { getDashboardRadarDataAction } from "../fricciones";
import { DEFAULT_CLIENTE_ID } from "@/lib/constants";

describe("getDashboardRadarDataAction", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("retorna los datos del radar usando DEFAULT_CLIENTE_ID cuando no se pasa clienteId", async () => {
    const expected = {
      detectedEvents: [{ id: "begin_checkout", name: "Inicio de checkout", count: 1 }],
      eventsConfig: {},
      eventDisplayNames: { begin_checkout: "Inicio de checkout" },
      totalAffectedSessions: 500,
    };
    mockGetRadarData.mockResolvedValueOnce(expected);

    const res = await getDashboardRadarDataAction();

    expect(mockGetRadarData).toHaveBeenCalledWith(DEFAULT_CLIENTE_ID);
    expect(res).toEqual(expected);
  });

  it("pasa el clienteId explícito al repositorio", async () => {
    mockGetRadarData.mockResolvedValueOnce({
      detectedEvents: [],
      eventsConfig: {},
      eventDisplayNames: {},
      totalAffectedSessions: 0,
    });

    await getDashboardRadarDataAction("custom-client-uuid");
    expect(mockGetRadarData).toHaveBeenCalledWith("custom-client-uuid");
  });

  it("retorna estructura vacía si el repositorio lanza una excepción", async () => {
    mockGetRadarData.mockRejectedValueOnce(new Error("Unexpected failure"));

    const res = await getDashboardRadarDataAction();

    expect(res).toEqual({
      detectedEvents: [],
      eventsConfig: {},
      eventDisplayNames: {},
      totalAffectedSessions: 0,
    });
  });
});
