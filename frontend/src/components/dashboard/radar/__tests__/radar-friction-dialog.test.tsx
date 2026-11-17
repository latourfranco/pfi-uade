import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { RadarFrictionDialog } from '../radar-friction-dialog';
import type { FrictionCluster } from '../../dashboard-radar-canvas';

const baseCluster: FrictionCluster = {
  id: 'clust-dialog-1',
  x: 100,
  y: 100,
  radius: 30,
  tier: 'alta',
  coreColor: '#DC2626',
  auraGradientColor: 'rgba(220, 38, 38, 0.55)',
  dotPalettes: { hot: '', mid: '', warm: '', soft: '' },
  name: 'Error en selector de talles',
  severity: 'alta',
  impact: '-30%',
  sessions: '5.000',
  users: '2.500',
  sessionsCount: '5.000',
  diagnosis: 'El desplegable no responde al primer tap.',
  proximityLabel: 'Criticidad alta',
};

describe('RadarFrictionDialog Component', () => {
  it('no renderiza contenido cuando cluster es null', async () => {
    await act(async () => {
      render(
        <RadarFrictionDialog
          cluster={null}
          eventName="Ficha de Producto"
          onClose={vi.fn()}
        />
      );
    });

    expect(screen.queryByText('Error en selector de talles')).not.toBeInTheDocument();
  });

  it('renderiza correctamente los datos y badges para criticidad alta con eventId', async () => {
    const handleClose = vi.fn();

    await act(async () => {
      render(
        <RadarFrictionDialog
          cluster={baseCluster}
          eventId="producto"
          eventName="Ficha de Producto"
          onClose={handleClose}
        />
      );
    });

    expect(screen.getByText('Error en selector de talles')).toBeInTheDocument();
    expect(screen.getByText('Criticidad alta')).toBeInTheDocument();
    expect(screen.getByText('Ficha de Producto')).toBeInTheDocument();
    expect(screen.getByText('2.500')).toBeInTheDocument();
    expect(screen.getByText('5.000')).toBeInTheDocument();
    expect(screen.getByText('El desplegable no responde al primer tap.')).toBeInTheDocument();

    const link = screen.getByRole('link', { name: /explorar detalle/i });
    expect(link).toHaveAttribute('href', '/dashboard/friccion/clust-dialog-1?event=producto');

    // Botón Volver
    const volverBtn = screen.getByRole('button', { name: /volver/i });
    fireEvent.click(volverBtn);
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('renderiza variante de criticidad media sin eventId', async () => {
    const mediaCluster: FrictionCluster = {
      ...baseCluster,
      id: 'clust-media',
      severity: 'media',
    };

    await act(async () => {
      render(
        <RadarFrictionDialog
          cluster={mediaCluster}
          eventName="Carrito"
          onClose={vi.fn()}
        />
      );
    });

    expect(screen.getByText('Criticidad media')).toBeInTheDocument();
    const link = screen.getByRole('link', { name: /explorar detalle/i });
    expect(link).toHaveAttribute('href', '/dashboard/friccion/clust-media');
  });

  it('renderiza variante de criticidad baja', async () => {
    const bajaCluster: FrictionCluster = {
      ...baseCluster,
      id: 'clust-baja',
      severity: 'baja',
    };

    await act(async () => {
      render(
        <RadarFrictionDialog
          cluster={bajaCluster}
          eventName="Checkout"
          onClose={vi.fn()}
        />
      );
    });

    expect(screen.getByText('Criticidad baja')).toBeInTheDocument();
  });

  it('llama a onClose cuando el diálogo dispara onOpenChange con false', async () => {
    const handleClose = vi.fn();

    await act(async () => {
      render(
        <RadarFrictionDialog
          cluster={baseCluster}
          eventName="Checkout"
          onClose={handleClose}
        />
      );
    });

    const closeTrigger = screen.getByTestId('mock-dialog-close-trigger');
    await act(async () => {
      fireEvent.click(closeTrigger);
    });

    expect(handleClose).toHaveBeenCalledTimes(1);
  });
});
