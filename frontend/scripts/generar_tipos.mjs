// Genera los tipos de TypeScript desde el OpenAPI de la API (un solo contrato backend-frontend).
//   npm run api:tipos            -> exporta el OpenAPI y regenera src/api/schema.d.ts
//   npm run api:tipos -- --check -> no escribe: falla si lo versionado no coincide con la API
import { execFileSync } from 'node:child_process'
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const verificar = process.argv.includes('--check')
const windows = resolve('../backend/.venv/Scripts/python.exe')
const unix = resolve('../backend/.venv/bin/python')
const python = process.env.FPA_PYTHON ?? (existsSync(windows) ? windows : unix)

const temporal = mkdtempSync(join(tmpdir(), 'fpa-openapi-'))
try {
  const json = join(temporal, 'openapi.json')
  const ts = join(temporal, 'schema.d.ts')
  execFileSync(python, ['scripts/exportar_openapi.py', json], { cwd: resolve('../backend') })
  execFileSync(
    process.execPath,
    [resolve('node_modules/openapi-typescript/bin/cli.js'), json, '-o', ts],
    { stdio: 'inherit' },
  )
  const destinoJson = resolve('src/api/openapi.json')
  const destinoTs = resolve('src/api/schema.d.ts')
  if (verificar) {
    const iguales =
      readFileSync(json, 'utf8') === readFileSync(destinoJson, 'utf8') &&
      readFileSync(ts, 'utf8') === readFileSync(destinoTs, 'utf8')
    if (!iguales) {
      console.error('Los tipos de src/api no coinciden con la API. Corre: npm run api:tipos')
      process.exit(1)
    }
    console.log('Los tipos coinciden con el OpenAPI actual.')
  } else {
    writeFileSync(destinoJson, readFileSync(json))
    writeFileSync(destinoTs, readFileSync(ts))
    console.log('Tipos regenerados: src/api/openapi.json y src/api/schema.d.ts')
  }
} finally {
  rmSync(temporal, { recursive: true, force: true })
}
