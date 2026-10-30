import { expect, test } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

// Purchasing con datos reales: importa el Excel del Budget a la COPIA de la base y captura la Hoja de
// sección, la Hoja de cuenta de Equipment/Supplies y el Editor de una partida (docs/imagenes/purchasing/).
const SALIDA = resolve('../docs/imagenes/purchasing')
const EXCEL = resolve('../docs/-1% - MZT Budget 26-27 TC 18.00 Final.xlsx')
mkdirSync(SALIDA, { recursive: true })

test('purchasing: importar, hoja de sección, hoja de cuenta y editor de partida', async ({ page }) => {
  await page.setViewportSize({ width: 1536, height: 1024 })
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Contralor' })
  await page.getByRole('navigation', { name: 'Secciones' }).getByRole('button', { name: 'Budget Studio' }).click()
  await page.getByRole('tab', { name: 'Captura' }).click()
  await page.getByRole('region', { name: 'Captura de Budget' }).waitFor({ timeout: 30_000 })
  await page.getByRole('button', { name: 'Abrir la hoja de Purchasing' }).click()
  await page.getByRole('region', { name: 'Hoja de cuentas por mes' }).waitFor()
  await page.getByLabel('Excel del Budget con la hoja Purchasing').setInputFiles(EXCEL)
  await expect(page.getByText(/Se importaron \d+ cuentas desde el Excel/)).toBeVisible({ timeout: 60_000 })
  await page.waitForTimeout(800)
  await page.screenshot({ path: `${SALIDA}/1-hoja.png`, fullPage: true })
  await page.getByRole('tab', { name: 'Comparación anual' }).click()
  await page.getByRole('img', { name: 'Comparativo anual' }).waitFor()
  await page.waitForTimeout(500)
  await page.screenshot({ path: `${SALIDA}/2-comparacion.png`, fullPage: true })
  await page.getByRole('button', { name: 'Volver a la Hoja de sección' }).click()
  await page.locator('.fila-linea-boton', { hasText: 'Equipment/Supplies' }).first().click()
  await page.getByRole('region', { name: 'Hoja de cuentas por mes' }).waitFor()
  await expect(page.getByRole('group', { name: 'Resumen de la hoja' })).toContainText('48,016.08')
  await page.waitForTimeout(800)
  await page.screenshot({ path: `${SALIDA}/3-hoja-de-cuenta-contract-serv-other.png`, fullPage: true })
  await page.locator('.fila-linea-boton').first().click()
  await page.getByRole('region', { name: 'Meses de la partida' }).waitFor()
  await page.waitForTimeout(500)
  await page.screenshot({ path: `${SALIDA}/4-editor-de-partida.png`, fullPage: true })
})
