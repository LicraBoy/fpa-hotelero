// Hoja completa de una sección (Other Income): el bloque inferior de la hoja de Contraloría. Funciones
// puras en MICROS (BigInt), como `calculo.ts`; nunca `number` para dinero. Replica las fórmulas del
// Excel (`Other Income`, filas 33 a 41):
//   Cum = suma simple de la inflación mensual hasta ese mes (no compuesta)
//   Total con inflación = Total del mes × (1 + Mthly)
//   Variance = Est Act − Budget previo;  % = Variance / Budget previo
// La inflación es INFORMATIVA: no cambia el Budget de las cuentas.

import { aMicros, textoDeMicros } from './calculo.ts'
import { multiplicarMicros } from './detalleCuenta.ts'

const MICROS = 1_000_000n

/** «0.05» (fracción, como la guarda la API) -> «5» (porcentaje, como se escribe en pantalla). */
export function fraccionAPorcentaje(fraccion: string | null): string {
  if (fraccion === null) return ''
  const micros = aMicros(fraccion)
  return micros === null ? fraccion : textoDeMicros(micros * 100n)
}

/** «5» -> «0.05». `null` si no es un número, o si pide más precisión de la que se guarda (6 decimales). */
export function porcentajeAFraccion(porcentaje: string): string | null {
  const micros = aMicros(porcentaje)
  if (micros === null || micros % 100n !== 0n) return null
  const fraccion = micros / 100n
  return fraccion < -MICROS || fraccion > MICROS ? null : textoDeMicros(fraccion)
}

/** Inflación acumulada mes a mes: suma simple (`Cum = SUM(M33:N33)`). Un mes vacío cuenta 0. */
export function acumulada(inflacion: readonly (bigint | null)[]): bigint[] {
  let corrido = 0n
  return inflacion.map((i) => (corrido += i ?? 0n))
}

/** Total del mes con la inflación del mes: `total + total × inflación`. */
export function totalConInflacion(totales: readonly bigint[], inflacion: readonly (bigint | null)[]): bigint[] {
  return totales.map((t, i) => t + multiplicarMicros(t, inflacion[i] ?? 0n))
}

/** Suma de los meses que tienen valor; `null` si ninguno lo tiene. */
export function sumaAnual(valores: readonly (bigint | null)[]): bigint | null {
  let total = 0n
  let alguno = false
  for (const v of valores) {
    if (v === null) continue
    total += v
    alguno = true
  }
  return alguno ? total : null
}

/** Variación del año: Est Act − Budget previo, y su porcentaje sobre el Budget previo. */
export function variacionAnual(
  estAct: readonly (bigint | null)[],
  previo: readonly (bigint | null)[],
): { diferencia: bigint; fraccion: bigint | null } | null {
  const e = sumaAnual(estAct)
  const p = sumaAnual(previo)
  if (e === null || p === null) return null
  const diferencia = e - p
  return { diferencia, fraccion: p === 0n ? null : (diferencia * MICROS) / p }
}

/** Fracción en micros (0.371455) -> «37.15%» para mostrar. */
export function formatoPorcentaje(fraccionMicros: bigint | null): string {
  if (fraccionMicros === null) return '—'
  const negativo = fraccionMicros < 0n
  const centesimas = ((negativo ? -fraccionMicros : fraccionMicros) + 50n) / 100n // a 2 decimales del %
  const texto = centesimas.toString().padStart(3, '0')
  return `${negativo && centesimas !== 0n ? '-' : ''}${texto.slice(0, -2)}.${texto.slice(-2)}%`
}

/** Cambio de `valor` contra `base`, como fracción en micros; `null` si la base es 0. */
export function cambioContraBase(base: bigint, valor: bigint): bigint | null {
  return base === 0n ? null : ((valor - base) * MICROS) / base
}

/** Importe en micros -> «500K», «1.5M», «850». Para las marcas del eje del gráfico (no para cifras). */
export function formatoCompacto(micros: bigint): string {
  const negativo = micros < 0n
  const abs = negativo ? -micros : micros
  const decimas = (valor: bigint, unidad: bigint) => {
    const d = (abs * 10n) / (valor * unidad)
    const entero = d / 10n
    const resto = d % 10n
    return resto === 0n ? `${entero}` : `${entero}.${resto}`
  }
  let texto: string
  if (abs >= 1_000_000n * MICROS) texto = `${decimas(1_000_000n, MICROS)}M`
  else if (abs >= 1_000n * MICROS) texto = `${decimas(1_000n, MICROS)}K`
  else texto = `${abs / MICROS}`
  return negativo && abs !== 0n ? `-${texto}` : texto
}

export interface SerieComparativo {
  id: 'budget' | 'estAct' | 'previo'
  nombre: string
  valores: bigint[]
}

/**
 * Las series del gráfico "Comparativo anual", solo las que traen los doce meses con dato: una serie
 * incompleta no se dibuja (nunca se completa con ceros).
 */
export function seriesComparativo(
  totales: readonly (bigint | null)[],
  estAct: readonly (bigint | null)[],
  previo: readonly (bigint | null)[],
): SerieComparativo[] {
  const candidatas: [SerieComparativo['id'], string, readonly (bigint | null)[]][] = [
    ['budget', 'Budget', totales],
    ['estAct', 'Est-Act año previo', estAct],
    ['previo', 'Budget año previo', previo],
  ]
  const salida: SerieComparativo[] = []
  for (const [id, nombre, vals] of candidatas) {
    if (vals.length > 0 && vals.every((v) => v !== null)) salida.push({ id, nombre, valores: vals as bigint[] })
  }
  return salida
}

