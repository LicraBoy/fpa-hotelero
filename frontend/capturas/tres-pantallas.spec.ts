import { expect, test, type Page } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

// Capturas de las 3 pantallas rediseñadas (Hoja de sección, Comparación anual, Editor mensual) con datos
// reales (ver playwright.captura.config.ts). Salen en docs/imagenes/rediseno-3-pantallas/.
const SALIDA = resolve('../docs/imagenes/rediseno-3-pantallas')
mkdirSync(SALIDA, { recursive: true })

const RESOLUCIONES: [string, number, number][] = [
  ['1536x1024', 1536, 1024],
  ['1312x700', 1312, 700],
  ['tableta-820x1180', 820, 1180],
  ['movil-390x844', 390, 844],
]

async function abrirHoja(page: Page, ancho: number, alto: number) {
  // El selector de usuario de desarrollo no se ve en pantallas angostas (shell): se entra ancho y luego se reduce
  await page.setViewportSize({ width: 1536, height: 1024 })
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Contralor' })
  await page.getByRole('navigation', { name: 'Secciones' }).getByRole('button', { name: 'Budget Studio' }).click()
  await page.getByRole('tab', { name: 'Captura' }).click()
  await page.getByRole('region', { name: 'Captura de Budget' }).waitFor({ timeout: 30_000 })
  await page.getByRole('button', { name: 'Abrir la hoja de Other Income' }).click()
  await page.getByRole('region', { name: 'Hoja de cuentas por mes' }).waitFor()
  await page.setViewportSize({ width: ancho, height: alto })
  await page.waitForTimeout(800)
}

// El desborde del DOCUMENTO a 390 px viene de `.ciclo-caja-acciones` (flujo del ciclo, fuera de estas tres
// pantallas). Aquí se comprueba que lo que pertenece a la hoja y al editor no se sale del ancho.
const sinDesborde = (page: Page) =>
  page.evaluate(() => {
    const cw = document.documentElement.clientWidth
    const raiz = document.querySelector('.hoja-seccion')
    if (!raiz) return false
    const fuera = [...raiz.querySelectorAll('*')].filter((e) => {
      const b = e.getBoundingClientRect()
      if (b.width === 0 || b.right <= cw + 1) return false
      for (let p = e.parentElement; p && p !== raiz; p = p.parentElement) {
        const o = getComputedStyle(p).overflowX
        if (o === 'auto' || o === 'scroll' || o === 'hidden') return false
      }
      return true
    })
    return fuera.length === 0
  })

for (const [nombre, ancho, alto] of RESOLUCIONES) {
  test(`hoja de sección ${nombre}`, async ({ page }) => {
    await abrirHoja(page, ancho, alto)
    expect(await sinDesborde(page)).toBe(true)
    await page.screenshot({ path: `${SALIDA}/1-hoja-${nombre}.png`, fullPage: true })
  })
  test(`comparación anual ${nombre}`, async ({ page }) => {
    await abrirHoja(page, ancho, alto)
    await page.getByRole('tab', { name: 'Comparación anual' }).click()
    await page.getByRole('img', { name: 'Comparativo anual' }).waitFor()
    await page.waitForTimeout(400)
    expect(await sinDesborde(page)).toBe(true)
    await page.screenshot({ path: `${SALIDA}/2-comparacion-${nombre}.png`, fullPage: true })
  })
  test(`editor mensual ${nombre}`, async ({ page }) => {
    await abrirHoja(page, ancho, alto)
    await page.locator('.fila-linea-boton', { hasText: 'Rental Income' }).first().click()
    await page.getByRole('region', { name: 'Meses de la cuenta' }).waitFor()
    await page.waitForTimeout(500)
    expect(await sinDesborde(page)).toBe(true)
    await page.screenshot({ path: `${SALIDA}/3-editor-${nombre}.png`, fullPage: true })
    // con cambios pendientes (barra inferior)
    await page.getByLabel('Factor para todos los meses').fill('1.08')
    await page.getByRole('button', { name: 'Aplicar a los 12 meses' }).click()
    await page.waitForTimeout(300)
    await page.screenshot({ path: `${SALIDA}/3-editor-cambios-${nombre}.png` })
  })
}
