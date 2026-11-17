import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, act } from '@testing-library/react';
import { StagePathsGraphic } from '../stage-paths-graphic';

describe('StagePathsGraphic Component', () => {
  it('renderiza en estado pending con traza punteada y sin cursor animado', async () => {
    let container: HTMLElement;
    await act(async () => {
      const res = render(<StagePathsGraphic status="pending" />);
      container = res.container;
    });

    expect(container!.querySelector('.stroke-dashed')).toBeInTheDocument();
    expect(container!.querySelector('.animate-web-cursor')).not.toBeInTheDocument();
    expect(container!.innerHTML).toContain('fill-neutral-200');
  });

  it('renderiza en estado active con cursor animado y ondas de click', async () => {
    let container: HTMLElement;
    await act(async () => {
      const res = render(<StagePathsGraphic status="active" />);
      container = res.container;
    });

    expect(container!.querySelector('.animate-web-cursor')).toBeInTheDocument();
    expect(container!.querySelector('.animate-web-click-1')).toBeInTheDocument();
    expect(container!.querySelector('.animate-web-click-2')).toBeInTheDocument();
    expect(container!.querySelector('.animate-pipeline-tracer')).toBeInTheDocument();
  });

  it('renderiza en estado completed con badge y curva consolidada sin cursor', async () => {
    let container: HTMLElement;
    await act(async () => {
      const res = render(<StagePathsGraphic status="completed" />);
      container = res.container;
    });

    expect(container!.querySelector('.zoom-in-50')).toBeInTheDocument();
    expect(container!.querySelector('.animate-web-cursor')).not.toBeInTheDocument();
    expect(container!.innerHTML).toContain('#EEF2FF');
  });
});
