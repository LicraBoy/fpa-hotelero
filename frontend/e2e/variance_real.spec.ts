import { expect, test, type APIRequestContext } from '@playwright/test'
import { existsSync, readFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { join, resolve } from 'node:path'

// Comparación de valores EN PANTALLA contra el Excel real de agosto 2026 (hoja `Ago`).
// Solo corre si los archivos reales existen (FPA_DATOS_REALES o la carpeta de Contraloría); las
// cifras de referencia las deja `crear_archivos_e2e.py` en `e2e/archivos/golden_real.json`, que NO
// se versiona. Se omiten las líneas con diferencias ya documentadas (19, ver la prueba dorada).
const CARPETA =
  process.env.FPA_DATOS_REALES ?? join(homedir(), 'Desktop', 'PLATAFORMA FP&A E INTELIGENCIA HOTELERA')
const EXCEL = join(CARPETA, '02. VT August 2026 Variance (Envio) (1).xlsx')
const GOLDEN = resolve('e2e/archivos/golden_real.json')
const hayDatos = existsSync(EXCEL) && existsSync(GOLDEN)

test.describe.configure({ mode: 'serial' })
test.skip(!hayDatos, 'No están el Excel real ni sus cifras de referencia')

const XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

interface Referencia {
  fila: number
  descripcion: string
  tipo: string
  cifras: (string | null)[]
}

const cabecera = (email: string) => ({ 'X-Usuario-Dev': email })

async function cargarAgostoReal(request: APIRequestContext) {
  const buffer = readFileSync(EXCEL)
  const adjunto = { name: 'variance_agosto_real.xlsx', mimeType: XLSX, buffer }
  const analista = cabecera('analista@torres.local')
  const hotel = (await (await request.get('/api/v1/hoteles', { headers: analista })).json())[0].id
  const base = `/api/v1/hoteles/${hotel}`

  let r = await request.post(`${base}/cargas`, {
    headers: analista,
    timeout: 120_000,
    multipart: { archivo: adjunto, fuente: 'variance_base_datos', confirmar_reemplazo: 'true' },
  })
  expect(r.status(), await r.text()).toBeLessThan(300)
  r = await request.post(`${base}/reporte/importar`, {
    headers: analista,
    timeout: 120_000,
    multipart: { archivo: adjunto, confirmar_reemplazo: 'true' },
  })
  expect(r.status(), await r.text()).toBe(201)
  const mapeo = (await r.json()).mapeo_version_id as number
  // Provisional hasta que Contraloría responda por estas dos cuentas (ver FASES_FUTURAS.md)
  for (const cuenta of ['4002013', '4003003']) {
    r = await request.put(`${base}/mapeo/versiones/${mapeo}/exclusiones`, {
      headers: analista,
      data: { cuenta_codigo: cuenta, motivo: 'Prueba: sin línea en la hoja Ago, pendiente de Contraloría' },
    })
    expect(r.status(), await r.text()).toBe(200)
  }
  r = await request.post(`${base}/mapeo/versiones/${mapeo}/aprobar`, {
    headers: cabecera('contralor@torres.local'),
    data: { periodos: ['2026-07', '2026-08'] },
  })
  expect(r.status(), await r.text()).toBe(200)
  r = await request.post(`${base}/budget/importar`, {
    headers: analista,
    timeout: 120_000,
    multipart: { archivo: adjunto, periodo_corte: '2026-08', confirmar_reemplazo: 'true' },
  })
  expect(r.status(), await r.text()).toBeLessThan(300)
}

// "▼ Desfavorable: (1,234.50)" -> -1234.5 ; "(12.3%)" -> -12.3 ; "—" -> null
function numeroDePantalla(texto: string): number | null {
  const limpio = texto.replace('▼', '').replace('Desfavorable:', '').trim()
  if (limpio === '—') return null
  const negativo = limpio.startsWith('(')
  const n = Number(limpio.replace(/[(),%]/g, ''))
  return negativo ? -n : n
}

function escapar(texto: string): string {
  return texto.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

const campoEsPorcentaje = (i: number) => i % 4 === 3

test.beforeAll(async ({ request }) => {
  test.setTimeout(300_000)
  await cargarAgostoReal(request)
})

test('las cifras en pantalla coinciden con las del Excel de Contraloría', async ({ page }) => {
  test.setTimeout(120_000)
  const referencias: Referencia[] = JSON.parse(readFileSync(GOLDEN, 'utf8'))
  expect(referencias.length).toBeGreaterThanOrEqual(10)

  await page.setViewportSize({ width: 1600, height: 900 })
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Analista' })
  await page
    .getByRole('navigation', { name: 'Secciones' })
    .getByRole('button', { name: 'Variance' })
    .click()
  await expect(page.getByRole('region', { name: 'Tabla de Variance' })).toBeVisible()
  await expect(page.getByText(/mapeo \(versión \d+\) deja fuera a propósito 2 cuentas/)).toBeVisible()

  const diferencias: string[] = []
  for (const ref of referencias) {
    const fila = page
      .getByRole('row')
      .filter({
        has: page.locator('.descripcion', { hasText: new RegExp(`^${escapar(ref.descripcion)}$`) }),
      })
    await expect(fila, ref.descripcion).toHaveCount(1)
    const textos = await fila.getByRole('cell').allInnerTexts()
    expect(textos).toHaveLength(12)
    ref.cifras.forEach((esperado, i) => {
      if (esperado === null) return
      const visto = numeroDePantalla(textos[i])
      const valor = Number(esperado)
      const objetivo = campoEsPorcentaje(i) ? valor * 100 : valor
      const tolerancia = campoEsPorcentaje(i) ? 0.11 : 0.11
      if (visto === null || Math.abs(visto - objetivo) > tolerancia + (campoEsPorcentaje(i) ? 0.001 * Math.abs(objetivo) : 0)) {
        diferencias.push(`${ref.descripcion} [col ${i}]: pantalla ${textos[i]} / Excel ${esperado}`)
      }
    })
  }
  expect(diferencias).toEqual([])
  // Captura para la revisión visual (trae cifras reales: no se versiona)
  await page.screenshot({ path: 'test-results/variance_agosto_real.png', fullPage: false })
})

test('el reporte real carga completo: secciones, totales y sin errores', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 900 })
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Analista' })
  await page
    .getByRole('navigation', { name: 'Secciones' })
    .getByRole('button', { name: 'Variance' })
    .click()
  await expect(page.getByRole('region', { name: 'Tabla de Variance' })).toBeVisible()
  expect(await page.getByRole('button', { name: /Commercial Services|Maid|Common Area/ }).count()).toBeGreaterThan(0)
  expect(await page.getByRole('row').count()).toBeGreaterThan(400)
  await expect(page.getByRole('alert')).toHaveCount(0)
})
