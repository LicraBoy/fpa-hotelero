// Cálculo del Budget en pantalla. Funciones puras (se prueban sin navegador). Los importes del
// Budget llegan con hasta 6 decimales y se manejan como enteros en MICROS (BigInt): nunca `number`.

const MICROS = 1_000_000n
const PATRON = /^(-?)(\d+)(?:\.(\d{1,6}))?$/
const MAXIMO = 10n ** 12n * MICROS // el mismo tope que el servidor (un billón)

/** "1234.5" -> 1234500000n. `null` si el texto no es un importe válido (o pasa del tope). */
export function aMicros(texto: string): bigint | null {
  const m = PATRON.exec(texto.trim().replace(/,/g, ''))
  if (!m) return null
  const micros = BigInt(m[2]) * MICROS + BigInt((m[3] ?? '').padEnd(6, '0'))
  if (micros > MAXIMO) return null
  return m[1] ? -micros : micros
}

/** 1234500000n -> "1234.5" (sin ceros sobrantes ni separadores: es lo que se envía a la API). */
export function textoDeMicros(micros: bigint): string {
  const negativo = micros < 0n
  const absoluto = negativo ? -micros : micros
  const enteros = (absoluto / MICROS).toString()
  const decimales = (absoluto % MICROS).toString().padStart(6, '0').replace(/0+$/, '')
  return `${negativo ? '-' : ''}${enteros}${decimales ? `.${decimales}` : ''}`
}

/** Importe para mostrar: 2 decimales (redondeo al más cercano, mitades hacia afuera) y miles. */
export function formatoMicros(micros: bigint | null): string {
  if (micros === null) return '—'
  const negativo = micros < 0n
  const absoluto = negativo ? -micros : micros
  const centavos = (absoluto + 5_000n) / 10_000n
  const texto = centavos.toString().padStart(3, '0')
  const enteros = texto.slice(0, -2).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return `${negativo && centavos !== 0n ? '-' : ''}${enteros}.${texto.slice(-2)}`
}

export interface Regla {
  linea_id: number
  componentes: { linea_id: number; signo: number }[]
}

/**
 * Valor de las líneas con regla de suma (totales y subtotales) a partir de las líneas base. Como en
 * el servidor, si una línea tiene regla manda la regla; un componente sin valor cuenta 0. Una línea
 * sin ningún dato en ninguno de sus componentes queda sin valor (`null`), no en cero.
 */
export function completarConTotales(
  reglas: readonly Regla[],
  base: ReadonlyMap<number, bigint>,
): Map<number, bigint | null> {
  const porLinea = new Map(reglas.map((r) => [r.linea_id, r]))
  const memo = new Map<number, bigint | null>()
  const enCurso = new Set<number>()

  function valor(linea: number): bigint | null {
    const regla = porLinea.get(linea)
    if (!regla) return base.get(linea) ?? null
    if (memo.has(linea)) return memo.get(linea) ?? null
    if (enCurso.has(linea)) return null // un ciclo no debería existir: no se calcula
    enCurso.add(linea)
    let total = 0n
    let hayDato = false
    for (const c of regla.componentes) {
      const v = valor(c.linea_id)
      if (v !== null) {
        total += BigInt(c.signo) * v
        hayDato = true
      }
    }
    enCurso.delete(linea)
    const resultado = hayDato ? total : null
    memo.set(linea, resultado)
    return resultado
  }

  const salida = new Map<number, bigint | null>()
  for (const linea of base.keys()) salida.set(linea, base.get(linea) ?? null)
  for (const regla of reglas) salida.set(regla.linea_id, valor(regla.linea_id))
  return salida
}

/** Clave de una celda editable: línea y mes. */
export const claveCelda = (linea: number, periodo: string) => `${linea}|${periodo}`

/**
 * Importe de referencia × (1 + porcentaje/100), a 2 decimales (redondeo al más cercano). El
 * porcentaje se da en centésimas de punto (p. ej. "5" o "-2.5"); `null` si no es válido.
 */
export function ajustarPorcentaje(micros: bigint, porcentaje: string): bigint | null {
  const p = aMicros(porcentaje === '' ? '0' : porcentaje)
  if (p === null) return null
  const ajustado = (micros * (100n * MICROS + p)) / (100n * MICROS)
  // a centavos (10_000 micros), con redondeo hacia afuera
  const signo = ajustado < 0n ? -1n : 1n
  const absoluto = ajustado < 0n ? -ajustado : ajustado
  return signo * ((absoluto + 5_000n) / 10_000n) * 10_000n
}

export interface CeldaPendiente {
  linea_id: number
  periodo: string
  importe: string
}

/**
 * Cambios a guardar: las celdas editadas cuyo valor difiere del Budget actual. Devuelve también las
 * celdas con texto no válido, para avisarlas antes de enviar.
 */
export function cambiosPendientes(
  ediciones: ReadonlyMap<string, string>,
  actuales: ReadonlyMap<string, bigint | null>,
): { cambios: CeldaPendiente[]; invalidas: string[] } {
  const cambios: CeldaPendiente[] = []
  const invalidas: string[] = []
  for (const [clave, texto] of ediciones) {
    const [linea, periodo] = clave.split('|')
    if (texto.trim() === '') continue // celda vaciada: se deja como estaba
    const micros = aMicros(texto)
    if (micros === null) {
      invalidas.push(clave)
      continue
    }
    if (actuales.get(clave) === micros) continue
    cambios.push({ linea_id: Number(linea), periodo, importe: textoDeMicros(micros) })
  }
  return { cambios, invalidas }
}

/** `2026-08` -> `2026/27`: el año fiscal va de julio a junio (se confirma con Contraloría). */
export function etiquetaAnoFiscal(periodo: string): string {
  const [anio, mes] = periodo.split('-').map(Number)
  const inicio = mes >= 7 ? anio : anio - 1
  return `${inicio}/${String((inicio + 1) % 100).padStart(2, '0')}`
}

/** Agrupa líneas consecutivas por sección, conservando el orden del reporte. */
export function agruparPorSeccionId<T extends { seccion_id: number | null }>(
  lineas: readonly T[],
): { seccionId: number | null; lineas: T[] }[] {
  const grupos: { seccionId: number | null; lineas: T[] }[] = []
  for (const linea of lineas) {
    const ultimo = grupos.at(-1)
    if (ultimo && ultimo.seccionId === linea.seccion_id) ultimo.lineas.push(linea)
    else grupos.push({ seccionId: linea.seccion_id, lineas: [linea] })
  }
  return grupos
}
