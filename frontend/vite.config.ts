import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// In development the app calls /api/... on its own origin, and Vite forwards
// those requests to the FastAPI service. No CORS set-up is needed.
const apiTarget = process.env.NXCAT_API_URL ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { '/api': apiTarget },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    restoreMocks: true,
  },
})
