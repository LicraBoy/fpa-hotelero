import { expect, test, type Page } from '@playwright/test'
import { abrirVariance, pestana, prepararReporteSintetico } from './datos'

// Flujo de cierre del Variance (Fase 5.4). Termina reabriendo el periodo para no bloquear las
// cargas de las demás pruebas, que comparten esta base.
test.describe.configure({ mode: 'serial' })

test.beforeAll(async ({ request }) => {
  await prepararReporteSintetico(request)
})

const barra = (page: Page) => page.getByRole('region', { name: 'Cierre del periodo' })

test('el Analista marca el periodo como comentado y revisado, pero no puede aprobar', async ({ page }) => {
  await abrirVariance(page, 'Analista')
  await expect(barra(page).getByText('Borrador')).toBeVisible()
  await expect(barra(page).getByRole('button', { name: 'Aprobar' })).toHaveCount(0)

  await barra(page).getByRole('button', { name: 'Marcar como comentado' }).click()
  await barra(page).getByRole('button', { name: /Confirmar/ }).click()
  await expect(barra(page).getByText('Comentado').first()).toBeVisible()

  await barra(page).getByRole('button', { name: 'Marcar como revisado' }).click()
  await barra(page).getByRole('button', { name: /Confirmar/ }).click()
  await expect(barra(page).getByText('Revisado').first()).toBeVisible()
  await expect(barra(page).getByRole('button', { name: 'Aprobar' })).toHaveCount(0)
})

test('el Contralor aprueba (se congelan las versiones) y reabre con un motivo', async ({ page }) => {
  await abrirVariance(page, 'Contralor')
  await barra(page).getByRole('button', { name: 'Aprobar' }).click()
  await barra(page).getByRole('button', { name: /Confirmar/ }).click()
  await expect(barra(page).getByText('Aprobado').first()).toBeVisible()
  await expect(barra(page).getByText(/Cifras congeladas: mapeo v/)).toBeVisible()
  await expect(barra(page).getByRole('button', { name: 'Bloquear' })).toBeVisible()

  // Reabrir exige el motivo
  await barra(page).getByRole('button', { name: 'Reabrir' }).click()
  await expect(barra(page).getByLabel('Motivo (obligatorio)')).toBeVisible()
  await barra(page).getByLabel('Motivo (obligatorio)').fill('Prueba: se reabre para recargar')
  await barra(page).getByRole('button', { name: /Confirmar/ }).click()
  await expect(barra(page).getByText('Borrador').first()).toBeVisible()

  await barra(page).getByText(/Historial del cierre/).click()
  await expect(barra(page).getByText(/Prueba: se reabre para recargar/)).toBeVisible()
})

test('el Responsable de departamento no ve la barra de cierre', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Responsable de área' })
  await pestana(page, 'Variance').click()
  await expect(page.getByRole('region', { name: 'Variance' })).toBeVisible()
  await expect(barra(page)).toHaveCount(0)
})
