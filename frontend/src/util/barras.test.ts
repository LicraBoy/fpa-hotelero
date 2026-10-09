import assert from 'node:assert/strict'
import { test } from 'node:test'
import { maximoAbsoluto, porcentajeBarra } from './barras.ts'

test('el máximo es el mayor valor absoluto, con negativos y sin datos', () => {
  assert.equal(maximoAbsoluto(['100.00', '-250.50', null, undefined]), 25050n)
  assert.equal(maximoAbsoluto([null, undefined]), 0n)
  assert.equal(maximoAbsoluto(['abc']), 0n) // ilegible: se ignora
})

test('el largo de la barra es proporcional y exacto a una décima', () => {
  const max = maximoAbsoluto(['200.00', '50.00'])
  assert.equal(porcentajeBarra('200.00', max), 100)
  assert.equal(porcentajeBarra('50.00', max), 25)
  assert.equal(porcentajeBarra('-100.00', max), 50) // el signo no cambia el largo
  assert.equal(porcentajeBarra('33.33', max), 16.6)
})

test('sin dato o sin máximo no hay barra, y nunca pasa de 100', () => {
  assert.equal(porcentajeBarra(null, 100n), 0)
  assert.equal(porcentajeBarra('10.00', 0n), 0)
  assert.equal(porcentajeBarra('999.00', 100n), 100)
})
