import assert from 'node:assert/strict'
import { test } from 'node:test'
import { etiquetaMesLargo, etiquetaRangoMeses } from './periodos.ts'

test('un periodo se escribe como mes y año', () => {
  assert.equal(etiquetaMesLargo('2026-08'), 'agosto 2026')
  assert.equal(etiquetaMesLargo('2027-01'), 'enero 2027')
  assert.equal(etiquetaMesLargo('no-es-periodo'), 'no-es-periodo')
})

test('el acumulado se escribe como rango de meses', () => {
  assert.equal(etiquetaRangoMeses(['2026-07', '2026-08', '2026-09']), 'jul – sep')
  assert.equal(etiquetaRangoMeses(['2026-07']), 'jul')
  assert.equal(etiquetaRangoMeses([]), '')
})
