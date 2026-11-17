import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { EurekaLogo } from '../eureka-logo';

describe('EurekaLogo Component', () => {
  it('renderiza con los valores por defecto (size md = 26px, priority true)', async () => {
    await act(async () => {
      render(<EurekaLogo />);
    });
    const img = screen.getByAltText('eureka logo');

    expect(img).toBeInTheDocument();
    expect(img).toHaveStyle({ height: '26px' });
  });

  it('aplica las alturas correspondientes para cada tamaño prestablecido', async () => {
    const expectedHeights = {
      sm: '20px',
      md: '26px',
      lg: '36px',
      xl: '48px',
    } as const;

    for (const [size, height] of Object.entries(expectedHeights) as Array<[keyof typeof expectedHeights, string]>) {
      let unmountFn!: () => void;
      await act(async () => {
        const { unmount } = render(<EurekaLogo size={size} />);
        unmountFn = unmount;
      });
      const img = screen.getByAltText('eureka logo');
      expect(img).toHaveStyle({ height });
      unmountFn();
    }
  });

  it('prioriza la prop height personalizada sobre el heightMap', async () => {
    await act(async () => {
      render(<EurekaLogo size="sm" height={72} />);
    });
    const img = screen.getByAltText('eureka logo');

    expect(img).toHaveStyle({ height: '72px' });
  });

  it('soporta className personalizada y priority false', async () => {
    await act(async () => {
      render(<EurekaLogo className="custom-logo-class" priority={false} />);
    });
    const img = screen.getByAltText('eureka logo');

    const wrapper = img.parentElement;
    expect(wrapper?.className).toContain('custom-logo-class');
  });
});
