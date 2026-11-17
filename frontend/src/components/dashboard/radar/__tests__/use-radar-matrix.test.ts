import { describe, it, expect } from 'vitest';
import { calculateRadarMatrix } from '../use-radar-matrix';
import type { EventConfig } from '../../dashboard-radar-canvas';

describe('calculateRadarMatrix and useRadarMatrix', () => {
  it('genera una retícula base limpia y uniforme cuando no hay evento seleccionado', () => {
    const dots = calculateRadarMatrix(null, 50, 200, 150);

    expect(dots.length).toBeGreaterThan(0);
    for (const dot of dots) {
      expect(dot.radius).toBe(1.05);
      expect(dot.fill).toBe('#C4C3B8');
      expect(dot.opacity).toBe(0.35);
    }
  });

  it('utiliza los valores predeterminados de dimensiones y paso de grilla', () => {
    const dots = calculateRadarMatrix(null);
    expect(dots.length).toBeGreaterThan(100);
  });

  it('excluye los puntos ubicados dentro del radio despejado detrás del nodo central (< 18)', () => {
    const mockEvent: EventConfig = {
      id: 'evt-1',
      nodeX: 100,
      nodeY: 100,
      clusters: [],
    } as unknown as EventConfig;

    const dots = calculateRadarMatrix(mockEvent, 50, 300, 300);

    const exactCenterDot = dots.find((d) => d.x === 100 && d.y === 100);
    expect(exactCenterDot).toBeUndefined();
  });

  it('retorna puntos base cuando el array de clusters está vacío', () => {
    const mockEvent: EventConfig = {
      id: 'evt-empty',
      nodeX: 500,
      nodeY: 500,
      clusters: [],
    } as unknown as EventConfig;

    const dots = calculateRadarMatrix(mockEvent, 100, 400, 300);
    expect(dots.length).toBeGreaterThan(0);
    expect(dots[0].fill).toBe('#C4C3B8');
  });

  it('calcula los gradientes de calor en función de las distancias al cluster', () => {
    const palette = {
      hot: '#EF4444',
      mid: '#F97316',
      warm: '#FBBF24',
      soft: '#FDE68A',
    };

    const mockEvent: EventConfig = {
      id: 'evt-heat',
      nodeX: 10,
      nodeY: 10,
      clusters: [
        {
          x: 100,
          y: 100,
          radius: 40,
          dotPalettes: palette,
        },
      ],
    } as unknown as EventConfig;

    const dots = calculateRadarMatrix(mockEvent, 10, 250, 250);

    // heatRatio > 0.65 -> hot
    const hotDot = dots.find((d) => d.fill === palette.hot);
    expect(hotDot).toBeDefined();
    expect(hotDot?.opacity).toBe(0.95);
    expect(hotDot?.radius).toBe(1.95);

    // 0.4 < heatRatio <= 0.65 -> mid
    const midDot = dots.find((d) => d.fill === palette.mid);
    expect(midDot).toBeDefined();
    expect(midDot?.opacity).toBe(0.85);
    expect(midDot?.radius).toBe(1.6);

    // 0.2 < heatRatio <= 0.4 -> warm
    const warmDot = dots.find((d) => d.fill === palette.warm);
    expect(warmDot).toBeDefined();
    expect(warmDot?.opacity).toBe(0.65);
    expect(warmDot?.radius).toBe(1.35);

    // 0.05 < heatRatio <= 0.2 -> soft (0.45, 1.2)
    const softWarmDot = dots.find(
      (d) => d.fill === palette.soft && d.opacity === 0.45 && d.radius === 1.2
    );
    expect(softWarmDot).toBeDefined();

    // Fuera del radio de influencia -> neutro
    const neutralDot = dots.find((d) => d.fill === '#C4C3B8');
    expect(neutralDot).toBeDefined();
  });

  it('asigna soft default con opacity 0.38 y radius 1.15 cuando heatRatio <= 0.05', () => {
    const palette = {
      hot: '#EF4444',
      mid: '#F97316',
      warm: '#FBBF24',
      soft: '#FDE68A',
    };

    const mockEvent: EventConfig = {
      id: 'evt-edge-case',
      nodeX: 0,
      nodeY: 0,
      clusters: [
        {
          x: 100,
          y: 4,
          radius: 40,
          dotPalettes: palette,
        },
      ],
    } as unknown as EventConfig;

    const dots = calculateRadarMatrix(mockEvent, 100, 150, 150);
    const targetDot = dots.find((d) => d.x === 100 && d.y === 100);

    expect(targetDot).toBeDefined();
    expect(targetDot?.fill).toBe(palette.soft);
    expect(targetDot?.opacity).toBe(0.38);
    expect(targetDot?.radius).toBe(1.15);
  });

  it('resuelve correctamente la comparación de distancias entre múltiples clusters', () => {
    const palette = {
      hot: '#EF4444',
      mid: '#F97316',
      warm: '#FBBF24',
      soft: '#FDE68A',
    };

    const mockEvent: EventConfig = {
      id: 'evt-multi-cluster',
      nodeX: 0,
      nodeY: 0,
      clusters: [
        { x: 50, y: 50, radius: 20, dotPalettes: palette },
        { x: 500, y: 500, radius: 20, dotPalettes: palette },
      ],
    } as unknown as EventConfig;

    const dots = calculateRadarMatrix(mockEvent, 50, 600, 600);
    expect(dots.length).toBeGreaterThan(0);
  });
});
