import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  aCuerpoApi,
  aplicarFactorATodos,
  celdasDesdeApi,
  hayCambios,
  importeDeCelda,
  seccionTieneTablaInterna,
  totalAnual,
  variacionContraBase,
  type CeldaEditable,
} from './detalleCuenta.ts'

const PERIODOS = [
  ...[7, 8, 9, 10, 11, 12].map((m) => `2026-${String(m).padStart(2, '0')}`),
  ...[1, 2, 3, 4, 5, 6].map((m) => `2027-${String(m).padStart(2, '0')}`),
]

const factor = (base: string, f: string): CeldaEditable => ({
  periodo: '2026-07',
  metodo: 'factor',
  base,
  factor: f,
  montoFijo: '',
})

test('base × factor, igual que el servidor (6 decimales)', () => {
  // 28634.109 × 1.17 = 33501.90753 -> en micros 33501907530
  assert.equal(importeDeCelda(factor('28634.109', '1.17')), 33_501_907_530n)
  assert.equal(importeDeCelda(factor('27270.58', '1.05')), 28_634_109_000n)
})

test('el redondeo de las mitades va al par, como Decimal.quantize', () => {
  // 0.000001 × 0.5 = 0.0000005 -> mitad exacta: 0 es par
  assert.equal(importeDeCelda(factor('0.000001', '0.5')), 0n)
  // 0.000003 × 0.5 = 0.0000015 -> mitad exacta: 2 es par
  assert.equal(importeDeCelda(factor('0.000003', '0.5')), 2n)
  // negativo: -0.000003 × 0.5 -> -2
  assert.equal(importeDeCelda(factor('-0.000003', '0.5')), -2n)
})

test('monto fijo y datos incompletos', () => {
  const fijo: CeldaEditable = { periodo: '2026-07', metodo: 'fijo', base: '', factor: '', montoFijo: '10000' }
  assert.equal(importeDeCelda(fijo), 10_000_000_000n)
  assert.equal(importeDeCelda({ ...fijo, montoFijo: '' }), null)
  assert.equal(importeDeCelda(factor('', '1.05')), null)
  assert.equal(importeDeCelda(factor('100', '')), null)
  assert.equal(importeDeCelda(factor('abc', '1.05')), null)
})

test('el total anual suma los doce meses y es null si falta alguno', () => {
  const celdas = celdasDesdeApi(PERIODOS, [], '1.05').map((c) => ({ ...c, base: '1000' }))
  assert.equal(totalAnual(celdas), 12_600_000_000n)
  celdas[3] = { ...celdas[3], base: '' }
  assert.equal(totalAnual(celdas), null)
})

test('celdasDesdeApi respeta lo guardado y rellena lo que falta', () => {
  const celdas = celdasDesdeApi(
    PERIODOS,
    [{ periodo: '2026-08', metodo: 'fijo', base: null, factor: null, monto_fijo: '10000', importe: '10000' }],
    '1.05',
  )
  assert.equal(celdas.length, 12)
  assert.deepEqual(celdas[1], { periodo: '2026-08', metodo: 'fijo', base: '', factor: '1.05', montoFijo: '10000' })
  assert.deepEqual(celdas[0], { periodo: '2026-07', metodo: 'factor', base: '', factor: '1.05', montoFijo: '' })
})

test('aplicar un factor a todos pasa los fijos a base × factor', () => {
  const celdas = celdasDesdeApi(PERIODOS, [], '1.05')
  celdas[0] = { ...celdas[0], metodo: 'fijo', montoFijo: '5' }
  const nuevas = aplicarFactorATodos(celdas, '1.17')
  assert.ok(nuevas.every((c) => c.metodo === 'factor' && c.factor === '1.17'))
})

test('el cuerpo del PUT lleva los doce meses o el motivo del error', () => {
  const celdas = celdasDesdeApi(PERIODOS, [], '1.05')
  assert.ok('error' in aCuerpoApi(celdas))
  const completas = celdas.map((c) => ({ ...c, base: '100.5' }))
  const cuerpo = aCuerpoApi(completas)
  assert.ok('celdas' in cuerpo)
  if ('celdas' in cuerpo) {
    assert.equal(cuerpo.celdas.length, 12)
    assert.deepEqual(cuerpo.celdas[0], { periodo: '2026-07', metodo: 'factor', base: '100.5', factor: '1.05' })
  }
})

test('hayCambios detecta cualquier diferencia', () => {
  const a = celdasDesdeApi(PERIODOS, [], '1.05')
  assert.equal(hayCambios(a, a.map((c) => ({ ...c }))), false)
  assert.equal(hayCambios(a.map((c, i) => (i === 5 ? { ...c, base: '1' } : c)), a), true)
})

test('variación contra la base', () => {
  assert.deepEqual(variacionContraBase(1_050_000_000n, '1000'), { diferencia: 50_000_000n, porcentaje: 5 })
  assert.deepEqual(variacionContraBase(10_000_000n, '0'), { diferencia: 10_000_000n, porcentaje: null })
  assert.equal(variacionContraBase(null, '1000'), null)
  assert.equal(variacionContraBase(1n, ''), null)
})

test('solo Other Income y Mgmt & Check In tienen tabla interna por ahora', () => {
  assert.equal(seccionTieneTablaInterna('Other Income'), true)
  assert.equal(seccionTieneTablaInterna('Mgmt & Check In'), true)
  assert.equal(seccionTieneTablaInterna('M g m t   &   C h e c k   I n'), true)
  assert.equal(seccionTieneTablaInterna('O t h e r   I n c o m e'), true)
  assert.equal(seccionTieneTablaInterna('Mgmt & Check'), false)
  assert.equal(seccionTieneTablaInterna(null), false)
})

test('los importes de la API (6 decimales) se muestran sin ceros sobrantes', () => {
  const celdas = celdasDesdeApi(
    PERIODOS,
    [{ periodo: '2026-07', metodo: 'factor', base: '1000.500000', factor: '1.050000', monto_fijo: null, importe: '1050.525' }],
    '1.05',
  )
  assert.deepEqual(celdas[0], { periodo: '2026-07', metodo: 'factor', base: '1000.5', factor: '1.05', montoFijo: '' })
})
