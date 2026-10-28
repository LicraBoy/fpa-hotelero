import { expect, test, type Page } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

// Capturas de «Comparación anual e inflación» v2 con datos reales (ver playwright.captura.config.ts).
// Salen SIN RECORTAR (página completa) en docs/imagenes/comparacion-v3/.
const SALIDA = resolve('../docs/imagenes/comparacion-v3')
mkdirSync(SALIDA, { recursive: true })

const TAMANOS: [string, number, number][] = [
  ['1536x1024', 1536, 1024],
  ['1312x900', 1312, 900],
]

async function abrir(page: Page, ancho: number, alto: number, tema: 'claro' | 'oscuro') {
  // El selector de usuario de desarrollo no se ve en pantallas angostas: se entra ancho y luego se ajusta
  await page.setViewportSize({ width: 1536, height: 1024 })
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Contralor' })
  await page.evaluate((t) => {
    document.documentElement.dataset.tema = t
  }, tema)
  await page.getByRole('navigation', { name: 'Secciones' }).getByRole('button', { name: 'Budget Studio' }).click()
  await page.getByRole('tab', { name: 'Captura' }).click()
  await page.getByRole('region', { name: 'Captura de Budget' }).waitFor({ timeout: 30_000 })
  await page.getByRole('button', { name: 'Abrir la hoja de Other Income' }).click()
  await page.getByRole('tab', { name: 'Comparación anual' }).click()
  await page.getByRole('img', { name: 'Comparativo anual' }).waitFor()
  await page.setViewportSize({ width: ancho, height: alto })
  await page.waitForTimeout(700)
}

// Con la página completa, la barra pegajosa de acciones queda donde estaba la ventana: se baja al final
async function alFinal(page: Page) {
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight))
  await page.waitForTimeout(300)
}

for (const tema of ['claro', 'oscuro'] as const) {
  for (const [nombre, ancho, alto] of TAMANOS) {
    test(`comparación ${tema} ${nombre}`, async ({ page }) => {
      await abrir(page, ancho, alto, tema)
      const m = await page.evaluate(() => {
        const d = document.documentElement
        const tabla = document.querySelector('.tm-contenedor') as HTMLElement
        const tarjeta = document.querySelector('.hoja-grafico-tarjeta') as HTMLElement
        const caja = document.querySelector('.graf-caja') as HTMLElement
        const svg = document.querySelector('.grafico-comparativo') as SVGElement
        return {
          docV: d.scrollHeight - d.clientHeight,
          docH: d.scrollWidth - d.clientWidth,
          tablaH: tabla.scrollWidth - tabla.clientWidth,
          tarjetaAlto: Math.round(tarjeta.getBoundingClientRect().height),
          svgAncho: Math.round(svg.getBoundingClientRect().width),
          cajaAncho: Math.round(caja.getBoundingClientRect().width),
          cabecera: Math.round((document.querySelector('.hoja-cabecera') as HTMLElement).getBoundingClientRect().height),
          franja: Math.round((document.querySelector('.hoja-franja') as HTMLElement).getBoundingClientRect().height),
        }
      })
      console.log(`${tema} ${nombre}: ${JSON.stringify(m)}`)
      await alFinal(page)
      await page.screenshot({ path: `${SALIDA}/${tema}-${nombre}.png`, fullPage: true })
    })
  }
}

test('tooltip activo (claro 1536x1024)', async ({ page }) => {
  await abrir(page, 1536, 1024, 'claro')
  await page.locator('.graf-caja').focus()
  for (let i = 0; i < 4; i++) await page.keyboard.press('ArrowRight')
  await expect(page.locator('.graf-tooltip')).toBeVisible()
  await page.screenshot({ path: `${SALIDA}/claro-1536x1024-tooltip.png`, fullPage: true })
})

test('tabla en móvil (claro 390x844)', async ({ page }) => {
  await abrir(page, 390, 844, 'claro')
  await alFinal(page)
  await page.screenshot({ path: `${SALIDA}/claro-390x844.png`, fullPage: true })
})

test('acumulado (oscuro 1536x1024)', async ({ page }) => {
  await abrir(page, 1536, 1024, 'oscuro')
  await page.getByRole('button', { name: 'Acumulado' }).click()
  await page.locator('.graf-caja').focus()
  for (let i = 0; i < 6; i++) await page.keyboard.press('ArrowRight')
  await page.screenshot({ path: `${SALIDA}/oscuro-1536x1024-acumulado.png`, fullPage: true })
})

test('barra con cambios pendientes (claro 1536x1024)', async ({ page }) => {
  await abrir(page, 1536, 1024, 'claro')
  await page.getByLabel('Inflación de Ago 26 (%)').fill('1.5')
  await page.getByLabel('Inflación de Sep 26 (%)').fill('2')
  await alFinal(page)
  await page.screenshot({ path: `${SALIDA}/claro-1536x1024-cambios.png`, fullPage: true })
})
