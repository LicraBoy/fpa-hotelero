import assert from 'node:assert/strict'
import { test } from 'node:test'
import { construirRuta, parsearRuta, permisoDeRuta, type Ruta } from './ruta.ts'

test('las rutas válidas se reconocen', () => {
  assert.deepEqual(parsearRuta('#/variance'), { tipo: 'variance', periodo: null })
  assert.deepEqual(parsearRuta('#/variance/2026-08'), { tipo: 'variance', periodo: '2026-08' })
  assert.deepEqual(parsearRuta('#/variance/2026-08/linea/12?bloque=ytd'), {
    tipo: 'desglose',
    periodo: '2026-08',
    lineaId: 12,
    bloque: 'ytd',
  })
  assert.deepEqual(parsearRuta('#/variance/2026-08/cuenta/6009001.001'), {
    tipo: 'cuenta',
    periodo: '2026-08',
    codigo: '6009001.001',
    bloque: 'mes',
  })
  assert.deepEqual(parsearRuta('#/variance/2026-08/asiento/8.1.100?bloque=mes'), {
    tipo: 'asiento',
    periodo: '2026-08',
    asiento: '8.1.100',
  })
  assert.deepEqual(parsearRuta(''), { tipo: 'sin-ruta' })
})

test('lo que no es de la lista blanca es inválido (la barra de direcciones es entrada del usuario)', () => {
  for (const malo of [
    '#/otra',
    'variance',
    '#/variance/2026-13',
    '#/variance/1999-01',
    '#/variance/2026-08/linea/0',
    '#/variance/2026-08/linea/abc',
    '#/variance/2026-08/linea/99999999999',
    '#/variance/2026-08/linea/1?bloque=anual',
    '#/variance/2026-08/cuenta/<script>alert(1)</script>',
    '#/variance/2026-08/cuenta/..%2F..%2Fetc',
    "#/variance/2026-08/cuenta/1' OR '1'='1",
    '#/variance/2026-08/cuenta/javascript:alert(1)',
    '#/variance/2026-08/cuenta/%E0%A4%A',
    '#/variance/2026-08/linea',
    '#/variance/2026-08/linea/1/extra',
    '#/variance/2026-08/cuenta/6009001.001?bloque=mes&linea=0',
    '#/variance/2026-08/cuenta/6009001.001?bloque=mes&linea=abc',
    '#/variance/2026-08/asiento/9.2.15?bloque=mes&cuenta=<script>',
  ]) {
    assert.deepEqual(parsearRuta(malo), { tipo: 'invalida' }, malo)
  }
})

test('construir y parsear son inversos', () => {
  const rutas: Ruta[] = [
    { tipo: 'variance', periodo: null },
    { tipo: 'variance', periodo: '2026-08' },
    { tipo: 'desglose', periodo: '2026-08', lineaId: 7, bloque: 'ytd' },
    { tipo: 'cuenta', periodo: '2026-08', codigo: '602-0086-000', bloque: 'mes' },
    { tipo: 'asiento', periodo: '2026-08', asiento: '9.2.15' },
    { tipo: 'cuenta', periodo: '2026-08', codigo: '6009001.001', bloque: 'ytd', lineaId: 12 },
    {
      tipo: 'asiento',
      periodo: '2026-08',
      asiento: '9.2.15',
      cuenta: '6009001.001',
      lineaId: 12,
      bloque: 'ytd',
    },
  ]
  for (const r of rutas) assert.deepEqual(parsearRuta(construirRuta(r)), r)
})

test('cada pantalla pide su permiso', () => {
  assert.equal(permisoDeRuta({ tipo: 'variance', periodo: null }), 'variance:leer')
  assert.equal(permisoDeRuta({ tipo: 'asiento', periodo: '2026-08', asiento: '1' }), 'drilldown:leer')
  assert.equal(permisoDeRuta({ tipo: 'sin-ruta' }), null)
})
