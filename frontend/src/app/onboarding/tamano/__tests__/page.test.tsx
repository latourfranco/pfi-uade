import React, { act } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import OnboardingTamanoPage from '../page';
import * as navigation from 'next/navigation';

describe('OnboardingTamanoPage (src/app/onboarding/tamano/page.tsx)', () => {
  const pushMock = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    localStorage.clear();
    vi.spyOn(navigation, 'useRouter').mockReturnValue({
      push: pushMock,
      replace: vi.fn(),
      prefetch: vi.fn(),
      back: vi.fn(),
      forward: vi.fn(),
      refresh: vi.fn(),
    } as unknown as ReturnType<typeof navigation.useRouter>);
  });

  it('renderiza con selección por defecto 1-49 y rubro E-commerce cuando no hay query params', async () => {
    vi.spyOn(navigation, 'useSearchParams').mockReturnValue(new URLSearchParams() as unknown as ReturnType<typeof navigation.useSearchParams>);

    await act(async () => {
      render(<OnboardingTamanoPage />);
    });

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('¿Cuántas personas trabajan con vos?');
    const defaultOption = screen.getByRole('radio', { name: '1-49' });
    expect(defaultOption).toHaveAttribute('aria-checked', 'true');

    const nextBtn = screen.getByRole('button', { name: /avanzar/i });
    expect(nextBtn).toBeEnabled();

    await act(async () => {
      fireEvent.click(nextBtn);
    });

    expect(sessionStorage.getItem('eureka_onboarding_tamano')).toBe('1-49');
    expect(localStorage.getItem('eureka_onboarding_tamano')).toBe('1-49');
    expect(pushMock).toHaveBeenCalledWith('/onboarding/interfaz?rubro=E-commerce&tamano=1-49');
  });

  it('inicializa con el tamaño indicado en query param y permite cambiar la opción seleccionada', async () => {
    vi.spyOn(navigation, 'useSearchParams').mockReturnValue(
      new URLSearchParams('rubro=Fintech&tamano=50-249') as unknown as ReturnType<typeof navigation.useSearchParams>
    );

    await act(async () => {
      render(<OnboardingTamanoPage />);
    });

    const initialOption = screen.getByRole('radio', { name: '50-249' });
    expect(initialOption).toHaveAttribute('aria-checked', 'true');

    // Cambiar a +1000
    const largeOption = screen.getByRole('radio', { name: '+1000' });
    await act(async () => {
      fireEvent.click(largeOption);
    });
    expect(largeOption).toHaveAttribute('aria-checked', 'true');

    const nextBtn = screen.getByRole('button', { name: /avanzar/i });
    await act(async () => {
      fireEvent.click(nextBtn);
    });

    expect(sessionStorage.getItem('eureka_onboarding_tamano')).toBe('+1000');
    expect(pushMock).toHaveBeenCalledWith('/onboarding/interfaz?rubro=Fintech&tamano=%2B1000');
  });
});
