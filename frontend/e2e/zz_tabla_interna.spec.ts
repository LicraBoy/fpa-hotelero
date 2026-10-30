import { expect, test, type APIRequestContext, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { cabecera, pestana, prepararReporteSintetico } from './datos'

// Budget por cuenta, parte 1: la tabla interna de cada cuenta de Other Income (base × factor o
// monto fijo, doce meses), con el reporte y el Excel SINTÉTICOS de backend/scripts/crear_archivos_e2e.py.
// OJO con el nombre (`zz_`): corre al final de la suite porque deja un ciclo de presupuesto abierto y
// la estructura del reporte con Other Income, y eso cambia lo que ven las demás pantallas.
test.describe.configure({ mode: 'serial' })

const XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
const contralor = cabecera('contralor@torres.local')

async function prepararCiclo(request: APIRequestContext) {
  const hotel = await prepararReporteSintetico(request)
  // Estructura con la sección Other Income (reemplaza a la del reporte sintético general)
  let r = await request.post(`/api/v1/hoteles/${hotel}/reporte/importar`, {
    headers: contralor,
    multipart: {
      archivo: {
        name: 'reporte_other_income.xlsx',
        mimeType: XLSX,
        buffer: readFileSync(resolve('e2e/archivos/reporte_other_income.xlsx')),
      },
      confirmar_reemplazo: 'true',
    },
  })
  expect(r.status(), await r.text()).toBe(201)
  // Calendario fiscal y ciclo en captura (si otra corrida ya los creó, se reutilizan)
  r = await request.post(`/api/v1/hoteles/${hotel}/presupuesto/anos-fiscales`, {
    headers: contralor,
    data: { etiqueta: '2026/27', mes_inicio: 7, mes_fin: 6 },
  })
  let ano: number
  if (r.status() === 201) {
    ano = (await r.json()).id
    r = await request.post(`/api/v1/hoteles/${hotel}/presupuesto/anos-fiscales/${ano}/periodos/generar`, {
      headers: contralor,
    })
    expect(r.status(), await r.text()).toBe(200)
  } else {
    const anos = await (await request.get(`/api/v1/hoteles/${hotel}/presupuesto/anos-fiscales`, { headers: contralor })).json()
    ano = anos[0].id
  }
  r = await request.post(`/api/v1/hoteles/${hotel}/presupuesto/ciclos`, {
    headers: contralor,
    data: { ano_fiscal_id: ano },
  })
  expect(r.status() === 201 || r.status() === 409, await r.text()).toBeTruthy()
}

test.beforeAll(async ({ request }) => {
  await prepararCiclo(request)
})

async function abrirCaptura(page: Page, usuario = 'Contralor') {
  await page.setViewportSize({ width: 1600, height: 900 })
  await page.goto('/')
  await page.getByLabel('Usuario (desarrollo)').selectOption({ label: usuario })
  await pestana(page, 'Budget').click()
  await page.getByRole('tab', { name: 'Captura' }).click()
  await expect(page.getByRole('heading', { name: 'Captura presupuestaria' })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Captura de Budget' })).toBeVisible()
}

// Los meses que vienen del Excel como monto fijo se pasan a Base × factor para poder capturar su base
async function aBaseFactor(page: Page, mes: string) {
  await expect(page.getByRole('region', { name: 'Meses de la cuenta' })).toBeVisible()
  await expect(page.getByRole('row', { name: new RegExp(mes) })).toBeVisible()
  const pasar = page.getByRole('row', { name: new RegExp(mes) }).getByRole('button', { name: 'Pasar a Base × factor' })
  if (await pasar.count()) await pasar.click()
}
const tabla = (page: Page) => page.getByRole('region', { name: 'Meses de la cuenta' })
const hoja = (page: Page) => page.getByRole('region', { name: 'Hoja de cuentas por mes' })
const rutaCuenta = (page: Page) => page.getByRole('navigation', { name: 'Ruta de la cuenta' })
// El resumen de la CUENTA abierta (la hoja tiene el suyo, arriba)
const resumenCuenta = (page: Page) => page.getByLabel('Resumen de la cuenta')
const herramientas = (page: Page) => page.getByRole('toolbar', { name: 'Herramientas de la tabla' })
const barraEstado = (page: Page) => page.locator('.ec-barra')

test('abrir el editor mensual de una cuenta, llenarla y guardar mensualiza la línea', async ({ page }) => {
  await abrirCaptura(page)
  await page.locator('.fila-linea-boton', { hasText: 'Rental Income' }).click()
  // Pantalla propia de la cuenta: la hoja de la sección no se ve mientras se edita
  await expect(page.getByRole('heading', { name: 'Rental Income', level: 2 })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Rental Income', level: 2 })).toBeVisible()
  await expect(hoja(page)).toHaveCount(0)
  await expect(page.getByText('Ejercicio fiscal 2026/27', { exact: true })).toBeVisible()
  await expect(tabla(page).getByRole('row')).toHaveCount(14) // encabezado + 12 meses + total
  // Una sola columna de Parámetro (factor o monto fijo según el método)
  await expect(tabla(page).getByRole('columnheader')).toHaveCount(6)
  await expect(tabla(page).getByRole('columnheader', { name: 'Parámetro' })).toHaveCount(1)

  // Sin datos todavía: no hay indicadores inventados ni barra de estado, y no se puede guardar
  await expect(resumenCuenta(page)).toHaveCount(0)
  await expect(barraEstado(page)).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Guardar tabla' })).toBeDisabled()
  await expect(herramientas(page).getByRole('button', { name: 'Descartar cambios' })).toBeDisabled()

  // La base de cada mes (Est-Act del año previo) con el factor 1.05 por omisión
  const meses = ['Jul 26', 'Ago 26', 'Sep 26', 'Oct 26', 'Nov 26', 'Dic 26', 'Ene 27', 'Feb 27', 'Mar 27', 'Abr 27', 'May 27', 'Jun 27']
  for (const mes of meses) await page.getByLabel(`Base de ${mes}`).fill('1000')
  await expect(tabla(page).getByRole('row').nth(1)).toContainText('1,050.00')
  await expect(resumenCuenta(page)).toContainText('12,600.00')
  await expect(resumenCuenta(page)).toContainText('12,000.00') // base anual
  await expect(resumenCuenta(page)).toContainText('+600.00') // variación contra la base, con signo
  await expect(resumenCuenta(page)).toContainText('1,050.00') // promedio mensual
  await expect(tabla(page).getByRole('row').last()).toContainText('12,600.00') // fila Total
  await expect(barraEstado(page)).toContainText('12 cambios pendientes')
  await expect(barraEstado(page)).toContainText('0 errores de validación')

  // Ya no existe la opción de monto fijo: no hay selector de método
  await expect(page.getByLabel('Método de Ago 26')).toHaveCount(0)
  await expect(tabla(page).getByRole('columnheader', { name: 'Método' })).toHaveCount(0)
  await page.getByLabel('Factor de Ago 26').fill('1.1')
  await expect(resumenCuenta(page)).toContainText('12,650.00') // 11 × 1,050 + 1,100

  // Un importe inválido se marca y no deja guardar
  await page.getByLabel('Base de Sep 26').fill('abc')
  await expect(page.getByLabel('Base de Sep 26')).toHaveAttribute('aria-invalid', 'true')
  await expect(page.getByRole('button', { name: 'Guardar tabla' })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Guardar cambios' })).toBeDisabled() // con errores, ninguna pareja guarda
  await expect(barraEstado(page)).toContainText('1 error de validación')
  await barraEstado(page).getByText('1 error de validación').click()
  await expect(barraEstado(page)).toContainText('Sep 26: La base no es un importe válido')
  await page.getByLabel('Base de Sep 26').fill('1000')

  await page.getByRole('button', { name: 'Guardar tabla' }).click()
  await expect(page.getByText('La línea quedó mensualizada en el ciclo')).toBeVisible()
  // Recargar trae lo guardado de la API (no lo que había en pantalla)
  await page.reload()
  await pestana(page, 'Budget').click()
  await page.getByRole('tab', { name: 'Captura' }).click()
  await page.locator('.fila-linea-boton', { hasText: 'Rental Income' }).click()
  await expect(page.getByLabel('Factor de Ago 26')).toHaveValue('1.10') // sin foco, con 2 decimales
  await expect(resumenCuenta(page)).toContainText('12,650.00')
})

test('navegar entre cuentas, aplicar un factor a todos los meses y volver a Captura', async ({ page }) => {
  await abrirCaptura(page)
  await page.locator('.fila-linea-boton', { hasText: 'Rental Income' }).click()
  await page.getByRole('button', { name: 'Siguiente ›' }).click()
  await expect(page.getByRole('heading', { name: 'Laundry Coins', level: 2 })).toBeVisible()
  await expect(page.getByText('2 de 3')).toBeVisible()
  await page.getByLabel('Ir a otra cuenta').selectOption({ label: 'Beauty Services' })
  await expect(page.getByRole('heading', { name: 'Beauty Services', level: 2 })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Siguiente ›' })).toBeDisabled()

  await page.getByLabel('Base de Jul 26').fill('100')
  await page.getByLabel('Factor para todos los meses').fill('1.17')
  await page.getByRole('button', { name: 'Aplicar a los 12 meses' }).click()
  await expect(page.getByLabel('Factor de Jul 26')).toHaveValue('1.17')
  await expect(tabla(page).getByRole('row').nth(1)).toContainText('117.00')

  await barraEstado(page).getByRole('button', { name: 'Descartar cambios' }).click()
  await expect(page.getByLabel('Base de Jul 26')).toHaveValue('')
  // Desde la cuenta se vuelve a la hoja; desde la hoja, a Captura
  await page.getByRole('button', { name: 'Volver a la Hoja de sección' }).click()
  await expect(rutaCuenta(page)).toHaveCount(0)
  await expect(hoja(page)).toBeVisible()
  await page.getByRole('navigation', { name: 'Ruta de la hoja' }).getByRole('button', { name: 'Volver a Captura' }).click()
  await expect(page.getByRole('region', { name: 'Captura de Budget' })).toBeVisible()
})

test('importar la hoja Other Income del Excel llena las tres cuentas y se ven al abrirlas', async ({ page }) => {
  await abrirCaptura(page)
  await page.getByRole('button', { name: 'Abrir la hoja de Other Income' }).click()
  await expect(page.getByLabel('Excel del Budget con la hoja Other Income')).toHaveCount(1) // un solo importador
  await page.getByLabel('Excel del Budget con la hoja Other Income').setInputFiles(resolve('e2e/archivos/budget_other_income.xlsx'))
  await expect(page.getByText('Se importaron 3 cuentas desde el Excel')).toBeVisible()
  await page.locator('.fila-linea-boton', { hasText: 'Laundry Coins' }).click()
  // Laundry Coins: 200 fijo cada mes = 2,400 al año
  await expect(resumenCuenta(page)).toContainText('2,400.00')
  // viene del Excel como monto fijo: se muestra de solo lectura, con salida a Base × factor
  await expect(page.getByRole('row', { name: /Jul 26/ })).toContainText('Monto fijo')
  await expect(page.getByLabel('Base de Jul 26')).toHaveCount(0)
  await page.getByLabel('Ir a otra cuenta').selectOption({ label: 'Beauty Services' })
  await expect(resumenCuenta(page)).toContainText('3,600.00')
})

test('un rol sin captura ve la tabla pero no puede editarla', async ({ page }) => {
  // El Analista no tiene `budget:capturar`: ve el detalle (lectura) sin inputs ni botón de guardar
  await abrirCaptura(page, 'Analista')
  await page.locator('.fila-linea-boton', { hasText: 'Rental Income' }).click()
  await expect(tabla(page)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Guardar tabla' })).toHaveCount(0)
  await expect(herramientas(page)).toHaveCount(0)
  await expect(barraEstado(page)).toHaveCount(0)
  await expect(page.getByLabel('Base de Jul 26')).toHaveCount(0)
})

test('la hoja completa de Other Income se abre desde la sección y trae el bloque inferior', async ({ page }) => {
  await abrirCaptura(page)
  await page.getByRole('button', { name: 'Abrir la hoja de Other Income' }).click()
  await expect(page.getByRole('navigation', { name: 'Ruta de la hoja' })).toContainText('Other Income')
  await expect(rutaCuenta(page)).toHaveCount(0) // por la sección no se abre ninguna cuenta
  const cuentas = page.getByRole('region', { name: 'Hoja de cuentas por mes' })
  await expect(cuentas.getByRole('row')).toHaveCount(5) // encabezado + 3 cuentas + Total Distribution

  // Importa del Excel: cuentas + inflación + Est Act + Budget previo
  await page.getByLabel('Excel del Budget con la hoja Other Income').setInputFiles(resolve('e2e/archivos/budget_other_income.xlsx'))
  await expect(page.getByText('Se importaron 3 cuentas')).toBeVisible()
  await expect(cuentas.getByRole('row').last()).toContainText('18,000.00') // 1,000 + 200 + 300 al mes, por 12
  const bloque = page.getByRole('region', { name: 'Inflación y comparativos' })
  await expect(bloque.getByRole('row', { name: /Est-Act año previo/ })).toContainText('24,000.00')
  await expect(bloque.getByRole('row', { name: /Budget año previo/ })).toContainText('18,000.00')
  await expect(bloque.getByRole('row', { name: /^Variación %/ })).toContainText('33.33%')
  await expect(bloque.getByRole('row', { name: /Total con inflación/ })).toContainText('1,515.00') // 1,500 × 1.01
})

test('la inflación se edita, se guarda y no cambia el Budget de las cuentas', async ({ page }) => {
  await abrirCaptura(page)
  await page.getByRole('button', { name: 'Abrir la hoja de Other Income' }).click()
  const bloque = page.getByRole('region', { name: 'Inflación y comparativos' })
  const total = page.getByRole('region', { name: 'Hoja de cuentas por mes' }).getByRole('row').last()
  const antes = (await total.textContent()) ?? ''
  await page.getByLabel('Inflación de Jul 26 (%)').fill('5')
  await expect(bloque.getByRole('row', { name: /Total con inflación/ })).toContainText('1,575.00') // 1,500 × 1.05
  await page.getByLabel('Inflación de Ago 26 (%)').fill('abc')
  await expect(page.getByRole('button', { name: 'Guardar inflación' })).toBeDisabled()
  await page.getByLabel('Inflación de Ago 26 (%)').fill('1')
  await page.getByRole('button', { name: 'Guardar inflación' }).click()
  await expect(page.getByText('Inflación guardada')).toBeVisible()
  await expect(page.getByLabel('Inflación de Jul 26 (%)')).toHaveValue('5')
  await expect(total).toHaveText(antes) // el Budget de las cuentas no se movió
})

test('desde la hoja se abre el editor mensual de una cuenta y se vuelve a la hoja', async ({ page }) => {
  await abrirCaptura(page)
  await page.getByRole('button', { name: 'Abrir la hoja de Other Income' }).click()
  await page.locator('.fila-linea-boton', { hasText: 'Laundry Coins' }).click()
  await expect(page.getByRole('heading', { name: 'Laundry Coins', level: 2 })).toBeVisible()
  await expect(page.getByRole('row', { name: /Jul 26/ })).toContainText('Monto fijo')
  await rutaCuenta(page).getByRole('button', { name: 'Volver a la Hoja de sección' }).click()
  await expect(rutaCuenta(page)).toHaveCount(0)
  await expect(page.getByRole('region', { name: 'Hoja de cuentas por mes' })).toBeVisible()
})

test('un rol sin captura ve la hoja pero no puede importar ni editar la inflación', async ({ page }) => {
  await abrirCaptura(page, 'Analista')
  await page.getByRole('button', { name: 'Abrir la hoja de Other Income' }).click()
  await expect(page.getByRole('region', { name: 'Inflación y comparativos' })).toBeVisible()
  await expect(page.getByLabel('Inflación de Jul 26 (%)')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Importar del Excel' })).toHaveCount(0)
})

test('el icono de una cuenta abre el Panel de línea y su nombre abre las tablas', async ({ page }) => {
  await abrirCaptura(page)
  // Al entrar a Captura el panel está cerrado
  await expect(page.getByRole('complementary', { name: /Panel de/ })).toHaveCount(0)
  await page.getByRole('button', { name: 'Ver el panel de línea de Rental Income' }).click()
  await expect(page.getByRole('complementary', { name: 'Panel de Rental Income' })).toBeVisible()
  await expect(hoja(page)).toHaveCount(0) // el icono no abre las tablas
  await page.locator('.fila-linea-boton', { hasText: 'Rental Income' }).click()
  await expect(page.getByRole('heading', { name: 'Rental Income', level: 2 })).toBeVisible()
})

test('el encabezado de la sección trae solo el icono de la hoja, sin texto', async ({ page }) => {
  await abrirCaptura(page)
  const boton = page.getByRole('button', { name: 'Abrir la hoja de Other Income' })
  await expect(boton).toBeVisible()
  await expect(boton).toHaveText('')
})

test('Captura se desplaza con la rueda del mouse pero sin barra de scroll visible', async ({ page }) => {
  await abrirCaptura(page)
  await page.getByRole('button', { name: 'Abrir la hoja de Other Income' }).click()
  await expect(hoja(page)).toBeVisible()
  // sin barra visible: el ancho de la ventana es igual al ancho útil de la página
  expect(await page.evaluate(() => window.innerWidth - document.documentElement.clientWidth)).toBe(0)
  // y se desplaza igual con la rueda
  await page.mouse.move(800, 500)
  await page.mouse.wheel(0, 600)
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(0)
})

test('Panel de línea de dinero: frase contra el objetivo, objetivo en línea y detalle por mes colapsable', async ({ page }) => {
  await abrirCaptura(page)
  await page.getByRole('button', { name: 'Ver el panel de línea de Rental Income' }).click()
  const cajon = page.getByRole('complementary', { name: 'Panel de Rental Income' })
  await expect(cajon.getByRole('heading', { name: /Propuesta anual/ })).toBeVisible()
  // sin objetivo: la frase invita a definirlo
  await expect(cajon.getByText('Define un objetivo para ver la diferencia.')).toBeVisible()
  // el objetivo se edita en línea: clic en el valor, Enter guarda
  await cajon.getByRole('button', { name: /^Objetivo de Rental Income/ }).click()
  const campo = cajon.getByRole('textbox', { name: 'Objetivo de Rental Income' })
  await campo.fill('10000')
  await campo.press('Enter')
  // hay objetivo pero esta línea aún no tiene propuesta: la frase lo dice
  await expect(cajon.getByText('Captura la propuesta para ver la diferencia.')).toBeVisible()
  await expect(cajon.getByRole('button', { name: /^Objetivo de Rental Income: \$ 10,000\.00/ })).toBeVisible()
  // el detalle por mes arranca abierto porque aquí el Actual se captura a mano; se puede colapsar
  await expect(cajon.getByRole('row', { name: /^Total/ })).toBeVisible()
  await cajon.getByText('Ver detalle por mes').click()
  await expect(cajon.getByRole('row', { name: /^Total/ })).toBeHidden()
  await cajon.getByText('Ver detalle por mes').click()
  await expect(cajon.getByRole('row', { name: /^Total/ })).toBeVisible()
  // esta línea aún no tiene cifras: en vez de una gráfica en blanco, un aviso claro
  await expect(cajon.getByText('Aún no hay cifras para graficar.')).toBeVisible()
})

test('el perfil de distribución muestra su vista previa dentro del cajón, sin salirse', async ({ page }) => {
  await abrirCaptura(page)
  // una propuesta anual escrita en la tabla (sin guardar) para poder repartirla
  await page.getByLabel('Budget de Rental Income, Jul 26').click()
  await page.getByRole('textbox', { name: 'Budget de Rental Income, Jul 26' }).fill('17088.65')
  await page.getByRole('button', { name: 'Ver el panel de línea de Rental Income' }).click()
  const cajon = page.getByRole('complementary', { name: 'Panel de Rental Income' })
  await cajon.getByRole('tab', { name: 'Perfil' }).click()
  await cajon.getByRole('button', { name: 'Rellenar con perfil…' }).click()
  await cajon.getByRole('combobox', { name: 'Perfil de distribución' }).selectOption({ label: 'Uniforme' })
  const previa = cajon.getByRole('list', { name: /Reparto previsto del perfil Uniforme/ })
  await expect(previa.getByRole('listitem')).toHaveCount(12)
  await expect(previa.getByRole('listitem').first()).toContainText('1,424.05')
  await expect(previa.getByRole('listitem').first()).toContainText('8.33 %')
  await expect(cajon.locator('.previa-total')).toContainText('Total del año')
  await expect(cajon.locator('.previa-total')).toContainText('17,088.65')
  // nada se sale del cajón (ni a lo ancho)
  expect(await cajon.evaluate((e) => e.scrollWidth <= e.clientWidth + 1)).toBe(true)
})

test('Hoja de sección: cambiar a Comparación anual y volver no pierde la inflación pendiente', async ({ page }) => {
  await abrirCaptura(page)
  await page.getByRole('button', { name: 'Abrir la hoja de Other Income' }).click()
  await page.getByLabel('Inflación de Jul 26 (%)').fill('3')
  await page.getByRole('tab', { name: 'Comparación anual' }).click()
  await expect(page.getByRole('heading', { name: 'Comparación anual e inflación' })).toBeVisible()
  await expect(page.getByLabel('Inflación de Jul 26 (%)')).toHaveValue('3')
  await expect(page.getByRole('button', { name: 'Guardar inflación' })).toHaveCount(1) // una sola pareja por vista
  // la vista no repite la tira de indicadores de la hoja
  await expect(page.getByRole('group', { name: 'Resumen de la hoja' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Volver a la Hoja de sección' }).click()
  await expect(page.getByRole('region', { name: 'Hoja de cuentas por mes' })).toBeVisible()
  await expect(page.getByLabel('Inflación de Jul 26 (%)')).toHaveValue('3')
  await expect(page.getByRole('button', { name: 'Guardar inflación' })).toHaveCount(1)
})

test('Hoja de sección: «Editar inflación» abre la comparación y enfoca la inflación mensual', async ({ page }) => {
  await abrirCaptura(page)
  await page.getByRole('button', { name: 'Abrir la hoja de Other Income' }).click()
  await page.getByRole('button', { name: 'Editar inflación' }).click()
  await expect(page.getByLabel('Inflación de Jul 26 (%)')).toBeFocused()
  await page.getByRole('button', { name: 'Volver a la Hoja de sección' }).click()
  await expect(page.getByRole('region', { name: 'Hoja de cuentas por mes' })).toBeVisible()
})

test('Hoja de sección: el buscador y el filtro no alteran los totales ni los indicadores', async ({ page }) => {
  await abrirCaptura(page)
  await page.getByRole('button', { name: 'Abrir la hoja de Other Income' }).click()
  const cuentas = page.getByRole('region', { name: 'Hoja de cuentas por mes' })
  const indicadores = page.getByRole('group', { name: 'Resumen de la hoja' })
  const pieAntes = await cuentas.getByRole('row').last().textContent()
  const resumenAntes = await indicadores.textContent()
  await page.getByLabel('Buscar cuenta').fill('Laundry')
  await expect(cuentas.getByRole('row')).toHaveCount(3) // encabezado + 1 cuenta + pie
  await expect(page.getByText('Mostrando 1 de 3 cuentas')).toBeVisible()
  expect(await cuentas.getByRole('row').last().textContent()).toBe(pieAntes)
  expect(await indicadores.textContent()).toBe(resumenAntes)
  await page.getByRole('button', { name: 'Limpiar la búsqueda y el filtro' }).click()
  await expect(cuentas.getByRole('row')).toHaveCount(5)
})

test('Hoja de sección: «Presupuesto por cuenta» está deshabilitada y dice que no hay datos', async ({ page }) => {
  await abrirCaptura(page)
  await page.getByRole('button', { name: 'Abrir la hoja de Other Income' }).click()
  await expect(page.getByRole('tab', { name: 'Presupuesto por cuenta' })).toBeDisabled()
  await expect(page.getByText('No disponible: la hoja no trae Est-Act ni Budget previo por cuenta.')).toBeVisible()
})

test('Comparación anual: el gráfico solo dibuja las series completas y trae su alternativa en texto', async ({ page }) => {
  await abrirCaptura(page)
  await page.getByRole('button', { name: 'Abrir la hoja de Other Income' }).click()
  await page.getByRole('tab', { name: 'Comparación anual' }).click()
  const grafico = page.getByRole('img', { name: 'Comparativo anual' })
  await expect(grafico).toBeVisible()
  const dibujadas = await grafico.locator('g.graf-serie').count()
  expect(dibujadas).toBeGreaterThan(0)
  await expect(page.getByRole('list', { name: 'Series del gráfico' }).getByRole('listitem')).toHaveCount(dibujadas)
  await expect(page.getByRole('region', { name: 'Inflación y comparativos' })).toBeVisible()
  // el documento no se desborda en horizontal
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
})

test('el encabezado de Captura y el flujo del ciclo solo se ven en la pantalla principal de Captura', async ({ page }) => {
  await abrirCaptura(page)
  const marco = page.getByRole('heading', { name: 'Captura presupuestaria' })
  const flujo = page.getByRole('button', { name: 'Enviar a revisión' })
  await expect(marco).toBeVisible()
  await expect(flujo).toBeVisible()
  // Hoja de sección
  await page.getByRole('button', { name: 'Abrir la hoja de Other Income' }).click()
  await expect(page.getByRole('region', { name: 'Hoja de cuentas por mes' })).toBeVisible()
  await expect(marco).toHaveCount(0)
  await expect(flujo).toHaveCount(0)
  // Comparación anual
  await page.getByRole('tab', { name: 'Comparación anual' }).click()
  await expect(page.getByRole('heading', { name: 'Comparación anual e inflación' })).toBeVisible()
  await expect(marco).toHaveCount(0)
  await expect(flujo).toHaveCount(0)
  // Editor mensual
  await page.getByRole('button', { name: 'Volver a la Hoja de sección' }).click()
  await page.locator('.fila-linea-boton', { hasText: 'Rental Income' }).click()
  await expect(page.getByRole('region', { name: 'Meses de la cuenta' })).toBeVisible()
  await expect(marco).toHaveCount(0)
  await expect(flujo).toHaveCount(0)
  // De vuelta a Captura reaparecen
  await page.getByRole('button', { name: 'Volver a la Hoja de sección' }).click()
  await page.getByRole('navigation', { name: 'Ruta de la hoja' }).getByRole('button', { name: 'Volver a Captura' }).click()
  await expect(marco).toBeVisible()
  await expect(flujo).toBeVisible()
})

test('Editor mensual: enfocar y salir de un campo sin editarlo no genera cambios pendientes', async ({ page }) => {
  await abrirCaptura(page)
  await page.locator('.fila-linea-boton', { hasText: 'Rental Income' }).click()
  // Jul 26 en Base × factor y guardado, para tener campos de base y de factor sin tocar
  await aBaseFactor(page, 'Jul 26')
  await page.getByLabel('Base de Jul 26').fill('500')
  await page.getByRole('button', { name: 'Guardar cambios' }).click()
  await expect(page.getByText('La línea quedó mensualizada en el ciclo')).toBeVisible()
  await expect(barraEstado(page)).toHaveCount(0)
  const base = page.getByLabel('Base de Jul 26')
  await base.focus()
  await base.blur()
  const parametro = page.getByLabel('Factor de Jul 26')
  await parametro.focus()
  await parametro.blur()
  await expect(barraEstado(page)).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Guardar tabla' })).toBeDisabled()
  await expect(page.locator('.ec-fila-modificada')).toHaveCount(0)
})

test('Editor mensual: las dos parejas de botones comparten estado y la fila modificada se marca', async ({ page }) => {
  await abrirCaptura(page)
  await page.locator('.fila-linea-boton', { hasText: 'Rental Income' }).click()
  const guardarArriba = page.getByRole('button', { name: 'Guardar tabla' })
  const descartarArriba = herramientas(page).getByRole('button', { name: 'Descartar cambios' })
  await expect(guardarArriba).toBeDisabled()
  await expect(descartarArriba).toBeDisabled()
  // Jul 26 en «Base × factor»: en monto fijo la base no se guarda (contrato de la API)
  await aBaseFactor(page, 'Jul 26')
  await page.getByLabel('Base de Jul 26').fill('777')
  // al editar, ambas parejas se habilitan y la fila queda marcada
  await expect(guardarArriba).toBeEnabled()
  await expect(descartarArriba).toBeEnabled()
  await expect(page.getByRole('button', { name: 'Guardar cambios' })).toBeEnabled()
  await expect(barraEstado(page).getByRole('button', { name: 'Descartar cambios' })).toBeEnabled()
  await expect(page.locator('.ec-fila-modificada')).toHaveCount(1)
  await expect(page.getByRole('row', { name: /Jul 26.*modificado/ })).toBeVisible()
  // descartar desde la barra inferior desmarca la fila y deshabilita la pareja de arriba
  await barraEstado(page).getByRole('button', { name: 'Descartar cambios' }).click()
  await expect(page.locator('.ec-fila-modificada')).toHaveCount(0)
  await expect(barraEstado(page)).toHaveCount(0)
  await expect(guardarArriba).toBeDisabled()
  await expect(descartarArriba).toBeDisabled()
  // guardar desde la barra deshabilita ambas parejas al terminar
  await aBaseFactor(page, 'Jul 26')
  await page.getByLabel('Base de Jul 26').fill('778')
  await page.getByRole('button', { name: 'Guardar cambios' }).click()
  await expect(page.getByText('La línea quedó mensualizada en el ciclo')).toBeVisible()
  await expect(barraEstado(page)).toHaveCount(0)
  await expect(guardarArriba).toBeDisabled()
  await expect(descartarArriba).toBeDisabled()
})

test('Editor mensual: sin foco se ve con 2 decimales, con foco el valor completo, y se envía sin formato', async ({ page }) => {
  await abrirCaptura(page)
  await page.locator('.fila-linea-boton', { hasText: 'Rental Income' }).click()
  await aBaseFactor(page, 'Jul 26')
  const base = page.getByLabel('Base de Jul 26')
  await base.fill('1234.5')
  await expect(base).toHaveValue('1234.5') // con foco: tal como se escribió
  await page.getByLabel('Factor para todos los meses').focus() // sale del campo
  await expect(base).toHaveValue('1,234.50') // sin foco: 2 decimales y miles
  await base.focus()
  await expect(base).toHaveValue('1234.5')
  const peticion = page.waitForRequest((r) => r.method() === 'PUT' && r.url().includes('/detalle'))
  await page.getByRole('button', { name: 'Guardar tabla' }).click()
  const cuerpo = (await peticion).postData() ?? ''
  expect(cuerpo).toContain('1234.5')
  expect(cuerpo).not.toContain('1,234.50')
  await expect(page.getByText('La línea quedó mensualizada en el ciclo')).toBeVisible()
})

// ---------- Comparación anual e inflación v2 (panel de análisis) ----------
async function abrirComparacion(page: Page, ancho = 1536, alto = 1024) {
  await abrirCaptura(page)
  await page.getByRole('button', { name: 'Abrir la hoja de Other Income' }).click()
  await page.getByRole('region', { name: 'Hoja de cuentas por mes' }).waitFor()
  // Se lee el Budget anual de la hoja (Pantalla 1) antes de pasar a la comparación
  const budgetHoja = (await page.getByRole('group', { name: 'Resumen de la hoja' }).textContent()) ?? ''
  await page.getByRole('tab', { name: 'Comparación anual' }).click()
  await page.getByRole('img', { name: 'Comparativo anual' }).waitFor()
  await page.setViewportSize({ width: ancho, height: alto })
  return /\$ [\d,]+\.\d\d/.exec(budgetHoja)?.[0] ?? ''
}
const grafico = (page: Page) => page.locator('.graf-caja')
const anuncio = (page: Page) => page.locator('.graf-caja [aria-live="polite"]')

test('Comparación anual: el gráfico ocupa el ancho de su tarjeta y la tabla cabe sin scroll a 1536×1024', async ({ page }) => {
  await abrirComparacion(page)
  const m = await page.evaluate(() => {
    const caja = document.querySelector('.graf-caja') as HTMLElement
    const svg = document.querySelector('.grafico-comparativo') as SVGElement
    const tarjeta = document.querySelector('.hoja-grafico-tarjeta') as HTMLElement
    const tabla = document.querySelector('.tm-contenedor') as HTMLElement
    const guardar = [...document.querySelectorAll('button')].find((b) => b.textContent?.includes('Guardar inflación'))
    return {
      razon: svg.getBoundingClientRect().width / caja.getBoundingClientRect().width,
      tarjetaAlto: tarjeta.getBoundingClientRect().height,
      desbordeTabla: tabla.scrollWidth - tabla.clientWidth,
      guardarAbajo: guardar ? guardar.getBoundingClientRect().bottom : Infinity,
      alto: window.innerHeight,
    }
  })
  expect(m.razon).toBeGreaterThanOrEqual(0.95)
  expect(m.tarjetaAlto).toBeGreaterThanOrEqual(280)
  expect(m.desbordeTabla).toBeLessThanOrEqual(0)
  expect(m.guardarAbajo).toBeLessThanOrEqual(m.alto)
})

test('Comparación anual: el documento no tiene scroll horizontal a 1536, 1312 y 390 px', async ({ page }) => {
  await abrirComparacion(page)
  for (const [ancho, alto] of [
    [1536, 1024],
    [1312, 900],
    [390, 844],
  ]) {
    await page.setViewportSize({ width: ancho, height: alto })
    await page.waitForTimeout(300)
    const desborde = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    expect(desborde, `a ${ancho} px`).toBeLessThanOrEqual(0)
  }
})

test('Comparación anual: la leyenda oculta y muestra series', async ({ page }) => {
  await abrirComparacion(page)
  const budget = page.getByRole('button', { name: 'Budget', exact: true })
  await expect(budget).toHaveAttribute('aria-pressed', 'true')
  await expect(page.locator('g.graf-serie.graf-budget')).toHaveCount(1)
  await budget.click()
  await expect(budget).toHaveAttribute('aria-pressed', 'false')
  await expect(page.locator('g.graf-serie.graf-budget')).toHaveCount(0)
  await budget.click()
  await expect(page.locator('g.graf-serie.graf-budget')).toHaveCount(1)
})

test('Comparación anual: el tooltip funciona por teclado y el mes activo se sincroniza con la tabla', async ({ page }) => {
  await abrirComparacion(page)
  await grafico(page).focus()
  await page.keyboard.press('ArrowRight')
  await expect(page.locator('.graf-tooltip')).toBeVisible()
  await expect(anuncio(page)).toContainText('Jul 26')
  await expect(page.locator('tr.tm-fila-activa')).toHaveCount(1)
  await expect(page.locator('tr.tm-fila-activa')).toContainText('Jul 26')
  await page.keyboard.press('ArrowRight')
  await expect(anuncio(page)).toContainText('Ago 26')
  await expect(page.locator('tr.tm-fila-activa')).toContainText('Ago 26')
  await page.keyboard.press('Escape')
  await expect(page.locator('.graf-tooltip')).toHaveCount(0)
  await expect(page.locator('tr.tm-fila-activa')).toHaveCount(0)
  // y al revés: enfocar el mes de una fila lo activa en el gráfico
  await page.mouse.move(2, 2) // el cursor fuera de la tabla: al hacer scroll no activa otra fila por hover
  await page.getByRole('rowheader', { name: 'Mar 27' }).focus()
  await expect(page.locator('.graf-tooltip')).toBeVisible()
  await expect(page.locator('.graf-tooltip-titulo')).toContainText('Mar 27')
})

test('Comparación anual: Acumulado termina en el total anual de cada serie', async ({ page }) => {
  const budgetHoja = await abrirComparacion(page)
  expect(budgetHoja).not.toBe('')
  await page.getByRole('button', { name: 'Acumulado' }).click()
  await grafico(page).focus()
  await page.keyboard.press('End')
  await expect(anuncio(page)).toContainText('Jun 27')
  await expect(anuncio(page)).toContainText(`Budget: ${budgetHoja}`)
  // Est-Act y Budget previo: contra el total de su fila en la tabla (si la serie está completa)
  // (celdas de la fila Total: —, acumulada, total con inflación, Est-Act, Budget previo, variación, %)
  for (const [nombre, columna] of [
    ['Est-Act año previo', 3],
    ['Budget año previo', 4],
  ] as const) {
    if ((await page.getByRole('button', { name: nombre, exact: true }).count()) === 0) continue
    const total = (await page.locator('tr.tm-total td').nth(columna).textContent()) ?? ''
    await expect(anuncio(page)).toContainText(`${nombre}: $ ${total.trim()}`)
  }
})

test('Comparación anual: un mes sin dato de variación no lleva barra', async ({ page }) => {
  await abrirComparacion(page)
  const celdas = await page.locator('tbody tr.tm-fila td:nth-child(7)').allTextContents()
  const conDato = celdas.filter((t) => t.trim() !== '—').length
  expect(celdas.length).toBe(12)
  await expect(page.locator('.grafico-banda .var-barra')).toHaveCount(conDato)
})

test('Tabla por mes: 12 filas con su total, variación con signo y flecha, y barras solo donde hay dato', async ({ page }) => {
  await abrirComparacion(page)
  const filas = page.locator('tbody tr.tm-fila')
  await expect(filas).toHaveCount(12)
  await expect(page.locator('tr.tm-total')).toContainText('Total')
  // cada celda de variación con dato lleva signo en el texto y una clase de calor; las vacías, «—» y sin barra
  const celdas = page.locator('tbody tr.tm-fila td:nth-child(7)')
  const textos = await celdas.allTextContents()
  const clases = await celdas.evaluateAll((els) => els.map((e) => e.className))
  textos.forEach((t, i) => {
    if (t.trim() === '—') expect(clases[i]).not.toMatch(/tm-calor-(pos|neg)/)
    else expect(clases[i]).toMatch(/tm-calor-(pos|neg|cero)-\d/)
    if (/[1-9]/.test(t.replace(/[,.]/g, '')) && t.trim() !== '—') expect(t).toMatch(/^[\s▲▼]*[+−-]/)
  })
  // mini-barras: una por celda de cifras con dato (3 columnas)
  const conDatoEst = (await page.locator('tbody tr.tm-fila td:nth-child(5)').allTextContents()).filter((t) => t.trim() !== '—').length
  await expect(page.locator('tbody tr.tm-fila td:nth-child(5) svg.tm-barra')).toHaveCount(conDatoEst)
  // los 3 grupos de color existen y el documento no se desborda
  await expect(page.locator('.tm-grupo')).toHaveCount(4)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
})

test('Editor mensual: un mes importado como monto fijo se ve de solo lectura y se puede pasar a Base × factor', async ({ page }) => {
  await abrirCaptura(page)
  await page.locator('.fila-linea-boton', { hasText: 'Laundry Coins' }).click()
  await expect(tabla(page)).toBeVisible() // el editor reemplaza al grid: sin esperarlo, «Mar 27» también está en el grid
  const fila = page.getByRole('row', { name: /Mar 27/ })
  await expect(fila).toContainText('Monto fijo')
  await expect(page.getByLabel('Base de Mar 27')).toHaveCount(0)
  await expect(page.getByLabel('Factor de Mar 27')).toHaveCount(0)
  await fila.getByRole('button', { name: 'Pasar a Base × factor' }).click()
  // ahora sí se captura su base, y falta el dato hasta que se escriba
  await expect(page.getByLabel('Base de Mar 27')).toBeEnabled()
  await expect(page.locator('.ec-fila-modificada')).toHaveCount(1)
  await expect(page.getByRole('button', { name: 'Guardar cambios' })).toBeDisabled()
  await page.getByLabel('Base de Mar 27').fill('180')
  await expect(page.getByRole('button', { name: 'Guardar cambios' })).toBeEnabled()
  // descartar devuelve el mes a como venía
  await barraEstado(page).getByRole('button', { name: 'Descartar cambios' }).click()
  await expect(page.locator('.ec-fila-modificada')).toHaveCount(0)
  await expect(fila).toContainText('Monto fijo')
})

// ---------- Mgmt & Check In: cuentas por partidas (Hoja de cuenta y Editor de partida) ----------
async function abrirMgmt(page: Page, usuario = 'Contralor') {
  await abrirCaptura(page, usuario)
  await page.getByRole('button', { name: 'Abrir la hoja de Mgmt & Check In' }).click()
  await expect(hoja(page)).toBeVisible()
}
const resumenHoja = (page: Page) => page.getByRole('group', { name: 'Resumen de la hoja' })
const resumenPartida = (page: Page) => page.getByRole('group', { name: 'Resumen de la partida' })
const abrirFila = (page: Page, texto: string) => page.locator('.fila-linea-boton', { hasText: texto }).click()

test('Mgmt & Check In: el Excel trae las cuentas por partidas y la Hoja de cuenta suma el Budget con inflación', async ({ page }) => {
  await abrirMgmt(page)
  await page.getByLabel('Excel del Budget con la hoja Mgmt & Check In').setInputFiles(resolve('e2e/archivos/budget_mgmt.xlsx'))
  await expect(page.getByText(/Se importaron 3 cuentas desde el Excel/)).toBeVisible()
  await abrirFila(page, 'Other Fringe')
  await expect(page.getByLabel('Hoja de la cuenta')).toBeVisible()
  await expect(resumenHoja(page)).toContainText('13,860.00') // (12,000 + 12 × 100) × 1.05
  await expect(resumenHoja(page)).toContainText('14,400.00') // Est-Act del año previo
  await expect(hoja(page)).toContainText('PARTY ROOM')
  await expect(hoja(page)).toContainText('Total Distribution')
  // la tabla trae las columnas de «Account Detail» del Excel, no solo los meses
  for (const col of ['Cant.', 'Unidad', 'Costo', 'Costo extendido']) {
    await expect(hoja(page).getByRole('columnheader', { name: col, exact: true })).toBeVisible()
  }
  await expect(hoja(page).getByRole('columnheader', { name: 'Distribución' })).toHaveCount(0)
  const fila = hoja(page).getByRole('row', { name: /PARTY ROOM/ })
  await expect(fila).toContainText('12,000.00')
  await expect(hoja(page).getByRole('row', { name: /Total Distribution/ })).toContainText('13,200.00') // Total Expense
  await expect(page.getByText(/sí entra al Budget/).first()).toBeVisible()
  // en modo cuenta ya no están las sub-pestañas de la hoja de sección
  await expect(page.getByRole('tab', { name: 'Presupuesto por cuenta' })).toHaveCount(0)
  // un solo botón de regreso, a la Hoja de sección
  await page.getByRole('button', { name: 'Volver a la Hoja de sección' }).click()
  await expect(hoja(page)).toContainText('Telephone')
})

test('Mgmt & Check In: editar una partida cuadra la distribución y recalcula el Budget', async ({ page }) => {
  await abrirMgmt(page)
  await abrirFila(page, 'Other Fringe')
  await abrirFila(page, 'PARTY ROOM')
  await expect(page.getByLabel('Editor de la partida PARTY ROOM')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Guardar partida' })).toBeDisabled()
  await page.getByLabel('Costo unitario').fill('13000')
  await expect(resumenPartida(page)).toContainText('1,000.00')
  await page.getByRole('button', { name: 'Estacional' }).click()
  await page.getByLabel('Importe de Dic 26').fill('13000')
  await page.getByRole('button', { name: 'Guardar partida' }).click()
  await expect(page.getByText(/Partida guardada/)).toBeVisible()
  await expect(resumenHoja(page)).toContainText('14,910.00') // (13,000 + 12 × 100) × 1.05
})

test('Mgmt & Check In: una cuenta sin hoja de detalle se pasa a partidas y se puede devolver', async ({ page }) => {
  await abrirMgmt(page)
  await abrirFila(page, 'Insurance')
  await page.getByRole('button', { name: 'Detallar por partidas' }).click()
  await expect(page.getByLabel('Hoja de la cuenta')).toBeVisible()
  await expect(resumenHoja(page)).toContainText('6,000.00') // no se pierde nada
  page.once('dialog', (d) => void d.accept())
  await page.getByRole('button', { name: 'Quitar partidas' }).click()
  await expect(tabla(page)).toBeVisible()
})

test('Mgmt & Check In: sin permiso de captura la Hoja de cuenta y la partida son de solo lectura', async ({ page }) => {
  await abrirMgmt(page, 'Analista')
  await abrirFila(page, 'Other Fringe')
  await expect(page.getByLabel('Hoja de la cuenta')).toBeVisible()
  await expect(page.getByRole('button', { name: '+ Agregar partida' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Quitar partidas' })).toHaveCount(0)
  await abrirFila(page, 'PARTY ROOM')
  await expect(page.getByLabel('Costo unitario')).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Guardar partida' })).toHaveCount(0)
})

test('Mgmt & Check In: «Importar partidas del Excel» trae solo las partidas de esa cuenta', async ({ page }) => {
  await abrirMgmt(page)
  // Insurance no tiene hoja de detalle en el Excel: avisa y no cambia nada
  await abrirFila(page, 'Insurance')
  await page.getByRole('button', { name: 'Detallar por partidas' }).click()
  await expect(page.getByLabel('Hoja de la cuenta')).toBeVisible()
  await page.getByLabel('Excel del Budget con las partidas de Insurance').setInputFiles(resolve('e2e/archivos/budget_mgmt.xlsx'))
  await expect(page.getByText(/no tiene partidas en el Excel/).first()).toBeVisible()
  await expect(resumenHoja(page)).toContainText('6,000.00')
  await page.getByRole('button', { name: 'Volver a la Hoja de sección' }).click()
  // Other Fringe se había editado a mano (14,910.00): el Excel devuelve sus partidas (13,860.00)
  await abrirFila(page, 'Other Fringe')
  await expect(resumenHoja(page)).toContainText('14,910.00')
  // el botón pide confirmación antes de reemplazar las partidas actuales
  let pregunta = ''
  page.once('dialog', (d) => {
    pregunta = d.message()
    void d.dismiss()
  })
  await page.getByRole('button', { name: 'Importar partidas del Excel' }).click()
  expect(pregunta).toContain('Se reemplazarán las 2 partidas actuales de Other Fringe')
  await page.getByLabel('Excel del Budget con las partidas de Other Fringe').setInputFiles(resolve('e2e/archivos/budget_mgmt.xlsx'))
  await expect(page.getByText(/Se importaron las partidas de Other Fringe/)).toBeVisible()
  await expect(resumenHoja(page)).toContainText('13,860.00')
})
