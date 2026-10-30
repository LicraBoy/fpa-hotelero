import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  acumulada,
  acumuladoDe,
  barrasVariacion,
  escalaSimetrica,
  extremosDe,
  nivelCalor,
  porcentajeBarra,
  superaUmbral,
  formatoEje,
  mesDesdeX,
  cambioContraBase,
  formatoCompacto,
  marcasEje,
  seriesComparativo,
  formatoPorcentaje,
  fraccionAPorcentaje,
  porcentajeAFraccion,
  sumaAnual,
  totalConInflacion,
  variacionAnual,
} from './hojaSeccion.ts'

test('la inflación pasa de fracción a porcentaje y de vuelta sin perder nada', () => {
  assert.equal(fraccionAPorcentaje('0.05'), '5')
  assert.equal(fraccionAPorcentaje('0.012500'), '1.25')
  assert.equal(fraccionAPorcentaje(null), '')
  assert.equal(porcentajeAFraccion('5'), '0.05')
  assert.equal(porcentajeAFraccion('1.25'), '0.0125')
  assert.equal(porcentajeAFraccion('-2'), '-0.02')
  assert.equal(porcentajeAFraccion('0'), '0')
})

test('un porcentaje inválido o fuera de rango no se acepta', () => {
  assert.equal(porcentajeAFraccion('abc'), null)
  assert.equal(porcentajeAFraccion('150'), null) // más de 100 %
  assert.equal(porcentajeAFraccion('0.00001'), null) // más precisión de la que se guarda
})

test('la acumulada es suma simple, como Cum = SUM(M33:N33) del Excel', () => {
  const infl = [10_000n, 20_000n, null, 30_000n]
  assert.deepEqual(acumulada(infl), [10_000n, 30_000n, 30_000n, 60_000n])
})

test('total con inflación = total × (1 + inflación del mes)', () => {
  const totales = [1_000_000_000n, 2_000_000_000n]
  assert.deepEqual(totalConInflacion(totales, [50_000n, null]), [1_050_000_000n, 2_000_000_000n])
})

test('variación y % del año con las cifras del Excel de Contraloría', () => {
  // Est Act 1,495,385.23 · Budget previo 1,090,363.34 -> 405,021.89 / 37.15 %
  const v = variacionAnual([1_495_385_230_000n], [1_090_363_340_000n])
  assert.ok(v)
  assert.equal(v.diferencia, 405_021_890_000n)
  assert.equal(formatoPorcentaje(v.fraccion), '37.15%')
})

test('sin Est Act o sin Budget previo no hay variación; con previo en cero no hay %', () => {
  assert.equal(variacionAnual([null, null], [1n, 1n]), null)
  assert.equal(variacionAnual([5n], [0n])?.fraccion, null)
  assert.equal(sumaAnual([null, null]), null)
  assert.equal(sumaAnual([1n, null, 2n]), 3n)
})

test('formato del porcentaje', () => {
  assert.equal(formatoPorcentaje(null), '—')
  assert.equal(formatoPorcentaje(447_722n), '44.77%')
  assert.equal(formatoPorcentaje(-50_000n), '-5.00%')
  assert.equal(formatoPorcentaje(0n), '0.00%')
})

test('el formato compacto del eje usa K y M', () => {
  assert.equal(formatoCompacto(500_000n * 1_000_000n), '500K')
  assert.equal(formatoCompacto(1_500_000n * 1_000_000n), '1.5M')
  assert.equal(formatoCompacto(2_000_000n * 1_000_000n), '2M')
  assert.equal(formatoCompacto(850n * 1_000_000n), '850')
  assert.equal(formatoCompacto(0n), '0')
})

test('una serie incompleta no se dibuja y nunca se rellena con ceros', () => {
  const doce = Array.from({ length: 12 }, (_, i) => BigInt(i + 1) * 1_000_000n)
  const incompleta: (bigint | null)[] = [...doce]
  incompleta[4] = null
  const series = seriesComparativo(doce, incompleta, doce.map(() => null))
  assert.deepEqual(
    series.map((s) => s.id),
    ['budget'],
  )
  assert.deepEqual(seriesComparativo([], [], []), [])
})

