import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, act } from '@testing-library/react';
import { AnalyticsConnectionGraphic } from '../analytics-connection-graphic';

describe('AnalyticsConnectionGraphic Component', () => {
  it('renderiza con estado de desconexión por defecto (isConnected = false, className vacía)', async () => {
    let container!: HTMLElement;
    await act(async () => {
      const res = render(<AnalyticsConnectionGraphic />);
      container = res.container;
    });

    const root = container.firstChild as HTMLElement;
    expect(root).toHaveAttribute('aria-hidden', 'true');

    // Estado desconectado: estilo eureka-primary en el nodo destino
    const disconnectedPing = container.querySelector('.bg-eureka-primary\\/20');
    expect(disconnectedPing).toBeInTheDocument();
    expect(disconnectedPing).toHaveClass('w-7', 'h-7');

    const emeraldPing = container.querySelector('.bg-emerald-500\\/25');
    expect(emeraldPing).not.toBeInTheDocument();
  });

  it('renderiza con estado conectado (isConnected = true)', async () => {
    let container!: HTMLElement;
    await act(async () => {
      const res = render(<AnalyticsConnectionGraphic isConnected={true} />);
      container = res.container;
    });

    // Estado conectado: estilo emerald en el nodo destino
    const connectedPing = container.querySelector('.bg-emerald-500\\/25');
    expect(connectedPing).toBeInTheDocument();
    expect(connectedPing).toHaveClass('w-9', 'h-9');

    const connectedBeacon = container.querySelector('.bg-emerald-600');
    expect(connectedBeacon).toBeInTheDocument();
  });

  it('aplica la clase className personalizada correctamente', async () => {
    let container!: HTMLElement;
    await act(async () => {
      const res = render(
        <AnalyticsConnectionGraphic className="custom-connection-class" />
      );
      container = res.container;
    });

    const root = container.firstChild as HTMLElement;
    expect(root).toHaveClass('custom-connection-class');
  });
});
