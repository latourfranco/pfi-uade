import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { DashboardProcessingPipeline } from '../dashboard-processing-pipeline';

describe('DashboardProcessingPipeline Component', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('inicia en la etapa 1 con progreso inicial y avanza hasta completar todas las etapas', async () => {
    const handleComplete = vi.fn();

    let unmount: () => void;
    await act(async () => {
      const res = render(
        <DashboardProcessingPipeline
          stageDurationMs={100}
          onComplete={handleComplete}
          className="custom-pipeline"
        />
      );
      unmount = res.unmount;
    });

    // Estado inicial
    expect(screen.getByText(/etapa 1 de 4/i)).toBeInTheDocument();
    expect(screen.getByText('Progreso global')).toBeInTheDocument();
    expect(screen.getByText('0%')).toBeInTheDocument();

    // Avanza a la etapa 2 (120ms transcurridos)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(120);
    });

    expect(screen.getByText(/etapa 2 de 4/i)).toBeInTheDocument();

    // Avanza a la etapa 3 (240ms transcurridos)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(120);
    });

    expect(screen.getByText(/etapa 3 de 4/i)).toBeInTheDocument();

    // Avanza a la etapa 4 (360ms transcurridos)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(120);
    });

    expect(screen.getByText(/etapa 4 de 4/i)).toBeInTheDocument();

    // Avanza hasta finalizar las 4 etapas (totalDuration = 400ms)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(120);
    });

    expect(screen.getByText(/procesamiento finalizado/i)).toBeInTheDocument();
    expect(screen.getByText(/análisis completado con éxito/i)).toBeInTheDocument();
    expect(screen.getByText('100%')).toBeInTheDocument();

    // Aún no debe llamarse onComplete antes del retardo de apreciación de 2000ms
    expect(handleComplete).not.toHaveBeenCalled();

    // Avanza los 2000ms de apreciación
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(handleComplete).toHaveBeenCalledTimes(1);

    // Limpieza
    await act(async () => {
      unmount();
    });
  });

  it('funciona correctamente sin callback onComplete', async () => {
    await act(async () => {
      render(<DashboardProcessingPipeline stageDurationMs={50} />);
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(50 * 4 + 2000);
    });

    expect(screen.getByText(/procesamiento finalizado/i)).toBeInTheDocument();
  });
});