/** Marcas «redondas» del eje Y desde 0 hasta cubrir `maximo` (en micros). Siempre incluye 0. */
export function marcasEje(maximo: bigint, cuantas = 4): bigint[] {
  if (maximo <= 0n) return [0n]
  const bruto = maximo / BigInt(cuantas)
  let paso = MICROS
  while (paso * 10n <= bruto) paso *= 10n
  for (const m of [1n, 2n, 2n, 5n, 10n]) {
    // 1, 2, 5, 10 × potencia de 10: el primero que alcance
    if (paso * m * BigInt(cuantas) >= maximo) {
      paso = paso * m
      break
    }
  }
  const marcas: bigint[] = []
  for (let v = 0n; v < maximo + paso; v += paso) marcas.push(v)
  return marcas
}

const MESES_CORTOS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
/** «2026-07» -> «Jul 26». */
export const etiquetaMes = (periodo: string) => `${MESES_CORTOS[Number(periodo.slice(5, 7)) - 1]} ${periodo.slice(2, 4)}`

/** Suma corrida de los mismos valores mensuales: el último punto es el total anual de la serie. */
export function acumuladoDe(valores: readonly bigint[]): bigint[] {
  let corrido = 0n
  return valores.map((v) => (corrido += v))
}

/** Marca del eje Y: «0», «500K», «1.0M», «1.5M» (en millones siempre con un decimal). */
export function formatoEje(micros: bigint): string {
  const negativo = micros < 0n
  const abs = negativo ? -micros : micros
  let texto: string
  if (abs >= 1_000_000n * MICROS) {
    const decimas = (abs * 10n) / (1_000_000n * MICROS)
    texto = `${decimas / 10n}.${decimas % 10n}M`
  } else if (abs >= 1_000n * MICROS) texto = `${abs / (1_000n * MICROS)}K`
  else texto = `${abs / MICROS}`
  return negativo && abs !== 0n ? `-${texto}` : texto
}

export interface BarraVariacion {
  indice: number
  valor: bigint
  signo: 'pos' | 'neg' | 'cero'
}

/** Barras de la banda de variación: solo los meses con dato (un mes sin dato no lleva barra). */
export function barrasVariacion(variacion: readonly (bigint | null)[]): BarraVariacion[] {
  const salida: BarraVariacion[] = []
  variacion.forEach((v, indice) => {
    if (v === null) return
    salida.push({ indice, valor: v, signo: v > 0n ? 'pos' : v < 0n ? 'neg' : 'cero' })
  })
  return salida
}

/** Magnitud máxima (en micros, positiva) para escalar una banda divergente; 0 si no hay barras. */
export function escalaSimetrica(barras: readonly BarraVariacion[]): bigint {
  return barras.reduce((m, b) => {
    const a = b.valor < 0n ? -b.valor : b.valor
    return a > m ? a : m
  }, 0n)
}

/** Índice del mes más cercano a la posición `x` (pixeles) en un eje que va de `izq` a `der` con `n` meses. */
export function mesDesdeX(x: number, izq: number, der: number, n: number): number {
  if (n <= 1 || der <= izq) return 0
  const t = (x - izq) / (der - izq)
  return Math.min(n - 1, Math.max(0, Math.round(t * (n - 1))))
}

/** Índices del mes máximo y mínimo (ignora los `null`); sin picos si hay menos de dos datos o todos son iguales. */
export function extremosDe(valores: readonly (bigint | null)[]): { max: number | null; min: number | null } {
  let max: number | null = null
  let min: number | null = null
  let validos = 0
  valores.forEach((v, i) => {
    if (v === null) return
    validos++
    if (max === null || v > (valores[max] as bigint)) max = i
    if (min === null || v < (valores[min] as bigint)) min = i
  })
  if (validos < 2 || max === null || min === null || valores[max] === valores[min]) return { max: null, min: null }
  return { max, min }
}

/** Nivel del mapa de calor (0 = sin dato o cero; 1–4 = intensidad) según |valor| / máximo. */
export function nivelCalor(valor: bigint | null, maximoAbs: bigint): 0 | 1 | 2 | 3 | 4 {
  if (valor === null || valor === 0n || maximoAbs <= 0n) return 0
  const abs = valor < 0n ? -valor : valor
  const cuarto = (abs * 4n + maximoAbs - 1n) / maximoAbs // 1..4 (redondeo hacia arriba)
  return (cuarto > 4n ? 4 : cuarto < 1n ? 1 : Number(cuarto)) as 1 | 2 | 3 | 4
}

/** Ancho de una mini-barra en % (entero 0–100); `null` o negativo no dibujan barra. */
export function porcentajeBarra(valor: bigint | null, maximo: bigint): number {
  if (valor === null || valor <= 0n || maximo <= 0n) return 0
  const p = Number((valor * 100n) / maximo)
  return Math.min(100, Math.max(0, p))
}

/** ¿La fracción (en micros, 1.0 = 100 %) supera el umbral? Sin dato no supera nada. */
export function superaUmbral(fraccion: bigint | null, umbral: bigint): boolean {
  return fraccion !== null && fraccion > umbral
}
