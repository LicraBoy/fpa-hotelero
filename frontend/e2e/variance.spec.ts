import { expect, test, type Page } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
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
  const boton = page.getByRole('table').getByRole('button', { name: /Expenses/ })
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

test('"Exportar a Excel" descarga un libro cuyas cifras son las de la pantalla', async ({ page }, info) => {
  await abrirVariance(page)
  const [descarga] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Exportar a Excel' }).click(),
  ])
  expect(descarga.suggestedFilename()).toBe('variance_2026-08.xlsx')
  const ruta = info.outputPath('variance_exportado.xlsx')
  await descarga.saveAs(ruta)
  expect(readFileSync(ruta).subarray(0, 2).toString()).toBe('PK') // un .xlsx es un zip

  // El libro se abre con openpyxl (script del backend) y se compara con lo que muestra la pantalla
  const python = process.env.FPA_PYTHON ?? resolve('../backend/.venv/Scripts/python.exe')
  const salida = execFileSync(python, ['scripts/leer_excel_exportado.py', ruta], {
    cwd: resolve('../backend'),
    encoding: 'utf8',
  })
  const filas: { descripcion: string; cifras: (string | null)[] }[] = JSON.parse(salida)
  const excel = new Map(filas.map((f) => [f.descripcion, f.cifras]))
  for (const [descripcion, esperado] of [
    ['Room Revenue', ['1000.00', '900.00', '100.00', '0.111111']],
    ['Salaries', ['400.00', '380.00', '-20.00', '-0.052632']],
    ['Total Expenses', ['550.25', '520.00', '-30.25', '-0.058173']],
    ['Net Profit', ['950.25', '980.00', '-29.75', '-0.030357']],
  ] as const) {
    expect(excel.get(descripcion)?.slice(0, 4), descripcion).toEqual(esperado)
  }
  // y esas mismas cifras son las que muestra la tabla
  expect((await celdas(page, 'Room Revenue')).slice(0, 4)).toEqual(['1,000.00', '900.00', '100.00', '11.1%'])
})

test('con un filtro, el Excel trae solo lo que muestra la pantalla', async ({ page }, info) => {
  await abrirVariance(page)
  await page.getByLabel('Solo totales y subtotales').check()
  await expect(page.getByRole('rowheader', { name: 'Room Revenue' })).toHaveCount(0)
  const [descarga] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Exportar a Excel' }).click(),
  ])
  const ruta = info.outputPath('variance_filtrado.xlsx')
  await descarga.saveAs(ruta)
  const python = process.env.FPA_PYTHON ?? resolve('../backend/.venv/Scripts/python.exe')
  const filas: { descripcion: string }[] = JSON.parse(
    execFileSync(python, ['scripts/leer_excel_exportado.py', ruta], {
      cwd: resolve('../backend'),
      encoding: 'utf8',
    }),
  )
  expect(filas.map((f) => f.descripcion).filter((d) => !['Revenue', 'Expenses'].includes(d))).toEqual([
    'Total Revenue',
    'Total Expenses',
    'Net Profit',
  ])
})

test('sin permiso para ver el reporte no hay botón de exportar', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Responsable de área' })
  await expect(page.getByRole('button', { name: 'Exportar a Excel' })).toHaveCount(0)
})

test('la leyenda explica las columnas y los colores', async ({ page }) => {
  await abrirVariance(page)
  const leyenda = page.getByRole('note', { name: 'Cómo leer la tabla' })
  await expect(leyenda).toContainText('Mes')
  await expect(leyenda).toContainText('Acumulado del año fiscal')
  await expect(leyenda).toContainText('Presupuesto anual')
  await expect(leyenda).toContainText('desfavorable')
})

test('las líneas sin cifras se ocultan con aviso y se pueden mostrar', async ({ page }) => {
  await abrirVariance(page)
  await expect(page.getByRole('rowheader', { name: 'Unused Expense' })).toHaveCount(0)
  const aviso = page.getByRole('status').filter({ hasText: 'línea oculta por no tener cifras' })
  await expect(aviso).toContainText('Hay 1 línea oculta')
  await aviso.getByRole('button', { name: 'Mostrarlas' }).click()
  await expect(page.getByRole('rowheader', { name: 'Unused Expense' })).toBeVisible()
  await expect(page.getByRole('status').filter({ hasText: 'oculta' })).toHaveCount(0)
  // el interruptor hace lo mismo
  await page.getByLabel('Ocultar líneas sin cifras').check()
  await expect(page.getByRole('rowheader', { name: 'Unused Expense' })).toHaveCount(0)
})

test('la búsqueda resalta lo encontrado, cuenta las líneas y no pliega nada', async ({ page }) => {
  await abrirVariance(page)
  await page.getByRole('table').getByRole('button', { name: /Expenses/ }).click() // se pliega
  await page.getByLabel('Buscar línea').fill('sala')
  const conteo = page.getByRole('status').filter({ hasText: 'encontrada' })
  await expect(conteo).toContainText('1 línea encontrada para «sala»')
  await expect(conteo).toContainText('en 1 sección')
  // lo encontrado se resalta y su sección se abre aunque estuviera plegada
  await expect(page.locator('mark.coincidencia')).toHaveText('Sala')
  await expect(page.getByRole('rowheader', { name: 'Salaries' })).toBeVisible()
  await page.getByLabel('Buscar línea').fill('<img src=x>')
  await expect(page.getByText('Ninguna línea coincide con los filtros.')).toBeVisible()
  expect(await page.locator('img[src="x"]').count()).toBe(0) // lo escrito nunca se interpreta
})

test('el índice de secciones lleva a la sección y la despliega', async ({ page }) => {
  await abrirVariance(page)
  const indice = page.getByRole('navigation', { name: 'Ir a una sección' })
  await expect(indice.getByRole('button', { name: /Expenses/ })).toBeVisible()
  const boton = page.getByRole('table').getByRole('button', { name: /Expenses/ })
  await boton.click() // plegada
  await expect(boton).toHaveAttribute('aria-expanded', 'false')
  await indice.getByRole('button', { name: /Expenses/ }).click()
  await expect(boton).toHaveAttribute('aria-expanded', 'true')
  await expect(page.getByRole('rowheader', { name: 'Salaries' })).toBeVisible()
})
