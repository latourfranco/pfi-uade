import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { RadarClusterGroup } from '../radar-cluster-group';
import type { FrictionCluster } from '../../dashboard-radar-canvas';

const mockCluster: FrictionCluster = {
  id: 'test-clust-1',
  x: 100,
  y: 200,
  radius: 30,
  tier: 'alta',
  coreColor: '#DC2626',
  auraGradientColor: 'rgba(220, 38, 38, 0.55)',
  dotPalettes: {
    hot: '#DC2626',
    mid: '#EF4444',
    warm: '#F87171',
    soft: '#FCA5A5',
  },
  name: 'Fricción en Checkout',
  severity: 'alta',
  impact: '-20%',
  sessions: '1.200',
  users: '800',
  sessionsCount: '1.200',
  diagnosis: 'Problema en botón',
  proximityLabel: 'Alta',
  pulseDelay: '0.4s',
};

describe('RadarClusterGroup Component', () => {
  it('renderiza dentro de SVG y responde a eventos de click', async () => {
    const handleSelect = vi.fn();

    await act(async () => {
      render(
        <svg>
          <RadarClusterGroup cluster={mockCluster} onSelect={handleSelect} />
        </svg>
      );
    });

    const button = screen.getByRole('button', { name: /ver patrón de fricción: fricción en checkout/i });
    expect(button).toBeInTheDocument();

    fireEvent.click(button);
    expect(handleSelect).toHaveBeenCalledWith(mockCluster);
  });

  it('soporta navegación y selección mediante teclado (Enter y Espacio)', async () => {
    const handleSelect = vi.fn();

    await act(async () => {
      render(
        <svg>
          <RadarClusterGroup cluster={mockCluster} onSelect={handleSelect} />
        </svg>
      );
    });

    const button = screen.getByRole('button', { name: /ver patrón de fricción: fricción en checkout/i });

    // Enter
    fireEvent.keyDown(button, { key: 'Enter' });
    expect(handleSelect).toHaveBeenCalledTimes(1);

    // Espacio
    fireEvent.keyDown(button, { key: ' ' });
    expect(handleSelect).toHaveBeenCalledTimes(2);

    // Otra tecla
    fireEvent.keyDown(button, { key: 'ArrowDown' });
    expect(handleSelect).toHaveBeenCalledTimes(2);
  });

  it('aplica el valor por defecto de pulseDelay cuando no se provee', async () => {
    const clusterWithoutDelay: FrictionCluster = {
      ...mockCluster,
      id: 'cluster-no-delay',
      pulseDelay: undefined,
    };

    let container!: HTMLElement;
    await act(async () => {
      const res = render(
        <svg>
          <RadarClusterGroup cluster={clusterWithoutDelay} onSelect={vi.fn()} />
        </svg>
      );
      container = res.container;
    });

    const auraGroup = container.querySelector('.animate-aura-pulse') as HTMLElement;
    expect(auraGroup.style.animationDelay).toBe('0s');
  });
});
