import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { RadarEmptyState } from '../radar-empty-state';

describe('RadarEmptyState Component', () => {
  it('renderiza el mensaje de instrucción y las ondas de radar', async () => {
    let container!: HTMLElement;
    await act(async () => {
      const res = render(<RadarEmptyState />);
      container = res.container;
    });

    expect(
      screen.getByText(/seleccioná un/i)
    ).toBeInTheDocument();
    expect(screen.getByText("flujo clave")).toBeInTheDocument();

    const svg = container.querySelector('svg');
    expect(svg).toBeInTheDocument();
  });
});
