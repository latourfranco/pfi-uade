import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, act } from '@testing-library/react';
import { RadarListeningGraphic } from '../radar-listening-graphic';

describe('RadarListeningGraphic Component', () => {
  it('renderiza la geometría del radar de escucha con valores por defecto (className vacía)', async () => {
    let container!: HTMLElement;
    await act(async () => {
      const res = render(<RadarListeningGraphic />);
      container = res.container;
    });

    const root = container.firstChild as HTMLElement;
    expect(root).toHaveAttribute('aria-hidden', 'true');

    // Verifica que se renderiza el SVG con los círculos concéntricos
    const circles = container.querySelectorAll('circle');
    expect(circles.length).toBe(5);

    // Verifica el punto central
    const centerPoint = container.querySelector('.bg-eureka-dark');
    expect(centerPoint).toBeInTheDocument();
  });

  it('aplica la clase className personalizada correctamente', async () => {
    let container!: HTMLElement;
    await act(async () => {
      const res = render(<RadarListeningGraphic className="custom-radar-class" />);
      container = res.container;
    });

    const root = container.firstChild as HTMLElement;
    expect(root).toHaveClass('custom-radar-class');
  });
});
