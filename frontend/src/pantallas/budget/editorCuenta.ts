// Lógica presentacional del Editor mensual: qué indicadores mostrar, cuántos
// cambios hay y qué errores de validación listar. Funciones puras en MICROS (BigInt); usan las de
// `detalleCuenta.ts` (que no se toca) y nunca recalculan un importe por su cuenta.

import { aMicros, formatoMicros, textoDeMicros } from './calculo.ts'
import {
  importeDeCelda,
  totalAnual,
  variacionContraBase,
  type CeldaEditable,
  type VariacionMes,
} from './detalleCuenta.ts'

const MESES_LARGOS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
const mesCorto = (periodo: string) => MESES_LARGOS[Number(periodo.slice(5, 7)) - 1]

/** «2026-07» … «2027-06» -> «Jul 2026 – Jun 2027». `null` si no hay periodos. */
export function rangoDePeriodos(periodos: readonly string[]): string | null {
  if (periodos.length === 0) return null
  const primero = periodos[0]
  const ultimo = periodos[periodos.length - 1]
  return `${mesCorto(primero)} ${primero.slice(0, 4)} – ${mesCorto(ultimo)} ${ultimo.slice(0, 4)}`
}

export interface ErrorCelda {
  periodo: string
  campo: 'base' | 'factor' | 'montoFijo'
  /** `invalido`: texto que no es un importe; `falta`: el mes no tiene el dato que su método pide. */
  tipo: 'invalido' | 'falta'
  texto: string
}

const vacio = (t: string) => t.trim() === ''
const invalido = (t: string) => !vacio(t) && aMicros(t) === null

/** Problemas de cada mes: textos inválidos y datos que faltan según el método elegido. */
export function erroresDeCeldas(celdas: readonly CeldaEditable[]): ErrorCelda[] {
  const salida: ErrorCelda[] = []
  for (const c of celdas) {
    if (invalido(c.base)) {
      salida.push({ periodo: c.periodo, campo: 'base', tipo: 'invalido', texto: 'La base no es un importe válido' })
    }
    if (c.metodo === 'factor') {
      if (invalido(c.factor)) {
        salida.push({ periodo: c.periodo, campo: 'factor', tipo: 'invalido', texto: 'El factor no es un número válido' })
      } else if (vacio(c.factor)) {
        salida.push({ periodo: c.periodo, campo: 'factor', tipo: 'falta', texto: 'Falta el factor' })
      }
      if (vacio(c.base)) {
        salida.push({ periodo: c.periodo, campo: 'base', tipo: 'falta', texto: 'Falta la base' })
      }
    } else if (invalido(c.montoFijo)) {
      salida.push({ periodo: c.periodo, campo: 'montoFijo', tipo: 'invalido', texto: 'El monto fijo no es un importe válido' })
    } else if (vacio(c.montoFijo)) {
      salida.push({ periodo: c.periodo, campo: 'montoFijo', tipo: 'falta', texto: 'Falta el monto fijo' })
    }
  }
  return salida
}

/** Para cada mes, si cambió respecto de lo guardado (cualquier campo). */
export function mesesModificados(celdas: readonly CeldaEditable[], inicial: readonly CeldaEditable[]): boolean[] {
  return celdas.map((c, i) => {
    const o = inicial[i]
    return !o || c.metodo !== o.metodo || c.base !== o.base || c.factor !== o.factor || c.montoFijo !== o.montoFijo
  })
}

/** Cuántos meses cambiaron respecto de lo guardado (cualquier campo). */
export function cambiosPorMes(celdas: readonly CeldaEditable[], inicial: readonly CeldaEditable[]): number {
  return mesesModificados(celdas, inicial).filter(Boolean).length
}

/**
 * Cómo se PINTA un campo cuando no tiene el foco (solo presentación; el valor guardado y enviado es el
 * texto tal cual). Importes: 2 decimales con separador de miles. Factor: nunca se trunca (mínimo 2
 * decimales). Vacío o inválido: el mismo texto.
 */
export function formatoCampo(texto: string, tipo: 'importe' | 'factor'): string {
  const micros = vacio(texto) ? null : aMicros(texto)
  if (micros === null) return texto
  if (tipo === 'importe') return formatoMicros(micros)
  const plano = textoDeMicros(micros)
  const [entero, decimales = ''] = plano.split('.')
  return `${entero}.${decimales.padEnd(2, '0')}`
}

export interface Indicadores {
  /** Suma de los doce meses; `null` si algún mes aún no tiene importe. */
  budgetAnual: bigint | null
  promedioMensual: bigint | null
  /** Suma de las bases (Est-Act previo); solo si **los doce meses** traen una base válida. */
  baseAnual: bigint | null
  /** Budget anual contra la base anual; solo si hay Budget y base completos. */
  variacion: VariacionMes | null
}

/**
 * Los indicadores del resumen, cada uno solo si sus datos son válidos y completos (si no, `null` y
 * la pantalla no lo muestra: nunca se rellena con ceros ni se suma una base a medias).
 */
export function indicadoresDe(celdas: readonly CeldaEditable[]): Indicadores {
  const total = totalAnual(celdas)
  const bases = celdas.map((c) => (vacio(c.base) ? null : aMicros(c.base)))
  const baseCompleta = bases.length > 0 && bases.every((b) => b !== null)
  const baseAnual = baseCompleta ? bases.reduce<bigint>((s, b) => s + (b ?? 0n), 0n) : null
  return {
    budgetAnual: total,
    promedioMensual: total === null ? null : total / BigInt(celdas.length),
    baseAnual,
    variacion: total !== null && baseAnual !== null ? variacionContraBase(total, textoDeMicros(baseAnual)) : null,
  }
}

/** Variación de un mes contra su base (para ambos métodos); `null` si no hay importe o base válidos. */
export function variacionDelMes(celda: CeldaEditable): VariacionMes | null {
  return variacionContraBase(importeDeCelda(celda), celda.base)
}

/** Clase de signo para los importes de variación: nunca solo color (el texto lleva +/−). */
export function claseSigno(diferencia: bigint | null): 'pos' | 'neg' | 'cero' {
  if (diferencia === null || diferencia === 0n) return 'cero'
  return diferencia > 0n ? 'pos' : 'neg'
}
