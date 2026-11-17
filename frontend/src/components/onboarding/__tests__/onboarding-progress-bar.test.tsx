import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { OnboardingProgressBar } from '../onboarding-progress-bar';

describe('OnboardingProgressBar Component', () => {
  it('renderiza con valores por defecto (totalSteps = 4, className vacía)', async () => {
    const { container } = render(<OnboardingProgressBar currentStep={2} />);
    const progressbar = await screen.findByRole('progressbar');

    expect(progressbar).toBeInTheDocument();
    expect(progressbar).toHaveAttribute('aria-valuenow', '2');
    expect(progressbar).toHaveAttribute('aria-valuemin', '1');
    expect(progressbar).toHaveAttribute('aria-valuemax', '4');
    expect(progressbar).toHaveAttribute('aria-label', 'Paso 2 de 4');
    expect(screen.getByText('Paso 2 de 4')).toBeInTheDocument();

    const bar = container.querySelector('.bg-eureka-primary');
    expect(bar).toHaveStyle({ width: '50%' });
  });

  it('soporta totalSteps personalizados y className adicional', async () => {
    const { container } = render(
      <OnboardingProgressBar currentStep={3} totalSteps={5} className="custom-progress" />
    );
    const progressbar = await screen.findByRole('progressbar');

    expect(progressbar).toHaveClass('custom-progress');
    expect(progressbar).toHaveAttribute('aria-valuenow', '3');
    expect(progressbar).toHaveAttribute('aria-valuemax', '5');
    expect(screen.getByText('Paso 3 de 5')).toBeInTheDocument();

    const bar = container.querySelector('.bg-eureka-primary');
    expect(bar).toHaveStyle({ width: '60%' });
  });

  it('limita el porcentaje a 0% cuando currentStep es negativo', async () => {
    const { container } = render(<OnboardingProgressBar currentStep={-2} totalSteps={4} />);
    await screen.findByRole('progressbar');

    const bar = container.querySelector('.bg-eureka-primary');
    expect(bar).toHaveStyle({ width: '0%' });
  });

  it('limita el porcentaje a 100% cuando currentStep supera totalSteps', async () => {
    const { container } = render(<OnboardingProgressBar currentStep={10} totalSteps={4} />);
    await screen.findByRole('progressbar');

    const bar = container.querySelector('.bg-eureka-primary');
    expect(bar).toHaveStyle({ width: '100%' });
  });
});
