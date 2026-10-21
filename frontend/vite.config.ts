/// <reference types="vitest" />
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: { host: true, port: 5173 },
  // maplibre-gl is split into its own chunk by the React.lazy dynamic import of the map view.
  build: { target: 'es2022' },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
  },
});
