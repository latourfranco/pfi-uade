import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, act } from '@testing-library/react';
import { RubroGridGraphic } from '../rubro-grid-graphic';

describe('RubroGridGraphic Component', () => {
  it('renderiza con los valores por defecto ("E-commerce" y className vacía)', async () => {
    let container!: HTMLElement;
    await act(async () => {
      const res = render(<RubroGridGraphic />);
      container = res.container;
    });

    const activeTiles = container.querySelectorAll('.bg-\\[\\#787DF6\\]');
    const inactiveTiles = container.querySelectorAll('.bg-white');

    // Grilla 4x3 = 12 baldosas en total. "E-commerce" tiene 2 activas y 10 inactivas
    expect(activeTiles.length).toBe(2);
    expect(inactiveTiles.length).toBe(10);
  });

  it('renderiza los patrones correspondientes para rubros válidos', async () => {
    const testCases: Record<string, number> = {
      Fintech: 4,
      Banca: 6,
      Viajes: 6,
      Entretenimiento: 4,
      SaaS: 6,
      Salud: 5,
      Educación: 4,
      Seguros: 8,
      Logística: 4,
      Otro: 4,
    };

    for (const [rubro, expectedActive] of Object.entries(testCases)) {
      let container!: HTMLElement;
      let unmountFn!: () => void;
      await act(async () => {
        const res = render(<RubroGridGraphic selectedRubro={rubro} />);
        container = res.container;
        unmountFn = res.unmount;
      });

      const activeTiles = container.querySelectorAll('.bg-\\[\\#787DF6\\]');
      expect(activeTiles.length).toBe(expectedActive);
      await act(async () => {
        unmountFn();
      });
    }
  });

  it('recurre al patrón "E-commerce" si selectedRubro es nulo, vacío o no existe', async () => {
    const invalidInputs = [null, '', 'RubroDesconocido'];

    for (const input of invalidInputs) {
      let container!: HTMLElement;
      let unmountFn!: () => void;
      await act(async () => {
        const res = render(<RubroGridGraphic selectedRubro={input} />);
        container = res.container;
        unmountFn = res.unmount;
      });

      const activeTiles = container.querySelectorAll('.bg-\\[\\#787DF6\\]');
      expect(activeTiles.length).toBe(2);
      await act(async () => {
        unmountFn();
      });
    }
  });

  it('aplica className personalizada y preserva aria-hidden', async () => {
    let container!: HTMLElement;
    await act(async () => {
      const res = render(<RubroGridGraphic className="custom-rubro-class" />);
      container = res.container;
    });

    const root = container.firstChild as HTMLElement;
    expect(root).toHaveClass('custom-rubro-class');
    expect(root).toHaveAttribute('aria-hidden', 'true');
  });
});
