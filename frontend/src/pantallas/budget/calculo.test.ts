import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  aMicros,
  ajustarPorcentaje,
  anosFiscalesConocidos,
  cambiosPendientes,
  claveCelda,
  compararVersiones,
  completarConTotales,
  diferenciaVsObjetivo,
  estadoRelativo,
  formatoMicros,
  principalesDiferencias,
  repartirConPerfil,
  seccionesIncompletas,
  serieObjetivoVsPropuesta,
  sumaCuadra,
  sumaImportes,
  sumarMicros,
  textoDeMicros,
  variacionPorcentual,
  clasificarCambioVersion,
  compararVersionesDetallado,
  calcularTotalesComparacion,
} from './calculo.ts'

test('los años fiscales conocidos vienen de las cargas vigentes y las versiones de Budget', () => {
  const cargas = [
    { estado: 'vigente', periodo: '2026-08' },
    { estado: 'vigente', periodo: '2025-05' },
    { estado: 'reemplazada', periodo: '2024-01' }, // no vigente: no cuenta
  ]
  const versiones = [{ ano_fiscal: '2026/27' }, { ano_fiscal: '2023/24' }]
  assert.deepEqual(anosFiscalesConocidos(cargas, versiones), ['2026/27', '2024/25', '2023/24'])
})

test('sin cargas ni versiones no hay años fiscales conocidos', () => {
  assert.deepEqual(anosFiscalesConocidos([], []), [])
})

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

test('la suma de los importes mensuales se compara exacta contra el anual', () => {
  const doceIguales = Object.fromEntries(
    Array.from({ length: 12 }, (_, i) => [`2026-${String(i + 1).padStart(2, '0')}`, '100.00']),
  )
  assert.equal(sumaCuadra(doceIguales, '1200.00'), true)
  assert.equal(sumaCuadra(doceIguales, '1200.01'), false)
})

test('un importe vacío cuenta como cero', () => {
  assert.equal(sumaCuadra({ '2026-07': '', '2026-08': '100.00' }, '100.00'), true)
})

test('un texto que no es un importe válido da null, no false', () => {
  assert.equal(sumaCuadra({ '2026-07': 'abc' }, '100.00'), null)
  assert.equal(sumaCuadra({ '2026-07': '100.00' }, 'abc'), null)
})

test('sumaImportes devuelve el total como texto decimal exacto', () => {
  assert.equal(sumaImportes({ a: '100.50', b: '0.50' }), '101')
  assert.equal(sumaImportes({}), '0')
  assert.equal(sumaImportes({ a: 'abc' }), null)
})

test('diferenciaVsObjetivo: propuesta igual, por arriba o por abajo del objetivo', () => {
  assert.deepEqual(diferenciaVsObjetivo('100.00', '100.00'), {
    diferenciaMicros: 0n,
    estado: 'en-rango',
  })
  assert.deepEqual(diferenciaVsObjetivo('0.00', '0.00'), { diferenciaMicros: 0n, estado: 'en-rango' })
  assert.deepEqual(diferenciaVsObjetivo('100.00', '120.00'), {
    diferenciaMicros: 20_000_000n,
    estado: 'sobre',
  })
  assert.deepEqual(diferenciaVsObjetivo('100.00', '80.00'), {
    diferenciaMicros: -20_000_000n,
    estado: 'bajo',
  })
})

test('diferenciaVsObjetivo con un importe inválido no inventa una diferencia', () => {
  assert.deepEqual(diferenciaVsObjetivo('abc', '100.00'), { diferenciaMicros: null, estado: 'en-rango' })
})

test('serieObjetivoVsPropuesta trae el texto exacto en micros, y el número solo para graficar', () => {
  const serie = serieObjetivoVsPropuesta([
    { seccion: 'Habitaciones', suma_objetivo: '100.00', suma_propuesta: '120.00' },
    { seccion: null, suma_objetivo: '0.00', suma_propuesta: '50.00' },
  ])
  assert.equal(serie[0].seccion, 'Habitaciones')
  assert.equal(serie[0].objetivo, 100)
  assert.equal(serie[0].propuesta, 120)
  assert.equal(serie[0].diferenciaMicros, 20_000_000n)
  assert.equal(serie[0].diferenciaPct, 20)
  assert.equal(serie[1].seccion, 'Sin sección')
  assert.equal(serie[1].diferenciaPct, null) // objetivo en 0: el porcentaje no tiene sentido
})

test('estadoRelativo: avance lineal marca completado/actual/pendiente', () => {
  assert.equal(estadoRelativo('borrador', 'revision'), 'completado')
  assert.equal(estadoRelativo('revision', 'revision'), 'actual')
  assert.equal(estadoRelativo('aprobado', 'revision'), 'pendiente')
  assert.equal(estadoRelativo('bloqueado', 'revision'), 'pendiente')
})

