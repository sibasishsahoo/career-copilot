import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],

  server: {
    proxy: {
      // The browser calls /api/applications ... Vite forwards it to the FastAPI backend as
      // /applications ... From the browser's point of view everything comes from ONE origin
      // (localhost:5173), so no CORS setup is needed during development.
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },

  // Vitest (the test runner) reads its settings from this same file.
  test: {
    environment: 'jsdom', // a fake browser, so components can be rendered in tests
    globals: true,
    setupFiles: './src/test/setup.ts',
    css: false,
  },
})
