import { expect, test, type Page } from '@playwright/test'
import { abrirVariance, prepararReporteSintetico } from './datos'

// Comentarios por línea (Fase 5.3) sobre el reporte sintético.
test.describe.configure({ mode: 'serial' })

test.beforeAll(async ({ request }) => {
  await prepararReporteSintetico(request)
})

const filaDe = (page: Page, linea: string) =>
  page.getByRole('row').filter({ has: page.getByRole('rowheader', { name: new RegExp(linea) }) })

async function abrirPanel(page: Page, usuario: string) {
  await abrirVariance(page, usuario)
  await filaDe(page, 'Salaries').getByRole('button', { name: 'Ver detalle de la línea' }).click()
  const panel = page.getByRole('dialog', { name: 'Detalle de la línea' })
  await expect(panel.getByRole('region', { name: 'Comentarios' })).toBeVisible()
  return panel
}

test('el Analista comenta, el texto con HTML se ve como texto y la fila lo indica', async ({
  page,
}) => {
  const panel = await abrirPanel(page, 'Analista')
  await panel.getByLabel('Nuevo comentario').fill('Subió por bono <b>anual</b> y <script>x</script>')
  await panel.getByRole('button', { name: 'Comentar' }).click()

  const hilo = panel.getByRole('article', { name: /Comentario de/ })
  await expect(hilo).toBeVisible()
  await expect(hilo).toContainText('<b>anual</b> y <script>x</script>')
  await expect(panel.locator('b')).toHaveCount(0)

  // la tabla marca la línea con su conteo, sin añadir columnas
  await expect(
    filaDe(page, 'Salaries').getByRole('img', { name: '1 comentarios, 1 pendientes' }),
  ).toBeVisible()

  await hilo.getByLabel('Estatus').selectOption('explicado')
  await expect(hilo.getByText('Explicado').first()).toBeVisible()
  await expect(
    filaDe(page, 'Salaries').getByRole('img', { name: '1 comentarios, 0 pendientes' }),
  ).toBeVisible()
})

test('responder y adjuntar evidencia; el archivo falso se rechaza', async ({ page }) => {
  const panel = await abrirPanel(page, 'Analista')
  const hilo = panel.getByRole('article', { name: /Comentario de/ })
  await hilo.getByLabel('Responder').fill('Confirmado con Recursos Humanos')
  await hilo.getByRole('button', { name: 'Responder', exact: true }).click()
  await expect(hilo.getByText('Confirmado con Recursos Humanos')).toBeVisible()

  const png = Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), Buffer.alloc(32)])
  await hilo.locator('input[type=file]').setInputFiles({ name: 'nomina.png', mimeType: 'image/png', buffer: png })
  await expect(hilo.getByRole('button', { name: 'nomina.png' })).toBeVisible()

  await hilo
    .locator('input[type=file]')
    .setInputFiles({ name: 'falso.png', mimeType: 'image/png', buffer: Buffer.from('MZ no soy imagen') })
  await expect(panel.getByRole('alert')).toContainText('no corresponde')
})

test('Dirección ve los comentarios pero no puede escribir', async ({ page }) => {
  await abrirVariance(page, 'Dirección')
  await filaDe(page, 'Salaries').getByRole('button', { name: 'Ver detalle de la línea' }).click()
  const panel = page.getByRole('dialog', { name: 'Detalle de la línea' })
  await expect(panel.getByRole('article', { name: /Comentario de/ })).toBeVisible()
  await expect(panel.getByLabel('Nuevo comentario')).toHaveCount(0)
  await expect(panel.getByRole('button', { name: 'Comentar' })).toHaveCount(0)
})
