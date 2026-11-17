import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { ModalConfirmacionBaja } from '../modal-confirmacion-baja';
import * as cuentaActions from '@/app/actions/cuenta';

vi.mock('@/app/actions/cuenta', () => ({
  solicitarBajaDefinitivaCuentaAction: vi.fn(),
}));

describe('ModalConfirmacionBaja', () => {
  const onOpenChangeMock = vi.fn();
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

  it('no muestra el contenido si isOpen es false', async () => {
    await act(async () => {
      render(
        <ModalConfirmacionBaja
          isOpen={false}
          onOpenChange={onOpenChangeMock}
        />
      );
    });

    expect(screen.queryByText('Confirmar baja definitiva')).not.toBeInTheDocument();
  });

  it('muestra el modal y mantiene deshabilitado el botón hasta tipear ELIMINAR MI CUENTA', async () => {
    await act(async () => {
      render(
        <ModalConfirmacionBaja
          isOpen={true}
          onOpenChange={onOpenChangeMock}
          clienteId="cli-test"
        />
      );
    });

    expect(
      screen.getByRole('heading', { name: /Confirmar baja definitiva/i })
    ).toBeInTheDocument();
    expect(screen.getByText('Revocación de tokens de Google:')).toBeInTheDocument();

    const confirmBtn = screen.getByRole('button', { name: /Confirmar baja definitiva/i });
    expect(confirmBtn).toBeDisabled();

    const input = screen.getByRole('textbox');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'OTRA COSA' } });
    });
    expect(confirmBtn).toBeDisabled();

    await act(async () => {
      fireEvent.change(input, { target: { value: 'ELIMINAR MI CUENTA' } });
    });
    expect(confirmBtn).not.toBeDisabled();
  });

  it('ejecuta solicitarBajaDefinitivaCuentaAction y redirige en caso de éxito', async () => {
    vi.mocked(cuentaActions.solicitarBajaDefinitivaCuentaAction).mockResolvedValue({
      success: true,
      redirectUrl: '/onboarding/rubro?cuenta_eliminada=true',
    });

    await act(async () => {
      render(
        <ModalConfirmacionBaja
          isOpen={true}
          onOpenChange={onOpenChangeMock}
          clienteId="cli-xyz"
        />
      );
    });

    const input = screen.getByRole('textbox');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'ELIMINAR MI CUENTA' } });
    });

    const confirmBtn = screen.getByRole('button', { name: /Confirmar baja definitiva/i });
    await act(async () => {
      fireEvent.click(confirmBtn);
    });

    await waitFor(() => {
      expect(cuentaActions.solicitarBajaDefinitivaCuentaAction).toHaveBeenCalledWith({
        clienteId: 'cli-xyz',
        confirmacion: 'ELIMINAR MI CUENTA',
        motivo: expect.any(String),
      });
      expect(window.location.href).toBe('/onboarding/rubro?cuenta_eliminada=true');
    });
  });

  it('muestra mensaje de error si la acción retorna success=false', async () => {
    vi.mocked(cuentaActions.solicitarBajaDefinitivaCuentaAction).mockResolvedValue({
      success: false,
      error: 'Error interno en la purga',
    });

    await act(async () => {
      render(
        <ModalConfirmacionBaja
          isOpen={true}
          onOpenChange={onOpenChangeMock}
        />
      );
    });

    const input = screen.getByRole('textbox');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'ELIMINAR MI CUENTA' } });
    });

    const confirmBtn = screen.getByRole('button', { name: /Confirmar baja definitiva/i });
    await act(async () => {
      fireEvent.click(confirmBtn);
    });

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Error interno en la purga');
    });
  });

  it('muestra mensaje fallback si la acción retorna success=false sin mensaje de error', async () => {
    vi.mocked(cuentaActions.solicitarBajaDefinitivaCuentaAction).mockResolvedValue({
      success: false,
    });

    await act(async () => {
      render(
        <ModalConfirmacionBaja
          isOpen={true}
          onOpenChange={onOpenChangeMock}
        />
      );
    });

    const input = screen.getByRole('textbox');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'ELIMINAR MI CUENTA' } });
    });

    const confirmBtn = screen.getByRole('button', { name: /Confirmar baja definitiva/i });
    await act(async () => {
      fireEvent.click(confirmBtn);
    });

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Ocurrió un fallo al procesar la baja de la cuenta. Intente nuevamente.'
      );
    });
  });

  it('muestra mensaje fallback si la acción retorna success=true pero sin redirectUrl', async () => {
    vi.mocked(cuentaActions.solicitarBajaDefinitivaCuentaAction).mockResolvedValue({
      success: true,
      redirectUrl: undefined as unknown as string,
    });

    await act(async () => {
      render(
        <ModalConfirmacionBaja
          isOpen={true}
          onOpenChange={onOpenChangeMock}
        />
      );
    });

    const input = screen.getByRole('textbox');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'ELIMINAR MI CUENTA' } });
    });

    const confirmBtn = screen.getByRole('button', { name: /Confirmar baja definitiva/i });
    await act(async () => {
      fireEvent.click(confirmBtn);
    });

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Ocurrió un fallo al procesar la baja de la cuenta. Intente nuevamente.'
      );
    });
  });

  it('captura excepción tipo Error al fallar la acción', async () => {
    vi.mocked(cuentaActions.solicitarBajaDefinitivaCuentaAction).mockRejectedValue(
      new Error('Fallo de red al conectar con servidor')
    );

    await act(async () => {
      render(
        <ModalConfirmacionBaja
          isOpen={true}
          onOpenChange={onOpenChangeMock}
        />
      );
    });

    const input = screen.getByRole('textbox');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'ELIMINAR MI CUENTA' } });
    });

    const confirmBtn = screen.getByRole('button', { name: /Confirmar baja definitiva/i });
    await act(async () => {
      fireEvent.click(confirmBtn);
    });

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Fallo de red al conectar con servidor'
      );
    });
  });

  it('captura excepción genérica (no Error) al fallar la acción', async () => {
    vi.mocked(cuentaActions.solicitarBajaDefinitivaCuentaAction).mockRejectedValue(
      'Crash no estructurado'
    );

    await act(async () => {
      render(
        <ModalConfirmacionBaja
          isOpen={true}
          onOpenChange={onOpenChangeMock}
        />
      );
    });

    const input = screen.getByRole('textbox');
    await act(async () => {
      fireEvent.change(input, { target: { value: 'ELIMINAR MI CUENTA' } });
    });

    const confirmBtn = screen.getByRole('button', { name: /Confirmar baja definitiva/i });
    await act(async () => {
      fireEvent.click(confirmBtn);
    });

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Error de conexión al tramitar la baja definitiva.'
      );
    });
  });

  it('cierra el modal cuando se hace clic en Cancelar', async () => {
    await act(async () => {
      render(
        <ModalConfirmacionBaja
          isOpen={true}
          onOpenChange={onOpenChangeMock}
        />
      );
    });

    const cancelBtn = screen.getByRole('button', { name: /Cancelar/i });
    await act(async () => {
      fireEvent.click(cancelBtn);
    });

    expect(onOpenChangeMock).toHaveBeenCalledWith(false);
  });
});
