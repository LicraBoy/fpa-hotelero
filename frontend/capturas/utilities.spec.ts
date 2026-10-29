import { expect, test } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

// Utilities con datos reales: importa el Excel del Budget a la COPIA de la base y captura la Hoja de sección y
// las cuentas de consumo (Electricity, y Water & Sewer que suma consumo y partidas) en docs/imagenes/utilities/.
const SALIDA = resolve('../docs/imagenes/utilities')
const EXCEL = resolve('../docs/-1% - MZT Budget 26-27 TC 18.00 Final.xlsx')
mkdirSync(SALIDA, { recursive: true })

test('utilities: importar, hoja de sección y cuentas de consumo', async ({ page }) => {
  await page.setViewportSize({ width: 1536, height: 1024 })
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Contralor' })
  await page.getByRole('navigation', { name: 'Secciones' }).getByRole('button', { name: 'Budget Studio' }).click()
  await page.getByRole('tab', { name: 'Captura' }).click()
  await page.getByRole('region', { name: 'Captura de Budget' }).waitFor({ timeout: 30_000 })
  await page.getByRole('button', { name: 'Abrir la hoja de Utilities' }).click()
  await page.getByRole('region', { name: 'Hoja de cuentas por mes' }).waitFor()
  await page.getByLabel('Excel del Budget con la hoja Utilities').setInputFiles(EXCEL)
  await expect(page.getByText(/Se importaron \d+ cuentas desde el Excel/)).toBeVisible({ timeout: 60_000 })
  await page.waitForTimeout(800)
  await page.screenshot({ path: `${SALIDA}/1-hoja.png`, fullPage: true })

  await page.locator('.fila-linea-boton', { hasText: 'Electricity' }).first().click()
  await page.getByRole('region', { name: 'Consumo mensual', exact: true }).waitFor()
  await expect(page.getByRole('group', { name: 'Resumen de la hoja' })).toContainText('6,541,183.68')
  await page.waitForTimeout(800)
  await page.screenshot({ path: `${SALIDA}/2-electricity.png`, fullPage: true })
  await page.getByRole('button', { name: 'Volver a la Hoja de sección' }).click()

  await page.locator('.fila-linea-boton', { hasText: 'Water' }).first().click()
  await page.getByRole('region', { name: 'Consumo mensual', exact: true }).waitFor()
  await expect(page.getByRole('group', { name: 'Resumen de la hoja' })).toContainText('3,885,121.25')
  await page.waitForTimeout(800)
  await page.screenshot({ path: `${SALIDA}/3-water.png`, fullPage: true })
})
