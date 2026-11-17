import { describe, it, expect } from "vitest";
import { getRadialCoord, RADIAL_DISTANCES, HEAT_PALETTES } from "../radar-constants";

describe("radar-constants", () => {
  it("calcula coordenadas radiales alrededor del centro por defecto (500, 275)", () => {
    expect(getRadialCoord(100, 0)).toEqual({ x: 600, y: 275 });
    expect(getRadialCoord(100, 90)).toEqual({ x: 500, y: 375 });
    expect(getRadialCoord(50, 180, 200, 100)).toEqual({ x: 150, y: 100 });
  });

  it("define distancias y paletas para los tres niveles de criticidad", () => {
    expect(RADIAL_DISTANCES.alta).toBeLessThan(RADIAL_DISTANCES.media);
    expect(RADIAL_DISTANCES.media).toBeLessThan(RADIAL_DISTANCES.baja);
    expect(HEAT_PALETTES.alta.coreColor).toBeDefined();
    expect(HEAT_PALETTES.media.coreColor).toBeDefined();
    expect(HEAT_PALETTES.baja.coreColor).toBeDefined();
  });
});
