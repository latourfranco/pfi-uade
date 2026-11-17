import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, act } from '@testing-library/react';
import { StageExtractionGraphic } from '../stage-extraction-graphic';

describe('StageExtractionGraphic Component', () => {
  it('renderiza en estado pending con estilos neutros y sin badge', async () => {
    let container: HTMLElement;
    await act(async () => {
      const res = render(<StageExtractionGraphic status="pending" />);
      container = res.container;
    });

    expect(container!.querySelector('.animate-ping')).not.toBeInTheDocument();
    expect(container!.querySelector('.animate-pipeline-packet-1')).not.toBeInTheDocument();
    expect(container!.innerHTML).toContain('fill-neutral-200');
  });

  it('renderiza en estado active con animación de halo ping y paquetes de datos', async () => {
    let container: HTMLElement;
    await act(async () => {
      const res = render(<StageExtractionGraphic status="active" />);
      container = res.container;
    });

    expect(container!.querySelector('.animate-ping')).toBeInTheDocument();
    expect(container!.querySelector('.animate-pipeline-packet-1')).toBeInTheDocument();
    expect(container!.querySelector('.animate-pipeline-packet-2')).toBeInTheDocument();
    expect(container!.querySelector('.animate-pipeline-packet-3')).toBeInTheDocument();
  });

  it('renderiza en estado completed con badge de check y círculos consolidados', async () => {
    let container: HTMLElement;
    await act(async () => {
      const res = render(<StageExtractionGraphic status="completed" />);
      container = res.container;
    });

    expect(container!.querySelector('.animate-ping')).not.toBeInTheDocument();
    expect(container!.querySelector('.zoom-in-50')).toBeInTheDocument();
    expect(container!.innerHTML).toContain('#EEF2FF');
  });
});
