import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, act, fireEvent } from '@testing-library/react';
import { CuentaView } from '../cuenta-view';
import * as authActions from '@/app/actions/auth';

vi.mock('@/app/actions/cuenta', () => ({
  actualizarPerfilInstitucionalAction: vi.fn(),
  solicitarBajaDefinitivaCuentaAction: vi.fn(),
}));

vi.mock('@/app/actions/auth', () => ({
  signOutAction: vi.fn(),
}));

describe('CuentaView', () => {
  it('renderiza la vista con el header, perfil, marco de privacidad y zona de peligro', async () => {
    await act(async () => {
      render(<CuentaView perfil={null} integracion={null} clienteId="cli-test" />);
    });

    expect(
      screen.getByText('Administración y Configuración de Cuenta')
    ).toBeInTheDocument();
    expect(screen.getByText('Volver al Radar')).toBeInTheDocument();
    expect(screen.getByText('Perfil Institucional')).toBeInTheDocument();
    expect(
      screen.getByText('Ejercicio del Derecho de Supresión de Datos')
    ).toBeInTheDocument();
    expect(screen.getByText('Zona de peligro')).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /cerrar sesión/i }));
    });
    expect(authActions.signOutAction).toHaveBeenCalled();
  });
});
