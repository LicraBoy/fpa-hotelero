import { expect, test, type Page } from '@playwright/test'
import { pestana } from './datos'

// Cada pantalla tiene su ruta por hash: se puede enlazar, sobrevive a recargar y respeta permisos.

async function entrar(page: Page, usuario: string, hash: string) {
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: usuario })
  await page.evaluate((h) => {
    window.location.hash = h
  }, hash)
}

test('recargar conserva la pantalla en la que estabas', async ({ page }) => {
  await entrar(page, 'Contralor', '#/usuarios')
  await expect(page.getByRole('heading', { name: 'Usuarios' })).toBeVisible()
  await page.reload()
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Contralor' })
  await expect(page.getByRole('heading', { name: 'Usuarios' })).toBeVisible()
  await expect(page).toHaveURL(/#\/usuarios$/)
})

test('al pulsar una sección cambia la ruta y la ubicación', async ({ page }) => {
  await entrar(page, 'Analista', '#/cargas')
  await pestana(page, 'Catálogo').click()
  await expect(page).toHaveURL(/#\/catalogo$/)
  await expect(page.getByRole('navigation', { name: 'Ubicación' })).toContainText('Datos')
  await expect(page.getByRole('navigation', { name: 'Ubicación' })).toContainText('Catálogo')
  await expect(pestana(page, 'Catálogo')).toHaveAttribute('aria-current', 'page')
})

test('sin permiso la ruta muestra «Sin acceso» y no consulta nada', async ({ page }) => {
  const peticiones: string[] = []
  page.on('request', (r) => peticiones.push(new URL(r.url()).pathname))
  await entrar(page, 'Analista', '#/usuarios')
  await expect(page.getByRole('alert', { name: 'Sin acceso' })).toBeVisible()
  await page.waitForTimeout(300)
  expect(peticiones.filter((p) => p.endsWith('/usuarios'))).toEqual([])
  await entrar(page, 'Analista', '#/cuenta') // Mi cuenta solo existe con sesión real
  await expect(page.getByRole('alert', { name: 'Sin acceso' })).toBeVisible()
})

test('una ruta inventada abre la primera pantalla disponible', async ({ page }) => {
  await entrar(page, 'Dirección', '#/no-existe')
  await expect(pestana(page, 'Variance')).toHaveAttribute('aria-current', 'page')
})

test('el menú lateral no lista nada que el rol no pueda abrir', async ({ page }) => {
  await entrar(page, 'Auditoría', '#/auditoria')
  const nav = page.getByRole('navigation', { name: 'Secciones' })
  await expect(nav.getByRole('button', { name: 'Usuarios' })).toHaveCount(0)
  await expect(nav.getByRole('button', { name: 'Budget' })).toHaveCount(0)
  await expect(nav.getByRole('button', { name: 'Auditoría' })).toBeVisible()
})

test('sin ruta se abre la primera pantalla y la dirección se completa sin mensaje de error', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Contralor' })
  await expect(pestana(page, 'Variance')).toHaveAttribute('aria-current', 'page')
  await expect(page.getByRole('alert', { name: 'Ruta no válida' })).toHaveCount(0)
  await expect(page).toHaveURL(/#\/variance$/)
  await page.evaluate(() => {
    window.location.hash = '#/no-existe'
  })
  await expect(page).toHaveURL(/#\/variance$/)
  await expect(page.getByRole('alert', { name: 'Ruta no válida' })).toHaveCount(0)
})
