import assert from 'node:assert/strict'
import { test } from 'node:test'
import { conSigno, costoTexto, cuerpoConsumo, diferencia, mesCambio, sumaDe, titulosBloques, totalDeMes } from './consumo.ts'

const M = 1_000_000n
const PERIODOS = ['2026-07', '2026-08']

test('los títulos de los bloques salen del año fiscal', () => {
  assert.deepEqual(titulosBloques(PERIODOS), {
    real_prev: 'Real 24/25',
    budget_prev: 'Budget 25/26',
    est_act: 'Est-Act 25-26',
    budget: 'Budget 26/27',
  })
})

test('el total del mes es unidades × costo en micros, sin decimales flotantes', () => {
  assert.equal(totalDeMes('7500', '24.9833'), 187374_750000n)
  assert.equal(totalDeMes('200', '15.5'), 3100n * M)
  assert.equal(totalDeMes('', '15'), null)
  assert.equal(totalDeMes('abc', '15'), null)
})

test('sumas y variaciones respetan los datos que faltan', () => {
  assert.equal(sumaDe([1n * M, null, 2n * M]), 3n * M)
  assert.equal(sumaDe([null, null]), null)
  assert.equal(diferencia(5n * M, 2n * M), 3n * M)
  assert.equal(diferencia(null, 2n * M), null)
  assert.equal(conSigno(1_500_000n), '+1.50')
  assert.equal(conSigno(-1_500_000n), '-1.50')
  assert.equal(conSigno(null), '—')
})

test('el costo unitario se muestra con 4 decimales', () => {
  assert.equal(costoTexto(24_983_300n), '24.9833')
  assert.equal(costoTexto(10n * M), '10.0000')
  assert.equal(costoTexto(null), '—')
})

test('un mes cambia si cambia su valor, no su escritura', () => {
  assert.equal(mesCambio({ unidades: '100', costo: '10' }, { unidades: '100.0', costo: '10.00' }), false)
  assert.equal(mesCambio({ unidades: '101', costo: '10' }, { unidades: '100', costo: '10' }), true)
})

test('el cuerpo del PUT lleva solo los meses cambiados y valida', () => {
  const original = [
    { unidades: '100', costo: '10' },
    { unidades: '200', costo: '10' },
  ]
  const editado = [original[0], { unidades: '250', costo: '12.5' }]
  assert.deepEqual(cuerpoConsumo(PERIODOS, editado, original), {
    meses: [{ periodo: '2026-08', unidades: '250', costo_unitario: '12.5' }],
  })
  assert.deepEqual(cuerpoConsumo(PERIODOS, original, original), { error: 'No hay cambios que guardar.' })
  assert.ok('error' in cuerpoConsumo(PERIODOS, [original[0], { unidades: 'x', costo: '1' }], original))
  assert.ok('error' in cuerpoConsumo(PERIODOS, [original[0], { unidades: '-1', costo: '1' }], original))
})
