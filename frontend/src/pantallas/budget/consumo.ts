// Cuentas de consumo del Budget (Diesel, Gas, Electricity, Water): por mes, unidades (Lts/Kwh/M3) × costo
// unitario = total, en cuatro bloques como la hoja del Excel. Solo el bloque «Budget» se edita. Funciones
// puras en MICROS (BigInt), gemelas de `fpa/servicios/presupuesto_consumo.py`; nunca `number` para dinero.

import { aMicros, formatoMicros } from './calculo.ts'
import { multiplicarMicros } from './detalleCuenta.ts'

export type BloqueConsumo = 'real_prev' | 'budget_prev' | 'est_act' | 'budget'

/** Un mes tal como lo trae la API: textos decimales o `null` si el Excel no lo traía. */
export interface MesConsumoApi {
  unidades: string | null
  costo_unitario: string | null
  total: string | null
}

/** Lo que el usuario edita de un mes del Budget (texto, como lo escribe). */
export interface MesEditable {
  unidades: string
  costo: string
}

/** Títulos de los 4 bloques según el año fiscal (`2026-07` → Budget 26/27, Budget 25/26, Real 24/25). */
export function titulosBloques(periodos: readonly string[]): Record<BloqueConsumo, string> {
  const anio = Number((periodos[0] ?? '2026-07').slice(2, 4))
  const par = (a: number) => `${String(a).padStart(2, '0')}/${String(a + 1).padStart(2, '0')}`
  return {
    real_prev: `Real ${par(anio - 2)}`,
    budget_prev: `Budget ${par(anio - 1)}`,
    est_act: `Est-Act ${String(anio - 1).padStart(2, '0')}-${String(anio).padStart(2, '0')}`,
    budget: `Budget ${par(anio)}`,
  }
}

const aMicrosONull = (t: string | null): bigint | null => (t === null || t.trim() === '' ? null : aMicros(t))

/** Texto decimal de la API a micros (`null` si falta o no es número). */
export const microsDe = (t: string | null): bigint | null => aMicrosONull(t)

/** `unidades × costo` en micros; `null` si falta alguno o no es un número. */
export function totalDeMes(unidades: string, costo: string): bigint | null {
  const u = aMicrosONull(unidades)
  const c = aMicrosONull(costo)
  return u === null || c === null ? null : multiplicarMicros(u, c)
}

/** Suma de un campo de los 12 meses (`null` si ninguno trae dato). */
export function sumaDe(valores: readonly (bigint | null)[]): bigint | null {
  const con = valores.filter((v): v is bigint => v !== null)
  return con.length === 0 ? null : con.reduce((s, v) => s + v, 0n)
}

/** Diferencia `a − b`, `null` si falta alguno. */
export const diferencia = (a: bigint | null, b: bigint | null): bigint | null => (a === null || b === null ? null : a - b)

/** `+1,234.50` / `-1,234.50` / `0.00` (el signo ayuda a leer variaciones). */
export function conSigno(m: bigint | null): string {
  if (m === null) return '—'
  return m > 0n ? `+${formatoMicros(m)}` : formatoMicros(m)
}

/** Costo unitario con 4 decimales (las tarifas traen más de 2: 24.9833). */
export function costoTexto(micros: bigint | null): string {
  if (micros === null) return '—'
  const negativo = micros < 0n
  const absoluto = negativo ? -micros : micros
  const diezmilesimas = (absoluto + 50n) / 100n
  const enteros = (diezmilesimas / 10_000n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return `${negativo ? '-' : ''}${enteros}.${(diezmilesimas % 10_000n).toString().padStart(4, '0')}`
}

/** ¿Cambió el mes respecto al original? Compara el valor numérico (no el texto). */
export function mesCambio(a: MesEditable, b: MesEditable): boolean {
  return aMicrosONull(a.unidades) !== aMicrosONull(b.unidades) || aMicrosONull(a.costo) !== aMicrosONull(b.costo)
}

export interface CuerpoConsumo {
  meses: { periodo: string; unidades: string; costo_unitario: string }[]
}

/** El cuerpo del PUT con solo los meses que cambiaron; `error` si algún mes no es válido. */
export function cuerpoConsumo(
  periodos: readonly string[],
  editados: readonly MesEditable[],
  originales: readonly MesEditable[],
): CuerpoConsumo | { error: string } {
  const meses: CuerpoConsumo['meses'] = []
  for (let i = 0; i < periodos.length; i++) {
    if (!mesCambio(editados[i], originales[i])) continue
    const u = aMicrosONull(editados[i].unidades)
    const c = aMicrosONull(editados[i].costo)
    if (u === null || c === null) return { error: `Revisa las unidades y el costo de ${periodos[i]}: deben ser números.` }
    if (u < 0n || c < 0n) return { error: `Las unidades y el costo de ${periodos[i]} no pueden ser negativos.` }
    meses.push({ periodo: periodos[i], unidades: editados[i].unidades.trim(), costo_unitario: editados[i].costo.trim() })
  }
  return meses.length === 0 ? { error: 'No hay cambios que guardar.' } : { meses }
}
