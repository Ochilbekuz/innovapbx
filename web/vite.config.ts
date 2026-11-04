/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

const design = fileURLToPath(new URL('../replica/design', import.meta.url));
const docs = fileURLToPath(new URL('../docs/qollanma', import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@design': design, '@docs': docs, '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: {
    fs: { allow: ['..'] },
    proxy: {
      '/api': { target: 'http://127.0.0.1:8710', changeOrigin: true },
      '/sip-ws': { target: 'http://127.0.0.1:8711', ws: true, changeOrigin: true },
    },
  },
  build: { sourcemap: false, chunkSizeWarningLimit: 700 },
  test: {
    environment: 'jsdom',
    globals: false,
    setupFiles: ['./src/test-setup.ts'],
    css: false,
    // Playwright e2e ("e2e/*.spec.ts") — bu yerda emas, `npx playwright test` bilan yuritiladi.
    exclude: ['**/node_modules/**', '**/e2e/**', 'target/**'],
  },
});
