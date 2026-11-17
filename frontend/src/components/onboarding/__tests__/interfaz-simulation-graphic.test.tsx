import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { InterfazSimulationGraphic } from '../interfaz-simulation-graphic';

describe('InterfazSimulationGraphic Component', () => {
  it('renderiza la ventana de simulación del navegador con valores por defecto', async () => {
    let container!: HTMLElement;
    await act(async () => {
      const res = render(<InterfazSimulationGraphic />);
      container = res.container;
    });

    expect(screen.getByText('https://your.merch.google')).toBeInTheDocument();

    const root = container.firstChild as HTMLElement;
    expect(root).toHaveAttribute('aria-hidden', 'true');

    // Verifica que los iconos mockeados de lucide se renderizan
    const lockIcon = container.querySelector('[data-icon="Lock"]');
    const pointerIcon = container.querySelector('[data-icon="MousePointer2"]');
    expect(lockIcon).toBeInTheDocument();
    expect(pointerIcon).toBeInTheDocument();
  });

  it('aplica la clase className personalizada correctamente', async () => {
    let container!: HTMLElement;
    await act(async () => {
      const res = render(<InterfazSimulationGraphic className="custom-interfaz-class" />);
      container = res.container;
    });

    const root = container.firstChild as HTMLElement;
    expect(root).toHaveClass('custom-interfaz-class');
  });
});
