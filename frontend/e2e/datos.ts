import { expect, type APIRequestContext, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// Datos de prueba compartidos: el reporte SINTÉTICO de cifras conocidas (ver
// backend/scripts/crear_archivos_e2e.py), cargado por API. Es idempotente: se puede llamar desde
// varias pruebas aunque otra ya lo haya cargado.

const XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
const archivo = readFileSync(resolve('e2e/archivos/variance_reporte.xlsx'))

export const cabecera = (email: string) => ({ 'X-Usuario-Dev': email })

const adjunto = () => ({ name: 'variance_reporte.xlsx', mimeType: XLSX, buffer: archivo })

export async function prepararReporteSintetico(request: APIRequestContext): Promise<number> {
  const analista = cabecera('analista@torres.local')
  const contralor = cabecera('contralor@torres.local')
  const hoteles = await (await request.get('/api/v1/hoteles', { headers: analista })).json()
  const hotel: number = hoteles[0].id

  // Movimientos de julio y agosto (reemplaza los que dejó otra prueba)
  let r = await request.post(`/api/v1/hoteles/${hotel}/cargas`, {
    headers: analista,
    multipart: {
      archivo: adjunto(),
      fuente: 'variance_base_datos',
      confirmar_reemplazo: 'true',
    },
  })
  expect(r.status(), await r.text()).toBeLessThan(300)
  // Estructura, reglas de suma y borrador de mapeo
  r = await request.post(`/api/v1/hoteles/${hotel}/reporte/importar`, {
    headers: analista,
    multipart: { archivo: adjunto(), confirmar_reemplazo: 'true' },
  })
  expect(r.status(), await r.text()).toBe(201)
  const borrador = (await r.json()).mapeo_version_id as number
  // Solo el contralor aprueba
  r = await request.post(`/api/v1/hoteles/${hotel}/mapeo/versiones/${borrador}/aprobar`, {
    headers: contralor,
    data: { periodos: ['2026-07', '2026-08'] },
  })
  expect(r.status(), await r.text()).toBe(200)
  // Budget del Excel
  r = await request.post(`/api/v1/hoteles/${hotel}/budget/importar`, {
    headers: analista,
    multipart: { archivo: adjunto(), periodo_corte: '2026-08', confirmar_reemplazo: 'true' },
  })
  expect(r.status(), await r.text()).toBeLessThan(300)
  return hotel
}

export const pestana = (page: Page, nombre: string) =>
  page.getByRole('navigation', { name: 'Secciones' }).getByRole('button', { name: nombre })

export async function abrirVariance(page: Page, usuario = 'Analista') {
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: usuario })
  await pestana(page, 'Variance').click()
  await expect(page.getByRole('region', { name: 'Tabla de Variance' })).toBeVisible()
}
