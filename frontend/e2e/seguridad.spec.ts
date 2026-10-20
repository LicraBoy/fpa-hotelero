import { expect, test, type Page } from '@playwright/test'

// Seguridad del frontend contra el BUILD DE PRODUCCIÓN servido con su CSP estricta.
// Los pasos son independientes del resto: no dependen de datos cargados.

async function elegirUsuario(page: Page, nombre: string) {
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: nombre })
}

const pestana = (page: Page, nombre: string) =>
  page.getByRole('navigation', { name: 'Secciones' }).getByRole('button', { name: nombre })

// Registra violaciones de la CSP y errores de consola que las mencionen.
async function vigilarCsp(page: Page): Promise<string[]> {
  const violaciones: string[] = []
  await page.exposeFunction('registrarViolacion', (texto: string) => violaciones.push(texto))
  await page.addInitScript(() => {
    document.addEventListener('securitypolicyviolation', (e) => {
      // @ts-expect-error función expuesta por Playwright
      window.registrarViolacion(`${e.violatedDirective}: ${e.blockedURI}`)
    })
  })
  page.on('console', (m) => {
    if (/content security policy|refused to (apply|load|execute)/i.test(m.text())) {
      violaciones.push(m.text())
    }
  })
  return violaciones
}

test('la página se sirve con la CSP estricta y sin nada en línea', async ({ page }) => {
  const respuesta = await page.goto('/')
  const csp = respuesta?.headers()['content-security-policy'] ?? ''
  expect(csp).toContain("default-src 'self'")
  expect(csp).toContain("script-src 'self'")
  expect(csp).toContain("style-src 'self'")
  expect(csp).toContain("object-src 'none'")
  expect(csp).toContain("frame-ancestors 'none'")
  expect(csp).not.toContain('unsafe-inline')
  expect(csp).not.toContain('unsafe-eval')
  const h = respuesta?.headers() ?? {}
  expect(h['x-content-type-options']).toBe('nosniff')
  expect(h['x-frame-options']).toBe('DENY')
  expect(h['referrer-policy']).toBe('no-referrer')
  // el documento no trae scripts ni estilos en línea
  expect(await page.locator('script:not([src])').count()).toBe(0)
  expect(await page.locator('style').count()).toBe(0)
  expect(await page.locator('[style]').count()).toBe(0)
})

test('recorrer la aplicación no provoca ninguna violación de la CSP', async ({ page }) => {
  const violaciones = await vigilarCsp(page)
  await page.goto('/')
  await expect(page.getByText('API conectada')).toBeVisible()
  for (const nombre of ['Cargas', 'Catálogo', 'Saldos', 'Variance', 'Auditoría']) {
    await pestana(page, nombre).click()
  }
  expect(violaciones).toEqual([])
})

test('las respuestas de la API llevan sus cabeceras de seguridad y no se guardan en cachés', async ({
  page,
}) => {
  const r = await page.request.get('/api/health')
  const h = r.headers()
  expect(h['content-security-policy']).toBe("default-src 'none'; frame-ancestors 'none'")
  expect(h['x-content-type-options']).toBe('nosniff')
  expect(h['cache-control']).toBe('no-store')
  expect(h['cross-origin-resource-policy']).toBe('same-origin')
})

test('no hay credenciales en el almacenamiento del navegador', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('API conectada')).toBeVisible()
  await elegirUsuario(page, 'Analista')
  await pestana(page, 'Variance').click()
  const almacenamiento = await page.evaluate(() => ({
    local: Object.keys(window.localStorage),
    sesion: Object.keys(window.sessionStorage),
    cookies: document.cookie,
  }))
  expect(almacenamiento.local).toEqual([]) // nada en localStorage
  expect(almacenamiento.cookies).toBe('')
  for (const clave of almacenamiento.sesion) {
    expect(clave).not.toMatch(/token|jwt|bearer|secret|password|credencial/i)
  }
  expect(almacenamiento.sesion).toEqual(['fpa_usuario_dev']) // solo la preferencia de desarrollo
})

test('una ruta con basura se rechaza y no ejecuta nada', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('API conectada')).toBeVisible()
  for (const hash of [
    '#/variance/2026-08/cuenta/<img src=x onerror=window.__xss=1>',
    '#/variance/2026-08/cuenta/javascript:window.__xss=1',
    "#/variance/<script>window.__xss=1</script>",
  ]) {
    await page.evaluate((h) => {
      window.location.hash = h
    }, hash)
    await page.waitForTimeout(150)
    expect(await page.evaluate(() => (window as unknown as { __xss?: number }).__xss)).toBeUndefined()
    expect(await page.locator('img[src="x"]').count()).toBe(0)
  }
})

test('sin permiso de drill-down no se muestra el detalle ni se consulta nada', async ({ page }) => {
  const peticiones: string[] = []
  page.on('request', (r) => peticiones.push(new URL(r.url()).pathname))
  await page.goto('/')
  // Dirección ve el reporte, pero no el detalle de cuentas y movimientos
  await elegirUsuario(page, 'Dirección')
  await expect(pestana(page, 'Variance')).toBeVisible()

  peticiones.length = 0
  await page.evaluate(() => {
    window.location.hash = '#/variance/2026-08/cuenta/6009001.001?bloque=mes'
  })
  await expect(page.getByRole('alert', { name: 'Sin acceso' })).toBeVisible()
  await page.waitForTimeout(300)
  expect(peticiones.filter((p) => p.includes('/variance') || p.includes('/asientos'))).toEqual([])
})

test('quien sí tiene permiso ve la pantalla de Variance', async ({ page }) => {
  await page.goto('/')
  await elegirUsuario(page, 'Analista')
  await pestana(page, 'Variance').click()
  await expect(page.getByRole('region', { name: 'Variance' })).toBeVisible()
  await expect(page.getByRole('alert', { name: 'Sin acceso' })).toHaveCount(0)
})
