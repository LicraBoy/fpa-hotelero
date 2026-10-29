// Partidas de una cuenta del Budget (p. ej. *Other Fringe* de Mgmt & Check In): cantidad, unidad y costo;
// el **costo extendido = cantidad × costo**; se reparte por mes (`mensual`: el extendido entre 12, con el
// residuo en los primeros meses; `estacional`: meses capturados; `importada`: meses del Excel). Funciones
// puras en MICROS (BigInt), gemelas de `fpa/servicios/presupuesto_partidas.py`; nunca `number` para dinero.

import { aMicros, textoDeMicros } from './calculo.ts'
import { multiplicarMicros } from './detalleCuenta.ts'

export type MetodoPartida = 'mensual' | 'estacional' | 'importada'

/** Lo que se edita de una partida: todo en texto, como lo escribe el usuario (se valida al guardar). */
export interface PartidaEditable {
  /** `null` si es una partida nueva que aún no se guarda. */
  id: number | null
  concepto: string
  cantidad: string
  unidad: string
  costo: string
  metodo: MetodoPartida
  /** 12 importes (solo cuentan en `estacional` e `importada`). */
  meses: string[]
}

export interface PartidaApi {
  id?: number | null
  concepto: string
  cantidad: string
  unidad: string | null
  costo: string
  metodo: string
  meses: string[]
}

const MESES = 12

const SECCIONES_CON_PARTIDAS = new Set(['mgmtcheckin', 'accounting', 'maidlinen', 'apartmentinterior', 'commonarea', 'utilities', 'owneractivities', 'othertaxesfeesandinsurance', 'ownerservices', 'purchasing', 'telephones', 'travelagency', 'store', 'cafeteria', 'bar', 'moneyexchange', 'restaurant', 'legal', 'itsystems'])

/** Secciones cuyas cuentas pueden capturarse por partidas (Mgmt & Check In, Accounting, Maid & Linen, Apartment Interior y Common Area). */
export const seccionAdmitePartidas = (descripcion: string | null | undefined): boolean =>
  descripcion != null && SECCIONES_CON_PARTIDAS.has(descripcion.toLowerCase().replace(/[^a-z0-9]/g, ''))
const MAX_PARTIDAS = 200

/** `cantidad × costo` en micros; `null` si falta o no es un número. */
export function extendidoDe(cantidad: string, costo: string): bigint | null {
  const q = cantidad.trim() === '' ? null : aMicros(cantidad)
  const c = costo.trim() === '' ? null : aMicros(costo)
  return q === null || c === null ? null : multiplicarMicros(q, c)
}

/** El extendido entre 12 meses; el residuo (en micros) va a los primeros meses: la suma siempre cierra. */
export function repartirMensual(extendido: bigint): bigint[] {
  const doce = BigInt(MESES)
  const base = extendido / doce // BigInt trunca hacia cero
  const resto = Number(extendido - base * doce)
  return Array.from({ length: MESES }, (_, i) => base + (i < resto ? 1n : 0n))
}

/** Los 12 meses de la partida en micros, o `null` si algún mes falta o no es válido. */
export function mesesDe(p: PartidaEditable): bigint[] | null {
  if (p.metodo === 'mensual') {
    const e = extendidoDe(p.cantidad, p.costo)
    return e === null ? null : repartirMensual(e)
  }
  const meses = p.meses.map((m) => (m.trim() === '' ? 0n : aMicros(m)))
  return meses.length === MESES && meses.every((m) => m !== null) ? (meses as bigint[]) : null
}

/** Un centavo en micros: el Excel guarda sus meses con ruido de coma flotante y costos con más decimales; por debajo, la suma cuadra. */
export const TOLERANCIA_SUMA_MICROS = 10_000n

/** `true` si la diferencia de `controlSuma` cabe en la tolerancia (se muestra como «Cuadra»). */
export const sumaCuadra = (control: bigint): boolean =>
  control > -TOLERANCIA_SUMA_MICROS && control < TOLERANCIA_SUMA_MICROS

/** Suma de los meses menos el extendido: 0 = cuadra, <0 = falta distribuir, >0 = excede. `null` si no se puede calcular. */
export function controlSuma(p: PartidaEditable): bigint | null {
  const e = extendidoDe(p.cantidad, p.costo)
  const m = mesesDe(p)
  if (e === null || m === null) return null
  return m.reduce((s, x) => s + x, 0n) - e
}

