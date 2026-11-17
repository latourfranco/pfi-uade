import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { PerfilInstitucionalCard } from '../perfil-institucional-card';
import * as cuentaActions from '@/app/actions/cuenta';

vi.mock('@/app/actions/cuenta', () => ({
  actualizarPerfilInstitucionalAction: vi.fn(),
}));

describe('PerfilInstitucionalCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const mockPerfil = {
    id: 'p-1',
    cliente_id: 'cli-001',
    nombre_organizacion: 'Global Payments S.A.',
    rubro: 'Fintech',
    tamano_equipo: '250+',
    dominio_url: 'https://globalpayments.io',
    estado_cuenta: 'activo' as const,
    created_at: '2026-10-24T10:00:00Z',
    updated_at: '2026-10-24T10:00:00Z',
  };

  const mockIntegracion = {
    id: 'int-1',
    cliente_id: 'cli-001',
    ga4_property_id: '445566778',
    client_gcp_project_id: 'gcp-gp-prod',
    gcp_region: 'southamerica-west1',
    activo: true,
    ultimo_lote_sincronizado: null,
    created_at: '2026-10-24T10:00:00Z',
    updated_at: '2026-10-24T10:00:00Z',
  };

  it('renderiza correctamente los valores del perfil y el estado de integración activa', async () => {
    await act(async () => {
      render(
        <PerfilInstitucionalCard
          perfil={mockPerfil}
          integracion={mockIntegracion}
          clienteId="cli-001"
        />
      );
    });

    expect(screen.getByDisplayValue('Global Payments S.A.')).toBeInTheDocument();
    expect(screen.getByDisplayValue('https://globalpayments.io')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Fintech')).toBeInTheDocument();
    expect(screen.getByDisplayValue('250+ personas')).toBeInTheDocument();

    expect(screen.getByText('445566778')).toBeInTheDocument();
    expect(screen.getByText('gcp-gp-prod')).toBeInTheDocument();
    expect(screen.getByText('southamerica-west1')).toBeInTheDocument();
    expect(screen.getByText('Activa y sincronizada')).toBeInTheDocument();
  });

  it('actualiza los datos y muestra feedback de éxito al enviar el formulario', async () => {
    vi.mocked(cuentaActions.actualizarPerfilInstitucionalAction).mockResolvedValue({
      success: true,
    });

    await act(async () => {
      render(
        <PerfilInstitucionalCard
          perfil={mockPerfil}
          integracion={mockIntegracion}
          clienteId="cli-001"
        />
      );
    });

    const inputNombre = screen.getByDisplayValue('Global Payments S.A.');
    await act(async () => {
      fireEvent.change(inputNombre, { target: { value: 'Global Payments Nueva Empresa' } });
    });

    const inputDominio = screen.getByDisplayValue('https://globalpayments.io');
    await act(async () => {
      fireEvent.change(inputDominio, { target: { value: 'https://newdomain.com' } });
    });

    const selectRubro = screen.getByDisplayValue('Fintech');
    await act(async () => {
      fireEvent.change(selectRubro, { target: { value: 'E-commerce' } });
    });

    const selectTamano = screen.getByDisplayValue('250+ personas');
    await act(async () => {
      fireEvent.change(selectTamano, { target: { value: '51-250' } });
    });

    const submitBtn = screen.getByRole('button', { name: /Guardar cambios/i });
    await act(async () => {
      fireEvent.click(submitBtn);
    });

    await waitFor(() => {
      expect(cuentaActions.actualizarPerfilInstitucionalAction).toHaveBeenCalled();
      expect(
        screen.getByText('Perfil institucional actualizado correctamente.')
      ).toBeInTheDocument();
    });
  });

  it('muestra feedback de error si la acción retorna success=false', async () => {
    vi.mocked(cuentaActions.actualizarPerfilInstitucionalAction).mockResolvedValue({
      success: false,
      error: 'Nombre de organización inválido',
    });

    await act(async () => {
      render(
        <PerfilInstitucionalCard
          perfil={mockPerfil}
          integracion={null}
          clienteId="cli-001"
        />
      );
    });

    const submitBtn = screen.getByRole('button', { name: /Guardar cambios/i });
    await act(async () => {
      fireEvent.click(submitBtn);
    });

    await waitFor(() => {
      expect(
        screen.getByText('Nombre de organización inválido')
      ).toBeInTheDocument();
    });
  });

  it('muestra feedback de error genérico si la acción arroja una excepción', async () => {
    vi.mocked(cuentaActions.actualizarPerfilInstitucionalAction).mockRejectedValue(
      new Error('Fallo de red al guardar')
    );

    await act(async () => {
      render(
        <PerfilInstitucionalCard
          perfil={mockPerfil}
          integracion={null}
          clienteId="cli-001"
        />
      );
    });

    const submitBtn = screen.getByRole('button', { name: /Guardar cambios/i });
    await act(async () => {
      fireEvent.click(submitBtn);
    });

    await waitFor(() => {
      expect(
        screen.getByText('Error de conexión al actualizar el perfil.')
      ).toBeInTheDocument();
    });
  });
});
