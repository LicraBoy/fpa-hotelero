import { defineConfig } from '@playwright/test'
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'

// Las pruebas de navegador levantan SU PROPIO backend limpio (puerto 8101, base temporal) y su
// propio frontend (puerto 5181): no tocan la base ni los puertos de desarrollo (8100 / 5180).
const PY_WINDOWS = resolve('../backend/.venv/Scripts/python.exe')
const PY_UNIX = resolve('../backend/.venv/bin/python')
const python = process.env.FPA_PYTHON ?? (existsSync(PY_WINDOWS) ? PY_WINDOWS : PY_UNIX)

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: false,
  workers: 1, // comparten una base de datos limpia: los pasos van en orden
  retries: 0,
  reporter: [['list']],
  globalSetup: './e2e/preparar.ts',
  use: {
    baseURL: 'http://localhost:5181',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    locale: 'es-MX',
  },
  webServer: [
    {
      command: `"${python}" scripts/servidor_e2e.py`,
      cwd: '../backend',
      url: 'http://127.0.0.1:8101/api/health',
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      // El build de producción servido con su CSP estricta (`vite preview`): cualquier script o
      // estilo en línea rompe la prueba, igual que rompería en producción.
      command: 'npm run build && npm run preview',
      url: 'http://localhost:5181',
      reuseExistingServer: false,
      timeout: 120_000,
      env: { FPA_WEB_PUERTO: '5181', FPA_API_URL: 'http://127.0.0.1:8101' },
    },
  ],
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
})
