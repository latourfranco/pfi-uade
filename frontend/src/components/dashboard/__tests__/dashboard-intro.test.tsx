import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, fireEvent } from '@testing-library/react';
import { DashboardIntro } from '../dashboard-intro';

vi.mock('../processing-pipeline/dashboard-processing-pipeline', () => ({
  DashboardProcessingPipeline: ({ onComplete }: { onComplete?: () => void }) => {
    return (
      <div data-testid="mock-pipeline">
        <button onClick={onComplete}>Complete Pipeline</button>
      </div>
    );
  },
}));

describe('DashboardIntro Component', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('inicia en la etapa de pipeline y avanza al titular y al callback onComplete', async () => {
    const handleComplete = vi.fn();

    await act(async () => {
      render(
        <DashboardIntro
          stageDurationMs={100}
          headlineDurationMs={200}
          onComplete={handleComplete}
        />
      );
    });

    // Inicialmente se muestra la estructura del pipeline
    expect(screen.getByTestId('mock-pipeline')).toBeInTheDocument();

    // Disparamos la compleción del pipeline
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /complete pipeline/i }));
    });

    // Transición a headline (350ms)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(350);
    });

    // Ahora se muestra el titular principal
    expect(
      screen.getByRole('heading', { name: /descubrí lo/i })
    ).toBeInTheDocument();

    // Avanza headlineDurationMs (200ms) para disparar onComplete
    await act(async () => {
      await vi.advanceTimersByTimeAsync(250);
    });

    expect(handleComplete).toHaveBeenCalledTimes(1);
  });

  it('funciona correctamente sin callback onComplete definido', async () => {
    await act(async () => {
      render(
        <DashboardIntro stageDurationMs={50} headlineDurationMs={50} />
      );
    });

    // Disparamos la compleción del pipeline
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /complete pipeline/i }));
    });

    // Avanza transición y headline
    await act(async () => {
      vi.advanceTimersByTime(350 + 50);
    });

    expect(
      screen.getByRole('heading', { name: /descubrí lo/i })
    ).toBeInTheDocument();
  });
});
