import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Puertos propios de este proyecto (8100 API / 5180 web) para no chocar con otros sistemas.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5180,
    strictPort: true,
    proxy: {
      '/api': 'http://localhost:8100',
    },
  },
})
