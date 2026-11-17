import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, act } from '@testing-library/react';
import { StageFrictionGraphic } from '../stage-friction-graphic';

describe('StageFrictionGraphic Component', () => {
  it('renderiza en estado pending con anillos neutros y sin haz de barrido', async () => {
    let container: HTMLElement;
    await act(async () => {
      const res = render(<StageFrictionGraphic status="pending" />);
      container = res.container;
    });

    expect(container!.querySelector('.animate-pipeline-sweep')).not.toBeInTheDocument();
    expect(container!.querySelector('.animate-friction-ping-1')).not.toBeInTheDocument();
    expect(container!.innerHTML).toContain('stroke-neutral-300');
  });

  it('renderiza en estado active con haz de barrido rotatorio y pulsos de fricción', async () => {
    let container: HTMLElement;
    await act(async () => {
      const res = render(<StageFrictionGraphic status="active" />);
      container = res.container;
    });

    expect(container!.querySelector('.animate-pipeline-sweep')).toBeInTheDocument();
    expect(container!.querySelector('.animate-friction-ping-1')).toBeInTheDocument();
    expect(container!.querySelector('.animate-friction-ping-2')).toBeInTheDocument();
  });

  it('renderiza en estado completed con badge de completado y focos consolidados', async () => {
    let container: HTMLElement;
    await act(async () => {
      const res = render(<StageFrictionGraphic status="completed" />);
      container = res.container;
    });

    expect(container!.querySelector('.zoom-in-50')).toBeInTheDocument();
    expect(container!.querySelector('.animate-pipeline-sweep')).not.toBeInTheDocument();
    expect(container!.innerHTML).toContain('#EEF2FF');
  });
});
