import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  controlSuma,
  sumaCuadra,
  cuerpoPartidas,
  distribucionDe,
  erroresDePartida,
  extendidoDe,
  mesesDe,
  partidaCambio,
  partidaDesdeApi,
  partidaNueva,
  repartirMensual,
  type PartidaEditable,
} from './partidas.ts'

const M = 1_000_000n
const mensual = (cantidad: string, costo: string): PartidaEditable => ({
  ...partidaNueva(),
  concepto: 'Teléfono',
  cantidad,
  costo,
})
const estacional = (cantidad: string, costo: string, meses: Record<number, string>): PartidaEditable => ({
  ...partidaNueva(),
  concepto: 'Regalos',
  cantidad,
  costo,
  metodo: 'estacional',
  meses: Array.from({ length: 12 }, (_, i) => meses[i] ?? ''),
})

test('el costo extendido es cantidad × costo, y sin número no hay extendido', () => {
  assert.equal(extendidoDe('12', '735'), 8820n * M)
  assert.equal(extendidoDe('3', '0.333333'), 999_999n)
  assert.equal(extendidoDe('', '5'), null)
  assert.equal(extendidoDe('abc', '5'), null)
})

test('el reparto mensual siempre cierra y el residuo va a los primeros meses', () => {
  for (const total of [100n * M, 7n, 1_000_000_000_001n, 8820n * M]) {
    const meses = repartirMensual(total)
    assert.equal(meses.length, 12)
    assert.equal(meses.reduce((s, x) => s + x, 0n), total)
  }
  assert.deepEqual(repartirMensual(7n).slice(0, 8), [1n, 1n, 1n, 1n, 1n, 1n, 1n, 0n])
})

test('una partida estacional dice si sus meses cuadran con el extendido', () => {
  const p = estacional('3', '10500', { 3: '10500', 4: '10500', 5: '10500' })
  assert.equal(controlSuma(p), 0n)
  assert.equal(controlSuma(estacional('4', '10500', { 3: '10500', 4: '10500', 5: '10500' })), -10500n * M) // faltan
  assert.equal(controlSuma(estacional('2', '10500', { 3: '10500', 4: '10500', 5: '10500' })), 10500n * M) // excede
  assert.equal(controlSuma(mensual('12', '4515')), 0n)
})

test('el ruido del Excel (millonésimos y hasta casi un centavo) cuadra; un centavo o más ya no', () => {
  assert.equal(sumaCuadra(0n), true)
  assert.equal(sumaCuadra(2n), true)
  assert.equal(sumaCuadra(-1n), true)
  assert.equal(sumaCuadra(8_900n), true)
  assert.equal(sumaCuadra(9_999n), true)
  assert.equal(sumaCuadra(10_000n), false)
  assert.equal(sumaCuadra(-10_000n), false)
})

test('la distribución suma las partidas mes a mes y es nula si una no se puede calcular', () => {
  const d = distribucionDe([mensual('12', '4515'), estacional('3', '10500', { 3: '10500', 4: '10500', 5: '10500' })])
  assert.equal(d[0], 4515n * M)
  assert.equal(d[3], (4515n + 10500n) * M)
  assert.ok(distribucionDe([mensual('12', '')]).every((x) => x === null))
  assert.equal(mesesDe(estacional('1', '5', { 0: 'x' })), null)
})

test('los errores impiden guardar; el concepto y los números se validan', () => {
  assert.deepEqual(erroresDePartida(mensual('12', '4515')), [])
  const e = erroresDePartida({ ...mensual('-1', ''), concepto: '  ' })
  assert.deepEqual(e.map((x) => x.campo).sort(), ['cantidad', 'concepto', 'costo'])
  assert.ok(erroresDePartida(estacional('1', '5', { 2: '-4' })).some((x) => x.campo === 'meses'))
})

test('el cuerpo del PUT lleva todas las partidas y no manda meses en las mensuales', () => {
  const infl = Object.fromEntries(Array.from({ length: 12 }, (_, i) => [`2026-${String(i + 1).padStart(2, '0')}`, '0.05']))
  const c = cuerpoPartidas([mensual('12', '4515'), estacional('3', '10500', { 3: '10500' })], infl)
  assert.ok(!('error' in c))
  if ('error' in c) return
  assert.equal(c.partidas.length, 2)
  assert.ok(!('meses' in c.partidas[0]))
  assert.equal((c.partidas[1].meses as string[]).length, 12)
  assert.equal(c.partidas[0].cantidad, '12')
  assert.deepEqual(cuerpoPartidas([], infl), { error: 'La cuenta necesita al menos una partida' })
  assert.ok('error' in cuerpoPartidas([mensual('12', '')], infl))
})

test('las partidas de la API se editan sin ceros sobrantes y los cambios se detectan', () => {
  const p = partidaDesdeApi({ id: 7, concepto: 'X', cantidad: '12.000000', unidad: null, costo: '735.500000', metodo: 'mensual', meses: Array(12).fill('0.000000') })
  assert.equal(p.cantidad, '12')
  assert.equal(p.costo, '735.5')
  assert.equal(p.unidad, '')
  assert.equal(partidaCambio(p, { ...p }), false)
  assert.equal(partidaCambio(p, { ...p, costo: '736' }), true)
  // los meses solo cuentan si la partida no es mensual
  assert.equal(partidaCambio(p, { ...p, meses: Array(12).fill('1') }), false)
  assert.equal(partidaCambio({ ...p, metodo: 'estacional' }, { ...p, metodo: 'estacional', meses: Array(12).fill('1') }), true)
})
