import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { DerechoSupresionCard } from '../derecho-supresion-card';

describe('DerechoSupresionCard', () => {
  it('renderiza la información sobre el derecho de supresión y los pilares de supresión', async () => {
    await act(async () => {
      render(<DerechoSupresionCard />);
    });

    expect(
      screen.getByText('Ejercicio del Derecho de Supresión de Datos')
    ).toBeInTheDocument();
    expect(screen.getByText('1. Revocación de Tokens')).toBeInTheDocument();
    expect(screen.getByText('2. Purga Transaccional & DW')).toBeInTheDocument();
    expect(screen.getByText('3. Trazabilidad Legal')).toBeInTheDocument();
  });
});