export function distribucionDe(partidas: readonly PartidaEditable[]): (bigint | null)[] {
  const todas = partidas.map(mesesDe)
  if (todas.some((m) => m === null)) return Array(MESES).fill(null)
  return Array.from({ length: MESES }, (_, i) => todas.reduce((s, m) => s + (m as bigint[])[i], 0n))
}

export function partidaDesdeApi(p: PartidaApi): PartidaEditable {
  return {
    id: p.id ?? null,
    concepto: p.concepto,
    cantidad: quitarCeros(p.cantidad),
    unidad: p.unidad ?? '',
    costo: quitarCeros(p.costo),
    metodo: (['mensual', 'estacional', 'importada'].includes(p.metodo) ? p.metodo : 'estacional') as MetodoPartida,
    meses: p.meses.map(quitarCeros),
  }
}

/** «12.000000» -> «12»; «0.500000» -> «0.5» (los importes de la API traen 6 decimales). */
function quitarCeros(texto: string): string {
  const m = aMicros(texto)
  return m === null ? texto : textoDeMicros(m)
}

export function partidaNueva(): PartidaEditable {
  return { id: null, concepto: '', cantidad: '1', unidad: '', costo: '', metodo: 'mensual', meses: Array(MESES).fill('') }
}

export interface ErrorPartida {
  campo: 'concepto' | 'cantidad' | 'unidad' | 'costo' | 'meses'
  texto: string
}

/** Problemas que impiden guardar la partida (la diferencia de la suma es un aviso aparte, no un error). */
export function erroresDePartida(p: PartidaEditable): ErrorPartida[] {
  const e: ErrorPartida[] = []
  if (p.concepto.trim() === '' || p.concepto.trim().length > 120) {
    e.push({ campo: 'concepto', texto: 'El concepto va de 1 a 120 caracteres' })
  }
  if (p.unidad.trim().length > 20) e.push({ campo: 'unidad', texto: 'La unidad admite hasta 20 caracteres' })
  for (const campo of ['cantidad', 'costo'] as const) {
    const v = p[campo].trim() === '' ? null : aMicros(p[campo])
    if (v === null) e.push({ campo, texto: `Falta ${campo === 'cantidad' ? 'la cantidad' : 'el costo'} o no es un número` })
    else if (v < 0n) e.push({ campo, texto: `${campo === 'cantidad' ? 'La cantidad' : 'El costo'} no puede ser negativo` })
  }
  if (p.metodo !== 'mensual') {
    p.meses.forEach((m, i) => {
      const v = m.trim() === '' ? 0n : aMicros(m)
      if (v === null || v < 0n) e.push({ campo: 'meses', texto: `El mes ${i + 1} no es un importe válido` })
    })
  }
  return e
}

/** El cuerpo del `PUT …/partidas`: todas las partidas y la inflación (12 fracciones) juntas. */
export function cuerpoPartidas(
  partidas: readonly PartidaEditable[],
  inflacion: Record<string, string>,
): { partidas: Record<string, unknown>[]; inflacion: Record<string, string> } | { error: string } {
  if (partidas.length === 0) return { error: 'La cuenta necesita al menos una partida' }
  if (partidas.length > MAX_PARTIDAS) return { error: `Una cuenta admite hasta ${MAX_PARTIDAS} partidas` }
  for (const p of partidas) {
    const err = erroresDePartida(p)
    if (err.length > 0) return { error: `${p.concepto.trim() || 'Una partida'}: ${err[0].texto}` }
  }
  return {
    partidas: partidas.map((p) => ({
      concepto: p.concepto.trim(),
      cantidad: textoDeMicros(aMicros(p.cantidad) ?? 0n),
      unidad: p.unidad.trim() === '' ? null : p.unidad.trim(),
      costo: textoDeMicros(aMicros(p.costo) ?? 0n),
      metodo: p.metodo,
      ...(p.metodo === 'mensual' ? {} : { meses: p.meses.map((m) => textoDeMicros(m.trim() === '' ? 0n : (aMicros(m) ?? 0n))) }),
    })),
    inflacion,
  }
}

/** ¿Cambió algo de la partida respecto de la guardada? (compara lo que se ve, no el formato). */
export function partidaCambio(a: PartidaEditable, b: PartidaEditable): boolean {
  return (
    a.concepto !== b.concepto ||
    a.cantidad !== b.cantidad ||
    a.unidad !== b.unidad ||
    a.costo !== b.costo ||
    a.metodo !== b.metodo ||
    (a.metodo !== 'mensual' && a.meses.some((m, i) => m !== b.meses[i]))
  )
}
