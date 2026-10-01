import { expect, test, type Page } from '@playwright/test'
import { pestana } from './datos'

// Respuestas simuladas de la API: no dependen de los datos que dejaron otras pruebas.

const carga = (id: number, periodo: string) => ({
  id,
  periodo,
  fuente: 'variance_base_datos',
  estado: 'vigente',
  nombre_archivo: 'x.xlsx',
  sha256: 'a'.repeat(64),
  n_movimientos: 1,
  total_debito: '1.00',
  total_credito: '0.00',
  fecha_min: `${periodo}-01`,
  fecha_max: `${periodo}-28`,
  creado_en: '2026-10-01T00:00:00Z',
  usuario_id: null,
  reemplazada_por_id: null,
})

const presupuesto = (periodo: string) => ({
  id: 1,
  tipo: 'budget',
  numero: 1,
  ano_fiscal: '2026/27',
  periodo_corte: periodo,
  estado: 'vigente',
  nombre_archivo: 'b.xlsx',
  sha256: 'b'.repeat(64),
  n_lineas: 3,
  version_estructura_id: 1,
  creada_en: '2026-10-01T00:00:00Z',
  usuario_id: null,
  reemplazada_en: null,
})

async function simularCargas(page: Page, periodos: string[], corteBudget: string | null) {
  await page.route('**/api/v1/hoteles/*/cargas', (r) =>
    r.fulfill({ json: periodos.map((p, i) => carga(i + 1, p)) }),
  )
  await page.route('**/api/v1/hoteles/*/budget/versiones', (r) =>
    r.fulfill({ json: corteBudget ? [presupuesto(corteBudget)] : [] }),
  )
}

test('sin mapeo aprobado se explica qué hacer, no un texto técnico', async ({ page }) => {
  await simularCargas(page, ['2026-09'], null)
  await page.route('**/api/v1/hoteles/*/variance?*', (r) =>
    r.fulfill({
      status: 404,
      json: { detail: 'No hay un mapeo aprobado; indica una versión o aprueba un borrador' },
    }),
  )
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Analista' })
  await pestana(page, 'Variance').click()
  const aviso = page.getByRole('alert').filter({ hasText: 'Todavía no hay un reporte armado' })
  await expect(aviso).toBeVisible()
  await expect(aviso).toContainText('mapeo de cuentas aprobado')
  await expect(aviso).toContainText('fpa.demo_agosto')
  await expect(page.getByText('indica una versión o aprueba un borrador')).toHaveCount(0)
})

test('otro error de la API sí se muestra tal cual', async ({ page }) => {
  await simularCargas(page, ['2026-08'], '2026-08')
  await page.route('**/api/v1/hoteles/*/variance?*', (r) =>
    r.fulfill({ status: 409, json: { detail: 'El Budget y el mapeo usan estructuras distintas' } }),
  )
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Analista' })
  await pestana(page, 'Variance').click()
  await expect(page.getByRole('alert')).toContainText('estructuras distintas')
  await expect(page.getByText('Todavía no hay un reporte armado')).toHaveCount(0)
})

test('abre en el mes del Budget vigente aunque haya un mes más reciente cargado', async ({
  page,
}) => {
  await simularCargas(page, ['2026-08', '2026-09'], '2026-08')
  const consultados: string[] = []
  await page.route('**/api/v1/hoteles/*/variance?*', (r) => {
    consultados.push(new URL(r.request().url()).searchParams.get('periodo') ?? '')
    return r.fulfill({ status: 404, json: { detail: 'No hay un mapeo aprobado' } })
  })
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Analista' })
  await pestana(page, 'Variance').click()
  await expect(page.getByLabel('Mes', { exact: true })).toHaveValue('2026-08')
  expect(consultados).not.toContain('2026-09') // nunca se pidió septiembre primero
  // y se puede elegir septiembre a mano
  await page.getByLabel('Mes', { exact: true }).selectOption('2026-09')
  await expect(page.getByLabel('Mes', { exact: true })).toHaveValue('2026-09')
})
