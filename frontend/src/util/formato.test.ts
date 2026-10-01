import assert from 'node:assert/strict'
import { test } from 'node:test'
import { esDesfavorable, formatoContable, formatoPorcentaje } from './formato.ts'

test('formato contable: miles, dos decimales y negativos entre paréntesis', () => {
  assert.equal(formatoContable('1234.5'), '1,234.50')
  assert.equal(formatoContable('0'), '0.00')
  assert.equal(formatoContable('-1234.5'), '(1,234.50)')
  assert.equal(formatoContable('57835193.08'), '57,835,193.08')
  assert.equal(formatoContable('1000000'), '1,000,000.00')
  assert.equal(formatoContable('999'), '999.00')
})

test('formato contable: sin dato se muestra —, nunca un cero inventado', () => {
  assert.equal(formatoContable(null), '—')
  assert.equal(formatoContable(undefined), '—')
  assert.equal(formatoContable('no es un número'), '—')
  assert.equal(formatoContable(''), '—')
})

test('formato contable: redondeo half-up sobre el valor absoluto, sin pasar por number', () => {
  assert.equal(formatoContable('20639.648946'), '20,639.65')
  assert.equal(formatoContable('0.005'), '0.01')
  assert.equal(formatoContable('0.004'), '0.00')
  assert.equal(formatoContable('-0.005'), '(0.01)')
  assert.equal(formatoContable('-0.004'), '0.00') // un cero negativo no lleva paréntesis
  assert.equal(formatoContable('0.995'), '1.00')
  // más grande de lo que un number representa con exactitud
  assert.equal(formatoContable('9007199254740993.99'), '9,007,199,254,740,993.99')
})

test('porcentaje: razón -> un decimal', () => {
  assert.equal(formatoPorcentaje('0.250000'), '25.0%')
  assert.equal(formatoPorcentaje('-0.500000'), '(50.0%)')
  assert.equal(formatoPorcentaje('1'), '100.0%')
  assert.equal(formatoPorcentaje('0'), '0.0%')
  assert.equal(formatoPorcentaje('778.781689'), '77,878.2%')
  assert.equal(formatoPorcentaje('0.00004'), '0.0%')
  assert.equal(formatoPorcentaje('-0.00004'), '0.0%')
  assert.equal(formatoPorcentaje(null), '—')
})

test('variación desfavorable: solo los negativos distintos de cero', () => {
  assert.equal(esDesfavorable('-0.01'), true)
  assert.equal(esDesfavorable('-1500.25'), true)
  assert.equal(esDesfavorable('0.00'), false)
  assert.equal(esDesfavorable('-0.00'), false)
  assert.equal(esDesfavorable('12.5'), false)
  assert.equal(esDesfavorable(null), false)
})