test('estadoRelativo: una reapertura no deja pasos futuros como completados', () => {
  // aprobado -> borrador (reapertura): solo "borrador" es el actual, el resto vuelve a pendiente
  assert.equal(estadoRelativo('borrador', 'borrador'), 'actual')
  assert.equal(estadoRelativo('aprobado', 'borrador'), 'pendiente')
  assert.equal(estadoRelativo('bloqueado', 'borrador'), 'pendiente')
})

const PESOS_UNIFORME = [...Array(11).fill('0.083333'), '0.083337']

test('repartirConPerfil: el perfil Uniforme cuadra exacto con el anual (caso del backend)', () => {
  const anual = aMicros('1200000.00')
  const importes = repartirConPerfil(anual as bigint, PESOS_UNIFORME)
  assert.ok(importes)
  assert.equal(importes!.length, 12)
  assert.deepEqual(
    importes!.reduce((a, b) => a + b, 0n),
    anual,
  )
  assert.equal(importes![0], aMicros('99999.60'))
  assert.equal(importes![11], aMicros('100004.40'))
})

test('repartirConPerfil: también cuadra exacto cuando el anual tiene micros difíciles de repartir', () => {
  const anual = aMicros('100.000001')
  const importes = repartirConPerfil(anual as bigint, PESOS_UNIFORME)
  assert.ok(importes)
  assert.equal(
    importes!.reduce((a, b) => a + b, 0n),
    anual,
  )
})

test('repartirConPerfil: el residuo se suma al último mes con peso distinto de cero (empate a la par)', () => {
  const pesos = ['0.5', '0.5', ...Array(10).fill('0')]
  const importes = repartirConPerfil(1n, pesos) // 0.000001: un residuo de un micro
  // 0.5 exacto es un empate: redondea al par (0), así que ambos meses "caen" en 0 antes del ajuste
  assert.deepEqual(importes, [0n, 1n, ...Array(10).fill(0n)])
})

test('repartirConPerfil: pesos inválidos (no son 12, o no son un número) dan null', () => {
  assert.equal(repartirConPerfil(1_000_000n, ['1', '0']), null)
  assert.equal(repartirConPerfil(1_000_000n, [...Array(11).fill('0.1'), 'abc']), null)
})

test('sumarMicros: sin ningún dato es null, no cero; los ausentes no cuentan como cero', () => {
  assert.equal(sumarMicros([]), null)
  assert.equal(sumarMicros([null, null]), null)
  assert.equal(sumarMicros([1_000_000n, null, 2_000_000n]), 3_000_000n)
})

test('compararVersiones: en ambas, solo en A, solo en B, e importe inválido', () => {
  const a = [
    { linea_id: 1, anual: '100.00' }, // en ambas, cambia
    { linea_id: 2, anual: '50.00' }, // solo en A
    { linea_id: 3, anual: 'abc' }, // inválido en A
  ]
  const b = [
    { linea_id: 1, anual: '120.00' },
    { linea_id: 3, anual: '10.00' },
    { linea_id: 4, anual: '5.00' }, // solo en B
  ]
  const r = compararVersiones(a, b)
  assert.deepEqual(
    r.map((d) => d.linea_id),
    [1, 2, 3, 4],
  )
  assert.deepEqual(r[0], { linea_id: 1, anualA: 100_000_000n, anualB: 120_000_000n, diferenciaMicros: 20_000_000n })
  assert.deepEqual(r[1], { linea_id: 2, anualA: 50_000_000n, anualB: null, diferenciaMicros: null })
  assert.deepEqual(r[2], { linea_id: 3, anualA: null, anualB: 10_000_000n, diferenciaMicros: null })
  assert.deepEqual(r[3], { linea_id: 4, anualA: null, anualB: 5_000_000n, diferenciaMicros: null })
})

test('seccionesIncompletas cuenta solo las secciones con alguna línea sin capturar', () => {
  assert.equal(
    seccionesIncompletas([
      { total_lineas: 3, lineas_capturadas: 3 },
      { total_lineas: 4, lineas_capturadas: 1 },
      { total_lineas: 2, lineas_capturadas: 0 },
    ]),
    2,
  )
  assert.equal(seccionesIncompletas([]), 0)
})

