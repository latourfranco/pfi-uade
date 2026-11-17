import React, { act } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import OnboardingRubroPage from '../page';
import * as navigation from 'next/navigation';

describe('OnboardingRubroPage (src/app/onboarding/rubro/page.tsx)', () => {
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

  it('renderiza con selección por defecto E-commerce cuando no hay query param', async () => {
    vi.spyOn(navigation, 'useSearchParams').mockReturnValue(new URLSearchParams() as unknown as ReturnType<typeof navigation.useSearchParams>);

    await act(async () => {
      render(<OnboardingRubroPage />);
    });

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('¿A qué se dedica tu empresa?');
    const ecommerceBtn = screen.getByRole('radio', { name: 'E-commerce' });
    expect(ecommerceBtn).toHaveAttribute('aria-checked', 'true');

    // Botón avanzar habilitado
    const nextBtn = screen.getByRole('button', { name: /avanzar/i });
    expect(nextBtn).toBeEnabled();

    // Click avanzar
    await act(async () => {
      fireEvent.click(nextBtn);
    });

    expect(sessionStorage.getItem('eureka_onboarding_rubro')).toBe('E-commerce');
    expect(localStorage.getItem('eureka_onboarding_rubro')).toBe('E-commerce');
    expect(pushMock).toHaveBeenCalledWith('/onboarding/tamano?rubro=E-commerce');
  });

  it('inicializa con el rubro indicado en el query param si pertenece a RUBRO_OPTIONS', async () => {
    vi.spyOn(navigation, 'useSearchParams').mockReturnValue(new URLSearchParams('rubro=Fintech') as unknown as ReturnType<typeof navigation.useSearchParams>);

    await act(async () => {
      render(<OnboardingRubroPage />);
    });

    const fintechBtn = screen.getByRole('radio', { name: 'Fintech' });
    expect(fintechBtn).toHaveAttribute('aria-checked', 'true');

    // Cambiar a otra opción
    const bancaBtn = screen.getByRole('radio', { name: 'Banca' });
    await act(async () => {
      fireEvent.click(bancaBtn);
    });
    expect(bancaBtn).toHaveAttribute('aria-checked', 'true');

    const nextBtn = screen.getByRole('button', { name: /avanzar/i });
    await act(async () => {
      fireEvent.click(nextBtn);
    });

    expect(pushMock).toHaveBeenCalledWith('/onboarding/tamano?rubro=Banca');
  });

  it('inicializa en "Otro" y llena customRubro si el query param es un rubro personalizado', async () => {
    vi.spyOn(navigation, 'useSearchParams').mockReturnValue(new URLSearchParams('rubro=Biotecnología') as unknown as ReturnType<typeof navigation.useSearchParams>);

    await act(async () => {
      render(<OnboardingRubroPage />);
    });

    const otroBtn = screen.getByRole('radio', { name: 'Otro' });
    expect(otroBtn).toHaveAttribute('aria-checked', 'true');

    const customInput = screen.getByLabelText('Especifica tu rubro') as HTMLInputElement;
    expect(customInput.value).toBe('Biotecnología');

    const nextBtn = screen.getByRole('button', { name: /avanzar/i });
    expect(nextBtn).toBeEnabled();

    await act(async () => {
      fireEvent.click(nextBtn);
    });

    expect(pushMock).toHaveBeenCalledWith('/onboarding/tamano?rubro=Biotecnolog%C3%ADa');
  });

  it('permite seleccionar "Otro", escribir un rubro personalizado y presionar Enter para avanzar', async () => {
    const user = userEvent.setup();
    vi.spyOn(navigation, 'useSearchParams').mockReturnValue(new URLSearchParams() as unknown as ReturnType<typeof navigation.useSearchParams>);

    await act(async () => {
      render(<OnboardingRubroPage />);
    });

    const otroBtn = screen.getByRole('radio', { name: 'Otro' });
    await act(async () => {
      fireEvent.click(otroBtn);
    });

    const nextBtn = screen.getByRole('button', { name: /avanzar/i });
    // Al seleccionar Otro sin texto, debe estar deshabilitado
    expect(nextBtn).toBeDisabled();

    const customInput = screen.getByLabelText('Especifica tu rubro');

    // Presionar otra tecla (ej. 'Tab') no avanza
    await act(async () => {
      fireEvent.keyDown(customInput, { key: 'Tab' });
    });
    expect(pushMock).not.toHaveBeenCalled();

    // Escribir texto
    await act(async () => {
      await user.type(customInput, 'AgroTech');
    });
    expect(nextBtn).toBeEnabled();

    // Presionar Enter en el input para avanzar
    await act(async () => {
      fireEvent.keyDown(customInput, { key: 'Enter' });
    });

    expect(sessionStorage.getItem('eureka_onboarding_rubro')).toBe('AgroTech');
    expect(pushMock).toHaveBeenCalledWith('/onboarding/tamano?rubro=AgroTech');
  });
});
