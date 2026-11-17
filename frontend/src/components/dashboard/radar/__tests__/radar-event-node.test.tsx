import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { RadarEventNode } from '../radar-event-node';

describe('RadarEventNode Component', () => {
  it('renderiza la etiqueta del evento y los elementos visuales centrales', async () => {
    let container!: HTMLElement;
    await act(async () => {
      const res = render(<RadarEventNode label="FICHA DE PRODUCTO" />);
      container = res.container;
    });

    expect(screen.getByText('FICHA DE PRODUCTO')).toBeInTheDocument();

    const halo = container.querySelector('.animate-halo-pulse');
    expect(halo).toBeInTheDocument();
  });
});
