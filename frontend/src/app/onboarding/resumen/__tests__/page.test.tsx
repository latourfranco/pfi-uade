import React, { act } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import OnboardingResumenPage from '../page';
import * as navigation from 'next/navigation';
import * as authActions from '@/app/actions/auth';

vi.mock('@/app/actions/auth', () => ({
  getAuthSessionSummaryAction: vi.fn(),
  completeOnboardingAction: vi.fn(),
  signInWithGoogleAction: vi.fn(),
}));

describe('OnboardingResumenPage (src/app/onboarding/resumen/page.tsx)', () => {
  const pushMock = vi.fn();
  const refreshMock = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    localStorage.clear();
    vi.mocked(authActions.getAuthSessionSummaryAction).mockResolvedValue({
      authenticated: false,
      email: null,
      nombreOrganizacion: null,
    });
    vi.spyOn(navigation, 'useRouter').mockReturnValue({
      push: pushMock,
      replace: vi.fn(),
      prefetch: vi.fn(),
      back: vi.fn(),
      forward: vi.fn(),
      refresh: refreshMock,
    } as unknown as ReturnType<typeof navigation.useRouter>);
  });

  it('renderiza resumen con valores predeterminados cuando no hay searchParams ni storage', async () => {
    vi.spyOn(navigation, 'useSearchParams').mockReturnValue(new URLSearchParams() as unknown as ReturnType<typeof navigation.useSearchParams>);

    await act(async () => {
      render(<OnboardingResumenPage />);
    });

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Listo. Ya estamos escuchando.');
    expect(screen.getByText('E-commerce')).toBeInTheDocument();
    expect(screen.getByText('50-249 personas')).toBeInTheDocument();
    expect(screen.getByText('No configurado')).toBeInTheDocument();
    expect(screen.getByText('Sin autenticación')).toBeInTheDocument();
    expect(screen.getByText('Configurada')).toBeInTheDocument();

    expect(screen.getByRole('link', { name: /rubro/i })).toHaveAttribute(
      'href',
      '/onboarding/rubro?rubro=E-commerce'
    );
    expect(screen.getByRole('link', { name: /equipo/i })).toHaveAttribute(
      'href',
      '/onboarding/tamano?rubro=E-commerce&tamano=50-249'
    );
    expect(screen.getByRole('link', { name: /sitio web/i })).toHaveAttribute(
      'href',
      '/onboarding/interfaz?rubro=E-commerce&tamano=50-249&propertyName='
    );
    expect(screen.getByRole('link', { name: /conexión con google analytics/i })).toHaveAttribute(
      'href',
      '/onboarding/fuente?rubro=E-commerce&tamano=50-249&propertyName='
    );

    const ctaBtn = screen.getByRole('button', { name: /continuar con google y activar radar/i });
    expect(ctaBtn).toBeInTheDocument();
  });

  it('inicia Google OAuth desde resumen cuando no hay sesión activa y valida nombre de organización', async () => {
    vi.spyOn(navigation, 'useSearchParams').mockReturnValue(
      new URLSearchParams('rubro=Retail&tamano=10-49&propertyName=https://tienda.com') as unknown as ReturnType<typeof navigation.useSearchParams>
    );
    vi.mocked(authActions.signInWithGoogleAction).mockResolvedValue({
      success: true,
    });

    await act(async () => {
      render(<OnboardingResumenPage />);
    });

    fireEvent.change(screen.getByLabelText('Nombre de la organización'), {
      target: { value: 'A' },
    });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /continuar con google y activar radar/i }));
    });
    expect(screen.getByRole('alert')).toHaveTextContent('mínimo 2 caracteres');

    fireEvent.change(screen.getByLabelText('Nombre de la organización'), {
      target: { value: 'Tienda SRL' },
    });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /continuar con google y activar radar/i }));
    });

    await waitFor(() => {
      expect(sessionStorage.getItem('eureka_onboarding_org')).toBe('Tienda SRL');
      expect(authActions.signInWithGoogleAction).toHaveBeenCalledWith(
        '/onboarding/resumen?complete=1'
      );
    });
  });

  it('auto-completa el onboarding al volver de Google OAuth con ?complete=1', async () => {
    sessionStorage.setItem('eureka_onboarding_org', 'Tienda SRL');
    vi.spyOn(navigation, 'useSearchParams').mockReturnValue(
      new URLSearchParams('rubro=Retail&tamano=10-49&propertyName=https://tienda.com&complete=1') as unknown as ReturnType<typeof navigation.useSearchParams>
    );
    vi.mocked(authActions.getAuthSessionSummaryAction).mockResolvedValue({
      authenticated: true,
      email: 'owner@tienda.com',
      nombreOrganizacion: 'Owner Google',
    });
    vi.mocked(authActions.completeOnboardingAction).mockResolvedValue({
      success: true,
      redirectUrl: '/dashboard?onboarding=true',
    });

    await act(async () => {
      render(<OnboardingResumenPage />);
    });

    await waitFor(() => {
      expect(authActions.completeOnboardingAction).toHaveBeenCalledWith(
        expect.objectContaining({
          rubro: 'Retail',
          tamano: '10-49',
          baseUrl: 'https://tienda.com',
          nombreOrganizacion: 'Tienda SRL',
        })
      );
      expect(pushMock).toHaveBeenCalledWith('/dashboard?onboarding=true');
      expect(refreshMock).toHaveBeenCalled();
    });
  });

  it('muestra error si completeOnboardingAction falla y soporta sesión ya autenticada', async () => {
    vi.spyOn(navigation, 'useSearchParams').mockReturnValue(
      new URLSearchParams() as unknown as ReturnType<typeof navigation.useSearchParams>
    );
    vi.mocked(authActions.getAuthSessionSummaryAction).mockResolvedValue({
      authenticated: true,
      email: 'ya@logeado.com',
      nombreOrganizacion: 'Org Activa',
    });
    vi.mocked(authActions.completeOnboardingAction).mockResolvedValue({
      success: false,
      error: 'Error al activar',
    });

    await act(async () => {
      render(<OnboardingResumenPage />);
    });

    await waitFor(() => {
      expect(screen.getByText('ya@logeado.com')).toBeInTheDocument();
    });

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /ver mi panorama de fricción/i }));
    });

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Error al activar');
    });
  });

  it('toma valores desde storage y searchParams según precedencia', async () => {
    sessionStorage.setItem('eureka_onboarding_rubro', 'Fintech');
    localStorage.setItem('eureka_onboarding_tamano', '1-49');
    sessionStorage.setItem('eureka_onboarding_url', 'https://mifintech.com');

    // Proveemos rubro por param (debe ganar el param), y dejamos tamano/propertyName en storage
    vi.spyOn(navigation, 'useSearchParams').mockReturnValue(
      new URLSearchParams('rubro=Banca') as unknown as ReturnType<typeof navigation.useSearchParams>
    );

    await act(async () => {
      render(<OnboardingResumenPage />);
    });

    expect(screen.getByText('Banca')).toBeInTheDocument();
    expect(screen.getByText('1-49 personas')).toBeInTheDocument();
    expect(screen.getByText('https://mifintech.com')).toBeInTheDocument();
  });

  it('permite seleccionar elementos mediante click y mouseEnter', async () => {
    vi.spyOn(navigation, 'useSearchParams').mockReturnValue(new URLSearchParams() as unknown as ReturnType<typeof navigation.useSearchParams>);

    await act(async () => {
      render(<OnboardingResumenPage />);
    });

    const rubroRow = screen.getByText('Rubro').closest('.group') as HTMLElement;
    const equipoRow = screen.getByText('Equipo').closest('.group') as HTMLElement;

    // Hover
    await act(async () => {
      fireEvent.mouseEnter(rubroRow);
    });
    expect(rubroRow.className).toContain('bg-[#EEF2FF]');

    // Click en otro elemento
    await act(async () => {
      fireEvent.click(equipoRow);
    });
    expect(equipoRow.className).toContain('bg-[#EEF2FF]');
    expect(rubroRow.className).not.toContain('bg-[#EEF2FF]');
  });

  it('soporta navegación mediante teclado (ArrowDown, ArrowUp, Escape) e ignora inputs', async () => {
    vi.spyOn(navigation, 'useSearchParams').mockReturnValue(new URLSearchParams() as unknown as ReturnType<typeof navigation.useSearchParams>);

    await act(async () => {
      render(
        <div>
          <input data-testid="dummy-input" />
          <textarea data-testid="dummy-textarea" />
          <OnboardingResumenPage />
        </div>
      );
    });

    const input = screen.getByTestId('dummy-input');
    const textarea = screen.getByTestId('dummy-textarea');
    const rubroRow = screen.getByText('Rubro').closest('.group') as HTMLElement;

    // Disparar ArrowDown dentro de un input (debe ser ignorado)
    await act(async () => {
      fireEvent.keyDown(input, { key: 'ArrowDown' });
      fireEvent.keyDown(textarea, { key: 'ArrowDown' });
    });
    expect(rubroRow.className).not.toContain('bg-[#EEF2FF]');

    // ArrowDown global: selecciona el primer elemento (índice 0)
    await act(async () => {
      fireEvent.keyDown(window, { key: 'ArrowDown' });
    });
    expect(rubroRow.className).toContain('bg-[#EEF2FF]');

    // ArrowDown de nuevo: avanza al siguiente elemento (índice 1)
    await act(async () => {
      fireEvent.keyDown(window, { key: 'ArrowDown' });
    });
    const equipoRow = screen.getByText('Equipo').closest('.group') as HTMLElement;
    expect(equipoRow.className).toContain('bg-[#EEF2FF]');

    // Escape: deselecciona
    await act(async () => {
      fireEvent.keyDown(window, { key: 'Escape' });
    });
    expect(equipoRow.className).not.toContain('bg-[#EEF2FF]');

    // ArrowUp global cuando nada está seleccionado: selecciona el último (índice 3)
    await act(async () => {
      fireEvent.keyDown(window, { key: 'ArrowUp' });
    });
    const gaRow = screen.getByText('Conexión con Google Analytics').closest('.group') as HTMLElement;
    expect(gaRow.className).toContain('bg-[#EEF2FF]');

    // ArrowUp de nuevo: retrocede al índice 3 (Autenticación del sitio)
    await act(async () => {
      fireEvent.keyDown(window, { key: 'ArrowUp' });
    });
    const authRow = screen.getByText('Autenticación del sitio').closest('.group') as HTMLElement;
    expect(authRow.className).toContain('bg-[#EEF2FF]');
  });
});
