import { execFileSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'

// Crea los Excel sintéticos de prueba antes de correr los tests.
export default function preparar(): void {
  const windows = resolve('../backend/.venv/Scripts/python.exe')
  const unix = resolve('../backend/.venv/bin/python')
  const python = process.env.FPA_PYTHON ?? (existsSync(windows) ? windows : unix)
  execFileSync(python, ['scripts/crear_archivos_e2e.py', resolve('e2e/archivos')], {
    cwd: resolve('../backend'),
    stdio: 'inherit',
  })
}
