import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import CuentaPage from '../page';
import * as cuentaActions from '@/app/actions/cuenta';

vi.mock('@/app/actions/cuenta', () => ({
  obtenerInformacionCuenta: vi.fn(),
  actualizarPerfilInstitucionalAction: vi.fn(),
  solicitarBajaDefinitivaCuentaAction: vi.fn(),
}));

describe('CuentaPage (src/app/dashboard/cuenta/page.tsx)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('obtiene la información de cuenta y renderiza la vista completa', async () => {
    const fakePerfil = {
      id: 'p-1',
      cliente_id: 'cli-001',
      nombre_organizacion: 'Fintech Solutions S.A.',
      rubro: 'Fintech',
      tamano_equipo: '50-249',
      dominio_url: 'https://fintech.example.com',
      estado_cuenta: 'activo' as const,
      created_at: '2026-10-24T10:00:00Z',
      updated_at: '2026-10-24T10:00:00Z',
    };

    const fakeIntegracion = {
      id: 'int-1',
      cliente_id: 'cli-001',
      ga4_property_id: '123456789',
      client_gcp_project_id: 'dw-client-prod',
      gcp_region: 'southamerica-west1',
      activo: true,
      ultimo_lote_sincronizado: null,
      created_at: '2026-10-24T10:00:00Z',
      updated_at: '2026-10-24T10:00:00Z',
    };

    vi.mocked(cuentaActions.obtenerInformacionCuenta).mockResolvedValue({
      perfil: fakePerfil,
      integracion: fakeIntegracion,
    });

    let renderedUi: React.ReactElement;
    await act(async () => {
      renderedUi = await CuentaPage();
    });

    await act(async () => {
      render(renderedUi);
    });

    expect(cuentaActions.obtenerInformacionCuenta).toHaveBeenCalled();
    expect(screen.getByText('Administración y Configuración de Cuenta')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Fintech Solutions S.A.')).toBeInTheDocument();
    expect(screen.getByText('123456789')).toBeInTheDocument();
    expect(screen.getByText('dw-client-prod')).toBeInTheDocument();
    expect(screen.getByText('Zona de peligro')).toBeInTheDocument();
  });

  it('renderiza con valores por defecto cuando no existe perfil previo', async () => {
    vi.mocked(cuentaActions.obtenerInformacionCuenta).mockResolvedValue({
      perfil: null,
      integracion: null,
    });

    let renderedUi: React.ReactElement;
    await act(async () => {
      renderedUi = await CuentaPage();
    });

    await act(async () => {
      render(renderedUi);
    });

    expect(cuentaActions.obtenerInformacionCuenta).toHaveBeenCalled();
    expect(screen.getByText('Administración y Configuración de Cuenta')).toBeInTheDocument();
    expect(screen.getByText('Zona de peligro')).toBeInTheDocument();
    expect(screen.getByText('Sin conexión activa')).toBeInTheDocument();
  });
});
