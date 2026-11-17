import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, act, waitFor } from '@testing-library/react';
import { StageDiagnosticsGraphic } from '../stage-diagnostics-graphic';

describe('StageDiagnosticsGraphic Component', () => {
  it('renderiza en estado pending con estilos neutros y sin destellos', async () => {
    let container!: HTMLElement;
    await act(async () => {
      const res = render(<StageDiagnosticsGraphic status="pending" />);
      container = res.container;
    });

    await waitFor(() => {
      expect(container.innerHTML).toContain('fill-neutral-200');
    });
    expect(container.querySelector('.animate-pipeline-sparkle')).not.toBeInTheDocument();
  });

  it('renderiza en estado active con halo ping y destello de chispa IA', async () => {
    let container!: HTMLElement;
    await act(async () => {
      const res = render(<StageDiagnosticsGraphic status="active" />);
      container = res.container;
    });

    await waitFor(() => {
      expect(container.querySelector('.animate-ping')).toBeInTheDocument();
    });
    expect(container.querySelector('.animate-pipeline-sparkle')).toBeInTheDocument();
  });

  it('renderiza en estado completed con badge de completado y sin destello activo', async () => {
    let container!: HTMLElement;
    await act(async () => {
      const res = render(<StageDiagnosticsGraphic status="completed" />);
      container = res.container;
    });

    await waitFor(() => {
      expect(container.querySelector('.zoom-in-50')).toBeInTheDocument();
    });
    expect(container.querySelector('.animate-pipeline-sparkle')).not.toBeInTheDocument();
    expect(container.innerHTML).toContain('#EEF2FF');
  });
});