test('principalesDiferencias: ordena por desviación absoluta y excluye líneas sin objetivo/propuesta', () => {
  const lineas = [
    { linea_id: 1, descripcion: 'A', seccion: 'Rooms', objetivo: '100.00', propuesta_anual: '120.00' }, // +20
    { linea_id: 2, descripcion: 'B', seccion: 'Rooms', objetivo: '100.00', propuesta_anual: '40.00' }, // -60
    { linea_id: 3, descripcion: 'C', seccion: null, objetivo: null, propuesta_anual: '50.00' }, // sin objetivo
    { linea_id: 4, descripcion: 'D', seccion: null, objetivo: '10.00', propuesta_anual: null }, // sin propuesta
    { linea_id: 5, descripcion: 'E', seccion: null, objetivo: '100.00', propuesta_anual: '105.00' }, // +5
  ]
  const r = principalesDiferencias(lineas, 2)
  assert.deepEqual(
    r.map((d) => d.linea_id),
    [2, 1],
  )
  assert.equal(r[0].diferenciaMicros, -60_000_000n)
})

test('variacionPorcentual: calcula variaciones positivas, negativas y protege división por cero', () => {
  // Base 100, Comparada 120 -> +20.00%
  assert.equal(variacionPorcentual(100_000_000n, 120_000_000n), 20)
  // Base 100, Comparada 75 -> -25.00%
  assert.equal(variacionPorcentual(100_000_000n, 75_000_000n), -25)
  // Base 0 -> null (no divide por cero)
  assert.equal(variacionPorcentual(0n, 50_000_000n), null)
  // Valores nulos -> null
  assert.equal(variacionPorcentual(null, 50_000_000n), null)
  assert.equal(variacionPorcentual(50_000_000n, null), null)
  assert.equal(variacionPorcentual(null, null), null)
  // Mismo valor -> 0%
  assert.equal(variacionPorcentual(80_000_000n, 80_000_000n), 0)
})

test('clasificarCambioVersion: identifica nueva, eliminada, modificada o sin cambio', () => {
  assert.equal(clasificarCambioVersion(null, 10_000_000n), 'nueva')
  assert.equal(clasificarCambioVersion(10_000_000n, null), 'eliminada')
  assert.equal(clasificarCambioVersion(10_000_000n, 20_000_000n), 'modificada')
  assert.equal(clasificarCambioVersion(15_000_000n, 15_000_000n), 'sin_cambio')
  assert.equal(clasificarCambioVersion(null, null), 'incompleta')
})

test('compararVersionesDetallado: combina líneas con su tipo y porcentaje de variación', () => {
  const vA = [
    { linea_id: 1, anual: '100.00' }, // Modificada
    { linea_id: 2, anual: '50.00' },  // Eliminada
    { linea_id: 3, anual: '30.00' },  // Sin cambio
  ]
  const vB = [
    { linea_id: 1, anual: '150.00' }, // +50%
    { linea_id: 3, anual: '30.00' },  // 0%
    { linea_id: 4, anual: '80.00' },  // Nueva
  ]
  const res = compararVersionesDetallado(vA, vB)
  assert.equal(res.length, 4)

  const l1 = res.find((r) => r.linea_id === 1)!
  assert.equal(l1.tipo, 'modificada')
  assert.equal(l1.diferenciaMicros, 50_000_000n)
  assert.equal(l1.diferenciaPct, 50)

  const l2 = res.find((r) => r.linea_id === 2)!
  assert.equal(l2.tipo, 'eliminada')
  assert.equal(l2.anualB, null)
  assert.equal(l2.diferenciaPct, null)

  const l3 = res.find((r) => r.linea_id === 3)!
  assert.equal(l3.tipo, 'sin_cambio')
  assert.equal(l3.diferenciaMicros, 0n)
  assert.equal(l3.diferenciaPct, 0)

  const l4 = res.find((r) => r.linea_id === 4)!
  assert.equal(l4.tipo, 'nueva')
  assert.equal(l4.anualA, null)
  assert.equal(l4.diferenciaPct, null)
})

test('calcularTotalesComparacion: concilia sumas, diferencia neta y conteos', () => {
  const filas = [
    { anualA: 100_000_000n, anualB: 150_000_000n }, // mod
    { anualA: 50_000_000n, anualB: null },          // elim
    { anualA: 30_000_000n, anualB: 30_000_000n },   // sin cambio
    { anualA: null, anualB: 20_000_000n },          // nueva
  ]
  const totales = calcularTotalesComparacion(filas)
  // Total A = 100 + 50 + 30 = 180M micros
  assert.equal(totales.totalA, 180_000_000n)
  // Total B = 150 + 30 + 20 = 200M micros
  assert.equal(totales.totalB, 200_000_000n)
  // Diferencia neta = +20M micros
  assert.equal(totales.diferenciaNeta, 20_000_000n)
  // Variación pct = 20 / 180 * 100 = 11.11%
  assert.equal(totales.diferenciaPct, 11.11)
  assert.equal(totales.conteoTotal, 4)
  assert.equal(totales.conteoNuevas, 1)
  assert.equal(totales.conteoEliminadas, 1)
  assert.equal(totales.conteoModificadas, 1)
  assert.equal(totales.conteoSinCambio, 1)
})
