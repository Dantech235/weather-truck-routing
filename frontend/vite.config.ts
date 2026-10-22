/// <reference types="vitest" />
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: { host: true, port: 5173 },
  // maplibre-gl is split into its own chunk by the React.lazy dynamic import of the map view.
  // maplibre-gl alone is ~800 kB minified; it lives in the lazy map chunk.
  build: { target: 'es2022', chunkSizeWarningLimit: 900 },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
  },
});
