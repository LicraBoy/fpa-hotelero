import { expect, test, type Page } from '@playwright/test'
import { abrirVariance, pestana, prepararReporteSintetico } from './datos'

// Budget en pantalla con el reporte SINTÉTICO (ver backend/scripts/crear_archivos_e2e.py): editar,
// copiar el Actual como punto de partida, guardar una versión nueva y ver el Variance con ella.
test.describe.configure({ mode: 'serial' })

test.beforeAll(async ({ request }) => {
  await prepararReporteSintetico(request)
})

async function abrirBudget(page: Page, usuario = 'Analista') {
  await page.setViewportSize({ width: 1600, height: 900 })
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: usuario })
  await pestana(page, 'Budget').click()
  await expect(page.getByRole('heading', { name: 'Budget 2026/27' })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Tabla de Budget' })).toBeVisible()
}

const entrada = (page: Page, linea: string, mes: string) =>
  page.getByLabel(`Budget de ${linea}, ${mes}`)

test('solo ven la pestaña Budget quienes pueden editarlo', async ({ page }) => {
  for (const [usuario, ve] of [
    ['Analista', true],
    ['Contralor', true],
    ['Dirección', false],
    ['Responsable de área', false],
  ] as const) {
    await page.goto('/')
    await page.getByLabel('Usuario (desarrollo)').selectOption({ label: usuario })
    await expect(pestana(page, 'Cargas').or(pestana(page, 'Catálogo')).first()).toBeVisible()
    await expect(pestana(page, 'Budget')).toHaveCount(ve ? 1 : 0)
  }
})

test('un importe no válido se marca y no deja guardar', async ({ page }) => {
  await abrirBudget(page)
  await expect(page.getByRole('status').filter({ hasText: 'Sin cambios.' })).toBeVisible()
  const celda = entrada(page, 'Room Revenue', 'Ago 26')
  await celda.fill('abc')
  await expect(celda).toHaveAttribute('aria-invalid', 'true')
  await expect(page.getByText('1 celda con un importe no válido')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Guardar como versión nueva' })).toBeDisabled()
  await page.getByRole('button', { name: 'Descartar cambios' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Sin cambios.' })).toBeVisible()
})

test('un mes sin Budget lo avisa y lleva a la pestaña Budget', async ({ page }) => {
  await abrirVariance(page)
  // El Budget del reporte de ejemplo es del corte de agosto: julio no tiene Budget del mes
  await page.getByLabel('Mes', { exact: true }).selectOption('2026-07')
  const aviso = page.getByRole('status').filter({ hasText: 'No hay Budget para 2026-07' })
  await expect(aviso).toBeVisible()
  await expect(aviso).toContainText('Presupuesto, Variación y % var. salen en «—»')
  await aviso.getByRole('button', { name: 'Capturar el Budget de 2026-07' }).click()
  await expect(page.getByRole('heading', { name: 'Budget 2026/27' })).toBeVisible()
  // quien no puede editar el Budget no ve el botón, solo la explicación
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Dirección' })
  await pestana(page, 'Variance').click()
  await page.getByLabel('Mes', { exact: true }).selectOption('2026-07')
  await expect(page.getByText('Pide a Contraloría que lo capture o lo importe.')).toBeVisible()
  await expect(page.getByRole('button', { name: /Capturar el Budget/ })).toHaveCount(0)
})

test('editar, copiar el Actual, guardar y ver el Variance con el Budget nuevo', async ({ page }) => {
  await abrirBudget(page)

  // El Actual de referencia está al lado y los totales se calculan solos
  const fila = (nombre: string) =>
    page.getByRole('row').filter({ has: page.getByRole('rowheader', { name: nombre }) })
  await expect(fila('Room Revenue').getByRole('cell').nth(3)).toHaveText('1,000.00') // Actual de agosto
  await entrada(page, 'Room Revenue', 'Ago 26').fill('900')
  await expect(page.getByText('1 cambio en 1 línea sin guardar')).toBeVisible()
  const totalAgosto = fila('Total Revenue').getByRole('cell').nth(2)
  await expect(totalAgosto).toHaveText('900.00') // la suma de sus líneas, al instante

  // Copiar el Actual (+10 %) solo donde no hay Budget ni se ha escrito nada
  await page.getByLabel('Ajuste sobre el Actual (%)').fill('10')
  await page.getByRole('button', { name: /Copiar el Actual/ }).click()
  await expect(page.getByText('Se copió el Actual en 3 celdas')).toBeVisible()
  await expect(entrada(page, 'Room Revenue', 'Jul 26')).toHaveValue('770') // 700 + 10 %
  await expect(entrada(page, 'Room Revenue', 'Ago 26')).toHaveValue('900') // lo escrito no se pisa
  await expect(entrada(page, 'Food Revenue', 'Ago 26')).toHaveValue('550.55') // 500.50 + 10 %

  // Guardar pide confirmación y crea una versión nueva
  await page.getByRole('button', { name: 'Guardar como versión nueva' }).click()
  await expect(page.getByText('Vas a guardar 4 cambios en 2 líneas')).toBeVisible()
  await page.getByRole('button', { name: 'Confirmar y guardar' }).click()
  await expect(page.getByText(/Budget guardado como versión \d+/)).toBeVisible()
  await expect(page.getByRole('status').filter({ hasText: 'Sin cambios.' })).toBeVisible()
  await expect(entrada(page, 'Room Revenue', 'Ago 26')).toHaveValue('900') // ya viene de la versión

  // El Variance usa de inmediato el Budget nuevo: mes 900, acumulado 770 + 900
  await abrirVariance(page)
  const filaVariance = page
    .getByRole('row')
    .filter({ has: page.getByRole('rowheader', { name: 'Room Revenue' }) })
  const textos = (await filaVariance.getByRole('cell').allInnerTexts()).map((t) =>
    t.replace(/\s+/g, ' ').trim(),
  )
  expect(textos.slice(0, 8)).toEqual([
    '1,000.00', '900.00', '100.00', '11.1%', // mes
    '1,700.00', '1,670.00', '30.00', '1.8%', // acumulado
  ]) // prettier-ignore
})
