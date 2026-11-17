import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const reactDomEntry = require.resolve('react-dom');
const reactEntry = require.resolve('react', { paths: [path.dirname(reactDomEntry)] });

export default defineConfig({
  plugins: [react()],
  resolve: {
    tsconfigPaths: true,
    dedupe: ['react', 'react-dom'],
    alias: [
      { find: /^react$/, replacement: reactEntry },
      { find: /^react-dom$/, replacement: reactDomEntry },
    ],
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    server: {
      deps: {
        inline: ['react', 'react-dom', '@testing-library/react'],
      },
    },
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'lcov'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/**/*.d.ts',
        'src/lib/constants.ts',
        'src/app/layout.tsx',
      ],
      thresholds: {
        statements: 85,
        branches: 85,
        perFile: true,
      },
    },
  },
});
