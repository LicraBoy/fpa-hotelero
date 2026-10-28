import { test } from '@playwright/test'

// Mide las cajas de los bloques principales de Captura a 1536 × 1024 y las compara con la
// referencia (x/y/ancho/alto estimados sobre «MEJORA PARA PRESUPEUSTO.png»; tolerancia ±4 px).
const REFERENCIA: Record<string, [number, number, number, number]> = {
  '.lateral': [0, 0, 212, 1024],
  '.barra-superior': [212, 0, 1324, 50],
  '.captura-cabecera': [228, 69, 1293, 88],
  '.budget-ciclo-card': [228, 167, 1293, 59],
  '.tarjeta-tabla': [228, 241, 930, 754],
  '.panel-linea-ref': [1168, 241, 353, 754],
  '.barra-cambios-ref': [228, 925, 930, 62],
}

test('medidas de los bloques (1536x1024)', async ({ page }) => {
  await page.setViewportSize({ width: 1536, height: 1024 })
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Contralor' })
  await page.getByRole('navigation', { name: 'Secciones' }).getByRole('button', { name: 'Budget Studio' }).click()
  await page.getByRole('tab', { name: 'Captura' }).click()
  await page.getByRole('region', { name: 'Captura de Budget' }).waitFor({ timeout: 30_000 })
  await page.waitForTimeout(1200)
  const filas: string[] = []
  for (const [selector, ref] of Object.entries(REFERENCIA)) {
    const existe = (await page.locator(selector).count()) > 0
    const caja = existe ? await page.locator(selector).first().boundingBox() : null
    if (!caja) {
      filas.push(`${selector.padEnd(24)} (no existe)   ref ${ref.join(',')}`)
      continue
    }
    const real = [caja.x, caja.y, caja.width, caja.height].map(Math.round)
    const dif = real.map((v, i) => v - ref[i])
    const ok = dif.every((d) => Math.abs(d) <= 4) ? 'OK ' : 'DIF'
    filas.push(`${ok} ${selector.padEnd(22)} real ${real.join(',').padEnd(22)} ref ${ref.join(',').padEnd(22)} dif ${dif.join(',')}`)
  }
  const pagina = await page.evaluate(() => ({
    scrollV: document.documentElement.scrollHeight - window.innerHeight,
    scrollH: document.documentElement.scrollWidth - window.innerWidth,
  }))
  console.log('MEDIDAS\n' + filas.join('\n') + `\nPAGINA scrollV=${pagina.scrollV} scrollH=${pagina.scrollH}`)
})
