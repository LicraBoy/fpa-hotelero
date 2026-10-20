import { expect, test, type Page } from '@playwright/test'

// Administración de usuarios (Fase 5.2) con la identidad de desarrollo.

async function elegirUsuario(page: Page, nombre: string) {
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: nombre })
}

const pestana = (page: Page, nombre: string) =>
  page.getByRole('navigation', { name: 'Secciones' }).getByRole('button', { name: nombre })

test('solo el Contralor ve la pantalla de Usuarios', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('API conectada')).toBeVisible()
  await elegirUsuario(page, 'Contralor')
  await expect(pestana(page, 'Usuarios')).toBeVisible()
  for (const otro of ['Analista', 'Responsable de área', 'Dirección', 'Auditoría']) {
    await elegirUsuario(page, otro)
    await expect(pestana(page, 'Cargas').or(pestana(page, 'Variance')).first()).toBeVisible()
    await expect(pestana(page, 'Usuarios')).toHaveCount(0)
  }
})

test('el Contralor crea un usuario y recibe la contraseña temporal una sola vez', async ({
  page,
}) => {
  await page.goto('/')
  await elegirUsuario(page, 'Contralor')
  await pestana(page, 'Usuarios').click()
  await expect(page.getByRole('heading', { name: 'Usuarios' })).toBeVisible()

  await page.getByRole('button', { name: 'Nuevo usuario' }).click()
  await page.getByLabel('Correo (es su usuario de entrada)').fill('persona.nueva@torres.local')
  await page.getByLabel('Nombre').fill('Persona Nueva')
  await page.getByLabel('Rol', { exact: true }).selectOption({ label: 'Analista de Contraloría' })
  await page.getByRole('button', { name: 'Crear usuario' }).click()

  await expect(page.getByText('Contraseña temporal de')).toBeVisible()
  await expect(page.getByRole('cell', { name: /Persona Nueva/ })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Editar Persona Nueva' })).toBeVisible()

  // Un correo repetido se rechaza con un mensaje claro
  await page.getByRole('button', { name: 'Nuevo usuario' }).click()
  await page.getByLabel('Correo (es su usuario de entrada)').fill('persona.nueva@torres.local')
  await page.getByLabel('Nombre').fill('Otra vez')
  await page.getByRole('button', { name: 'Crear usuario' }).click()
  await expect(page.getByRole('alert')).toContainText('ya tiene acceso')
})

test('el Responsable de departamento entra al Variance pero no puede exportarlo', async ({
  page,
}) => {
  await page.goto('/')
  await elegirUsuario(page, 'Responsable de área')
  await pestana(page, 'Variance').click()
  await expect(page.getByRole('heading', { name: 'Variance' }).first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Exportar a Excel' })).toHaveCount(0)
})
