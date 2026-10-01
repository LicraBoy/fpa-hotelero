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
