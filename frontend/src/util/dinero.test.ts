import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  aCentavos,
  aTextoPlano,
  deCentavos,
  formatoDinero,
  negar,
  sumar,
  sumarCentavos,
} from './dinero.ts'

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

test('negar cambia el signo sin perder centavos', () => {
  assert.equal(negar('5.00'), '-5.00')
  assert.equal(negar('-5.00'), '5.00')
  assert.equal(negar('0.00'), '0.00')
  assert.equal(negar('1234567.89'), '-1234567.89')
  // el resultado se puede seguir sumando (no trae separadores de miles)
  assert.equal(sumar([negar('1500.50'), '1500.50']), '0.00')
})

test('sumas de miles: el texto plano se puede volver a leer, el formateado no', () => {
  const total = sumarCentavos(['1000.00', '500.50'])
  assert.equal(total, 150050n)
  assert.equal(aTextoPlano(total), '1500.50')
  assert.equal(aCentavos(aTextoPlano(total)), total) // viaje de ida y vuelta
  assert.equal(sumar(['1000.00', '500.50']), '1,500.50') // formateado: solo para mostrar
  assert.throws(() => aCentavos(sumar(['1000.00', '500.50'])))
  assert.equal(aTextoPlano(-5n), '-0.05')
  assert.equal(aTextoPlano(0n), '0.00')
})
