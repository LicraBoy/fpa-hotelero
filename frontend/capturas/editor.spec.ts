import { test, type Page } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

// Capturas del EDITOR DE CUENTA con datos reales (ver playwright.captura.config.ts).
const SALIDA = resolve('../docs/imagenes/editor-cuenta')
mkdirSync(SALIDA, { recursive: true })

async function abrir(page: Page, ancho: number, alto: number) {
  await page.setViewportSize({ width: ancho, height: alto })
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Contralor' })
  await page.getByRole('navigation', { name: 'Secciones' }).getByRole('button', { name: 'Budget Studio' }).click()
  await page.getByRole('tab', { name: 'Captura' }).click()
  await page.getByRole('region', { name: 'Captura de Budget' }).waitFor({ timeout: 30_000 })
  await page.locator('.fila-linea-boton', { hasText: 'Rental Income' }).first().click()
  await page.getByRole('region', { name: 'Meses de la cuenta' }).waitFor()
  await page.waitForTimeout(800)
}

for (const [ancho, alto] of [[1536, 1024], [1312, 700]] as [number, number][]) {
  test(`editor sin cambios ${ancho}x${alto}`, async ({ page }) => {
    await abrir(page, ancho, alto)
    await page.screenshot({ path: `${SALIDA}/sin-cambios-${ancho}x${alto}.png` })
  })
  test(`editor con cambios ${ancho}x${alto}`, async ({ page }) => {
    await abrir(page, ancho, alto)
    await page.getByLabel('Factor para todos los meses').fill('1.08')
    await page.getByRole('button', { name: 'Aplicar a los 12 meses' }).click()
    await page.waitForTimeout(300)
    await page.screenshot({ path: `${SALIDA}/con-cambios-${ancho}x${alto}.png` })
  })
}

test('editor con error de validación 1536x1024', async ({ page }) => {
  await abrir(page, 1536, 1024)
  await page.getByLabel('Base de Sep 26').fill('abc')
  await page.locator('.ec-errores summary').click()
  await page.waitForTimeout(300)
  await page.screenshot({ path: `${SALIDA}/error-1536x1024.png` })
})
