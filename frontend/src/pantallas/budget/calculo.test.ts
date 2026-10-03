import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  aMicros,
  ajustarPorcentaje,
  cambiosPendientes,
  claveCelda,
  completarConTotales,
  formatoMicros,
  textoDeMicros,
} from './calculo.ts'

test('los importes se leen y se escriben en micros sin perder decimales', () => {
  assert.equal(aMicros('13091.0325'), 13_091_032_500n)
  assert.equal(aMicros('-0.000001'), -1n)
  assert.equal(aMicros('1,234.50'), 1_234_500_000n) // acepta separador de miles
  assert.equal(textoDeMicros(13_091_032_500n), '13091.0325')
  assert.equal(textoDeMicros(-1_500_000n), '-1.5')
  assert.equal(textoDeMicros(0n), '0')
})

test('un texto que no es un importe, o pasa del tope, no se acepta', () => {
  for (const malo of ['', 'abc', '1.2.3', '1e5', 'NaN', '1.1234567', '--1', '1000000000001']) {
    assert.equal(aMicros(malo), null, malo)
  }
  assert.equal(aMicros('1000000000000'), 1_000_000_000_000_000_000n) // el tope exacto sí
})

test('el formato muestra 2 decimales, con miles, y — si no hay dato', () => {
  assert.equal(formatoMicros(null), '—')
  assert.equal(formatoMicros(13_091_032_500n), '13,091.03')
  assert.equal(formatoMicros(2_500n), '0.00') // 0.0025 redondea a 0.00
  assert.equal(formatoMicros(5_000n), '0.01') // mitades hacia afuera
  assert.equal(formatoMicros(-1_234_567_890n), '-1,234.57')
  assert.equal(formatoMicros(-1n), '0.00') // nunca "-0.00"
})

const reglas = [
  { linea_id: 10, componentes: [{ linea_id: 1, signo: 1 }, { linea_id: 2, signo: 1 }] },
  { linea_id: 20, componentes: [{ linea_id: 10, signo: 1 }, { linea_id: 3, signo: -1 }] },
]

test('los totales salen de sus reglas, también los que dependen de otros totales', () => {
  const base = new Map<number, bigint>([
    [1, 100_000_000n],
    [2, 50_000_000n],
    [3, 30_000_000n],
  ])
  const r = completarConTotales(reglas, base)
  assert.equal(r.get(10), 150_000_000n)
  assert.equal(r.get(20), 120_000_000n) // 150 − 30
  assert.equal(r.get(1), 100_000_000n)
})

test('un componente sin dato cuenta 0, pero un total sin ningún dato queda sin valor', () => {
  const parcial = completarConTotales(reglas, new Map([[1, 100_000_000n]]))
  assert.equal(parcial.get(10), 100_000_000n) // la línea 2 no tiene dato: cuenta 0
  assert.equal(completarConTotales(reglas, new Map()).get(10), null) // nada: no es un cero
})

test('si una línea tiene regla, manda la regla aunque venga también en la base', () => {
  const r = completarConTotales(reglas, new Map([[1, 1n], [2, 2n], [10, 999n]]))
  assert.equal(r.get(10), 3n)
})

test('un ciclo en las reglas no cuelga ni inventa un valor', () => {
  const ciclo = [
    { linea_id: 1, componentes: [{ linea_id: 2, signo: 1 }] },
    { linea_id: 2, componentes: [{ linea_id: 1, signo: 1 }] },
  ]
  const r = completarConTotales(ciclo, new Map())
  assert.equal(r.get(1), null)
})

test('copiar el Actual con un ajuste porcentual redondea a centavos', () => {
  assert.equal(ajustarPorcentaje(100_000_000n, ''), 100_000_000n) // sin ajuste
  assert.equal(ajustarPorcentaje(100_000_000n, '5'), 105_000_000n)
  assert.equal(ajustarPorcentaje(100_000_000n, '-2.5'), 97_500_000n)
  assert.equal(ajustarPorcentaje(-100_000_000n, '10'), -110_000_000n)
  assert.equal(ajustarPorcentaje(333_333_333n, '0'), 333_330_000n) // a 2 decimales
  assert.equal(ajustarPorcentaje(1n, 'x'), null)
})

