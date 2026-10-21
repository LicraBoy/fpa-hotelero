import { expect, test } from '@playwright/test'

// Inicio de sesión real (ADR 0005) contra el build de producción. El servidor de pruebas siembra
// una contraseña solo para el Contralor de desarrollo (backend/scripts/servidor_e2e.py).
const USUARIO = 'contralor@torres.local'
const CLAVE = 'Clave-e2e-2026'

async function abrirLogin(page: import('@playwright/test').Page) {
  await page.goto('/')
  await page.getByRole('button', { name: 'Probar inicio de sesión real' }).click()
  await expect(page.getByRole('heading', { name: 'Plataforma FP&A Hotelera' })).toBeVisible()
}

test('una contraseña incorrecta no entra y muestra un mensaje genérico', async ({ page }) => {
  await abrirLogin(page)
  await page.getByLabel('Usuario (correo)').fill(USUARIO)
  await page.getByLabel('Contraseña').fill('otra-clave-123')
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page.getByRole('alert')).toContainText('Usuario, contraseña o código incorrectos')
  await expect(page.getByRole('navigation', { name: 'Secciones' })).toHaveCount(0)
})

test('entrar, ver Mi cuenta y cerrar sesión', async ({ page }) => {
  await abrirLogin(page)
  await page.getByLabel('Usuario (correo)').fill(USUARIO)
  await page.getByLabel('Contraseña').fill(CLAVE)
  await page.getByRole('button', { name: 'Entrar' }).click()

  const nav = page.getByRole('navigation', { name: 'Secciones' })
  await expect(nav).toBeVisible()
  // La contraseña y el token no quedan en el almacenamiento del navegador
  const guardado = await page.evaluate(() => JSON.stringify({ ...sessionStorage, ...localStorage }))
  expect(guardado).not.toContain(CLAVE)

  await page.getByRole('button', { name: 'Menú de usuario' }).click()
  await page.getByRole('button', { name: 'Mi cuenta' }).click()
  await expect(page.getByRole('heading', { name: 'Mi cuenta' })).toBeVisible()
  await expect(page.getByRole('heading', { name: /Verificación en dos pasos/ })).toBeVisible()

  // Recargar conserva la sesión (cookie HttpOnly): en desarrollo se vuelve al selector y, al
  // elegir el inicio de sesión real, entra directo sin pedir contraseña
  await page.reload()
  await page.getByRole('button', { name: 'Probar inicio de sesión real' }).click()
  await expect(page.getByRole('navigation', { name: 'Secciones' })).toBeVisible()
  await expect(page.getByLabel('Usuario (correo)')).toHaveCount(0)

  await page.getByRole('button', { name: 'Menú de usuario' }).click()
  await page.getByRole('button', { name: 'Cerrar sesión' }).click()
  await expect(page.getByLabel('Usuario (correo)')).toBeVisible()
  await page.reload()
  // En desarrollo se vuelve al selector; la sesión ya no existe
  await expect(page.getByRole('button', { name: 'Probar inicio de sesión real' })).toBeVisible()
})
