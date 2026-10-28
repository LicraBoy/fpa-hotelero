import { expect, test, type Page } from '@playwright/test'
import { abrirVariance, pestana, prepararReporteSintetico } from './datos'

// Budget en pantalla con el reporte SINTÉTICO (ver backend/scripts/crear_archivos_e2e.py): editar,
// guardar una versión nueva y ver el Variance con ella.
// Captura (ronda 3): una cifra por celda; solo la celda activa es un input; el Actual del mes está
// en el tooltip de la celda y, para las líneas con Actual capturable, en el panel «Panel de línea».
test.describe.configure({ mode: 'serial' })

test.beforeAll(async ({ request }) => {
  await prepararReporteSintetico(request)
})

async function abrirBudget(page: Page, usuario = 'Analista') {
  await page.setViewportSize({ width: 1600, height: 900 })
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: usuario })
  await pestana(page, 'Budget').click()
  await page.getByRole('tab', { name: 'Captura' }).click()
  await expect(page.getByRole('heading', { name: 'Captura presupuestaria' })).toBeVisible()
  await expect(page.getByText('Ejercicio fiscal 2026/27')).toBeVisible()
  await expect(page.getByRole('region', { name: 'Captura de Budget' })).toBeVisible()
}

const celda = (page: Page, linea: string, mes: string) => page.getByLabel(`Budget de ${linea}, ${mes}`)

/** Activa la celda (clic) y escribe en su input. */
async function escribir(page: Page, linea: string, mes: string, valor: string) {
  await celda(page, linea, mes).click()
  await page.getByRole('textbox', { name: `Budget de ${linea}, ${mes}` }).fill(valor)
}

const barra = (page: Page) => page.locator('.barra-cambios')

test('todos los roles con permisos de Budget ven Budget Studio (captura por ciclo, objetivo o revisión)', async ({ page }) => {
  // Desde el ciclo de presupuesto, Dirección (objetivo) y Responsable de área (captura) también
  // entran a Budget; lo que cambia es qué pueden escribir dentro.
  for (const usuario of ['Analista', 'Contralor', 'Dirección', 'Responsable de área']) {
    await page.goto('/')
    await page.getByLabel('Usuario (desarrollo)').selectOption({ label: usuario })
    await expect(pestana(page, 'Cargas').or(pestana(page, 'Catálogo')).first()).toBeVisible()
    await expect(pestana(page, 'Budget')).toHaveCount(1)
  }
})

test('un importe no válido se marca y no deja guardar', async ({ page }) => {
  await abrirBudget(page)
  await expect(barra(page)).toHaveCount(0) // sin cambios no hay barra
  await escribir(page, 'Room Revenue', 'Ago 26', 'abc')
  await expect(celda(page, 'Room Revenue', 'Ago 26')).toHaveAttribute('aria-invalid', 'true')
  await expect(barra(page)).toContainText('1 celda inválida')
  await expect(page.getByRole('button', { name: 'Guardar cambios' })).toBeDisabled()
  await page.getByRole('button', { name: 'Descartar cambios' }).click()
  await expect(barra(page)).toHaveCount(0)
})

test('un mes sin Budget lo avisa y lleva a la pestaña Budget', async ({ page }) => {
  await abrirVariance(page)
  // El Budget del reporte de ejemplo es del corte de agosto: julio no tiene Budget del mes
  await page.getByLabel('Mes', { exact: true }).selectOption('2026-07')
  const aviso = page.getByRole('status').filter({ hasText: 'No hay Budget para 2026-07' })
  await expect(aviso).toBeVisible()
  await expect(aviso).toContainText('Presupuesto, Variación y % var. salen en «—»')
  await aviso.getByRole('button', { name: 'Capturar el Budget de 2026-07' }).click()
  await expect(page.getByRole('heading', { name: 'Captura presupuestaria' })).toBeVisible()
  // quien no puede editar el Budget no ve el botón, solo la explicación
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Dirección' })
  await pestana(page, 'Variance').click()
  await page.getByLabel('Mes', { exact: true }).selectOption('2026-07')
  await expect(page.getByText('Pide a Contraloría que lo capture o lo importe.')).toBeVisible()
  await expect(page.getByRole('button', { name: /Capturar el Budget/ })).toHaveCount(0)
})