test('solo se envían las celdas que cambiaron y las no válidas se avisan', () => {
  const actuales = new Map<string, bigint | null>([
    [claveCelda(1, '2026-08'), 100_000_000n],
    [claveCelda(1, '2026-09'), null],
  ])
  const ediciones = new Map([
    [claveCelda(1, '2026-08'), '100'], // igual al Budget actual: no es un cambio
    [claveCelda(1, '2026-09'), '120.5'], // celda vacía que ahora tiene Budget
    [claveCelda(2, '2026-08'), 'abc'], // no válida
    [claveCelda(3, '2026-08'), ''], // vaciada: se ignora
  ])
  const { cambios, invalidas } = cambiosPendientes(ediciones, actuales)
  assert.deepEqual(cambios, [{ linea_id: 1, periodo: '2026-09', importe: '120.5' }])
  assert.deepEqual(invalidas, [claveCelda(2, '2026-08')])
})

test('el año fiscal va de julio a junio', async () => {
  const { etiquetaAnoFiscal } = await import('./calculo.ts')
  assert.equal(etiquetaAnoFiscal('2026-08'), '2026/27')
  assert.equal(etiquetaAnoFiscal('2026-07'), '2026/27')
  assert.equal(etiquetaAnoFiscal('2026-06'), '2025/26')
  assert.equal(etiquetaAnoFiscal('2027-01'), '2026/27')
  assert.equal(etiquetaAnoFiscal('2099-12'), '2099/00')
})

test('las líneas se agrupan por sección sin cambiar su orden', async () => {
  const { agruparPorSeccionId } = await import('./calculo.ts')
  const g = agruparPorSeccionId([
    { seccion_id: 1, n: 'a' },
    { seccion_id: 1, n: 'b' },
    { seccion_id: null, n: 'c' },
    { seccion_id: 1, n: 'd' },
  ])
  assert.deepEqual(
    g.map((x) => [x.seccionId, x.lineas.map((l) => l.n).join('')]),
    [[1, 'ab'], [null, 'c'], [1, 'd']],
  )
})

test('los Actuales capturados se cambian aparte del Budget y vaciarlos los borra', async () => {
  const { cambiosActualPendientes, claveActual, cambiosPendientes } = await import('./calculo.ts')
  const vigentes = new Map<string, bigint | null>([
    [claveCelda(9, '2026-07'), 17_217_500n],
    [claveCelda(9, '2026-08'), 17_133_700n],
    [claveCelda(9, '2026-09'), null],
  ])
  const ediciones = new Map([
    [claveActual(9, '2026-07'), '17.2175'], // igual al vigente: no es un cambio
    [claveActual(9, '2026-08'), ''], // vaciado: se borra
    [claveActual(9, '2026-09'), '17.4'], // nuevo
    [claveActual(9, '2026-10'), 'abc'], // no válido
    [claveActual(9, '2026-11'), ''], // vacío y sin valor: nada
    [claveCelda(9, '2026-09'), '18'], // una edición de Budget: no se mezcla
  ])
  const { cambios, invalidas } = cambiosActualPendientes(ediciones, vigentes)
  assert.deepEqual(cambios, [
    { linea_id: 9, periodo: '2026-08', importe: null },
    { linea_id: 9, periodo: '2026-09', importe: '17.4' },
  ])
  assert.deepEqual(invalidas, [claveActual(9, '2026-10')])
  // y las ediciones de Actual no se cuelan en los cambios de Budget
  const presupuesto = cambiosPendientes(ediciones, new Map([[claveCelda(9, '2026-09'), null]]))
  assert.deepEqual(presupuesto.cambios, [{ linea_id: 9, periodo: '2026-09', importe: '18' }])
  assert.deepEqual(presupuesto.invalidas, [])
})
