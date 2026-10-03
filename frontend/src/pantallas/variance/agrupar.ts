import type { LineaVariance, SeccionVariance } from '../../api/tipos'

export interface GrupoSeccion {
  seccion: SeccionVariance | null // null: líneas que no pertenecen a ninguna sección
  lineas: LineaVariance[]
}

/**
 * Agrupa las líneas (ya en el orden del reporte) por su sección, conservando ese orden. Las líneas
 * sin sección (p. ej. el tipo de cambio) forman su propio grupo. Un grupo nuevo empieza cada vez que
 * cambia la sección, así que el orden original no se altera.
 */
export function agruparPorSeccion(
  lineas: LineaVariance[],
  secciones: SeccionVariance[],
): GrupoSeccion[] {
  const porId = new Map(secciones.map((s) => [s.id, s]))
  const grupos: GrupoSeccion[] = []
  for (const linea of lineas) {
    const seccion = linea.seccion_id === null ? null : (porId.get(linea.seccion_id) ?? null)
    const ultimo = grupos.at(-1)
    if (ultimo && (ultimo.seccion?.id ?? null) === (seccion?.id ?? null)) {
      ultimo.lineas.push(linea)
    } else {
      grupos.push({ seccion, lineas: [linea] })
    }
  }
  return grupos
}

const CERO = /^-?0+(\.0+)?$/

function esCero(texto: string | null): boolean {
  return texto === null || CERO.test(texto.trim())
}

/**
 * Una línea sin nada que mirar: de detalle o informativa, sin Actual y sin Presupuesto en ninguno de
 * los tres bloques. Los totales y subtotales nunca se consideran vacíos (se leen aunque valgan 0).
 */
export function esLineaVacia(linea: LineaVariance): boolean {
  if (linea.tipo === 'total' || linea.tipo === 'subtotal') return false
  return [linea.mes, linea.ytd, linea.anual].every((c) => esCero(c.actual) && esCero(c.budget))
}

/**
 * Quita de cada grupo las líneas vacías. Una sección que se queda sin líneas desaparece. Devuelve
 * también cuántas se quitaron, para avisarlo en pantalla (nunca se ocultan en silencio).
 */
export function sinLineasVacias(grupos: GrupoSeccion[]): { grupos: GrupoSeccion[]; ocultas: number } {
  let ocultas = 0
  const salida: GrupoSeccion[] = []
  for (const g of grupos) {
    const lineas = g.lineas.filter((l) => {
      const vacia = esLineaVacia(l)
      if (vacia) ocultas += 1
      return !vacia
    })
    if (lineas.length > 0) salida.push({ seccion: g.seccion, lineas })
  }
  return { grupos: salida, ocultas }
}

/**
 * Parte un texto en trozos marcando los que coinciden con `busqueda` (sin distinguir mayúsculas ni
 * acentos). Nunca arma HTML: la pantalla pinta cada trozo como texto.
 */
export function trozosResaltados(
  texto: string,
  busqueda: string,
): { texto: string; coincide: boolean }[] {
  const quitarAcentos = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '')
  const buscado = quitarAcentos(busqueda.trim()).toLowerCase()
  if (buscado === '') return [{ texto, coincide: false }]
  // normalizar letra por letra mantiene los índices alineados con el texto original
  const plano = Array.from(texto, (c) => quitarAcentos(c).toLowerCase()[0] ?? c).join('')
  const trozos: { texto: string; coincide: boolean }[] = []
  let desde = 0
  for (let i = plano.indexOf(buscado); i !== -1; i = plano.indexOf(buscado, desde)) {
    if (i > desde) trozos.push({ texto: texto.slice(desde, i), coincide: false })
    trozos.push({ texto: texto.slice(i, i + buscado.length), coincide: true })
    desde = i + buscado.length
  }
  if (desde < texto.length) trozos.push({ texto: texto.slice(desde), coincide: false })
  return trozos
}

/**
 * Etiquetas del índice de secciones. Varias secciones se llaman igual (el reporte repite «Store»,
 * «Bar»…): las repetidas llevan su número, «Store (1)», «Store (2)», para distinguirlas.
 */
export function etiquetasDeSecciones(nombres: readonly string[]): string[] {
  const total = new Map<string, number>()
  for (const n of nombres) total.set(n, (total.get(n) ?? 0) + 1)
  const visto = new Map<string, number>()
  return nombres.map((n) => {
    if ((total.get(n) ?? 0) < 2) return n
    const k = (visto.get(n) ?? 0) + 1
    visto.set(n, k)
    return `${n} (${k})`
  })
}

/** Id del ancla de una sección (para saltar a ella desde el índice). */
export const anclaDeSeccion = (id: number | null) => `seccion-${id ?? 'sin'}`
