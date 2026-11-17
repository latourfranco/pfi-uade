import { describe, it, expect } from 'vitest';
import OnboardingIndexPage from '../page';
import { redirect } from 'next/navigation';

describe('OnboardingIndexPage (src/app/onboarding/page.tsx)', () => {
  it('redirige inmediatamente a /onboarding/rubro', () => {
    expect(() => OnboardingIndexPage()).toThrow('NEXT_REDIRECT: /onboarding/rubro');
    expect(redirect).toHaveBeenCalledWith('/onboarding/rubro');
  });
});
