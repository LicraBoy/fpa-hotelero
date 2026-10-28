import assert from 'node:assert/strict'
import { test } from 'node:test'
import { celdasDesdeApi, type CeldaEditable } from './detalleCuenta.ts'
import {
  cambiosPorMes,
  claseSigno,
  erroresDeCeldas,
  formatoCampo,
  mesesModificados,
  indicadoresDe,
  rangoDePeriodos,
  variacionDelMes,
} from './editorCuenta.ts'

const PERIODOS = [
  ...[7, 8, 9, 10, 11, 12].map((m) => `2026-${String(m).padStart(2, '0')}`),
  ...[1, 2, 3, 4, 5, 6].map((m) => `2027-${String(m).padStart(2, '0')}`),
]

const conBase = (base: string, factor = '1.05'): CeldaEditable[] =>
  celdasDesdeApi(PERIODOS, [], factor).map((c) => ({ ...c, base }))

test('el rango fiscal sale de los periodos reales', () => {
  assert.equal(rangoDePeriodos(PERIODOS), 'Jul 2026 – Jun 2027')
  assert.equal(rangoDePeriodos([]), null)
})

test('con base completa se muestran los cuatro indicadores', () => {
  const i = indicadoresDe(conBase('1000'))
  assert.equal(i.budgetAnual, 12_600_000_000n) // 12 × 1,000 × 1.05
  assert.equal(i.promedioMensual, 1_050_000_000n)
  assert.equal(i.baseAnual, 12_000_000_000n)
  assert.equal(i.variacion?.diferencia, 600_000_000n)
  assert.equal(i.variacion?.porcentaje, 5)
})

test('sin datos no hay ningún indicador (no se rellena con ceros)', () => {
  const i = indicadoresDe(celdasDesdeApi(PERIODOS, [], '1.05'))
  assert.deepEqual(i, { budgetAnual: null, promedioMensual: null, baseAnual: null, variacion: null })
})

test('con la base a medias solo hay Budget y promedio si hay importes, nunca una base parcial', () => {
  const celdas = conBase('1000')
  celdas[3] = { ...celdas[3], base: '', metodo: 'fijo', montoFijo: '500' }
  const i = indicadoresDe(celdas)
  assert.equal(i.baseAnual, null)
  assert.equal(i.variacion, null)
  assert.equal(i.budgetAnual, 12_050_000_000n) // 11 × 1,050 + 500 fijo
})

test('un mes en monto fijo con base también tiene su variación contra la base', () => {
  const celda: CeldaEditable = { periodo: '2026-07', metodo: 'fijo', base: '1000', factor: '1.05', montoFijo: '1200' }
  const v = variacionDelMes(celda)
  assert.equal(v?.diferencia, 200_000_000n)
  assert.equal(v?.porcentaje, 20)
  assert.equal(variacionDelMes({ ...celda, base: '' }), null)
})

test('los errores distinguen texto inválido de dato que falta', () => {
  const celdas = conBase('1000')
  celdas[0] = { ...celdas[0], base: 'abc' }
  celdas[1] = { ...celdas[1], factor: '' }
  celdas[2] = { ...celdas[2], metodo: 'fijo', montoFijo: '' }
  celdas[3] = { ...celdas[3], metodo: 'fijo', montoFijo: 'x' }
  const e = erroresDeCeldas(celdas)
  assert.deepEqual(
    e.map((x) => `${x.periodo}:${x.campo}:${x.tipo}`),
    [
      '2026-07:base:invalido',
      '2026-08:factor:falta',
      '2026-09:montoFijo:falta',
      '2026-10:montoFijo:invalido',
    ],
  )
})

test('una cuenta sin datos tiene doce meses con "falta la base"', () => {
  const e = erroresDeCeldas(celdasDesdeApi(PERIODOS, [], '1.05'))
  assert.equal(e.length, 12)
  assert.ok(e.every((x) => x.tipo === 'falta' && x.campo === 'base'))
})

test('cuenta los meses que cambiaron, no los campos', () => {
  const inicial = conBase('1000')
  const celdas = inicial.map((c) => ({ ...c }))
  assert.equal(cambiosPorMes(celdas, inicial), 0)
  celdas[2] = { ...celdas[2], base: '1', factor: '2' } // dos campos, un mes
  celdas[5] = { ...celdas[5], metodo: 'fijo' }
  assert.equal(cambiosPorMes(celdas, inicial), 2)
})

test('el signo se dice con la clase y con el texto, no solo con color', () => {
  assert.equal(claseSigno(5n), 'pos')
  assert.equal(claseSigno(-5n), 'neg')
  assert.equal(claseSigno(0n), 'cero')
  assert.equal(claseSigno(null), 'cero')
})

test('marca los meses que cambiaron y los desmarca al volver a lo guardado', () => {
  const inicial = conBase('1000')
  const celdas = inicial.map((c) => ({ ...c }))
  assert.deepEqual(mesesModificados(celdas, inicial), Array(12).fill(false))
  celdas[2] = { ...celdas[2], base: '1' }
  assert.deepEqual(
    mesesModificados(celdas, inicial).map((x, i) => (x ? i : -1)).filter((i) => i >= 0),
    [2],
  )
  celdas[2] = { ...inicial[2] }
  assert.equal(mesesModificados(celdas, inicial).some(Boolean), false)
})

test('sin foco los importes llevan 2 decimales y miles; el factor no se trunca; lo inválido queda igual', () => {
  assert.equal(formatoCampo('27270.58', 'importe'), '27,270.58')
  assert.equal(formatoCampo('1000', 'importe'), '1,000.00')
  assert.equal(formatoCampo('0', 'importe'), '0.00')
  assert.equal(formatoCampo('1.05', 'factor'), '1.05')
  assert.equal(formatoCampo('1', 'factor'), '1.00')
  assert.equal(formatoCampo('1.0525', 'factor'), '1.0525')
  assert.equal(formatoCampo('', 'importe'), '')
  assert.equal(formatoCampo('abc', 'importe'), 'abc')
})
