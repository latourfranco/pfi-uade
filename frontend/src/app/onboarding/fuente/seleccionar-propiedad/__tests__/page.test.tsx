import { act } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import SeleccionarPropiedadPage from '../page';
import * as nextHeaders from 'next/headers';
import { redirect } from 'next/navigation';

describe('SeleccionarPropiedadPage (src/app/onboarding/fuente/seleccionar-propiedad/page.tsx)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('redirige a sesion_expirada si la cookie ga4_pending_auth no existe', async () => {
    vi.spyOn(nextHeaders, 'cookies').mockResolvedValue({
      get: vi.fn(() => undefined),
      set: vi.fn(),
      delete: vi.fn(),
    } as unknown as Awaited<ReturnType<typeof nextHeaders.cookies>>);

    await expect(SeleccionarPropiedadPage()).rejects.toThrow('NEXT_REDIRECT: /onboarding/fuente?error=sesion_expirada');
    expect(redirect).toHaveBeenCalledWith('/onboarding/fuente?error=sesion_expirada');
  });

  it('redirige a sesion_invalida si el valor de la cookie no es un JSON válido', async () => {
    vi.spyOn(nextHeaders, 'cookies').mockResolvedValue({
      get: vi.fn(() => ({ name: 'ga4_pending_auth', value: 'invalid-json' })),
      set: vi.fn(),
      delete: vi.fn(),
    } as unknown as Awaited<ReturnType<typeof nextHeaders.cookies>>);

    await expect(SeleccionarPropiedadPage()).rejects.toThrow('NEXT_REDIRECT: /onboarding/fuente?error=sesion_invalida');
    expect(redirect).toHaveBeenCalledWith('/onboarding/fuente?error=sesion_invalida');
  });

  it('redirige a no_ga4_property_found si la cookie contiene un objeto sin la clave properties', async () => {
    vi.spyOn(nextHeaders, 'cookies').mockResolvedValue({
      get: vi.fn(() => ({
        name: 'ga4_pending_auth',
        value: JSON.stringify({}),
      })),
      set: vi.fn(),
      delete: vi.fn(),
    } as unknown as Awaited<ReturnType<typeof nextHeaders.cookies>>);

    await expect(SeleccionarPropiedadPage()).rejects.toThrow('NEXT_REDIRECT: /onboarding/fuente?error=no_ga4_property_found');
    expect(redirect).toHaveBeenCalledWith('/onboarding/fuente?error=no_ga4_property_found');
  });

  it('redirige a no_ga4_property_found si la cookie contiene un array vacío de propiedades', async () => {
    vi.spyOn(nextHeaders, 'cookies').mockResolvedValue({
      get: vi.fn(() => ({
        name: 'ga4_pending_auth',
        value: JSON.stringify({ properties: [] }),
      })),
      set: vi.fn(),
      delete: vi.fn(),
    } as unknown as Awaited<ReturnType<typeof nextHeaders.cookies>>);

    await expect(SeleccionarPropiedadPage()).rejects.toThrow('NEXT_REDIRECT: /onboarding/fuente?error=no_ga4_property_found');
    expect(redirect).toHaveBeenCalledWith('/onboarding/fuente?error=no_ga4_property_found');
  });

  it('renderiza correctamente el formulario de selección cuando hay múltiples propiedades', async () => {
    const mockProperties = [
      {
        propertyId: '12345',
        propertyName: 'Tienda Oficial',
        accountName: 'Cuenta Principal',
      },
      {
        propertyId: '67890',
        propertyName: 'Tienda Secundaria',
        accountName: 'Cuenta Principal',
      },
    ];

    vi.spyOn(nextHeaders, 'cookies').mockResolvedValue({
      get: vi.fn(() => ({
        name: 'ga4_pending_auth',
        value: JSON.stringify({ properties: mockProperties }),
      })),
      set: vi.fn(),
      delete: vi.fn(),
    } as unknown as Awaited<ReturnType<typeof nextHeaders.cookies>>);

    const jsx = await SeleccionarPropiedadPage();

    await act(async () => {
      render(jsx);
    });

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Selecciona la propiedad de GA4 a vincular.');
    expect(screen.getByText('Tienda Oficial')).toBeInTheDocument();
    expect(screen.getByText('Tienda Secundaria')).toBeInTheDocument();

    const radios = screen.getAllByRole('radio');
    expect(radios.length).toBe(2);
    expect(radios[0]).toBeChecked();
    expect(radios[1]).not.toBeChecked();

    expect(screen.getByRole('button', { name: /confirmar e integrar propiedad/i })).toBeInTheDocument();
  });
});
