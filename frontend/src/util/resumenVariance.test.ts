import assert from 'node:assert/strict'
import { test } from 'node:test'
import type { LineaVariance } from '../api/tipos.ts'
import { resumirVariance } from './resumenVariance.ts'

function linea(descripcion: string, tipo: string, variacion: string | null): LineaVariance {
  const cifras = { actual: '0.00', budget: '0.00', var: variacion, pct: null }
  return {
    linea_id: 1,
    descripcion,
    tipo,
    mes: cifras,
    ytd: cifras,
    anual: cifras,
  } as unknown as LineaVariance
}

test('cuenta favorables y desfavorables y localiza los extremos', () => {
  const r = resumirVariance([
    linea('A', 'detalle', '100.00'),
    linea('B', 'detalle', '-99.50'),
    linea('C', 'detalle', '-20.00'),
    linea('D', 'detalle', '250.25'),
    linea('E', 'detalle', '0.00'),
  ])
  assert.equal(r.conVariacion, 5)
  assert.equal(r.desfavorables, 2)
  assert.equal(r.favorables, 2)
  assert.deepEqual(r.mayorDesfavorable, { descripcion: 'B', variacion: '-99.50' })
  assert.deepEqual(r.mayorFavorable, { descripcion: 'D', variacion: '250.25' })
})

test('los totales, subtotales e informativas no entran (no se mezclan sentidos de signo)', () => {
  const r = resumirVariance([
    linea('Total', 'total', '-5000.00'),
    linea('Sub', 'subtotal', '300.00'),
    linea('Tipo de cambio', 'informativa', '-1.00'),
    linea('Real', 'detalle', '-10.00'),
  ])
  assert.equal(r.conVariacion, 1)
  assert.equal(r.mayorDesfavorable?.descripcion, 'Real')
  assert.equal(r.mayorFavorable, null)
})

test('sin Variación calculada no hay resumen ni extremos inventados', () => {
  const r = resumirVariance([linea('Sin budget', 'detalle', null)])
  assert.deepEqual(r, {
    conVariacion: 0,
    desfavorables: 0,
    favorables: 0,
    mayorDesfavorable: null,
    mayorFavorable: null,
  })
})

test('con empate gana la primera línea del reporte (orden estable)', () => {
  const r = resumirVariance([linea('Primera', 'detalle', '-50.00'), linea('Segunda', 'detalle', '-50.00')])
  assert.equal(r.mayorDesfavorable?.descripcion, 'Primera')
})

test('una cifra ilegible se ignora en lugar de adivinarla', () => {
  const r = resumirVariance([linea('Rara', 'detalle', 'abc'), linea('Ok', 'detalle', '-1.00')])
  assert.equal(r.conVariacion, 1)
})
