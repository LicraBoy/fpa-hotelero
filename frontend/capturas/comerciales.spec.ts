import { expect, test } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

// Commercial Services con datos reales: cada negocio tiene dos secciones con el mismo nombre (ventas y gastos).
// Importa el Excel del Budget a la COPIA de la base desde cada una (la 1.ª y la 2.ª) y captura su Hoja de sección.
const SALIDA = resolve('../docs/imagenes/comerciales')
const EXCEL = resolve('../docs/-1% - MZT Budget 26-27 TC 18.00 Final.xlsx')
mkdirSync(SALIDA, { recursive: true })

const CASOS = [
  { nombre: 'Store', posicion: 0, cuentas: 2, total: '', archivo: 'store-ventas' },
  { nombre: 'Store', posicion: 1, cuentas: 7, total: '', archivo: 'store-gastos' },
  { nombre: 'Cafeteria', posicion: 1, cuentas: 5, total: '', archivo: 'cafeteria-gastos' },
  { nombre: 'Restaurant', posicion: 1, cuentas: 11, total: '', archivo: 'restaurant-gastos' },
]

for (const c of CASOS) {
  test(`${c.archivo}: importar desde la sección ${c.posicion + 1} de ${c.nombre}`, async ({ page }) => {
    await page.setViewportSize({ width: 1536, height: 1024 })
    await page.goto('/')
    await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Contralor' })
    await page.getByRole('navigation', { name: 'Secciones' }).getByRole('button', { name: 'Budget Studio' }).click()
    await page.getByRole('tab', { name: 'Captura' }).click()
    await page.getByRole('region', { name: 'Captura de Budget' }).waitFor({ timeout: 30_000 })
    await page.getByRole('button', { name: `Abrir la hoja de ${c.nombre}`, exact: true }).nth(c.posicion).click()
    await page.getByRole('region', { name: 'Hoja de cuentas por mes' }).waitFor()
    await page.getByLabel(`Excel del Budget con la hoja ${c.nombre}`).setInputFiles(EXCEL)
    await expect(page.getByText(`Se importaron ${c.cuentas} cuentas desde el Excel.`)).toBeVisible({ timeout: 60_000 })
    await page.waitForTimeout(800)
    await page.screenshot({ path: `${SALIDA}/${c.archivo}.png`, fullPage: true })
  })
}
