import React, { act } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import DashboardPage from '../page';
import * as navigation from 'next/navigation';

vi.mock('@/components/dashboard/dashboard-intro', () => ({
  DashboardIntro: ({ onComplete }: { onComplete: () => void }) => (
    <div data-testid="mock-dashboard-intro">
      <button onClick={onComplete}>Completar Intro</button>
    </div>
  ),
}));

vi.mock('@/components/dashboard/dashboard-view', () => ({
  DashboardView: () => <div data-testid="mock-dashboard-view">Vista Dashboard</div>,
}));

describe('DashboardPage (src/app/dashboard/page.tsx)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renderiza directamente DashboardView cuando no hay parámetros de intro ni onboarding', async () => {
    vi.spyOn(navigation, 'useSearchParams').mockReturnValue(new URLSearchParams() as unknown as ReturnType<typeof navigation.useSearchParams>);

    await act(async () => {
      render(<DashboardPage />);
    });

    expect(screen.getByTestId('mock-dashboard-view')).toBeInTheDocument();
    expect(screen.queryByTestId('mock-dashboard-intro')).not.toBeInTheDocument();
  });

  it('inicia en fase entering con onboarding=true, pasa a visible tras 40ms, y transiciona a dashboard al completar', async () => {
    vi.useFakeTimers();
    const replaceStateSpy = vi.spyOn(window.history, 'replaceState');
    vi.spyOn(navigation, 'useSearchParams').mockReturnValue(
      new URLSearchParams('onboarding=true') as unknown as ReturnType<typeof navigation.useSearchParams>
    );

    let container!: HTMLElement;
    await act(async () => {
      const res = render(<DashboardPage />);
      container = res.container;
    });

    // Intro presente en fase entering
    expect(screen.getByTestId('mock-dashboard-intro')).toBeInTheDocument();
    const introWrapper = container.querySelector('.fixed.inset-0');
    expect(introWrapper?.className).toContain('translate-y-2');

    // 40ms después -> visible
    await act(async () => {
      vi.advanceTimersByTime(40);
    });
    expect(introWrapper?.className).toContain('opacity-100');

    // Completar intro
    const completeBtn = screen.getByRole('button', { name: /completar intro/i });
    await act(async () => {
      fireEvent.click(completeBtn);
    });

    // Fase exiting
    expect(introWrapper?.className).toContain('opacity-0');
    expect(introWrapper?.className).toContain('blur-[2px]');

    // 600ms después -> fase dashboard
    await act(async () => {
      vi.advanceTimersByTime(600);
    });

    expect(screen.getByTestId('mock-dashboard-view')).toBeInTheDocument();
    expect(replaceStateSpy).toHaveBeenCalledWith(null, '', '/dashboard');

    vi.useRealTimers();
  });

  it('muestra la intro cuando el parámetro intro=true está presente', async () => {
    vi.spyOn(navigation, 'useSearchParams').mockReturnValue(
      new URLSearchParams('intro=true') as unknown as ReturnType<typeof navigation.useSearchParams>
    );

    await act(async () => {
      render(<DashboardPage />);
    });

    expect(screen.getByTestId('mock-dashboard-intro')).toBeInTheDocument();
  });
});
