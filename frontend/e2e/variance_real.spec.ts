import { expect, test, type APIRequestContext } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { join, resolve } from 'node:path'

// Comparación de valores EN PANTALLA contra el Excel real de MAZATLÁN (agosto 2026, hojas `Ago` y
// `Jul-Ago`). El acumulado de referencia es julio + agosto (el Excel no trae acumulado ni anual).
// Solo corre si los archivos reales existen (FPA_DATOS_REALES o la carpeta de Contraloría); las
// cifras de referencia las deja `crear_archivos_e2e.py` en `e2e/archivos/golden_real.json`, que NO
// se versiona. Se omiten las líneas con diferencias ya documentadas (ver `test_variance_dorada_mzt.py`).
const CARPETA =
  process.env.FPA_DATOS_REALES ?? join(homedir(), 'Desktop', 'PLATAFORMA FP&A E INTELIGENCIA HOTELERA')
const NOMBRE = '02. MZT August 2026 Variance (Envio).xlsx'
const EN_REPO = resolve('../docs/adr', NOMBRE)
const EXCEL = existsSync(join(CARPETA, NOMBRE)) ? join(CARPETA, NOMBRE) : EN_REPO
const VARIACION = existsSync(join(CARPETA, '02. MZT August 2026 Variance.xlsx'))
  ? join(CARPETA, '02. MZT August 2026 Variance.xlsx')
  : resolve('../docs/adr/02. MZT August 2026 Variance.xlsx')
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
  // El sentido de la Variación de cada línea (columnas G, L y Q del Excel de la Variación)
  if (existsSync(VARIACION)) {
    r = await request.post(`${base}/reporte/convenciones`, {
      headers: analista,
      timeout: 120_000,
      multipart: {
        archivo: { name: 'variacion.xlsx', mimeType: XLSX, buffer: readFileSync(VARIACION) },
      },
    })
    expect(r.status(), await r.text()).toBe(200)
  }
  // Provisional hasta que Contraloría responda por estas cuentas (ver HALLAZGOS_CONTRALORIA.md)
  for (const cuenta of ['4003001.010', '4003001.020', '4002020']) {
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
    multipart: { archivo: adjunto, confirmar_reemplazo: 'true' }, // Mazatlán trae sus meses
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
  await expect(page.getByText(/mapeo \(versión \d+\) deja fuera a propósito 3 cuentas/)).toBeVisible()

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

test('el tipo de cambio muestra el Actual real, el Budget fijo y su variación', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 900 })
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Analista' })
  await page
    .getByRole('navigation', { name: 'Secciones' })
    .getByRole('button', { name: 'Variance' })
    .click()
  await expect(page.getByRole('region', { name: 'Tabla de Variance' })).toBeVisible()
  const fila = page
    .getByRole('row')
    .filter({ has: page.locator('.descripcion', { hasText: /^Exchange Rate:?$/ }) })
  await expect(fila).toHaveCount(1)
  const textos = await fila.getByRole('cell').allInnerTexts()
  // Actual 17.1337, Budget 18, Var = Budget - Actual = 0.8663, % = Var / Budget = 4.8 %
  expect(numeroDePantalla(textos[0])).toBeCloseTo(17.13, 2)
  expect(numeroDePantalla(textos[1])).toBeCloseTo(18, 2)
  expect(numeroDePantalla(textos[2])).toBeCloseTo(0.87, 2)
  expect(numeroDePantalla(textos[3])).toBeCloseTo(4.8, 1)
  // un tipo de cambio no se suma: el acumulado es el promedio de los meses capturados (julio y
  // agosto = 17.1756), con Variación Actual − Presupuesto = −0.82 y −4.6 %, como en el Excel
  expect(numeroDePantalla(textos[4])).toBeCloseTo(17.18, 2)
  expect(numeroDePantalla(textos[5])).toBeCloseTo(18, 2)
  expect(numeroDePantalla(textos[6])).toBeCloseTo(-0.82, 2)
  expect(numeroDePantalla(textos[7])).toBeCloseTo(-4.6, 1)
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

test('"Cargar más" recorre todos los movimientos de una cuenta grande y cuadra con su neto', async ({
  page,
}) => {
  test.setTimeout(180_000)
  await page.goto('/#/variance/2026-08/cuenta/5001002.002?bloque=ytd')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Analista' })
  const cuadre = page.getByRole('status', { name: 'Cuadre de la cuenta' })
  await expect(cuadre).toContainText('Mostrados 50 de')
  const total = Number(/de (\d+)/.exec((await cuadre.innerText()).replace(/\s+/g, ' '))?.[1])
  expect(total).toBeGreaterThan(100) // la cuenta tiene cientos de movimientos: hacen falta varias páginas
  const boton = page.getByRole('button', { name: /Cargar más/ })
  while (await boton.count()) {
    await boton.click()
    await expect(boton).toBeEnabled({ timeout: 20_000 }).catch(() => undefined)
  }
  await expect(cuadre).toContainText(`Mostrados ${total} de ${total}`)
  await expect(cuadre).toContainText('Cuadra con el neto de la cuenta')
  // nunca se repiten movimientos: tantas filas como movimientos
  const filas = page.getByRole('region', { name: 'Movimientos', exact: true }).getByRole('row')
  await expect(filas).toHaveCount(total + 1)
})

test('el Excel exportado de agosto real trae las mismas cifras de referencia que el Excel de Mazatlán', async ({
  page,
}, info) => {
  test.setTimeout(120_000)
  const referencias: Referencia[] = JSON.parse(readFileSync(GOLDEN, 'utf8'))
  await page.setViewportSize({ width: 1600, height: 900 })
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Analista' })
  await page
    .getByRole('navigation', { name: 'Secciones' })
    .getByRole('button', { name: 'Variance' })
    .click()
  await expect(page.getByRole('region', { name: 'Tabla de Variance' })).toBeVisible()
  const [descarga] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Exportar a Excel' }).click(),
  ])
  const ruta = info.outputPath('variance_real_exportado.xlsx')
  await descarga.saveAs(ruta)
  const python = process.env.FPA_PYTHON ?? resolve('../backend/.venv/Scripts/python.exe')
  const filas: { descripcion: string; cifras: (string | null)[] }[] = JSON.parse(
    execFileSync(python, ['scripts/leer_excel_exportado.py', ruta], {
      cwd: resolve('../backend'),
      encoding: 'utf8',
      maxBuffer: 50 * 1024 * 1024,
    }),
  )
  expect(filas.length).toBeGreaterThan(400)
  const excel = new Map(filas.map((f) => [f.descripcion, f.cifras]))
  const diferencias: string[] = []
  for (const ref of referencias) {
    const cifras = excel.get(ref.descripcion)
    expect(cifras, ref.descripcion).toBeDefined()
    ref.cifras.forEach((esperado, i) => {
      if (esperado === null || cifras?.[i] === null || cifras?.[i] === undefined) return
      const objetivo = Number(esperado)
      const visto = Number(cifras[i])
      const tolerancia = campoEsPorcentaje(i) ? 0.0011 + 0.00001 * Math.abs(objetivo) : 0.11
      if (Math.abs(visto - objetivo) > tolerancia) {
        diferencias.push(`${ref.descripcion} [col ${i}]: Excel exportado ${cifras[i]} / hoja Ago ${esperado}`)
      }
    })
  }
  expect(diferencias).toEqual([])
})
