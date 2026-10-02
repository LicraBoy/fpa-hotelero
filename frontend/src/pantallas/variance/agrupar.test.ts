import assert from 'node:assert/strict'
import { test } from 'node:test'
import type { LineaVariance, SeccionVariance } from '../../api/tipos.ts'
import { agruparPorSeccion } from './agrupar.ts'

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