test('el tipo de cambio de cada mes se captura a mano y el Variance lo usa', async ({ page }) => {
  await abrirBudget(page)
  // el Budget fijo (18) viene del Excel; el Actual del mes todavía no se ha capturado
  await expect(celda(page, 'Exchange Rate:', 'Ago 26')).toHaveText('18.00')
  // el Actual capturable vive en el panel de la línea: se elige la línea y se escribe ahí
  await page.locator('.fila-linea-boton', { hasText: 'Exchange Rate:' }).click()
  const actual = page.getByLabel('Actual de Exchange Rate:, Ago 26')
  await expect(actual).toHaveValue('')
  await actual.fill('17.4')
  await expect(barra(page)).toContainText('1 cambio en 1 línea')
  await page.getByRole('button', { name: 'Guardar cambios' }).click()
  await expect(page.getByText('Vas a guardar 1 cambio en 1 línea')).toBeVisible()
  await expect(page.getByText('quedan en la bitácora')).toBeVisible()
  await page.getByRole('button', { name: 'Confirmar y guardar' }).click()
  await expect(page.getByText('Guardado: 1 Actual capturado')).toBeVisible()
  await expect(page.getByLabel('Actual de Exchange Rate:, Ago 26')).toHaveValue('17.4')

  // En el Variance: Actual 17.40, Presupuesto 18.00, Variación = Presupuesto − Actual = 0.60 (3.3 %)
  await abrirVariance(page)
  const fila = page
    .getByRole('row')
    .filter({ has: page.getByRole('rowheader', { name: 'Exchange Rate:' }) })
  const textos = (await fila.getByRole('cell').allInnerTexts()).map((t) =>
    t.replace(/\s+/g, ' ').trim(),
  )
  expect(textos.slice(0, 4)).toEqual(['17.40', '18.00', '0.60', '3.3%'])
  // un valor no válido se marca y no deja guardar; vaciar la celda borra lo capturado
  await pestana(page, 'Budget').click()
  await page.getByRole('tab', { name: 'Captura' }).click()
  await page.locator('.fila-linea-boton', { hasText: 'Exchange Rate:' }).click()
  await page.getByLabel('Actual de Exchange Rate:, Ago 26').fill('abc')
  await expect(page.getByLabel('Actual de Exchange Rate:, Ago 26')).toHaveAttribute('aria-invalid', 'true')
  await expect(page.getByRole('button', { name: 'Guardar cambios' })).toBeDisabled()
  await page.getByLabel('Actual de Exchange Rate:, Ago 26').fill('')
  await page.getByRole('button', { name: 'Guardar cambios' }).click()
  await page.getByRole('button', { name: 'Confirmar y guardar' }).click()
  await expect(page.getByText('Guardado: 1 Actual capturado')).toBeVisible()
  await expect(page.getByLabel('Actual de Exchange Rate:, Ago 26')).toHaveValue('')
})

