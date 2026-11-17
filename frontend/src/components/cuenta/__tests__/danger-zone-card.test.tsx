import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { DangerZoneCard } from '../danger-zone-card';

vi.mock('@/app/actions/cuenta', () => ({
  solicitarBajaDefinitivaCuentaAction: vi.fn(),
}));

describe('DangerZoneCard', () => {
  it('renderiza la información de la zona de peligro y botón de baja', async () => {
    await act(async () => {
      render(<DangerZoneCard clienteId="cli-123" />);
    });

    expect(screen.getByText('Zona de peligro')).toBeInTheDocument();
    expect(screen.getByText('Baja definitiva de la cuenta')).toBeInTheDocument();
    expect(
      screen.getByText(/Tramita la supresión total e irreversible/i)
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Tramitar baja definitiva/i })
    ).toBeInTheDocument();
  });

  it('abre el modal de confirmación al presionar el botón de baja definitiva', async () => {
    await act(async () => {
      render(<DangerZoneCard clienteId="cli-123" />);
    });

    expect(
      screen.queryByRole('heading', { name: /Confirmar baja definitiva/i })
    ).not.toBeInTheDocument();

    const triggerBtn = screen.getByRole('button', { name: /Tramitar baja definitiva/i });
    await act(async () => {
      fireEvent.click(triggerBtn);
    });

    expect(
      screen.getByRole('heading', { name: /Confirmar baja definitiva/i })
    ).toBeInTheDocument();
  });
});
