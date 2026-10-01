import assert from 'node:assert/strict'
import { test } from 'node:test'
import { aCentavos, deCentavos, formatoDinero, sumar } from './dinero.ts'

test('importes exactos en centavos enteros', () => {
  assert.equal(aCentavos('57835193.08'), 5783519308n)
  assert.equal(aCentavos('-0.5'), -50n)
  assert.equal(deCentavos(-5n), '-0.05')
  assert.equal(formatoDinero('1234567.8'), '1,234,567.80')
})

test('sumar no pierde centavos (0.1 + 0.2)', () => {
  assert.equal(sumar(['0.10', '0.20']), '0.30')
  assert.equal(sumar(['100.50', '-0.50', '0.01']), '100.01')
})

test('un importe inválido es un error, no un cero', () => {
  assert.throws(() => aCentavos('abc'))
  assert.throws(() => aCentavos('1.234'))
})
