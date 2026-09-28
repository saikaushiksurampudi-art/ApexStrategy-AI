import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
    // Component tests live beside the code; e2e lives in ../tests/e2e (pytest).
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
