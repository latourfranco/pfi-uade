import React, { act } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import OnboardingInterfazPage from '../page';
import * as navigation from 'next/navigation';

describe('OnboardingInterfazPage (src/app/onboarding/interfaz/page.tsx)', () => {
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

  it('permite ingresar una URL válida y avanza guardándola en storage', async () => {
    vi.spyOn(navigation, 'useSearchParams').mockReturnValue(new URLSearchParams() as unknown as ReturnType<typeof navigation.useSearchParams>);

    await act(async () => {
      render(<OnboardingInterfazPage />);
    });

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('¿Qué sitio web vamos a analizar?');

    const input = screen.getByLabelText(/url de tu sitio web/i);
    const nextBtn = screen.getByRole('button', { name: /avanzar/i });
    expect(nextBtn).toBeDisabled();

    await act(async () => {
      fireEvent.change(input, { target: { value: 'mitienda.com' } });
    });
    expect(nextBtn).not.toBeDisabled();

    await act(async () => {
      fireEvent.click(nextBtn);
    });

    expect(sessionStorage.getItem('eureka_onboarding_interfaz')).toBe('https://mitienda.com');
    expect(localStorage.getItem('eureka_onboarding_interfaz')).toBe('https://mitienda.com');
    expect(sessionStorage.getItem('eureka_onboarding_url')).toBe('https://mitienda.com');
    expect(localStorage.getItem('eureka_onboarding_url')).toBe('https://mitienda.com');

    expect(pushMock).toHaveBeenCalledWith(
      '/onboarding/fuente?rubro=E-commerce&tamano=50-249&propertyName=https%3A%2F%2Fmitienda.com'
    );
  });

  it('toma en cuenta los parámetros de rubro, tamaño y URL previa', async () => {
    vi.spyOn(navigation, 'useSearchParams').mockReturnValue(
      new URLSearchParams('rubro=Fintech&tamano=250-999&propertyName=https://fintech.ar') as unknown as ReturnType<typeof navigation.useSearchParams>
    );

    await act(async () => {
      render(<OnboardingInterfazPage />);
    });

    const nextBtn = screen.getByRole('button', { name: /avanzar/i });
    await act(async () => {
      fireEvent.click(nextBtn);
    });

    expect(pushMock).toHaveBeenCalledWith(
      '/onboarding/fuente?rubro=Fintech&tamano=250-999&propertyName=https%3A%2F%2Ffintech.ar'
    );
  });

  it('precarga URL desde storage y valida URLs inválidas', async () => {
    sessionStorage.setItem('eureka_onboarding_url', 'https://guardada.com');
    vi.spyOn(navigation, 'useSearchParams').mockReturnValue(
      new URLSearchParams() as unknown as ReturnType<typeof navigation.useSearchParams>
    );

    await act(async () => {
      render(<OnboardingInterfazPage />);
    });

    const input = screen.getByLabelText(/url de tu sitio web/i) as HTMLInputElement;
    expect(input.value).toBe('https://guardada.com');

    await act(async () => {
      fireEvent.change(input, { target: { value: 'sin-punto' } });
    });
    expect(screen.getByRole('button', { name: /avanzar/i })).toBeDisabled();

    await act(async () => {
      fireEvent.change(input, { target: { value: 'https://[invalid' } });
    });
    expect(screen.getByText(/ingresá una url válida/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /avanzar/i })).toBeDisabled();
  });

  it('permite configurar usuario/contraseña y storage_state encriptado', async () => {
    vi.spyOn(navigation, 'useSearchParams').mockReturnValue(
      new URLSearchParams() as unknown as ReturnType<typeof navigation.useSearchParams>
    );

    await act(async () => {
      render(<OnboardingInterfazPage />);
    });

    const urlInput = screen.getByLabelText(/url de tu sitio web/i);
    await act(async () => {
      fireEvent.change(urlInput, { target: { value: 'https://privada.com' } });
    });

    const credsRadio = screen.getByRole('radio', { name: /usuario y contraseña/i });
    await act(async () => {
      fireEvent.click(credsRadio);
    });

    const nextBtn = screen.getByRole('button', { name: /avanzar/i });
    expect(nextBtn).toBeDisabled();

    await act(async () => {
      fireEvent.change(screen.getByLabelText(/usuario o email/i), {
        target: { value: 'qa@privada.com' },
      });
      fireEvent.change(screen.getByLabelText(/contraseña/i), {
        target: { value: 'clave123' },
      });
    });
    expect(nextBtn).not.toBeDisabled();

    const storageRadio = screen.getByRole('radio', { name: /sesión pre-autenticada/i });
    await act(async () => {
      fireEvent.click(storageRadio);
    });
    expect(nextBtn).toBeDisabled();
    expect(screen.queryByText(/AES/i)).not.toBeInTheDocument();

    const jsonArea = screen.getByLabelText(/datos de sesión/i);
    await act(async () => {
      fireEvent.change(jsonArea, { target: { value: 'invalido' } });
    });
    expect(screen.getByText(/ingresá un objeto json válido/i)).toBeInTheDocument();
    expect(nextBtn).toBeDisabled();

    await act(async () => {
      fireEvent.change(jsonArea, { target: { value: '{"cookies":[],"origins":[]}' } });
    });
    expect(nextBtn).not.toBeDisabled();

    await act(async () => {
      fireEvent.click(nextBtn);
    });

    await waitFor(() => {
      expect(sessionStorage.getItem('eureka_onboarding_auth')).toContain('"mode":"storage_state"');
    });
    expect(pushMock).toHaveBeenCalledWith(
      '/onboarding/fuente?rubro=E-commerce&tamano=50-249&propertyName=https%3A%2F%2Fprivada.com'
    );
  });
});
