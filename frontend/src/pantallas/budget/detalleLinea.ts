// Cálculos del cajón «Panel de línea». Funciones puras en MICROS (BigInt), como `calculo.ts`
// (que no se toca): nunca `number` para dinero. Una línea informativa (p. ej. el tipo de cambio) no
// suma dinero: se promedia.

import { aMicros, formatoMicros } from './calculo.ts'

const MICROS = 1_000_000n

/** Promedio simple de los meses con dato (los vacíos no cuentan); `null` si ninguno tiene dato. */
export function promedioMicros(valores: readonly (bigint | null)[]): bigint | null {
  let suma = 0n
  let n = 0n
  for (const v of valores) {
    if (v === null) continue
    suma += v
    n += 1n
  }
  if (n === 0n) return null
  // Redondeo al más cercano, mitades hacia afuera (como `formatoMicros`).
  const doble = (suma * 2n) / n
  return doble >= 0n ? (doble + 1n) / 2n : (doble - 1n) / 2n
}

/** Cuántos meses traen dato. */
export function mesesConDato(valores: readonly (bigint | null)[]): number {
  return valores.filter((v) => v !== null).length
}

/** Importe con 4 decimales y miles, para tipos de cambio (17.2175). `—` si no hay dato. */
export function formatoCuatroDecimales(m: bigint | null): string {
  if (m === null) return '—'
  const negativo = m < 0n
  const abs = negativo ? -m : m
  const redondeado = (abs + 50n) / 100n // a 4 decimales
  const texto = redondeado.toString().padStart(5, '0')
  const enteros = texto.slice(0, -4).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return `${negativo && redondeado !== 0n ? '-' : ''}${enteros}.${texto.slice(-4)}`
}

export interface Frase {
  texto: string
  /** `sobre`: la propuesta pasa del objetivo; `bajo`: se queda corto; `igual`; `sin-objetivo`. */
  estado: 'sobre' | 'bajo' | 'igual' | 'sin-objetivo' | 'sin-propuesta'
}

/**
 * La diferencia contra el objetivo dicha en una frase. Es neutral: no dice si es favorable o no,
 * porque no hay una regla de negocio que lo defina.
 */
export function fraseDiferencia(objetivo: string | null, propuesta: bigint | null): Frase {
  const o = objetivo === null ? null : aMicros(objetivo)
  if (o === null) {
    return { texto: 'Define un objetivo para ver la diferencia.', estado: 'sin-objetivo' }
  }
  if (propuesta === null) {
    return { texto: 'Captura la propuesta para ver la diferencia.', estado: 'sin-propuesta' }
  }
  const diferencia = propuesta - o
  if (diferencia === 0n) return { texto: 'Coincide con el objetivo.', estado: 'igual' }
  const abs = diferencia < 0n ? -diferencia : diferencia
  const importe = `$${formatoMicros(abs)}`
  const baseAbs = o < 0n ? -o : o
  // Porcentaje a 2 decimales, redondeado al más cercano (no truncado)
  const pct = o === 0n ? '' : ` (${formatoPct((abs * 20_000n + baseAbs) / (baseAbs * 2n))} %)`
  return diferencia > 0n
    ? { texto: `Estás ${importe}${pct} por encima del objetivo.`, estado: 'sobre' }
    : { texto: `Estás ${importe}${pct} por debajo del objetivo.`, estado: 'bajo' }
}

/** 78 (centésimas de punto) -> «0.78». */
function formatoPct(centesimas: bigint): string {
  const texto = centesimas.toString().padStart(3, '0')
  return `${texto.slice(0, -2)}.${texto.slice(-2)}`
}

export { MICROS }
