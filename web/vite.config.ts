import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Port 5180 (not Vite's default 5173, which is used by another project on this machine).
// strictPort: fail loudly instead of silently moving to a port the API's CORS doesn't allow.
const PORT = 5180

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: PORT, strictPort: true },
  preview: { port: PORT, strictPort: true },
  build: {
    rollupOptions: {
      output: {
        // Long-lived vendor chunks: cached across deploys of our own code.
        manualChunks(id: string) {
          if (id.includes('node_modules/@supabase')) return 'supabase'
          if (/node_modules\/(react|react-dom|react-router|scheduler)\//.test(id)) return 'react'
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    restoreMocks: true,
  },
})
