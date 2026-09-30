import { expect, test, type Page } from '@playwright/test'
import { resolve } from 'node:path'

// Recorrido completo de la Fase 1 en un navegador real contra un backend limpio.
// Los pasos comparten la misma base de datos, por eso van en orden.
test.describe.configure({ mode: 'serial' })

const archivo = (nombre: string) => resolve('e2e/archivos', nombre)

async function elegirUsuario(page: Page, nombre: string) {
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: nombre })
}

async function subir(page: Page, nombre: string, fuente: 'con130' | 'variance_base_datos') {
  const formulario = page.getByRole('region', { name: 'Subir archivo' })
  await formulario.getByLabel('Tipo de archivo').selectOption(fuente)
  await formulario.getByLabel('Archivo (.xlsx)').setInputFiles(archivo(nombre))
  await formulario.getByRole('button', { name: 'Subir y validar' }).click()
}

const pestana = (page: Page, nombre: string) =>
  page.getByRole('navigation', { name: 'Secciones' }).getByRole('button', { name: nombre })

test('la app abre, se conecta a la API y el contralor ve todas las secciones', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Plataforma FP&A Hotelera', level: 1 })).toBeVisible()
  await expect(page.getByText('API conectada')).toBeVisible()
  for (const nombre of ['Cargas', 'Catálogo', 'Saldos', 'Auditoría']) {
    await expect(pestana(page, nombre)).toBeVisible()
  }
  await expect(page.getByText('Todavía no hay cargas en este hotel.')).toBeVisible()
})

test('archivos que no son un Excel se rechazan con un mensaje claro', async ({ page }) => {
  await page.goto('/')
  await elegirUsuario(page, 'Analista')
  await subir(page, 'falso.xlsx', 'variance_base_datos')
  await expect(page.getByRole('alert')).toContainText('no es un libro de Excel')
  await subir(page, 'zip_no_excel.xlsx', 'variance_base_datos')
  await expect(page.getByRole('alert')).toContainText('no es un libro de Excel')
  await expect(page.getByText('Todavía no hay cargas en este hotel.')).toBeVisible()
})

test('subir un Variance crea la carga y muestra su reporte de calidad', async ({ page }) => {
  await page.goto('/')
  await elegirUsuario(page, 'Analista')
  await subir(page, 'variance_agosto.xlsx', 'variance_base_datos')
  const resultado = page.getByRole('status').filter({ hasText: 'Carga creada' })
  await expect(resultado).toBeVisible()
  await expect(resultado).toContainText('2 movimientos')
  await expect(resultado).toContainText('Aprobado')
  const cargas = page.getByRole('region', { name: 'Cargas' })
  await expect(cargas.getByRole('row', { name: /2026-08.*vigente/ })).toBeVisible()
})

test('subir el mismo archivo otra vez no cambia nada', async ({ page }) => {
  await page.goto('/')
  await elegirUsuario(page, 'Analista')
  await subir(page, 'variance_agosto.xlsx', 'variance_base_datos')
  await expect(page.getByRole('status')).toContainText('ya estaba cargado')
  const cargas = page.getByRole('region', { name: 'Cargas' })
  await expect(cargas.getByRole('row')).toHaveCount(2) // encabezado + 1 carga
})

test('otro archivo del mismo mes pide confirmación y al confirmar reemplaza', async ({ page }) => {
  await page.goto('/')
  await elegirUsuario(page, 'Analista')
  await subir(page, 'variance_agosto_corregido.xlsx', 'variance_base_datos')
  await expect(page.getByRole('status')).toContainText('Ya hay datos cargados para estos meses')
  await expect(page.getByRole('button', { name: 'Confirmar reemplazo' })).toBeVisible()
  const conflicto = page.getByRole('row', { name: /2026-08/ }).first()
  await expect(conflicto).toContainText('100.50') // crédito vigente
  await expect(conflicto).toContainText('120.00') // crédito nuevo
  // sin confirmar no se cambió nada
  const cargas = page.getByRole('region', { name: 'Cargas' })
  await expect(cargas.getByRole('row')).toHaveCount(2)

  await page.getByRole('button', { name: 'Confirmar reemplazo' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Carga reemplazada' })).toBeVisible()
  await expect(cargas.getByRole('row', { name: /reemplazada/ })).toBeVisible()
  await expect(cargas.getByRole('row', { name: /variance_agosto_corregido.*/ })).toContainText('vigente')
})

test('se puede ver la calidad de una carga', async ({ page }) => {
  await page.goto('/')
  await elegirUsuario(page, 'Analista')
  const cargas = page.getByRole('region', { name: 'Cargas' })
  await cargas.getByRole('row', { name: /vigente/ }).getByRole('button', { name: 'Ver calidad' }).click()
  await expect(cargas).toContainText('Calidad de datos')
  await expect(cargas).toContainText('Aprobado')
})

test('el catálogo muestra las cuentas y se puede buscar', async ({ page }) => {
  await page.goto('/')
  await elegirUsuario(page, 'Analista')
  await pestana(page, 'Catálogo').click()
  await expect(page.getByText('4001002.001')).toBeVisible()
  await expect(page.getByText('6009001.001')).toBeVisible()
  await page.getByLabel('Buscar cuenta').fill('SUELDOS')
  await expect(page.getByText('6009001.001')).toBeVisible()
  await expect(page.getByText('4001002.001')).toHaveCount(0)
})

test('los saldos del mes suman exacto, con el reemplazo aplicado', async ({ page }) => {
  await page.goto('/')
  await elegirUsuario(page, 'Analista')
  await pestana(page, 'Saldos').click()
  await expect(page.getByLabel('Mes')).toHaveValue('2026-08')
  const tabla = page.getByRole('table')
  await expect(tabla.getByRole('row', { name: /4001002\.001/ })).toContainText('120.00') // corregido
  await expect(tabla.getByRole('row', { name: /6009001\.001/ })).toContainText('40.25')
  const total = tabla.getByRole('row', { name: /^Total/ })
  await expect(total).toContainText('40.25') // débito
  await expect(total).toContainText('120.00') // crédito
  await expect(total).toContainText('-79.75') // resultado = débito − crédito
})

test('la bitácora registra lo ocurrido y solo la ve contralor o auditoría', async ({ page }) => {
  await page.goto('/')
  await pestana(page, 'Auditoría').click() // usuario predeterminado: contralor
  const bitacora = page.getByRole('region', { name: 'Bitácora de auditoría' })
  for (const accion of [
    'carga.archivo_rechazado',
    'carga.creada',
    'carga.duplicada',
    'carga.reemplazada',
  ]) {
    await expect(bitacora.getByText(accion).first()).toBeVisible()
  }
  await elegirUsuario(page, 'Analista')
  await expect(pestana(page, 'Auditoría')).toHaveCount(0)
})

test('cada rol ve solo lo que le corresponde', async ({ page }) => {
  await page.goto('/')

  await elegirUsuario(page, 'Responsable de área')
  await expect(pestana(page, 'Catálogo')).toBeVisible()
  for (const nombre of ['Cargas', 'Saldos', 'Auditoría']) {
    await expect(pestana(page, nombre)).toHaveCount(0)
  }

  await elegirUsuario(page, 'Dirección')
  await expect(pestana(page, 'Cargas')).toBeVisible()
  await expect(pestana(page, 'Saldos')).toBeVisible()
  await expect(page.getByRole('region', { name: 'Subir archivo' })).toHaveCount(0) // no puede cargar
})
