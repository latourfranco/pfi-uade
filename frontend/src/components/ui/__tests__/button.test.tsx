import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Button, buttonVariants } from '../button';

describe('Button Component', () => {
  it('renderiza con las clases y variantes por defecto (default, default)', async () => {
    render(<Button>Click Me</Button>);
    const button = await screen.findByRole('button', { name: /click me/i });

    expect(button).toBeInTheDocument();
    expect(button.className).toContain('bg-primary');
    expect(button.className).toContain('h-8');
  });

  it('aplica correctamente todas las variantes disponibles', async () => {
    const variants: Array<NonNullable<Parameters<typeof buttonVariants>[0]>['variant']> = [
      'default',
      'outline',
      'secondary',
      'ghost',
      'destructive',
      'link',
    ];

    for (const variant of variants) {
      const { unmount } = render(<Button variant={variant}>Boton {variant}</Button>);
      const btn = await screen.findByRole('button', { name: new RegExp(`Boton ${variant}`, 'i') });
      expect(btn).toBeInTheDocument();
      unmount();
    }
  });

  it('aplica correctamente todos los tamaños disponibles', async () => {
    const sizes: Array<NonNullable<Parameters<typeof buttonVariants>[0]>['size']> = [
      'default',
      'xs',
      'sm',
      'lg',
      'icon',
      'icon-xs',
      'icon-sm',
      'icon-lg',
    ];

    for (const size of sizes) {
      const { unmount } = render(<Button size={size}>Size {size}</Button>);
      const btn = await screen.findByRole('button', { name: new RegExp(`Size ${size}`, 'i') });
      expect(btn).toBeInTheDocument();
      unmount();
    }
  });

  it('combina clases personalizadas mediante className', async () => {
    render(<Button className="custom-test-class shadow-xl">Custom</Button>);
    const btn = await screen.findByRole('button', { name: /custom/i });

    expect(btn.className).toContain('custom-test-class');
    expect(btn.className).toContain('shadow-xl');
  });

  it('ejecuta el callback onClick al hacer clic', async () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Accion</Button>);

    const btn = await screen.findByRole('button', { name: /accion/i });
    fireEvent.click(btn);

    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('respeta la propiedad disabled y no ejecuta clics', async () => {
    const handleClick = vi.fn();
    render(<Button disabled onClick={handleClick}>Deshabilitado</Button>);

    const btn = await screen.findByRole('button', { name: /deshabilitado/i });
    expect(btn).toBeDisabled();

    fireEvent.click(btn);
    expect(handleClick).not.toHaveBeenCalled();
  });

  it('evalua buttonVariants invocado directamente con y sin argumentos', () => {
    const defaultClasses = buttonVariants();
    expect(defaultClasses).toContain('bg-primary');
    expect(defaultClasses).toContain('h-8');

    const customClasses = buttonVariants({ variant: 'destructive', size: 'lg', className: 'extra' });
    expect(customClasses).toContain('text-destructive');
    expect(customClasses).toContain('h-9');
    expect(customClasses).toContain('extra');
  });
});
