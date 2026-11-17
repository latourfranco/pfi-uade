import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { AudienceBreakdownCard } from '../audience-breakdown-card';
import type { AudienceBreakdownCategory } from '@/lib/friction-data';

describe('AudienceBreakdownCard Component', () => {
  it('renderiza título de categoría y elementos ordenados por porcentaje, filtrando los de 0%', async () => {
    const mockCategory: AudienceBreakdownCategory = {
      title: 'Dispositivo',
      items: [
        { label: 'Mobile', percentage: 25 },
        { label: 'Desktop', percentage: 65 },
        { label: 'Tablet', percentage: 10 },
        { label: 'Smart TV', percentage: 0 },
      ],
    };

    let container: HTMLElement;
    await act(async () => {
      const res = render(<AudienceBreakdownCard category={mockCategory} />);
      container = res.container;
    });

    expect(screen.getByText('Dispositivo')).toBeInTheDocument();
    expect(screen.getByText('Desktop')).toBeInTheDocument();
    expect(screen.getByText('65%')).toBeInTheDocument();
    expect(screen.getByText('Mobile')).toBeInTheDocument();
    expect(screen.getByText('25%')).toBeInTheDocument();
    expect(screen.getByText('Tablet')).toBeInTheDocument();
    expect(screen.getByText('10%')).toBeInTheDocument();

    // El elemento con 0% no debe aparecer
    expect(screen.queryByText('Smart TV')).not.toBeInTheDocument();

    // Primer item tiene la barra primaria
    expect(container!.querySelector('.bg-eureka-primary')).toBeInTheDocument();
    // Items secundarios tienen opacidad 50%
    expect(container!.querySelector('.bg-eureka-primary\\/50')).toBeInTheDocument();
  });

  it('muestra como máximo el top 5 de elementos ordenados por porcentaje descendente', async () => {
    const mockCategory: AudienceBreakdownCategory = {
      title: 'UBICACIÓN',
      items: [
        { label: 'Chile', percentage: 4 },
        { label: 'Argentina', percentage: 40 },
        { label: 'España', percentage: 12 },
        { label: 'México', percentage: 22 },
        { label: 'Colombia', percentage: 10 },
        { label: 'Perú', percentage: 8 },
        { label: 'Uruguay', percentage: 2 },
      ],
    };

    await act(async () => {
      render(<AudienceBreakdownCard category={mockCategory} />);
    });

    // Top 5: Argentina (40%), México (22%), España (12%), Colombia (10%), Perú (8%)
    expect(screen.getByText('Argentina')).toBeInTheDocument();
    expect(screen.getByText('México')).toBeInTheDocument();
    expect(screen.getByText('España')).toBeInTheDocument();
    expect(screen.getByText('Colombia')).toBeInTheDocument();
    expect(screen.getByText('Perú')).toBeInTheDocument();

    // El 6to y 7mo no deben renderizarse
    expect(screen.queryByText('Chile')).not.toBeInTheDocument();
    expect(screen.queryByText('Uruguay')).not.toBeInTheDocument();
  });
});