test('editar, guardar y ver el Variance con el Budget nuevo', async ({ page }) => {
  await abrirBudget(page)

  // El Budget del Excel (900) se ve en la celda y el Actual de referencia (1,000) en su tooltip;
  // los totales se calculan solos
  const fila = (nombre: string) =>
    page.getByRole('row').filter({ has: page.getByRole('rowheader', { name: nombre }) })
  await expect(celda(page, 'Room Revenue', 'Ago 26')).toHaveText('900.00')
  await expect(fila('Room Revenue').getByRole('cell').nth(2)).toHaveAttribute('title', /Actual: 1,000\.00/)
  await escribir(page, 'Room Revenue', 'Ago 26', '950')
  await expect(barra(page)).toContainText('1 cambio en 1 línea')
  const totalAgosto = fila('Total Revenue').getByRole('cell').nth(2)
  await expect(totalAgosto).toHaveText('1,550.00') // 950 + 600: la suma de sus líneas, al instante

  // Un mes sin Budget (julio) también se escribe a mano; lo demás no se toca
  await escribir(page, 'Room Revenue', 'Jul 26', '770')
  await expect(barra(page)).toContainText('2 cambios en 1 línea')
  await expect(page.getByRole('textbox', { name: 'Budget de Room Revenue, Jul 26' })).toHaveValue('770') // la celda activa es un input
  await expect(celda(page, 'Room Revenue', 'Ago 26')).toHaveText('950.00')
  await expect(celda(page, 'Food Revenue', 'Ago 26')).toHaveText('600.00') // sin cambios

  // Guardar pide confirmación y crea una versión nueva
  await page.getByRole('button', { name: 'Guardar cambios' }).click()
  await expect(page.getByText(/Vas a guardar \d+ cambios en \d+ líneas?/)).toBeVisible()
  await page.getByRole('button', { name: 'Confirmar y guardar' }).click()
  await expect(page.getByText(/Budget guardado como versión \d+/)).toBeVisible()
  await expect(barra(page)).toHaveCount(0)
  await expect(celda(page, 'Room Revenue', 'Ago 26')).toHaveText('950.00') // ya viene de la versión

  // El Variance usa de inmediato el Budget nuevo: mes 950, acumulado 770 + 950
  await abrirVariance(page)
  const filaVariance = page
    .getByRole('row')
    .filter({ has: page.getByRole('rowheader', { name: 'Room Revenue' }) })
  const textos = (await filaVariance.getByRole('cell').allInnerTexts()).map((t) =>
    t.replace(/\s+/g, ' ').trim(),
  )
  expect(textos.slice(0, 8)).toEqual([
    '1,000.00', '950.00', '50.00', '5.3%', // mes
    '1,700.00', '1,720.00', '▼ Desfavorable: (20.00)', '(1.2%)', // acumulado
  ]) // prettier-ignore
})

test('Panel de línea de una línea informativa: promedio, sin objetivo ni perfil, Actual capturable', async ({ page }) => {
  await abrirBudget(page)
  await page.locator('.fila-linea-boton', { hasText: 'Exchange Rate:' }).click()
  const cajon = page.getByRole('complementary', { name: 'Panel de Exchange Rate:' })
  await expect(cajon).toBeVisible()
  await expect(cajon.getByText('Línea informativa')).toBeVisible()
  await expect(cajon.getByRole('heading', { name: /Promedio del año/ })).toBeVisible()
  // las filas de Perfil y Nota siempre se ven, con el texto que corresponde
  await expect(cajon.getByText('No aplica: no suma dinero')).toBeVisible()
  await expect(cajon.getByText('Esta línea no se captura en el ciclo')).toBeVisible()
  // sin objetivo, sin perfil y sin la suma de tipos de cambio
  await expect(cajon.getByText('Contra el objetivo')).toHaveCount(0)
  await expect(cajon.getByRole('tab', { name: 'Perfil' })).toHaveCount(0)
  await expect(cajon.getByRole('row', { name: /^Total/ })).toHaveCount(0)
  // el detalle por mes está abierto porque ahí se captura el Actual, con fila de promedio
  await expect(cajon.getByRole('row', { name: /^Promedio/ })).toBeVisible()
  await cajon.getByLabel('Actual de Exchange Rate:, Jul 26').fill('17.2175')
  await cajon.getByLabel('Actual de Exchange Rate:, Ago 26').fill('17.1337')
  await expect(cajon.getByText('2 de 12 meses con dato')).toBeVisible()
  await expect(cajon.getByRole('row', { name: /^Promedio/ })).toContainText('17.1756') // (17.2175 + 17.1337) / 2
  // la gráfica (con cifras) se ve completa, no aplastada
  const alto = await cajon.locator('.cajon-grafica svg.main-svg').first().evaluate((e) => e.getBoundingClientRect().height)
  expect(alto).toBeGreaterThan(180)
  // Esc cierra el cajón
  await cajon.getByRole('button', { name: 'Ocultar el panel de línea' }).focus()
  await page.keyboard.press('Escape')
  await expect(cajon).toHaveCount(0)
})
