import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  Dialog,
  DialogTrigger,
  DialogPortal,
  DialogClose,
  DialogOverlay,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
} from '../dialog';

describe('Dialog Components', () => {
  it('renderiza la composicion completa del dialogo con todas sus partes', async () => {
    render(
      <Dialog open={true}>
        <DialogTrigger>Abrir Dialogo</DialogTrigger>
        <DialogPortal>
          <DialogOverlay className="custom-overlay" />
          <DialogContent className="custom-content">
            <DialogHeader className="custom-header">
              <DialogTitle className="custom-title">Titulo del Dialogo</DialogTitle>
              <DialogDescription className="custom-desc">
                Descripcion detallada del contenido.
              </DialogDescription>
            </DialogHeader>
            <div data-testid="dialog-body">Cuerpo de prueba</div>
            <DialogFooter className="custom-footer">
              <button>Accion Secundaria</button>
            </DialogFooter>
          </DialogContent>
        </DialogPortal>
      </Dialog>
    );

    const title = await screen.findByText('Titulo del Dialogo');
    expect(title).toBeInTheDocument();
    expect(title).toHaveAttribute('data-slot', 'dialog-title');
    expect(title.className).toContain('custom-title');

    const desc = screen.getByText('Descripcion detallada del contenido.');
    expect(desc).toHaveAttribute('data-slot', 'dialog-description');
    expect(desc.className).toContain('custom-desc');

    const content = screen.getByText('Cuerpo de prueba').closest('[data-slot="dialog-content"]');
    expect(content).toBeInTheDocument();
    expect(content?.className).toContain('custom-content');

    const trigger = screen.getByText('Abrir Dialogo');
    expect(trigger).toHaveAttribute('data-slot', 'dialog-trigger');

    // Por defecto showCloseButton es true en DialogContent
    const closeBtn = screen.getByRole('button', { name: /close/i });
    expect(closeBtn).toBeInTheDocument();
  });

  it('DialogContent no renderiza el boton de cerrar si showCloseButton es false', async () => {
    render(
      <Dialog open={true}>
        <DialogContent showCloseButton={false}>
          <div>Sin boton cerrar</div>
        </DialogContent>
      </Dialog>
    );

    await screen.findByText('Sin boton cerrar');
    const closeBtn = screen.queryByRole('button', { name: /close/i });
    expect(closeBtn).toBeNull();
  });

  it('DialogFooter renderiza el boton Close cuando showCloseButton es true', async () => {
    render(
      <Dialog open={true}>
        <DialogFooter showCloseButton={true}>
          <span>Boton de Accion</span>
        </DialogFooter>
      </Dialog>
    );

    await screen.findByText('Boton de Accion');
    const footerCloseBtn = screen.getByRole('button', { name: /close/i });
    expect(footerCloseBtn).toBeInTheDocument();
    expect(footerCloseBtn.className).toContain('cursor-pointer');
  });

  it('DialogFooter no renderiza boton Close cuando showCloseButton es false', async () => {
    render(
      <Dialog open={true}>
        <DialogFooter showCloseButton={false}>
          <span>Footer simple</span>
        </DialogFooter>
      </Dialog>
    );

    await screen.findByText('Footer simple');
    const footerCloseBtn = screen.queryByRole('button', { name: /close/i });
    expect(footerCloseBtn).toBeNull();
  });

  it('renderiza DialogClose directamente', async () => {
    render(
      <DialogClose className="custom-close-standalone">
        <span>Cerrar Modal</span>
      </DialogClose>
    );

    const close = await screen.findByText('Cerrar Modal');
    expect(close.closest('[data-slot="dialog-close"]')).toBeInTheDocument();
  });
});
