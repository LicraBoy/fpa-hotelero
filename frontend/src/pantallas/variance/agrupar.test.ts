import assert from 'node:assert/strict'
import { test } from 'node:test'
import type { LineaVariance, SeccionVariance } from '../../api/tipos.ts'
import { agruparPorSeccion, esLineaVacia, sinLineasVacias, trozosResaltados } from './agrupar.ts'

const cifras = { actual: '0.00', budget: null, var: null, pct: null }
function linea(id: number, seccion_id: number | null): LineaVariance {
  return {
    linea_id: id,
    orden: id,
    tipo: 'detalle',
    nivel: 1,
    seccion_id,
    codigo_corporativo: null,
    descripcion: `L${id}`,
    convencion: 'real_menos_presupuesto',
    capturada: false,
    mes: cifras,
    ytd: cifras,
    anual: cifras,
  }
}
const secciones: SeccionVariance[] = [
  { id: 100, descripcion: 'Ingresos', linea_total_id: 3 },
  { id: 200, descripcion: 'Gastos', linea_total_id: null },
]

test('agrupa por sección conservando el orden del reporte', () => {
  const g = agruparPorSeccion([linea(1, null), linea(2, 100), linea(3, 100), linea(4, 200)], secciones)
  assert.deepEqual(
    g.map((x) => [x.seccion?.descripcion ?? null, x.lineas.map((l) => l.linea_id)]),
    [
      [null, [1]],
      ['Ingresos', [2, 3]],
      ['Gastos', [4]],
    ],
  )
})

test('una sección desconocida cae en el grupo sin sección y la lista vacía da cero grupos', () => {
  assert.equal(agruparPorSeccion([], secciones).length, 0)
  const g = agruparPorSeccion([linea(1, 999), linea(2, null)], secciones)
  assert.equal(g.length, 1)
  assert.equal(g[0].seccion, null)
})

test('una sección que reaparece más adelante abre un grupo nuevo (no reordena)', () => {
  const g = agruparPorSeccion([linea(1, 100), linea(2, 200), linea(3, 100)], secciones)
  assert.deepEqual(
    g.map((x) => x.lineas.map((l) => l.linea_id)),
    [[1], [2], [3]],
  )
})


const con = (actual: string, budget: string | null) => ({ actual, budget, var: null, pct: null })

test('una línea sin Actual ni Presupuesto en ningún bloque está vacía; un total nunca', () => {
  const base = linea(1, 100)
  assert.equal(esLineaVacia({ ...base, mes: con('0.00', '0.00'), ytd: con('0', null), anual: con('0.00', null) }), true)
  assert.equal(esLineaVacia({ ...base, mes: con('0.00', '5.00'), ytd: con('0', null), anual: con('0', null) }), false)
  assert.equal(esLineaVacia({ ...base, mes: con('0.00', null), ytd: con('-0.01', null), anual: con('0', null) }), false)
  assert.equal(esLineaVacia({ ...base, tipo: 'total', mes: con('0', '0'), ytd: con('0', '0'), anual: con('0', '0') }), false)
})

test('al ocultar las vacías se avisa cuántas son y una sección sin líneas desaparece', () => {
  const vacia = (id: number, seccion: number) => ({
    ...linea(id, seccion),
    mes: con('0.00', '0.00'),
    ytd: con('0.00', '0.00'),
    anual: con('0.00', '0.00'),
  })
  const con_dato = { ...linea(2, 100), mes: con('10.00', null) }
  const grupos = agruparPorSeccion([vacia(1, 100), con_dato, vacia(3, 200)], secciones)
  const r = sinLineasVacias(grupos)
  assert.equal(r.ocultas, 2)
  assert.deepEqual(
    r.grupos.map((g) => g.lineas.map((l) => l.linea_id)),
    [[2]],
  )
})

test('la búsqueda resalta sin distinguir mayúsculas ni acentos y no arma HTML', () => {
  assert.deepEqual(trozosResaltados('Total Maid & Linen', 'maid'), [
    { texto: 'Total ', coincide: false },
    { texto: 'Maid', coincide: true },
    { texto: ' & Linen', coincide: false },
  ])
  assert.deepEqual(trozosResaltados('Compensación', 'COMPENSACION'), [
    { texto: 'Compensación', coincide: true },
  ])
  assert.deepEqual(trozosResaltados('<b>x</b>', 'b'), [
    { texto: '<', coincide: false },
    { texto: 'b', coincide: true },
    { texto: '>x</', coincide: false },
    { texto: 'b', coincide: true },
    { texto: '>', coincide: false },
  ])
  assert.deepEqual(trozosResaltados('Salaries', ''), [{ texto: 'Salaries', coincide: false }])
  assert.deepEqual(trozosResaltados('Salaries', 'zzz'), [{ texto: 'Salaries', coincide: false }])
})

test('las secciones con el mismo nombre se distinguen con su número en el índice', async () => {
  const { etiquetasDeSecciones } = await import('./agrupar.ts')
  assert.deepEqual(etiquetasDeSecciones(['Income', 'Store', 'Bar', 'Store', 'Expenses', 'Store']), [
    'Income',
    'Store (1)',
    'Bar',
    'Store (2)',
    'Expenses',
    'Store (3)',
  ])
  assert.deepEqual(etiquetasDeSecciones([]), [])
})
