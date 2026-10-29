import { expect, test } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

// Legal e IT Systems con datos reales: importa el Excel del Budget a la COPIA de la base desde cada sección y
// captura su Hoja de sección (docs/imagenes/legal_it/).
const SALIDA = resolve('../docs/imagenes/legal_it')
const EXCEL = resolve('../docs/-1% - MZT Budget 26-27 TC 18.00 Final.xlsx')
mkdirSync(SALIDA, { recursive: true })

const CASOS = [
  { nombre: 'Legal', cuentas: 9, archivo: 'legal' },
  { nombre: 'IT Systems', cuentas: 11, archivo: 'it-systems' },
]

for (const c of CASOS) {
  test(`${c.archivo}: importar y ver la hoja de sección`, async ({ page }) => {
    await page.setViewportSize({ width: 1536, height: 1024 })
    await page.goto('/')
    await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Contralor' })
    await page.getByRole('navigation', { name: 'Secciones' }).getByRole('button', { name: 'Budget Studio' }).click()
    await page.getByRole('tab', { name: 'Captura' }).click()
    await page.getByRole('region', { name: 'Captura de Budget' }).waitFor({ timeout: 30_000 })
    await page.getByRole('button', { name: `Abrir la hoja de ${c.nombre}`, exact: true }).click()
    await page.getByRole('region', { name: 'Hoja de cuentas por mes' }).waitFor()
    await page.getByLabel(`Excel del Budget con la hoja ${c.nombre}`).setInputFiles(EXCEL)
    await expect(page.getByText(`Se importaron ${c.cuentas} cuentas desde el Excel.`)).toBeVisible({ timeout: 60_000 })
    await page.waitForTimeout(800)
    await page.screenshot({ path: `${SALIDA}/${c.archivo}.png`, fullPage: true })
  })
}