test('las marcas del eje parten de 0 y cubren el máximo', () => {
  const marcas = marcasEje(1_863_000n * 1_000_000n)
  assert.equal(marcas[0], 0n)
  assert.ok(marcas[marcas.length - 1] >= 1_863_000n * 1_000_000n)
  assert.deepEqual(marcasEje(0n), [0n])
})

test('el cambio contra la base es una fracción y no existe con base 0', () => {
  assert.equal(cambioContraBase(1_000_000_000n, 1_062_000_000n), 62_000n) // +6.2 %
  assert.equal(cambioContraBase(0n, 5n), null)
})

test('el acumulado termina en el total anual de cada serie', () => {
  const m = [1_000_000n, 2_000_000n, 3_000_000n, 4_000_000n]
  const acum = acumuladoDe(m)
  assert.deepEqual(acum, [1_000_000n, 3_000_000n, 6_000_000n, 10_000_000n])
  assert.equal(acum[acum.length - 1], sumaAnual(m))
  assert.deepEqual(acumuladoDe([]), [])
})

test('las marcas del eje llevan un decimal en millones', () => {
  assert.equal(formatoEje(0n), '0')
  assert.equal(formatoEje(500_000n * 1_000_000n), '500K')
  assert.equal(formatoEje(1_000_000n * 1_000_000n), '1.0M')
  assert.equal(formatoEje(1_500_000n * 1_000_000n), '1.5M')
  assert.equal(formatoEje(850n * 1_000_000n), '850')
})

test('un mes sin dato no lleva barra de variación y la escala es simétrica', () => {
  const barras = barrasVariacion([5n, null, -8n, 0n, null])
  assert.deepEqual(
    barras.map((b) => [b.indice, b.signo]),
    [
      [0, 'pos'],
      [2, 'neg'],
      [3, 'cero'],
    ],
  )
  assert.equal(escalaSimetrica(barras), 8n)
  assert.equal(escalaSimetrica([]), 0n)
})

test('la posición del ratón se traduce al mes más cercano', () => {
  assert.equal(mesDesdeX(50, 50, 650, 12), 0)
  assert.equal(mesDesdeX(650, 50, 650, 12), 11)
  assert.equal(mesDesdeX(10, 50, 650, 12), 0)
  assert.equal(mesDesdeX(900, 50, 650, 12), 11)
  assert.equal(mesDesdeX(350, 50, 650, 12), 6)
})

test('los picos ignoran los meses sin dato y no aparecen con datos iguales o insuficientes', () => {
  assert.deepEqual(extremosDe([5n, null, 9n, 1n, 9n]), { max: 2, min: 3 })
  assert.deepEqual(extremosDe([5n, 5n, 5n]), { max: null, min: null })
  assert.deepEqual(extremosDe([7n, null, null]), { max: null, min: null })
  assert.deepEqual(extremosDe([null, null]), { max: null, min: null })
})

test('el mapa de calor tiene cuatro niveles y la ausencia o el cero no se pintan', () => {
  assert.equal(nivelCalor(null, 100n), 0)
  assert.equal(nivelCalor(0n, 100n), 0)
  assert.equal(nivelCalor(1n, 100n), 1)
  assert.equal(nivelCalor(25n, 100n), 1)
  assert.equal(nivelCalor(26n, 100n), 2)
  assert.equal(nivelCalor(-51n, 100n), 3)
  assert.equal(nivelCalor(100n, 100n), 4)
  assert.equal(nivelCalor(5n, 0n), 0)
})

test('la mini-barra es un entero 0–100 y solo existe con valor positivo', () => {
  assert.equal(porcentajeBarra(50n, 100n), 50)
  assert.equal(porcentajeBarra(100n, 100n), 100)
  assert.equal(porcentajeBarra(null, 100n), 0)
  assert.equal(porcentajeBarra(-5n, 100n), 0)
  assert.equal(porcentajeBarra(5n, 0n), 0)
})

test('la bandera de umbral compara sobre la fracción y la ausencia no la activa', () => {
  const cien = 1_000_000n // 100 %
  assert.equal(superaUmbral(2_703_800n, cien), true) // 270.38 %
  assert.equal(superaUmbral(cien, cien), false)
  assert.equal(superaUmbral(null, cien), false)
})
