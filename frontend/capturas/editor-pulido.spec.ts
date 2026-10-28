import { expect, test, type Page } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

// Capturas del Editor mensual pulido, con datos reales (ver playwright.captura.config.ts).
// Salen en docs/imagenes/editor-pulido/.
const SALIDA = resolve('../docs/imagenes/editor-pulido')
mkdirSync(SALIDA, { recursive: true })

const TAMANOS: [string, number, number][] = [
  ['1536x1024', 1536, 1024],
  ['1312x900', 1312, 900],
]

async function abrirEditor(page: Page, ancho: number, alto: number, tema: 'claro' | 'oscuro') {
  await page.setViewportSize({ width: ancho, height: alto })
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Contralor' })
  await page.evaluate((t) => {
    document.documentElement.dataset.tema = t
  }, tema)
  await page.getByRole('navigation', { name: 'Secciones' }).getByRole('button', { name: 'Budget Studio' }).click()
  await page.getByRole('tab', { name: 'Captura' }).click()
  await page.getByRole('region', { name: 'Captura de Budget' }).waitFor({ timeout: 30_000 })
  await page.getByRole('button', { name: 'Abrir la hoja de Other Income' }).click()
  await page.locator('.fila-linea-boton', { hasText: 'Rental Income' }).first().click()
  await page.getByRole('region', { name: 'Meses de la cuenta' }).waitFor()
  await page.waitForTimeout(500)
}

for (const tema of ['claro', 'oscuro'] as const) {
  for (const [nombre, ancho, alto] of TAMANOS) {
    test(`editor ${tema} ${nombre}`, async ({ page }) => {
      await abrirEditor(page, ancho, alto, tema)
      // la tabla cabe sin scroll vertical interno y el documento no se desborda
      const medidas = await page.evaluate(() => {
        const t = document.querySelector('.ec-tabla-tarjeta') as HTMLElement
        const d = document.documentElement
        return { internoV: t.scrollHeight - t.clientHeight, docH: d.scrollWidth - d.clientWidth }
      })
      console.log(`${tema} ${nombre}: scroll interno vertical=${medidas.internoV}px, desborde horizontal del documento=${medidas.docH}px`)
      expect(medidas.docH).toBeLessThanOrEqual(0)
      await page.screenshot({ path: `${SALIDA}/${tema}-${nombre}-sin-cambios.png` })
      // dos cambios pendientes: la base de dos meses (en «Base × factor»)
      for (const mes of ['Ago 26', 'Oct 26']) {
        await page.getByLabel(`Base de ${mes}`).fill('15000.5')
      }
      await page.getByLabel('Base de Nov 26').focus()
      await expect(page.locator('.ec-barra')).toBeVisible()
      await page.waitForTimeout(300)
      await page.screenshot({ path: `${SALIDA}/${tema}-${nombre}-con-cambios.png` })
    })
  }
}

test('editor con un error de validación (claro 1536x1024)', async ({ page }) => {
  await abrirEditor(page, 1536, 1024, 'claro')
  await page.getByLabel('Base de Sep 26').fill('abc')
  await page.waitForTimeout(300)
  const estilo = await page.getByLabel('Base de Sep 26').evaluate((e) => {
    const c = getComputedStyle(e)
    return `${c.borderTopColor} / ${c.backgroundColor}`
  })
  console.log(`input inválido: borde / fondo = ${estilo}`)
  await page.locator('.ec-errores summary').click()
  await page.waitForTimeout(300)
  await page.screenshot({ path: `${SALIDA}/claro-1536x1024-error.png` })
})
