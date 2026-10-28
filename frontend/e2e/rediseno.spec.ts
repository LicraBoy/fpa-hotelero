import { expect, test } from '@playwright/test'
import { abrirVariance, pestana, prepararReporteSintetico } from './datos'

// Lo nuevo del rediseño: barra lateral agrupada, barra superior, tema claro/oscuro, resumen del mes
// y colores de variación. Cifras del reporte SINTÉTICO (backend/scripts/crear_archivos_e2e.py).
test.describe.configure({ mode: 'serial' })

test.beforeAll(async ({ request }) => {
  await prepararReporteSintetico(request)
})

test('la barra lateral agrupa las secciones y solo muestra lo que el rol puede ver', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Contralor' })
  const nav = page.getByRole('navigation', { name: 'Secciones' })
  // Sidebar de la referencia: Financiero, Budget Studio (bloque expandible) y un grupo con el resto
  await expect(nav.getByRole('group', { name: 'Financiero' }).getByRole('button')).toHaveText(['Variance', 'Por departamento', 'Saldos'])
  await expect(nav.getByRole('group', { name: 'Budget Studio' }).getByRole('button', { name: 'Budget Studio' })).toBeVisible()
  await expect(nav.getByRole('group', { name: 'Administración' }).getByRole('button')).toHaveText(['Cargas', 'Catálogo', 'Auditoría', 'Usuarios'])
  // el analista no ve Auditoría ni Usuarios: esos botones desaparecen
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Analista' })
  await expect(pestana(page, 'Cargas')).toBeVisible()
  await expect(nav.getByRole('button', { name: 'Auditoría' })).toHaveCount(0)
})

test('la barra superior muestra dónde estoy, el hotel, el usuario y el estado de la API', async ({ page }) => {
  await abrirVariance(page)
  const ubicacion = page.getByRole('navigation', { name: 'Ubicación' })
  await expect(ubicacion).toContainText('Financiero')
  await expect(ubicacion).toContainText('Variance')
  await expect(page.getByLabel('Hotel')).toBeVisible()
  await expect(page.getByText('API conectada')).toBeVisible()
  await page.getByRole('link', { name: 'Ver el desglose de Salaries, mes' }).click()
  await expect(ubicacion).toContainText('Desglose')
})

test('el interruptor cambia el tema y la elección se conserva al recargar', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light' })
  await page.goto('/')
  await expect(page.locator('html')).toHaveAttribute('data-tema', 'claro')
  await page.getByRole('button', { name: 'Cambiar a tema oscuro' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-tema', 'oscuro')
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-tema', 'oscuro')
  await page.getByRole('button', { name: 'Cambiar a tema claro' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-tema', 'claro')
})

test('sin elección el tema sigue al del sistema', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' })
  await page.goto('/')
  await expect(page.locator('html')).toHaveAttribute('data-tema', 'oscuro')
})

test('el resumen del mes sale de las variaciones que ya muestra la tabla', async ({ page }) => {
  await abrirVariance(page)
  const resumen = page.getByRole('region', { name: 'Resumen del mes' })
  await expect(resumen).toContainText('3 de 4') // líneas desfavorables de las de detalle con variación
  await expect(resumen).toContainText('(99.50)')
  await expect(resumen).toContainText('Food Revenue')
  await expect(resumen).toContainText('100.00')
  await expect(resumen).toContainText('Room Revenue')
})

test('variación favorable en verde y desfavorable en rojo, sin cambiar el texto de las cifras', async ({ page }) => {
  await abrirVariance(page)
  const fila = page.getByRole('row').filter({ has: page.getByRole('rowheader', { name: 'Room Revenue' }) })
  const favorable = fila.locator('td.favorable').first()
  await expect(favorable).toHaveText('100.00') // la flecha ▲ es de CSS: no entra al texto
  const desfavorable = page
    .getByRole('row')
    .filter({ has: page.getByRole('rowheader', { name: 'Food Revenue' }) })
    .locator('td.desfavorable')
    .first()
  await expect(desfavorable).toContainText('(99.50)')
  await expect(desfavorable).toContainText('Desfavorable')
})
