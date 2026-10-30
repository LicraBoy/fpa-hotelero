import { expect, test } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

// VDS Allocation Collections con datos reales: importa el Excel del Budget a la COPIA de la base y captura la
// Hoja de sección (dos líneas con importes negativos) en docs/imagenes/vds/.
const SALIDA = resolve('../docs/imagenes/vds')
const EXCEL = resolve('../docs/-1% - MZT Budget 26-27 TC 18.00 Final.xlsx')
mkdirSync(SALIDA, { recursive: true })

test('vds: importar y ver la hoja de sección', async ({ page }) => {
  await page.setViewportSize({ width: 1536, height: 1024 })
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Contralor' })
  await page.getByRole('navigation', { name: 'Secciones' }).getByRole('button', { name: 'Budget Studio' }).click()
  await page.getByRole('tab', { name: 'Captura' }).click()
  await page.getByRole('region', { name: 'Captura de Budget' }).waitFor({ timeout: 30_000 })
  await page.getByRole('button', { name: 'Abrir la hoja de VDS Allocation Collections' }).click()
  await page.getByRole('region', { name: 'Hoja de cuentas por mes' }).waitFor()
  await page.getByLabel('Excel del Budget con la hoja VDS Allocation Collections').setInputFiles(EXCEL)
  await expect(page.getByText(/Se importaron 2 cuentas desde el Excel/)).toBeVisible({ timeout: 60_000 })
  await expect(page.getByRole('group', { name: 'Resumen de la hoja' })).toContainText('-268,627.88')
  await page.waitForTimeout(800)
  await page.screenshot({ path: `${SALIDA}/1-hoja.png`, fullPage: true })
})
