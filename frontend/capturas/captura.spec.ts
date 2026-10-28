import { test, type Page } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

// Capturas de la pantalla de Captura con datos reales (ver playwright.captura.config.ts).
// Salen en docs/imagenes/hoja-seccion/. FPA_ETAPA=f1|f2|... las separa por fase de trabajo.
const ETAPA = process.env.FPA_ETAPA ?? 'actual'
const SALIDA = resolve('../docs/imagenes/hoja-seccion')
mkdirSync(SALIDA, { recursive: true })

async function entrar(page: Page, ancho: number, alto: number) {
  await page.setViewportSize({ width: ancho, height: alto })
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Contralor' })
  await page.getByRole('navigation', { name: 'Secciones' }).getByRole('button', { name: 'Budget Studio' }).click()
  await page.getByRole('tab', { name: 'Captura' }).click()
  await page.getByRole('region', { name: 'Captura de Budget' }).waitFor({ timeout: 30_000 })
  await page.waitForTimeout(1200)
}

const RESOLUCIONES: [number, number][] = [
  [1536, 1024],
  [1312, 617],
  [1280, 900],
  [768, 1024],
  [390, 844],
]

for (const [ancho, alto] of RESOLUCIONES) {
  test(`captura ${ancho}x${alto}`, async ({ page }) => {
    await entrar(page, ancho, alto)
    await page.screenshot({ path: `${SALIDA}/${ETAPA}-${ancho}x${alto}.png` })
  })
}

test('captura con una cuenta abierta (1536x1024)', async ({ page }) => {
  await entrar(page, 1536, 1024)
  const cuenta = page.locator('.fila-linea-boton', { hasText: 'Rental Income' }).first()
  if (await cuenta.count()) await cuenta.click()
  await page.waitForTimeout(1200)
  await page.screenshot({ path: `${SALIDA}/${ETAPA}-cuenta-1536x1024.png` })
})
