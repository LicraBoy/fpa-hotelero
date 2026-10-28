import { defineConfig } from '@playwright/test'
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'

// Capturas de pantalla con DATOS REALES: el backend corre sobre una COPIA de `fpa_dev.db`
// (backend/scripts/servidor_captura.py, puerto 8102) y el frontend es el build servido en 5182.
// No toca la base ni los puertos de desarrollo (8100 / 5180) ni los de las pruebas e2e (8101 / 5181).
//   npx playwright test -c playwright.captura.config.ts
const PY_WINDOWS = resolve('../backend/.venv/Scripts/python.exe')
const PY_UNIX = resolve('../backend/.venv/bin/python')
const WEB = process.env.FPA_CAPTURA_WEB ?? '5182'
const python = process.env.FPA_PYTHON ?? (existsSync(PY_WINDOWS) ? PY_WINDOWS : PY_UNIX)
// FPA_CAPTURA_REUSAR=1: los servidores ya están corriendo (API en 8102 y `npm run dev` en 5182): solo captura.
const reusar = process.env.FPA_CAPTURA_REUSAR === '1'

export default defineConfig({
  testDir: './capturas',
  timeout: 90_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: `http://localhost:${WEB}`,
    locale: 'es-MX',
  },
  webServer: [
    {
      command: `"${python}" scripts/servidor_captura.py`,
      cwd: '../backend',
      url: 'http://127.0.0.1:8102/api/health',
      reuseExistingServer: reusar,
      timeout: 90_000,
    },
    {
      command: 'npm run build && npm run preview',
      url: `http://localhost:${WEB}`,
      reuseExistingServer: reusar,
      timeout: 120_000,
      env: { FPA_WEB_PUERTO: WEB, FPA_API_URL: 'http://127.0.0.1:8102' },
    },
  ],
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
})
