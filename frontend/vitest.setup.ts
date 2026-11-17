import '@testing-library/jest-dom/vitest';
import { vi, afterEach } from 'vitest';
import { cleanup, act } from '@testing-library/react';

// Habilita entorno de act para React 19 en Vitest/JSDOM
// @ts-expect-error IS_REACT_ACT_ENVIRONMENT is used by React
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

afterEach(async () => {
  await act(async () => {
    cleanup();
  });
});

// Mock de Next.js App Router Navigation
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => '/',
  redirect: vi.fn((url: string) => {
    const error = new Error(`NEXT_REDIRECT: ${url}`);
    (error as unknown as { digest: string }).digest = `NEXT_REDIRECT;${url}`;
    throw error;
  }),
}));

// Mock de Next.js Headers (cookies)
vi.mock('next/headers', () => {
  const cookieStore = new Map<string, { name: string; value: string }>();
  return {
    cookies: vi.fn(async () => ({
      get: vi.fn((name: string) => cookieStore.get(name)),
      set: vi.fn((name: string, value: string) => {
        cookieStore.set(name, { name, value });
      }),
      delete: vi.fn((name: string) => {
        cookieStore.delete(name);
      }),
    })),
  };
});

// Mock de ResizeObserver para JSDOM
globalThis.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Mock de matchMedia para JSDOM
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Mock de lucide-react
vi.mock('lucide-react', async () => {
  const React = await import('react');
  const makeIcon = (name: string) => {
    return React.forwardRef<SVGSVGElement, React.SVGProps<SVGSVGElement>>(
      function MockIcon(props, ref) {
        return React.createElement('svg', { ref, 'data-icon': name, ...props });
      }
    );
  };

  const icons = [
    'XIcon',
    'ArrowRight',
    'Globe',
    'BarChart3',
    'Users',
    'MousePointer2',
    'Lock',
    'Check',
    'ArrowLeft',
    'CheckCircle2',
    'ChevronLeft',
    'ChevronRight',
    'Sparkles',
    'ZoomIn',
    'X',
    'ShieldCheck',
    'AlertCircle',
    'Coins',
    'Loader2',
    'KeyRound',
    'AlertTriangle',
    'ShieldAlert',
    'Trash2',
    'Database',
    'Clock',
    'FileText',
    'Building2',
    'Briefcase',
    'UserCog',
    'Settings',
    'TrendingDown',
    'Download',
    'Mail',
    'LogOut',
  ];

  const exportObj: Record<string, ReturnType<typeof makeIcon>> = {};
  for (const icon of icons) {
    exportObj[icon] = makeIcon(icon);
  }

  return new Proxy(exportObj, {
    get: (target, prop: string) => {
      if (typeof prop === 'string' && prop in target) return target[prop];
      return makeIcon(String(prop));
    },
  });
});

// Mock de @base-ui/react/button
vi.mock('@base-ui/react/button', async () => {
  const React = await import('react');
  const Button = React.forwardRef<HTMLButtonElement, React.ComponentPropsWithoutRef<'button'>>(
    function MockButton({ children, ...props }, ref) {
      return React.createElement('button', { ref, ...props }, children);
    }
  );
  return { Button };
});

// Mock de @base-ui/react/dialog
vi.mock('@base-ui/react/dialog', async () => {
  const React = await import('react');

  const Root = ({
    children,
    open = true,
    onOpenChange,
    ...props
  }: React.ComponentPropsWithoutRef<'div'> & {
    open?: boolean;
    onOpenChange?: (open: boolean) => void;
  }) => {
    return React.createElement(
      'div',
      { 'data-slot': 'dialog', 'data-state': open ? 'open' : 'closed', ...props },
      open ? children : null,
      onOpenChange
        ? React.createElement('button', {
            'data-testid': 'mock-dialog-close-trigger',
            onClick: () => onOpenChange(false),
          })
        : null
    );
  };

  const Trigger = ({ children, ...props }: React.ComponentPropsWithoutRef<'button'>) => {
    return React.createElement('button', { 'data-slot': 'dialog-trigger', ...props }, children);
  };

  const Portal = ({ children }: { children?: React.ReactNode }) => {
    return React.createElement(React.Fragment, null, children);
  };

  const Backdrop = ({ ...props }: React.ComponentPropsWithoutRef<'div'>) => {
    return React.createElement('div', { 'data-slot': 'dialog-overlay', ...props });
  };

  const Popup = ({ children, ...props }: React.ComponentPropsWithoutRef<'div'>) => {
    return React.createElement('div', { 'data-slot': 'dialog-content', ...props }, children);
  };

  const Title = ({ children, ...props }: React.ComponentPropsWithoutRef<'h2'>) => {
    return React.createElement('h2', { 'data-slot': 'dialog-title', ...props }, children);
  };

  const Description = ({ children, ...props }: React.ComponentPropsWithoutRef<'p'>) => {
    return React.createElement('p', { 'data-slot': 'dialog-description', ...props }, children);
  };

  const Close = ({
    render,
    children,
    ...props
  }: React.ComponentPropsWithoutRef<'button'> & { render?: React.ReactElement }) => {
    if (render && React.isValidElement(render)) {
      return React.cloneElement(render, props as Record<string, unknown>, children);
    }
    return React.createElement('button', { 'data-slot': 'dialog-close', ...props }, children);
  };

  return {
    Dialog: {
      Root,
      Trigger,
      Portal,
      Backdrop,
      Popup,
      Title,
      Description,
      Close,
    },
  };
});

// Mock de next/image
vi.mock('next/image', async () => {
  const React = await import('react');
  return {
    default: React.forwardRef<
      HTMLImageElement,
      React.ComponentPropsWithoutRef<'img'> & { priority?: boolean; fill?: boolean }
    >(function MockImage({ priority, fill, ...props }, ref) {
      void priority;
      void fill;
      return React.createElement('img', { ref, ...props });
    }),
  };
});

// Mock de next/link
vi.mock('next/link', async () => {
  const React = await import('react');
  return {
    default: React.forwardRef<
      HTMLAnchorElement,
      React.ComponentPropsWithoutRef<'a'> & { href: string | { pathname?: string } }
    >(function MockLink({ href, children, ...props }, ref) {
      const resolvedHref = typeof href === 'object' && href !== null ? (href as { pathname?: string }).pathname || '' : href;
      return React.createElement('a', { ref, href: resolvedHref, ...props }, children);
    }),
  };
});
