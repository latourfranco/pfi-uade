import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { AudienceSummaryCard } from '../audience-summary-card';

describe('AudienceSummaryCard Component', () => {
  it('renderiza la etiqueta de sección y el texto de resumen de audiencia', async () => {
    const summaryText = 'Usuarios de desktop navegando desde Chrome en Argentina.';

    await act(async () => {
      render(<AudienceSummaryCard summary={summaryText} />);
    });

    expect(screen.getByText('Quiénes son')).toBeInTheDocument();
    expect(screen.getByText(summaryText)).toBeInTheDocument();
  });
});
