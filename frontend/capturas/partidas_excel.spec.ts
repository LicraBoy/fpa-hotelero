import { expect, test } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

// Other Fringe con datos reales: parte de la COPIA de la base (una sola partida «Importe actual»),
// trae las partidas de su hoja del Excel con «Importar partidas del Excel» y captura antes y después.
const SALIDA = resolve('../docs/imagenes/partidas_excel')
const EXCEL = resolve('../docs/-1% - MZT Budget 26-27 TC 18.00 Final.xlsx')
mkdirSync(SALIDA, { recursive: true })

test('other fringe: de una partida resumida a las 16 partidas del Excel', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 1000 })
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Contralor' })
  await page.getByRole('navigation', { name: 'Secciones' }).getByRole('button', { name: 'Budget Studio' }).click()
  await page.getByRole('tab', { name: 'Captura' }).click()
  await page.getByRole('region', { name: 'Captura de Budget' }).waitFor({ timeout: 30_000 })
  await page.getByRole('button', { name: 'Abrir la hoja de Mgmt & Check In' }).click()
  await page.getByRole('region', { name: 'Hoja de cuentas por mes' }).waitFor()
  await page.locator('.fila-linea-boton', { hasText: 'Other Fringe' }).first().click()
  await page.getByRole('region', { name: 'Hoja de cuentas por mes' }).waitFor()
  await page.waitForTimeout(800)
  await page.screenshot({ path: `${SALIDA}/1-antes.png`, fullPage: true })
  await page.getByLabel('Excel del Budget con las partidas de Other Fringe').setInputFiles(EXCEL)
  await expect(page.getByText(/Se importaron las partidas de Other Fringe/)).toBeVisible({ timeout: 60_000 })
  await expect(page.getByRole('group', { name: 'Resumen de la hoja' })).toContainText('375,952.50')
  await page.waitForTimeout(800)
  await page.screenshot({ path: `${SALIDA}/2-despues.png`, fullPage: true })
  await page.getByRole('region', { name: 'Hoja de cuentas por mes' }).evaluate((e) => e.scrollTo({ left: 700 }))
  await page.waitForTimeout(300)
  await page.screenshot({ path: `${SALIDA}/3-meses.png`, fullPage: true })
})
