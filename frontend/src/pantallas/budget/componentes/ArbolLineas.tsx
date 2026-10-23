import type { components } from '../../../api/schema'
import type { LineaEdicionBudget } from '../../../api/tipos'
import { claveCelda, formatoMicros, sumarMicros } from '../calculo'

type LineaCaptura = components['schemas']['LineaCapturaSalida']

interface Grupo {
  seccionId: number | null
  lineas: LineaEdicionBudget[]
}

interface Props {
  grupos: Grupo[]
  nombreSeccion: ReadonlyMap<number, string>
  periodos: string[]
  budget: ReadonlyMap<string, bigint | null>
  objetivoPorLinea: ReadonlyMap<number, LineaCaptura>
  seleccionada: number | null
  onSeleccionar: (lineaId: number) => void
}

/**
 * Árbol de líneas por sección (spec §5.1): navegación compacta para elegir la línea a capturar en
 * `DetalleCapturaLinea`, sin duplicar el filtrado — recibe los mismos `grupos` ya filtrados que usa
 * la tabla. No es una segunda tabla: solo el anual y, si hay objetivo, su diferencia.
 */
export function ArbolLineas({
  grupos,
  nombreSeccion,
  periodos,
  budget,
  objetivoPorLinea,
  seleccionada,
  onSeleccionar,
}: Props) {
  return (
    <nav className="arbol-lineas" aria-label="Líneas por sección">
      {grupos.map((g) => (
        <details key={`${g.seccionId}-${g.lineas[0]?.linea_id}`} open>
          <summary>{g.seccionId === null ? 'Sin sección' : (nombreSeccion.get(g.seccionId) ?? 'Sin sección')}</summary>
          <ul className="arbol-lineas-lista">
            {g.lineas.map((l) => {
              const anual = sumarMicros(periodos.map((per) => budget.get(claveCelda(l.linea_id, per)) ?? null))
              const captura = objetivoPorLinea.get(l.linea_id)
              const objetivo = captura?.objetivo ?? null
              return (
                <li key={l.linea_id}>
                  <button
                    type="button"
                    className={`arbol-linea-boton${seleccionada === l.linea_id ? ' arbol-linea-activa' : ''}`}
                    aria-current={seleccionada === l.linea_id ? 'true' : undefined}
                    onClick={() => onSeleccionar(l.linea_id)}
                  >
                    <span className="arbol-linea-nombre">{l.descripcion}</span>
                    <span className="arbol-linea-cifras suave">
                      {formatoMicros(anual)}
                      {objetivo !== null && <> · obj. {objetivo}</>}
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        </details>
      ))}
      {grupos.length === 0 && <p className="suave">Ninguna línea coincide con el filtro.</p>}
    </nav>
  )
}
