import assert from 'node:assert/strict'
import { test } from 'node:test'
import { formatoCuatroDecimales, fraseDiferencia, mesesConDato, promedioMicros } from './detalleLinea.ts'

test('el promedio ignora los meses sin dato', () => {
  // 17.2175 + 17.1337 + 16.7798 = 51.1310 -> / 3 = 17.043667
  const p = promedioMicros([17_217_500n, 17_133_700n, 16_779_800n, null, null, null])
  assert.equal(p, 17_043_667n)
  assert.equal(formatoCuatroDecimales(p), '17.0437')
})

test('sin ningún dato no hay promedio', () => {
  assert.equal(promedioMicros([null, null]), null)
  assert.equal(promedioMicros([]), null)
  assert.equal(mesesConDato([null, null]), 0)
})

test('cuenta los meses con dato', () => {
  assert.equal(mesesConDato([1n, null, 0n, 5n]), 3) // un 0 también es un dato
})

test('el promedio redondea las mitades hacia afuera', () => {
  assert.equal(promedioMicros([1n, 2n]), 2n) // 1.5 -> 2
  assert.equal(promedioMicros([-1n, -2n]), -2n)
})

test('formato a 4 decimales con miles', () => {
  assert.equal(formatoCuatroDecimales(null), '—')
  assert.equal(formatoCuatroDecimales(18_000_000n), '18.0000')
  assert.equal(formatoCuatroDecimales(1_234_567_890_000n), '1,234,567.8900')
  assert.equal(formatoCuatroDecimales(-17_217_500n), '-17.2175')
  assert.equal(formatoCuatroDecimales(0n), '0.0000')
})

test('la frase explica la diferencia contra el objetivo', () => {
  // 64,000 de objetivo, 64,498.68 de propuesta -> 498.68 por encima (0.78 %)
  const sobre = fraseDiferencia('64000', 64_498_680_000n)
  assert.equal(sobre.estado, 'sobre')
  assert.equal(sobre.texto, 'Estás $498.68 (0.78 %) por encima del objetivo.')
  const bajo = fraseDiferencia('64000', 63_000_000_000n)
  assert.equal(bajo.estado, 'bajo')
  assert.equal(bajo.texto, 'Estás $1,000.00 (1.56 %) por debajo del objetivo.')
  assert.deepEqual(fraseDiferencia('64000', 64_000_000_000n), { texto: 'Coincide con el objetivo.', estado: 'igual' })
})

test('sin objetivo (o sin propuesta) la frase invita a definirlo', () => {
  assert.equal(fraseDiferencia(null, 1n).estado, 'sin-objetivo')
  assert.equal(fraseDiferencia(null, null).estado, 'sin-objetivo')
  // con objetivo pero sin propuesta, pide la propuesta (no el objetivo)
  assert.equal(fraseDiferencia('100', null).estado, 'sin-propuesta')
  assert.match(fraseDiferencia('100', null).texto, /Captura la propuesta/)
  assert.match(fraseDiferencia(null, 1n).texto, /Define un objetivo/)
})

test('con objetivo en cero no hay porcentaje, pero sí la frase', () => {
  assert.equal(fraseDiferencia('0', 5_000_000n).texto, 'Estás $5.00 por encima del objetivo.')
})
