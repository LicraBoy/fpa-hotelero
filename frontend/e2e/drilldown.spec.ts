import { expect, test, type Page } from '@playwright/test'
import { abrirVariance, prepararReporteSintetico } from './datos'

// Recorrido completo: cifra -> cuentas -> movimientos -> asiento, comprobando en cada paso que lo
// mostrado suma la cifra del paso anterior. Datos sintéticos de cifras conocidas.
//   Salaries (agosto): 400.00 = 150.00 + 150.00 + 100.00 · acumulado: 780.00 (julio 380.00)
test.describe.configure({ mode: 'serial' })

test.beforeAll(async ({ request }) => {
  await prepararReporteSintetico(request)
})

const estado = (page: Page, nombre: string) => page.getByRole('status', { name: nombre })

test('de la cifra al asiento, con las sumas cuadrando en cada paso', async ({ page }) => {
  await abrirVariance(page)

  // 1) la cifra del reporte
  await page.getByRole('link', { name: 'Ver el desglose de Salaries, mes' }).click()
  await expect(page).toHaveURL(/#\/variance\/2026-08\/linea\/\d+\?bloque=mes/)

  // 2) sus cuentas: una sola, con signo + (gasto Deudor), y la suma cuadra
  await expect(page.getByRole('heading', { name: 'Desglose: Salaries' })).toBeVisible()
  const cuentas = page.getByRole('table', { name: 'Cuentas de la línea' })
  await expect(cuentas.getByRole('row', { name: /6009001\.001/ })).toContainText('400.00')
  await expect(page.getByRole('status').filter({ hasText: 'Cifra del reporte' })).toContainText(
    'Cifra del reporte: 400.00',
  )
  await expect(page.getByRole('status').filter({ hasText: 'Cifra del reporte' })).toContainText('Cuadra')

  // 3) los movimientos de la cuenta: 3 en agosto, suman 400.00 = neto de la cuenta
  await cuentas.getByRole('link', { name: '6009001.001' }).click()
  await expect(page.getByRole('heading', { name: /Movimientos de 6009001\.001/ })).toBeVisible()
  const cuadre = estado(page, 'Cuadre de la cuenta')
  await expect(cuadre).toContainText('Mostrados 3 de 3')
  await expect(cuadre).toContainText('Suma mostrada: 400.00')
  await expect(cuadre).toContainText('Neto de la cuenta: 400.00')
  await expect(cuadre).toContainText('Cuadra con el neto de la cuenta')
  const movimientos = page.getByRole('region', { name: 'Movimientos', exact: true })
  await expect(movimientos.getByRole('row')).toHaveCount(1 + 3) // encabezado + 3 movimientos
  await expect(movimientos).toContainText('Quincena 1')

  // 4) el asiento de un movimiento
  await movimientos.getByRole('link', { name: '8.1.4' }).click()
  await expect(page.getByRole('heading', { name: 'Asiento 8.1.4' })).toBeVisible()
  const asiento = page.getByRole('table', { name: 'Líneas del asiento' })
  await expect(asiento).toContainText('Quincena 1')
  await expect(asiento).toContainText('150.00')
  await expect(estado(page, 'Totales del asiento')).toContainText('Débito: 150.00')
  // El Variance solo trae cuentas de resultados: el asiento no tiene que cuadrar y se explica
  await expect(page.getByText('Solo cuentas de resultados')).toBeVisible()
})

test('el acumulado del año fiscal suma julio y agosto', async ({ page }) => {
  await abrirVariance(page)
  await page.getByRole('link', { name: 'Ver el desglose de Salaries, acumulado' }).click()
  await expect(page).toHaveURL(/bloque=ytd/)
  await expect(page.getByText('Acumulado del año fiscal').first()).toBeVisible()
  await expect(page.getByRole('status').filter({ hasText: 'Cifra del reporte' })).toContainText(
    'Cifra del reporte: 780.00',
  )
  await page.getByRole('table', { name: 'Cuentas de la línea' }).getByRole('link', { name: '6009001.001' }).click()
  const cuadre = estado(page, 'Cuadre de la cuenta')
  await expect(cuadre).toContainText('Mostrados 4 de 4') // 3 de agosto + 1 de julio
  await expect(cuadre).toContainText('Suma mostrada: 780.00')
  await expect(cuadre).toContainText('Cuadra con el neto de la cuenta')
})

test('un total se desglosa en sus componentes y cada uno en sus cuentas', async ({ page }) => {
  await abrirVariance(page)
  await page.getByRole('link', { name: 'Ver el desglose de Net Profit, mes' }).click()
  await expect(page.getByRole('heading', { name: 'Desglose: Net Profit' })).toBeVisible()
  const componentes = page.getByRole('table', { name: 'Componentes del total' })
  await expect(componentes.getByRole('row', { name: /Total Revenue/ })).toContainText('+')
  await expect(componentes.getByRole('row', { name: /Total Revenue/ })).toContainText('1,500.50')
  await expect(componentes.getByRole('row', { name: /Total Expenses/ })).toContainText('550.25')
  await expect(page.getByRole('status').filter({ hasText: 'Cifra del reporte' })).toContainText(
    'Cifra del reporte: 950.25',
  )
  await expect(page.getByRole('status').filter({ hasText: 'Cifra del reporte' })).toContainText('Cuadra')
  // se baja un nivel: Total Revenue -> Room Revenue -> sus cuentas
  await componentes.getByRole('link', { name: 'Total Revenue' }).click()
  await page.getByRole('table', { name: 'Componentes del total' }).getByRole('link', { name: 'Room Revenue' }).click()
  const cuentas = page.getByRole('table', { name: 'Cuentas de la línea' })
  await expect(cuentas.getByRole('row', { name: /4001002\.001/ })).toContainText('−') // Acreedora: signo −
  await expect(cuentas.getByRole('row', { name: /4001002\.001/ })).toContainText('1,000.00')
})

test('un concepto con HTML se muestra como texto y no se interpreta', async ({ page }) => {
  await page.goto('/#/variance/2026-08/cuenta/4001002.001?bloque=mes')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Analista' })
  const movimientos = page.getByRole('region', { name: 'Movimientos', exact: true })
  await expect(movimientos).toContainText('Hospedaje <b>agosto</b> & más')
  expect(await movimientos.locator('b').count()).toBe(0)
})

test('las migas de pan regresan al reporte', async ({ page }) => {
  await page.goto('/#/variance/2026-08/cuenta/6009001.001?bloque=mes')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Analista' })
  await expect(page.getByRole('heading', { name: /Movimientos de 6009001\.001/ })).toBeVisible()
  await page.getByRole('navigation', { name: 'Ruta de navegación' }).getByRole('link', { name: /Variance 2026-08/ }).click()
  await expect(page.getByRole('region', { name: 'Tabla de Variance' })).toBeVisible()
})

test('una cuenta sin movimientos o una línea inexistente se explican sin romper', async ({ page }) => {
  await page.goto('/#/variance/2026-08/cuenta/9999999?bloque=mes')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Analista' })
  await expect(page.getByText('La cuenta no tiene movimientos en este periodo.')).toBeVisible()
  await page.goto('/#/variance/2026-08/linea/999999?bloque=mes')
  await expect(page.getByRole('alert')).toContainText(/no encontrada/i)
})

test('dirección ve el reporte pero no el desglose (ni por la dirección directa)', async ({ page }) => {
  const peticiones: string[] = []
  page.on('request', (r) => peticiones.push(new URL(r.url()).pathname))
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Dirección' })
  peticiones.length = 0
  await page.evaluate(() => {
    window.location.hash = '#/variance/2026-08/cuenta/6009001.001?bloque=mes'
  })
  await expect(page.getByRole('alert', { name: 'Sin acceso' })).toBeVisible()
  await page.waitForTimeout(300)
  expect(peticiones.filter((p) => p.includes('movimientos') || p.includes('desglose'))).toEqual([])
})
