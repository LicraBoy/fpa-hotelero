import { expect, test, type Page } from '@playwright/test'
import { pestana, prepararReporteSintetico } from './datos'

// Vista «Por departamento» (respuesta simulada de la API: el reporte sintético no trae departamentos).
test.describe.configure({ mode: 'serial' })

test.beforeAll(async ({ request }) => {
  await prepararReporteSintetico(request)
})

const imp = (mes: string, ytd = mes) => ({ mes, ytd })

const respuesta = {
  periodo: '2026-08',
  version_mapeo_id: 1,
  periodos_ytd: ['2026-07', '2026-08'],
  periodos_sin_datos: [],
  tipos: ['ingreso', 'nomina', 'operacion', 'costo', 'otros', 'sin_tipo'],
  cuentas_vinculadas: 4,
  cuentas_sin_departamento: 1,
  cuentas_sin_tipo: 1,
  detalle_de_cuentas: true,
  departamentos: [
    {
      departamento: 'HOUSEKEEPING',
      por_tipo: { nomina: imp('300.00', '600.00'), operacion: imp('50.00', '90.00') },
      ingreso: imp('0.00'),
      gasto: imp('350.00', '690.00'),
      resultado: imp('-350.00', '-690.00'),
      n_cuentas: 2,
      cuentas: [
        { codigo: '6001001', descripcion: 'SUELDOS', tipo: 'nomina', mes: '300.00', ytd: '600.00', n_lineas: 1 },
        { codigo: '6001002', descripcion: 'INSUMOS', tipo: 'operacion', mes: '50.00', ytd: '90.00', n_lineas: 2 },
      ],
    },
    {
      departamento: null,
      por_tipo: { sin_tipo: imp('1000.00', '2000.00') },
      ingreso: imp('0.00'),
      gasto: imp('0.00'),
      resultado: imp('0.00'),
      n_cuentas: 1,
      cuentas: [{ codigo: '4001001', descripcion: 'HABITACIONES', tipo: 'sin_tipo', mes: '1000.00', ytd: '2000.00', n_lineas: 1 }],
    },
  ],
  total: {
    departamento: null,
    por_tipo: { nomina: imp('300.00', '600.00'), operacion: imp('50.00', '90.00'), sin_tipo: imp('1000.00', '2000.00') },
    ingreso: imp('0.00'),
    gasto: imp('350.00', '690.00'),
    resultado: imp('-350.00', '-690.00'),
    n_cuentas: 3,
    cuentas: [],
  },
}

async function abrir(page: Page, usuario: string) {
  await page.route('**/variance/departamentos?*', (r) => r.fulfill({ json: respuesta }))
  await page.goto('/#/departamentos')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: usuario })
  await expect(page.getByRole('heading', { name: 'Por departamento' })).toBeVisible()
}

test('muestra los departamentos, el aviso de lo que falta y cambia entre mes y acumulado', async ({ page }) => {
  await abrir(page, 'Analista')
  const tabla = page.getByRole('table', { name: /Importes por departamento/ })
  await expect(tabla.getByRole('button', { name: /HOUSEKEEPING/ })).toBeVisible()
  await expect(tabla.getByRole('button', { name: /Sin departamento/ })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Resumen por departamento' })).toContainText('Cuentas sin departamento')
  await expect(tabla).toContainText('350.00')
  await page.getByRole('button', { name: 'Acumulado' }).click()
  await expect(tabla).toContainText('690.00')
  await expect(page.getByText(/no se calculan por departamento/)).toBeVisible()
})

test('un departamento se despliega con sus cuentas y enlaza al detalle si el rol puede', async ({ page }) => {
  await abrir(page, 'Analista')
  await page.getByRole('button', { name: /HOUSEKEEPING/ }).click()
  await expect(page.getByRole('link', { name: '6001001' })).toBeVisible()
  await expect(page.getByText('SUELDOS')).toBeVisible()
})

test('el Responsable de departamento no ve la entrada en el menú', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: 'Responsable de área' })
  await expect(page.getByRole('navigation', { name: 'Secciones' })).toBeVisible()
  await expect(pestana(page, 'Por departamento')).toHaveCount(0)
})
