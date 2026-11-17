import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, act } from '@testing-library/react';
import { TamanoPyramidGraphic } from '../tamano-pyramid-graphic';

describe('TamanoPyramidGraphic Component', () => {
  it('renderiza con los valores por defecto ("1-49", fila 3 con 1 box activo)', async () => {
    let container!: HTMLElement;
    await act(async () => {
      const res = render(<TamanoPyramidGraphic />);
      container = res.container;
    });

    const activeBoxes = container.querySelectorAll('.bg-\\[\\#787DF6\\]');
    const inactiveBoxes = container.querySelectorAll('.bg-white');

    // Pirámide: 4 + 3 + 2 + 1 = 10 boxes totales. Fila 3 activa: 1 box activo, 9 inactivos
    expect(activeBoxes.length).toBe(1);
    expect(inactiveBoxes.length).toBe(9);
  });

  it('activa la fila correspondiente para cada tamaño válido', async () => {
    const testCases: Record<string, number> = {
      '+1000': 4, // Fila 0 activa (4 cajas)
      '250-999': 3, // Fila 1 activa (3 cajas)
      '50-249': 2, // Fila 2 activa (2 cajas)
      '1-49': 1, // Fila 3 activa (1 caja)
    };

    for (const [tamano, expectedActiveCount] of Object.entries(testCases)) {
      let container!: HTMLElement;
      let unmountFn!: () => void;
      await act(async () => {
        const res = render(<TamanoPyramidGraphic selectedTamano={tamano} />);
        container = res.container;
        unmountFn = res.unmount;
      });

      const activeBoxes = container.querySelectorAll('.bg-\\[\\#787DF6\\]');
      expect(activeBoxes.length).toBe(expectedActiveCount);
      await act(async () => {
        unmountFn();
      });
    }
  });

  it('recurre a "1-49" cuando selectedTamano es nulo, vacío o inexistente', async () => {
    const invalidInputs = [null, '', 'tamaño_desconocido'];

    for (const input of invalidInputs) {
      let container!: HTMLElement;
      let unmountFn!: () => void;
      await act(async () => {
        const res = render(<TamanoPyramidGraphic selectedTamano={input} />);
        container = res.container;
        unmountFn = res.unmount;
      });

      const activeBoxes = container.querySelectorAll('.bg-\\[\\#787DF6\\]');
      expect(activeBoxes.length).toBe(1);
      await act(async () => {
        unmountFn();
      });
    }
  });

  it('aplica className personalizada y atributo aria-hidden', async () => {
    let container!: HTMLElement;
    await act(async () => {
      const res = render(<TamanoPyramidGraphic className="custom-pyramid-class" />);
      container = res.container;
    });

    const root = container.firstChild as HTMLElement;
    expect(root).toHaveClass('custom-pyramid-class');
    expect(root).toHaveAttribute('aria-hidden', 'true');
  });
});
