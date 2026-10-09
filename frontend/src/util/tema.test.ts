import assert from 'node:assert/strict'
import { test } from 'node:test'
import { esPreferenciaTema, resolverTema, temaContrario } from './tema.ts'

test('una preferencia explícita manda sobre el sistema', () => {
  assert.equal(resolverTema('claro', true), 'claro')
  assert.equal(resolverTema('oscuro', false), 'oscuro')
})

test('en automático se sigue al sistema', () => {
  assert.equal(resolverTema('auto', true), 'oscuro')
  assert.equal(resolverTema('auto', false), 'claro')
})

test('el interruptor fija el tema contrario al visible', () => {
  assert.equal(temaContrario('claro'), 'oscuro')
  assert.equal(temaContrario('oscuro'), 'claro')
})

test('solo se aceptan preferencias conocidas (lo guardado es entrada no confiable)', () => {
  for (const ok of ['auto', 'claro', 'oscuro']) assert.equal(esPreferenciaTema(ok), true)
  for (const mal of ['', 'dark', null, undefined, 3, '<script>']) assert.equal(esPreferenciaTema(mal), false)
})
