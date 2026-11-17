import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { CuentaView } from '@/components/cuenta/cuenta-view';
import * as cuentaActions from '@/app/actions/cuenta';

vi.mock('@/app/actions/cuenta', () => ({
  actualizarPerfilInstitucionalAction: vi.fn(),
  solicitarBajaDefinitivaCuentaAction: vi.fn(),
}));

describe('Flujo de Integración: Supresión de Datos y Baja de Cuenta', () => {
  const originalLocation = window.location;

  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(window, 'location', {
      writable: true,
      configurable: true,
      value: { ...originalLocation, href: '' },
    });
  });

  afterEach(() => {
    Object.defineProperty(window, 'location', {
      writable: true,
      configurable: true,
      value: originalLocation,
    });
  });

  it('permite al usuario abrir la Zona de peligro, confirmar con la frase exacta y completar la baja con redirección', async () => {
    vi.mocked(cuentaActions.solicitarBajaDefinitivaCuentaAction).mockResolvedValue({
      success: true,
      redirectUrl: '/onboarding/rubro?cuenta_eliminada=true',
      purga: {
        success: true,
        auditoriaId: 'aud-e2e',
        tokensRevocados: true,
        sesionesInvalidadas: true,
        bdTransaccionalPurgada: true,
        dwPurgaDisparada: true,
      },
    });

    const fakePerfil = {
      id: 'prf-e2e',
      cliente_id: 'cli-e2e-001',
      nombre_organizacion: 'Fintech E2E Org',
      rubro: 'Fintech',
      tamano_equipo: '50-249',
      dominio_url: 'https://fintech.e2e',
      estado_cuenta: 'activo' as const,
      created_at: '2026-10-24T10:00:00Z',
      updated_at: '2026-10-24T10:00:00Z',
    };

    const fakeIntegracion = {
      id: 'int-e2e',
      cliente_id: 'cli-e2e-001',
      ga4_property_id: '99887766',
      client_gcp_project_id: 'dw-gcp-e2e',
      gcp_region: 'us-central1',
      activo: true,
      ultimo_lote_sincronizado: null,
      created_at: '2026-10-24T10:00:00Z',
      updated_at: '2026-10-24T10:00:00Z',
    };

    await act(async () => {
      render(
        <CuentaView
          perfil={fakePerfil}
          integracion={fakeIntegracion}
          clienteId="cli-e2e-001"
        />
      );
    });

    // 1. Verificación de renderizado de la vista de cuenta y perfil
    expect(screen.getByText('Administración y Configuración de Cuenta')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Fintech E2E Org')).toBeInTheDocument();
    expect(screen.getByText('99887766')).toBeInTheDocument();

    // 2. Abrir Zona de peligro y disparar modal
    const botonTramitarBaja = screen.getByRole('button', { name: /Tramitar baja definitiva/i });
    await act(async () => {
      fireEvent.click(botonTramitarBaja);
    });

    const modalTitle = screen.getByRole('heading', { name: /Confirmar baja definitiva/i });
    expect(modalTitle).toBeInTheDocument();

    // 3. El botón de confirmación destructiva debe estar deshabilitado al inicio
    const botonConfirmar = screen.getByRole('button', { name: /Confirmar baja definitiva/i });
    expect(botonConfirmar).toBeDisabled();

    // 4. Escribir texto erróneo: continúa deshabilitado
    const inputConfirmacion = screen.getByRole('textbox', { name: /Para proceder/i });
    await act(async () => {
      fireEvent.change(inputConfirmacion, { target: { value: 'eliminar' } });
    });
    expect(botonConfirmar).toBeDisabled();

    // 5. Escribir la frase exacta 'ELIMINAR MI CUENTA': se habilita
    await act(async () => {
      fireEvent.change(inputConfirmacion, { target: { value: 'ELIMINAR MI CUENTA' } });
    });
    expect(botonConfirmar).not.toBeDisabled();

    // 6. Confirmar baja definitiva
    await act(async () => {
      fireEvent.click(botonConfirmar);
    });

    // 7. Verificación de despacho y redirección post-supresión
    await waitFor(() => {
      expect(cuentaActions.solicitarBajaDefinitivaCuentaAction).toHaveBeenCalledWith({
        clienteId: 'cli-e2e-001',
        confirmacion: 'ELIMINAR MI CUENTA',
        motivo: expect.any(String),
      });
      expect(window.location.href).toBe('/onboarding/rubro?cuenta_eliminada=true');
    });
  });
});
