import { expect, test, type Page } from '@playwright/test'
import { abrirVariance, prepararReporteSintetico } from './datos'

// Pantalla de Variance con un reporte SINTÉTICO de cifras conocidas (ver
// backend/scripts/crear_archivos_e2e.py). Los datos se cargan por API; las cifras se comprueban en
// pantalla, contra lo que dice el Excel de ejemplo (columnas D a Q de su hoja `Ago`).
test.describe.configure({ mode: 'serial' })

// Celdas de una fila de la tabla, por el texto de su descripción
async function celdas(page: Page, descripcion: string): Promise<string[]> {
  const fila = page.getByRole('row').filter({ has: page.getByRole('rowheader', { name: descripcion }) })
  const textos = await fila.getByRole('cell').allInnerTexts()
  return textos.map((t) => t.replace(/\s+/g, ' ').trim())
}

test.beforeAll(async ({ request }) => {
  await prepararReporteSintetico(request)
})

test('el reporte de agosto muestra las cifras del Excel de ejemplo', async ({ page }) => {
  await abrirVariance(page)
  await expect(page.getByLabel('Mes', { exact: true })).toHaveValue('2026-08')
  // Mes: Actual, Presupuesto, Variación, % | YTD: ... | Anual: ...
  expect(await celdas(page, 'Room Revenue')).toEqual([
    '1,000.00', '900.00', '100.00', '11.1%',
    '1,700.00', '1,700.00', '0.00', '0.0%',
    '1,700.00', '10,800.00', '▼ Desfavorable: (9,100.00)', '(84.3%)',
  ]) // prettier-ignore
  expect(await celdas(page, 'Salaries')).toEqual([
    '400.00', '380.00', '▼ Desfavorable: (20.00)', '(5.3%)',
    '780.00', '760.00', '▼ Desfavorable: (20.00)', '(2.6%)',
    '780.00', '4,560.00', '3,780.00', '82.9%',
  ]) // prettier-ignore
})

test('los totales y subtotales salen de las reglas y se distinguen visualmente', async ({
  page,
}) => {
  await abrirVariance(page)
  expect((await celdas(page, 'Total Revenue')).slice(0, 4)).toEqual([
    '1,500.50', '1,500.00', '0.50', '0.0%',
  ])
  expect((await celdas(page, 'Total Expenses')).slice(0, 4)).toEqual([
    '550.25', '520.00', '▼ Desfavorable: (30.25)', '(5.8%)',
  ]) // prettier-ignore
  expect((await celdas(page, 'Net Profit')).slice(0, 4)).toEqual([
    '950.25', '980.00', '▼ Desfavorable: (29.75)', '(3.0%)',
  ]) // prettier-ignore
  await expect(page.getByRole('row').filter({ hasText: 'Total Revenue' })).toHaveClass(/fila-total/)
  await expect(page.getByRole('row').filter({ hasText: 'Net Profit' })).toHaveClass(/fila-subtotal/)
  await expect(page.getByRole('row').filter({ hasText: 'Room Revenue' })).toHaveClass(/fila-detalle/)
})

test('las secciones se pliegan y los subtotales siguen visibles', async ({ page }) => {
  await abrirVariance(page)
  const boton = page.getByRole('button', { name: /Expenses/ })
  await expect(boton).toHaveAttribute('aria-expanded', 'true')
  await boton.click()
  await expect(boton).toHaveAttribute('aria-expanded', 'false')
  await expect(page.getByRole('rowheader', { name: 'Salaries' })).toHaveCount(0)
  await expect(page.getByRole('rowheader', { name: 'Total Expenses' })).toBeVisible()
  await boton.click()
  await expect(page.getByRole('rowheader', { name: 'Salaries' })).toBeVisible()
})

test('los filtros acotan las líneas: sección, texto y solo totales', async ({ page }) => {
  await abrirVariance(page)
  await page.getByLabel('Sección', { exact: true }).selectOption({ label: 'Revenue' })
  await expect(page.getByRole('rowheader', { name: 'Room Revenue' })).toBeVisible()
  await expect(page.getByRole('rowheader', { name: 'Salaries' })).toHaveCount(0)
  await page.getByLabel('Sección', { exact: true }).selectOption({ label: 'Todas' })
  await page.getByLabel('Buscar línea').fill('suppl')
  await expect(page.getByRole('rowheader', { name: 'Supplies' })).toBeVisible()
  await expect(page.getByRole('rowheader', { name: 'Room Revenue' })).toHaveCount(0)
  await page.getByLabel('Buscar línea').fill('')
  await page.getByLabel('Solo totales y subtotales').check()
  await expect(page.getByRole('rowheader', { name: 'Room Revenue' })).toHaveCount(0)
  await expect(page.getByRole('rowheader', { name: 'Net Profit' })).toBeVisible()
})

test('la pantalla explica la convención de signo y el Budget del corte', async ({ page }) => {
  await abrirVariance(page)
  await expect(page.getByText('Variación favorable = positiva')).toBeVisible()
  await expect(page.getByText(/Año fiscal 2026\/27/)).toBeVisible()
  await expect(page.getByText(/acumulado de 2026-07, 2026-08/)).toBeVisible()
})

test('el encabezado y la columna de la línea quedan fijos al desplazarse', async ({ page }) => {
  await page.setViewportSize({ width: 700, height: 500 })
  await abrirVariance(page)
  const contenedor = page.getByRole('region', { name: 'Tabla de Variance' })
  const encabezado = contenedor.getByRole('columnheader', { name: 'Línea' })
  const antes = await encabezado.boundingBox()
  await contenedor.evaluate((el) => {
    el.scrollLeft = 400
    el.scrollTop = 20
  })
  const despues = await encabezado.boundingBox()
  expect(Math.abs((despues?.x ?? 0) - (antes?.x ?? 0))).toBeLessThan(2) // fija a la izquierda
  const fila = contenedor.getByRole('rowheader', { name: 'Room Revenue' })
  const x = (await fila.boundingBox())?.x ?? -1
  expect(x).toBeGreaterThanOrEqual((await contenedor.boundingBox())?.x ?? 0)
})

test('dirección ve el reporte, pero sin enlaces de desglose', async ({ page }) => {
  await abrirVariance(page, 'Dirección')
  await expect(page.getByRole('rowheader', { name: 'Room Revenue' })).toBeVisible()
  await expect(page.getByRole('link', { name: /Ver el desglose/ })).toHaveCount(0)
})

test('el analista ve enlaces de desglose en las cifras de Actual', async ({ page }) => {
  await abrirVariance(page, 'Analista')
  const enlace = page.getByRole('link', { name: 'Ver el desglose de Room Revenue, mes' })
  await expect(enlace).toHaveAttribute('href', /#\/variance\/2026-08\/linea\/\d+\?bloque=mes/)
})
