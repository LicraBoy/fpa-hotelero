import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Puertos propios de este proyecto (8100 API / 5180 web) para no chocar con otros sistemas.
// Las pruebas e2e usan otros (8101 / 5181) mediante estas variables.
const api = process.env.FPA_API_URL ?? 'http://127.0.0.1:8100'
const puerto = Number(process.env.FPA_WEB_PUERTO ?? 5180)

export default defineConfig({
  plugins: [react()],
  server: {
    port: puerto,
    strictPort: true,
    proxy: {
      '/api': api,
    },
  },
})
