import { expect, test, type Page } from '@playwright/test'
import { abrirVariance, pestana, prepararReporteSintetico } from './datos'

// Variance v2 con el reporte SINTÉTICO (backend/scripts/crear_archivos_e2e.py): tipografía, encabezados
// con contexto, secciones, panel de la línea, herramientas y barra lateral plegable.
test.describe.configure({ mode: 'serial' })

test.beforeAll(async ({ request }) => {
  await prepararReporteSintetico(request)
})

const filaDe = (page: Page, nombre: string) =>
  page.getByRole('row').filter({ has: page.getByRole('rowheader', { name: nombre }) })

test('usa la tipografía Inter, autoalojada', async ({ page }) => {
  await abrirVariance(page)
  const resultado = await page.evaluate(async () => {
    await document.fonts.ready
    return {
      familia: getComputedStyle(document.body).fontFamily,
      cargada: document.fonts.check('14px "Inter Variable"'),
    }
  })
  expect(resultado.familia).toContain('Inter Variable')
  expect(resultado.cargada).toBe(true)
})

test('los encabezados de grupo dicen de qué periodo son', async ({ page }) => {
  await abrirVariance(page)
  const tabla = page.getByRole('region', { name: 'Tabla de Variance' })
  await expect(tabla.getByRole('columnheader', { name: /Mes.*agosto 2026/ })).toBeVisible()
  await expect(tabla.getByRole('columnheader', { name: /Acumulado.*jul – ago.*2026\/27/ })).toBeVisible()
  await expect(tabla.getByRole('columnheader', { name: /Presupuesto anual.*2026\/27/ })).toBeVisible()
})

test('cada sección cuenta sus líneas y sus variaciones desfavorables', async ({ page }) => {
  await abrirVariance(page)
  const seccion = page.getByRole('table').getByRole('button', { name: /Expenses/ })
  await expect(seccion).toContainText('5 líneas')
  await expect(seccion).toContainText('2 desfavorables')
})

test('la barra apilada del resumen reparte las líneas por sentido', async ({ page }) => {
  await abrirVariance(page)
  const barra = page.getByRole('img', { name: /desfavorables/ })
  await expect(barra).toHaveAttribute('aria-label', /3 desfavorables/)
})

test('Expandir todo y Plegar todo mueven todas las secciones', async ({ page }) => {
  await abrirVariance(page)
  const secciones = page.getByRole('table').locator('.boton-seccion')
  await page.getByRole('button', { name: 'Plegar todo' }).click()
  for (const s of await secciones.all()) await expect(s).toHaveAttribute('aria-expanded', 'false')
  await page.getByRole('button', { name: 'Expandir todo' }).click()
  for (const s of await secciones.all()) await expect(s).toHaveAttribute('aria-expanded', 'true')
})

test('la densidad cambia entre cómoda y compacta', async ({ page }) => {
  await abrirVariance(page)
  const contenedor = page.getByRole('region', { name: 'Tabla de Variance' })
  await expect(contenedor).not.toHaveClass(/densidad-compacta/)
  await page.getByRole('button', { name: 'Densidad: cómoda' }).click()
  await expect(contenedor).toHaveClass(/densidad-compacta/)
  await expect(page.getByRole('button', { name: 'Densidad: compacta' })).toBeVisible()
})

test('el panel de la línea muestra mes, acumulado y anual, y se cierra con Esc', async ({ page }) => {
  await abrirVariance(page)
  await filaDe(page, 'Salaries').getByRole('button', { name: 'Ver detalle de la línea' }).click()
  const panel = page.getByRole('dialog', { name: 'Detalle de la línea' })
  await expect(panel).toBeVisible()
  await expect(panel.getByRole('heading', { name: 'Salaries' })).toBeVisible()
  const mes = panel.getByRole('region', { name: 'Detalle: Mes' })
  await expect(mes).toContainText('400.00') // Actual de agosto
  await expect(mes).toContainText('380.00') // Presupuesto
  await expect(mes).toContainText('(20.00)') // Variación
  await expect(panel.getByRole('region', { name: 'Detalle: Acumulado' })).toContainText('780.00')
  await expect(panel.getByRole('region', { name: 'Detalle: Presupuesto anual' })).toBeVisible()
  await expect(panel.getByRole('link', { name: 'Ver cuentas del mes' })).toHaveAttribute(
    'href',
    /#\/variance\/2026-08\/linea\/\d+\?bloque=mes/,
  )
  await page.keyboard.press('Escape')
  await expect(panel).toHaveCount(0)
})

test('pulsar la fila también abre el panel, y un enlace de cifra sigue llevando al desglose', async ({ page }) => {
  await abrirVariance(page)
  await filaDe(page, 'Supplies').getByRole('rowheader').click()
  await expect(page.getByRole('dialog', { name: 'Detalle de la línea' })).toContainText('Supplies')
  await page.getByRole('button', { name: 'Cerrar detalle' }).click()
  await page.getByRole('link', { name: 'Ver el desglose de Salaries, mes' }).click()
  await expect(page.getByRole('heading', { name: /Desglose: Salaries/ })).toBeVisible()
})

test('sin permiso de desglose el panel no ofrece enlaces a las cuentas', async ({ page }) => {
  await abrirVariance(page, 'Dirección')
  await filaDe(page, 'Salaries').getByRole('button', { name: 'Ver detalle de la línea' }).click()
  const panel = page.getByRole('dialog', { name: 'Detalle de la línea' })
  await expect(panel).toContainText('400.00')
  await expect(panel.getByRole('link')).toHaveCount(0)
})

test('la barra lateral se pliega, deja las secciones accesibles y se recuerda al recargar', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Analista' })
  await page.getByRole('button', { name: 'Contraer el menú lateral' }).click()
  await expect(page.locator('.app')).toHaveClass(/app-plegado/)
  await expect(pestana(page, 'Variance')).toBeAttached()
  await page.reload()
  await expect(page.locator('.app')).toHaveClass(/app-plegado/)
  await page.getByRole('button', { name: 'Expandir el menú lateral' }).click()
  await expect(page.locator('.app')).not.toHaveClass(/app-plegado/)
})

test('el desglose muestra el peso de cada cuenta en su línea', async ({ page }) => {
  await abrirVariance(page)
  await page.getByRole('link', { name: 'Ver el desglose de Salaries, mes' }).click()
  const cuentas = page.getByRole('table', { name: 'Cuentas de la línea' })
  await expect(cuentas.getByRole('columnheader', { name: 'Peso en la línea' })).toBeVisible()
  await expect(cuentas.getByRole('row', { name: /6009001\.001/ })).toContainText('100.0%') // única cuenta
})
