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

/** Clave de una celda de Actual capturado a mano: se distingue de las de Budget con «A|». */
export const claveActual = (linea: number, periodo: string) => `A|${linea}|${periodo}`

export interface ActualPendiente {
  linea_id: number
  periodo: string
  importe: string | null // null: borrar el valor capturado
}

/**
 * Actuales capturados a cambiar: los que difieren del valor vigente. Un texto vacío en una celda que
 * tenía valor lo borra; vacío en una que no tenía, no es un cambio. Devuelve también las celdas con
 * texto no válido.
 */
export function cambiosActualPendientes(
  ediciones: ReadonlyMap<string, string>,
  vigentes: ReadonlyMap<string, bigint | null>,
): { cambios: ActualPendiente[]; invalidas: string[] } {
  const cambios: ActualPendiente[] = []
  const invalidas: string[] = []
  for (const [clave, texto] of ediciones) {
    if (!clave.startsWith('A|')) continue
    const [, linea, periodo] = clave.split('|')
    const vigente = vigentes.get(claveCelda(Number(linea), periodo)) ?? null
    if (texto.trim() === '') {
      if (vigente !== null) cambios.push({ linea_id: Number(linea), periodo, importe: null })
      continue
    }
    const micros = aMicros(texto)
    if (micros === null) {
      invalidas.push(clave)
      continue
    }
    if (vigente === micros) continue
    cambios.push({ linea_id: Number(linea), periodo, importe: textoDeMicros(micros) })
  }
  return { cambios, invalidas }
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
    if (clave.startsWith('A|')) continue // los Actuales capturados van aparte
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

/**
 * Años fiscales que ya existen en el sistema (por las cargas vigentes y las versiones de Budget
 * guardadas), más reciente primero. Otras pantallas (p. ej. Presupuesto) los reusan: el año fiscal
 * no se vuelve a pedir a mano donde ya se conoce.
 */
export function anosFiscalesConocidos(
  cargas: readonly { estado: string; periodo: string }[],
  versiones: readonly { ano_fiscal: string }[],
): string[] {
  const salida = new Set<string>()
  for (const v of versiones) salida.add(v.ano_fiscal)
  for (const c of cargas) if (c.estado === 'vigente') salida.add(etiquetaAnoFiscal(c.periodo))
  return [...salida].sort().reverse()
}

/**
 * ¿La suma de los importes mensuales cuadra exactamente con el anual? `null` si el anual o algún
 * importe no es un número válido (se avisa aparte, no como "no cuadra").
 */
export function sumaCuadra(importes: Record<string, string>, anual: string): boolean | null {
  const anualMicros = aMicros(anual)
  if (anualMicros === null) return null
  let total = 0n
  for (const texto of Object.values(importes)) {
    const m = aMicros(texto === '' ? '0' : texto)
    if (m === null) return null
    total += m
  }
  return total === anualMicros
}

/** Suma de los importes mensuales como texto (para mostrarla junto al anual). `null` si alguno no es válido. */
export function sumaImportes(importes: Record<string, string>): string | null {
  let total = 0n
  for (const texto of Object.values(importes)) {
    const m = aMicros(texto === '' ? '0' : texto)
    if (m === null) return null
    total += m
  }
  return textoDeMicros(total)
}

/** Suma de valores en micros que puedan ser `null` (sin dato): si ninguno tiene dato, `null` (no un
 * cero inventado); los que sí tienen dato se suman, el resto cuenta como ausente, no como cero. */
export function sumarMicros(valores: readonly (bigint | null)[]): bigint | null {
  const con = valores.filter((v): v is bigint => v !== null)
  return con.length === 0 ? null : con.reduce((a, v) => a + v, 0n)
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

// --- Budget Studio: Resumen (etapa 1) ---------------------------------------

export interface DiferenciaObjetivo {
  diferenciaMicros: bigint | null
  estado: 'sobre' | 'bajo' | 'en-rango'
}

/**
 * Propuesta menos objetivo del ciclo, y su sentido neutral (sin favorable/desfavorable: no hay
 * regla de negocio que lo defina). `null` si alguna suma no es un importe válido.
 */
export function diferenciaVsObjetivo(sumaObjetivo: string, sumaPropuesta: string): DiferenciaObjetivo {
  const objetivo = aMicros(sumaObjetivo)
  const propuesta = aMicros(sumaPropuesta)
  if (objetivo === null || propuesta === null) return { diferenciaMicros: null, estado: 'en-rango' }
  const diferencia = propuesta - objetivo
  const estado = diferencia > 0n ? 'sobre' : diferencia < 0n ? 'bajo' : 'en-rango'
  return { diferenciaMicros: diferencia, estado }
}

export interface SerieSeccionChart {
  seccion: string
  /** Para graficar (Plotly no acepta BigInt): nunca usar esto para texto exacto, solo posición. */
  objetivo: number
  propuesta: number
  objetivoMicros: bigint
  propuestaMicros: bigint
  diferenciaMicros: bigint
  diferenciaPct: number | null
}

/**
 * Serie objetivo vs. propuesta por sección, a partir de `resumen.por_seccion` tal cual lo entrega
 * la API. El texto exacto (tooltip, tabla alterna) debe salir de los campos `*Micros` vía
 * `formatoMicros`, nunca de `objetivo`/`propuesta` (son `number`, solo para la posición del trazo).
 */
export function serieObjetivoVsPropuesta(
  porSeccion: readonly { seccion: string | null; suma_objetivo: string; suma_propuesta: string }[],
): SerieSeccionChart[] {
  return porSeccion.map((s) => {
    const objetivoMicros = aMicros(s.suma_objetivo) ?? 0n
    const propuestaMicros = aMicros(s.suma_propuesta) ?? 0n
    const diferenciaMicros = propuestaMicros - objetivoMicros
    const diferenciaPct =
      objetivoMicros !== 0n ? Number((diferenciaMicros * 10_000n) / objetivoMicros) / 100 : null
    return {
      seccion: s.seccion ?? 'Sin sección',
      objetivo: Number(objetivoMicros) / 1_000_000,
      propuesta: Number(propuestaMicros) / 1_000_000,
      objetivoMicros,
      propuestaMicros,
      diferenciaMicros,
      diferenciaPct,
    }
  })
}

export const ESTADOS_CICLO = ['borrador', 'enviado', 'revision', 'aprobado', 'bloqueado'] as const
export type EstadoCiclo = (typeof ESTADOS_CICLO)[number]
export type EstadoPaso = 'completado' | 'actual' | 'pendiente'

/**
 * Estado de un paso del stepper del ciclo respecto al estado real (`actual`). No asume un flujo
 * estrictamente lineal: si `actual` es una reapertura (p. ej. `aprobado` -> `borrador`), los pasos
 * posteriores a `actual` quedan `pendiente` aunque ya se hayan completado antes.
 */
export function estadoRelativo(paso: EstadoCiclo, actual: string): EstadoPaso {
  if (paso === actual) return 'actual'
  const iPaso = ESTADOS_CICLO.indexOf(paso)
  const iActual = ESTADOS_CICLO.indexOf(actual as EstadoCiclo)
  if (iActual === -1) return 'pendiente'
  return iPaso < iActual ? 'completado' : 'pendiente'
}

/** Cuántas secciones de `resumen.por_seccion` todavía tienen alguna línea sin capturar. */
export function seccionesIncompletas(
  porSeccion: readonly { total_lineas: number; lineas_capturadas: number }[],
): number {
  return porSeccion.filter((s) => s.lineas_capturadas < s.total_lineas).length
}

export interface DiferenciaLinea {
  linea_id: number
  descripcion: string
  seccion: string | null
  diferenciaMicros: bigint
}

/**
 * Las líneas con mayor desviación absoluta entre propuesta y objetivo (de las que tienen ambos
 * capturados), de mayor a menor — para el panel de "principales diferencias" del Resumen. Una
 * línea sin objetivo o sin propuesta no tiene una diferencia que mostrar: se excluye, no cuenta 0.
 */
export function principalesDiferencias(
  lineas: readonly {
    linea_id: number
    descripcion: string
    seccion: string | null
    objetivo: string | null
    propuesta_anual: string | null
  }[],
  limite = 5,
): DiferenciaLinea[] {
  const conDiferencia: DiferenciaLinea[] = []
  for (const l of lineas) {
    if (l.objetivo === null || l.propuesta_anual === null) continue
    const objetivo = aMicros(l.objetivo)
    const propuesta = aMicros(l.propuesta_anual)
    if (objetivo === null || propuesta === null) continue
    conDiferencia.push({
      linea_id: l.linea_id,
      descripcion: l.descripcion,
      seccion: l.seccion,
      diferenciaMicros: propuesta - objetivo,
    })
  }
  conDiferencia.sort((a, b) => {
    const absA = a.diferenciaMicros < 0n ? -a.diferenciaMicros : a.diferenciaMicros
    const absB = b.diferenciaMicros < 0n ? -b.diferenciaMicros : b.diferenciaMicros
    return absB > absA ? 1 : absB < absA ? -1 : 0
  })
  return conDiferencia.slice(0, limite)
}

/** num/den redondeado al entero más cercano, mitad al par (igual que `Decimal.quantize` de Python
 * sin un `rounding` explícito: es lo que usa el backend en `repartir()`). `den` > 0. */
function divisionMitadAlPar(num: bigint, den: bigint): bigint {
  const cociente = num / den // trunca hacia 0 (semántica de BigInt)
  const resto = num % den // mismo signo que `num`, |resto| < den
  const dosResto = (resto < 0n ? -resto : resto) * 2n
  if (dosResto < den) return cociente
  const signo = num < 0n ? -1n : 1n
  if (dosResto > den) return cociente + signo
  return cociente % 2n === 0n ? cociente : cociente + signo
}

/**
 * Reparte `anual` (en micros) según `pesos` (12 textos que deben sumar 1.000000, como los trae
 * `PerfilSalida`): calca `repartir()` del backend (`presupuesto_distribucion.py`) al micro, para que
 * la vista previa del perfil nunca difiera de lo que de verdad se va a guardar. El residuo de
 * redondeo se suma al último mes con peso distinto de cero. `null` si los pesos no son 12 textos
 * válidos (no se valida aquí que sumen 1: eso ya lo garantiza el backend al crear el perfil).
 */
export function repartirConPerfil(anual: bigint, pesos: readonly string[]): bigint[] | null {
  if (pesos.length !== 12) return null
  const pesosMicros = pesos.map((p) => aMicros(p))
  if (pesosMicros.some((p) => p === null)) return null
  const pesosValidos = pesosMicros as bigint[]
  const importes = pesosValidos.map((peso) => divisionMitadAlPar(anual * peso, MICROS))
  const suma = importes.reduce((a, b) => a + b, 0n)
  const diferencia = anual - suma
  if (diferencia !== 0n) {
    let indice = pesosValidos.length - 1
    while (indice >= 0 && pesosValidos[indice] === 0n) indice -= 1
    if (indice < 0) indice = pesosValidos.length - 1
    importes[indice] += diferencia
  }
  return importes
}

export interface DiferenciaVersion {
  linea_id: number
  anualA: bigint | null
  anualB: bigint | null
  diferenciaMicros: bigint | null
}

/**
 * Compara el anual de cada línea entre dos versiones de Budget (spec §7, "Time Machine"). Une las
 * líneas de ambas versiones (una línea que solo aparece en una de las dos trae `null` del otro
 * lado, nunca un cero inventado); la diferencia solo se calcula cuando ambos lados tienen dato.
 */
export function compararVersiones(
  base: readonly { linea_id: number; anual: string | null }[],
  comparar: readonly { linea_id: number; anual: string | null }[],
): DiferenciaVersion[] {
  const porLineaB = new Map(comparar.map((l) => [l.linea_id, l.anual]))
  const vistos = new Set<number>()
  const salida: DiferenciaVersion[] = []

  function fila(linea_id: number, anualATexto: string | null, anualBTexto: string | null): DiferenciaVersion {
    const anualA = anualATexto === null ? null : aMicros(anualATexto)
    const anualB = anualBTexto === null ? null : aMicros(anualBTexto)
    return {
      linea_id,
      anualA,
      anualB,
      diferenciaMicros: anualA !== null && anualB !== null ? anualB - anualA : null,
    }
  }

  for (const l of base) {
    vistos.add(l.linea_id)
    salida.push(fila(l.linea_id, l.anual, porLineaB.get(l.linea_id) ?? null))
  }
  for (const l of comparar) {
    if (vistos.has(l.linea_id)) continue
    salida.push(fila(l.linea_id, null, l.anual))
  }
  return salida
}

/**
 * Calcula la variación porcentual entre dos importes en micros: (comparar - base) / |base| * 100.
 * `null` si alguno es null, o si la base es 0n (evita división por cero y ambigüedad de denominador nulo).
 */
export function variacionPorcentual(base: bigint | null, comparar: bigint | null): number | null {
  if (base === null || comparar === null || base === 0n) return null
  const diferencia = comparar - base
  const absBase = base < 0n ? -base : base
  return Number((diferencia * 10_000n) / absBase) / 100
}

export type TipoCambioVersion = 'nueva' | 'eliminada' | 'modificada' | 'sin_cambio' | 'incompleta'

/**
 * Clasifica la naturaleza del cambio entre dos versiones de Budget para una línea.
 */
export function clasificarCambioVersion(anualA: bigint | null, anualB: bigint | null): TipoCambioVersion {
  if (anualA === null && anualB !== null) return 'nueva'
  if (anualA !== null && anualB === null) return 'eliminada'
  if (anualA === null && anualB === null) return 'incompleta'
  return anualA === anualB ? 'sin_cambio' : 'modificada'
}

export interface DiferenciaVersionDetallada extends DiferenciaVersion {
  tipo: TipoCambioVersion
  diferenciaPct: number | null
}

/**
 * Comparación enriquecida entre dos versiones con clasificación de cambio y porcentaje de variación.
 */
export function compararVersionesDetallado(
  base: readonly { linea_id: number; anual: string | null }[],
  comparar: readonly { linea_id: number; anual: string | null }[],
): DiferenciaVersionDetallada[] {
  const basicas = compararVersiones(base, comparar)
  return basicas.map((d) => ({
    ...d,
    tipo: clasificarCambioVersion(d.anualA, d.anualB),
    diferenciaPct: variacionPorcentual(d.anualA, d.anualB),
  }))
}

export interface TotalesControlComparacion {
  totalA: bigint | null
  totalB: bigint | null
  diferenciaNeta: bigint | null
  diferenciaPct: number | null
  conteoTotal: number
  conteoNuevas: number
  conteoEliminadas: number
  conteoModificadas: number
  conteoSinCambio: number
}

/**
 * Totales consolidados de control para facilitar la conciliación entre versiones.
 */
export function calcularTotalesComparacion(
  filas: readonly { anualA: bigint | null; anualB: bigint | null; tipo?: TipoCambioVersion }[],
): TotalesControlComparacion {
  let conA = 0
  let conB = 0
  let totalA = 0n
  let totalB = 0n
  let conteoNuevas = 0
  let conteoEliminadas = 0
  let conteoModificadas = 0
  let conteoSinCambio = 0

  for (const f of filas) {
    if (f.anualA !== null) {
      totalA += f.anualA
      conA++
    }
    if (f.anualB !== null) {
      totalB += f.anualB
      conB++
    }
    const tipo = f.tipo ?? clasificarCambioVersion(f.anualA, f.anualB)
    if (tipo === 'nueva') conteoNuevas++
    else if (tipo === 'eliminada') conteoEliminadas++
    else if (tipo === 'modificada') conteoModificadas++
    else if (tipo === 'sin_cambio') conteoSinCambio++
  }

  const finalTotalA = conA > 0 ? totalA : null
  const finalTotalB = conB > 0 ? totalB : null
  const diferenciaNeta = finalTotalA !== null && finalTotalB !== null ? finalTotalB - finalTotalA : null
  const diferenciaPct = variacionPorcentual(finalTotalA, finalTotalB)

  return {
    totalA: finalTotalA,
    totalB: finalTotalB,
    diferenciaNeta,
    diferenciaPct,
    conteoTotal: filas.length,
    conteoNuevas,
    conteoEliminadas,
    conteoModificadas,
    conteoSinCambio,
  }
}
