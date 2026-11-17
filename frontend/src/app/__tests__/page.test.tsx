import { describe, it, expect } from 'vitest';
import RootPage from '../page';
import { redirect } from 'next/navigation';

describe('RootPage (src/app/page.tsx)', () => {
  it('redirige inmediatamente a /onboarding/rubro', () => {
    expect(() => RootPage()).toThrow('NEXT_REDIRECT: /onboarding/rubro');
    expect(redirect).toHaveBeenCalledWith('/onboarding/rubro');
  });
});
