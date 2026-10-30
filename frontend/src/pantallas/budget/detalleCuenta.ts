// Tabla interna de una cuenta del Budget (p. ej. *Other Income*): cada mes sale de una base y un
// factor (`importe = base × factor`, la base es el Est-Act del año previo) o de un monto fijo.
// Funciones puras, en MICROS (BigInt) como `calculo.ts`; nunca `number`. El redondeo calca al
// `Decimal.quantize` del servidor (mitades al par) para que lo que se ve sea lo que se guarda.

import { aMicros, textoDeMicros } from './calculo.ts'

const MICROS = 1_000_000n

export type MetodoCelda = 'factor' | 'fijo'

/** Una celda tal como se edita: todo texto, para poder mostrar lo que el usuario está escribiendo. */
export interface CeldaEditable {
  periodo: string
  metodo: MetodoCelda
  base: string
  factor: string
  montoFijo: string
}

/** Lo que devuelve la API para un mes. */
export interface CeldaApi {
  periodo: string
  metodo: string
  base: string | null
  factor: string | null
  monto_fijo: string | null
  importe: string
}

export interface CeldaEnvio {
  periodo: string
  metodo: MetodoCelda
  base?: string
  factor?: string
  monto_fijo?: string
}

/** Las secciones del reporte cuyas cuentas tienen tabla interna: *Other Income* y *Mgmt & Check In*. */
const SECCIONES_CON_TABLA = new Set(['otherincome', 'mgmtcheckin', 'accounting', 'maidlinen', 'apartmentinterior', 'commonarea', 'utilities', 'owneractivities', 'othertaxesfeesandinsurance', 'ownerservices', 'vdsallocationcollections', 'purchasing', 'telephones', 'travelagency', 'store', 'cafeteria', 'bar', 'moneyexchange', 'restaurant', 'legal', 'itsystems'])

const normalizar = (texto: string) => texto.toLowerCase().replace(/[^a-z0-9]/g, '')

export function seccionTieneTablaInterna(descripcionSeccion: string | null | undefined): boolean {
  return descripcionSeccion != null && SECCIONES_CON_TABLA.has(normalizar(descripcionSeccion))
}

/** `a * b / 1e6` redondeado al entero más cercano, las mitades al par (como `Decimal.quantize`). */
export function multiplicarMicros(a: bigint, b: bigint): bigint {
  const producto = a * b
  const negativo = producto < 0n
  const absoluto = negativo ? -producto : producto
  let cociente = absoluto / MICROS
  const resto = absoluto % MICROS
  const mitad = MICROS / 2n
  if (resto > mitad || (resto === mitad && cociente % 2n === 1n)) cociente += 1n
  return negativo ? -cociente : cociente
}

/** Importe del mes en micros, o `null` si faltan datos o alguno no es un número válido. */
export function importeDeCelda(c: CeldaEditable): bigint | null {
  if (c.metodo === 'fijo') return c.montoFijo.trim() === '' ? null : aMicros(c.montoFijo)
  if (c.base.trim() === '' || c.factor.trim() === '') return null
  const base = aMicros(c.base)
  const factor = aMicros(c.factor)
  return base === null || factor === null ? null : multiplicarMicros(base, factor)
}

export function importesDe(celdas: readonly CeldaEditable[]): (bigint | null)[] {
  return celdas.map(importeDeCelda)
}

/** Suma de los 12 meses; `null` si algún mes todavía no tiene importe. */
export function totalAnual(celdas: readonly CeldaEditable[]): bigint | null {
  let total = 0n
  for (const importe of importesDe(celdas)) {
    if (importe === null) return null
    total += importe
  }
  return total
}

/** «2000.000000» (la API guarda 6 decimales) -> «2000»; lo que no sea un importe se deja como está. */
function limpiar(texto: string | null): string {
  if (texto === null) return ''
  const micros = aMicros(texto)
  return micros === null ? texto : textoDeMicros(micros)
}

/** Celdas para editar: lo guardado en la API y, donde falte, base vacía con el factor por omisión. */
export function celdasDesdeApi(
  periodos: readonly string[],
  guardadas: readonly CeldaApi[],
  factorPorOmision: string,
): CeldaEditable[] {
  const porPeriodo = new Map(guardadas.map((g) => [g.periodo, g]))
  return periodos.map((periodo) => {
    const g = porPeriodo.get(periodo)
    if (!g) return { periodo, metodo: 'factor', base: '', factor: factorPorOmision, montoFijo: '' }
    return {
      periodo,
      metodo: g.metodo === 'fijo' ? 'fijo' : 'factor',
      base: limpiar(g.base),
      factor: g.factor === null ? factorPorOmision : limpiar(g.factor),
      montoFijo: limpiar(g.monto_fijo),
    }
  })
}

/** El mismo factor en todos los meses (los que eran montos fijos pasan a `base × factor`). */
export function aplicarFactorATodos(celdas: readonly CeldaEditable[], factor: string): CeldaEditable[] {
  return celdas.map((c) => ({ ...c, metodo: 'factor', factor }))
}

/** El cuerpo del `PUT .../detalle`, o el motivo por el que todavía no se puede guardar. */
export function aCuerpoApi(
  celdas: readonly CeldaEditable[],
): { celdas: CeldaEnvio[] } | { error: string } {
  const salida: CeldaEnvio[] = []
  for (const c of celdas) {
    if (importeDeCelda(c) === null) {
      return { error: `Falta o no es válido un dato de ${c.periodo}` }
    }
    if (c.metodo === 'fijo') {
      salida.push({ periodo: c.periodo, metodo: 'fijo', monto_fijo: textoDeMicros(aMicros(c.montoFijo) ?? 0n) })
    } else {
      salida.push({
        periodo: c.periodo,
        metodo: 'factor',
        base: textoDeMicros(aMicros(c.base) ?? 0n),
        factor: textoDeMicros(aMicros(c.factor) ?? 0n),
      })
    }
  }
  return { celdas: salida }
}

/** ¿Cambió algo respecto de lo guardado (o de la plantilla inicial)? */
export function hayCambios(a: readonly CeldaEditable[], b: readonly CeldaEditable[]): boolean {
  return a.some((c, i) => {
    const o = b[i]
    return !o || c.metodo !== o.metodo || c.base !== o.base || c.factor !== o.factor || c.montoFijo !== o.montoFijo
  })
}

/** Variación del Budget del mes contra su base (Est-Act): importe, diferencia y porcentaje. */
export interface VariacionMes {
  diferencia: bigint
  porcentaje: number | null
}

export function variacionContraBase(importe: bigint | null, base: string): VariacionMes | null {
  const b = base.trim() === '' ? null : aMicros(base)
  if (importe === null || b === null) return null
  const diferencia = importe - b
  const porcentaje = b === 0n ? null : Number((diferencia * 10_000n) / b) / 100
  return { diferencia, porcentaje }
}
