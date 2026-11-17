import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, act } from '@testing-library/react';
import { PipelineArrowConnector } from '../pipeline-arrow-connector';

describe('PipelineArrowConnector Component', () => {
  it('renderiza en estado pending sin clase de flujo activo ni gradiente activo', async () => {
    let container: HTMLElement;
    await act(async () => {
      const res = render(
        <PipelineArrowConnector status="pending" className="custom-arrow" />
      );
      container = res.container;
    });

    expect(container!.querySelector('.custom-arrow')).toBeInTheDocument();
    expect(container!.querySelector('.stroke-neutral-300')).toBeInTheDocument();
    expect(container!.querySelector('.animate-connector-flow')).not.toBeInTheDocument();
  });

  it('renderiza en estado active con animación de flujo activa', async () => {
    let container: HTMLElement;
    await act(async () => {
      const res = render(
        <PipelineArrowConnector status="active" />
      );
      container = res.container;
    });

    expect(container!.querySelector('.animate-connector-flow')).toBeInTheDocument();
    expect(container!.querySelector('.stroke-eureka-primary')).toBeInTheDocument();
  });

  it('renderiza en estado completed con stroke de eureka-primary y sin animación de flujo', async () => {
    let container: HTMLElement;
    await act(async () => {
      const res = render(
        <PipelineArrowConnector status="completed" />
      );
      container = res.container;
    });

    expect(container!.querySelector('.animate-connector-flow')).not.toBeInTheDocument();
    expect(container!.querySelector('.stroke-eureka-primary')).toBeInTheDocument();
  });
});
