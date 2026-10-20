import { expect, test } from '@playwright/test'
import { abrirVariance, pestana, prepararReporteSintetico } from './datos'

// Cadena de hashes de la bitácora e historial de la cifra (Fase 5.5).
test.describe.configure({ mode: 'serial' })

test.beforeAll(async ({ request }) => {
  await prepararReporteSintetico(request)
})

test('la bitácora muestra que la cadena está íntegra y se puede verificar de nuevo', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Contralor' })
  await pestana(page, 'Auditoría').click()
  const estado = page.getByRole('status', { name: 'Integridad de la bitácora' })
  await expect(estado.getByText('Cadena íntegra')).toBeVisible()
  await estado.getByRole('button', { name: 'Verificar de nuevo' }).click()
  await expect(estado.getByText('Cadena íntegra')).toBeVisible()
  await expect(estado).toContainText('eventos')
})

test('el panel de la línea trae el historial de la cifra con la carga que la produjo', async ({ page }) => {
  await abrirVariance(page, 'Analista')
  await page
    .getByRole('row')
    .filter({ has: page.getByRole('rowheader', { name: /Salaries/ }) })
    .getByRole('button', { name: 'Ver detalle de la línea' })
    .click()
  const panel = page.getByRole('dialog', { name: 'Detalle de la línea' })
  await panel.getByText('Historial de la cifra').click()
  await expect(panel.getByText('Carga', { exact: true }).first()).toBeVisible()
})
