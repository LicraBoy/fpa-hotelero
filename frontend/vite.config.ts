import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Puertos propios de este proyecto (8100 API / 5180 web) para no chocar con otros sistemas.
// Las pruebas e2e usan otros (8101 / 5181) mediante estas variables.
const api = process.env.FPA_API_URL ?? 'http://127.0.0.1:8100'
const puerto = Number(process.env.FPA_WEB_PUERTO ?? 5180)

// Política de seguridad del frontend (docs/adr/0004-seguridad-del-frontend.md). La de producción
// no permite NADA en línea: ni scripts ni estilos. `vite preview` sirve el build con esta misma
// política, y las pruebas de navegador corren contra ella.
const CSP_PRODUCCION = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self'",
  "img-src 'self' data:",
  "font-src 'self'",
  "connect-src 'self'",
  "object-src 'none'",
  "base-uri 'none'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join('; ')

// El servidor de desarrollo necesita 'unsafe-inline' (el refresco en caliente de React inyecta un
// script y Vite inyecta los estilos) y un WebSocket. Solo vale para desarrollo local.
const CSP_DESARROLLO = CSP_PRODUCCION.replace("script-src 'self'", "script-src 'self' 'unsafe-inline'")
  .replace("style-src 'self'", "style-src 'self' 'unsafe-inline'")
  .replace("connect-src 'self'", "connect-src 'self' ws: wss:")

const OTRAS_CABECERAS = {
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'DENY',
  'Referrer-Policy': 'no-referrer',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
  'Cross-Origin-Opener-Policy': 'same-origin',
}

export default defineConfig({
  plugins: [tailwindcss(), react()],
  server: {
    port: puerto,
    strictPort: true,
    proxy: {
      '/api': api,
    },
    headers: { ...OTRAS_CABECERAS, 'Content-Security-Policy': CSP_DESARROLLO },
  },
  preview: {
    port: puerto,
    strictPort: true,
    proxy: {
      '/api': api,
    },
    headers: { ...OTRAS_CABECERAS, 'Content-Security-Policy': CSP_PRODUCCION },
  },
})
