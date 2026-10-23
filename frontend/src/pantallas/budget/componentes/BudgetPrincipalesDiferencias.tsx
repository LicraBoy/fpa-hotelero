import type { components } from '../../../api/schema'
import { formatoMicros, principalesDiferencias } from '../calculo'

type LineaCaptura = components['schemas']['LineaCapturaSalida']

interface Props {
  lineas: readonly LineaCaptura[]
  onSeleccionarSeccion: (seccion?: string) => void
}

/**
 * Las líneas con mayor desviación absoluta entre propuesta y objetivo (spec 9.1.5, "panel de
 * principales diferencias"). Solo entran líneas con ambos capturados — no hay una regla de
 * favorable/desfavorable para Budget, así que el signo se muestra como texto, nunca en rojo/verde.
 */
export function BudgetPrincipalesDiferencias({ lineas, onSeleccionarSeccion }: Props) {
  const top = principalesDiferencias(lineas, 5)
  if (top.length === 0) return null

  return (
    <section className="tarjeta budget-chart-contenedor budget-diferencias" aria-label="Principales diferencias vs. objetivo">
      <div className="budget-chart-cabecera">
        <div>
          <h3>Principales diferencias</h3>
          <p className="suave">Propuesta vs. objetivo, mayor desviación primero</p>
        </div>
      </div>
      <ul className="budget-diferencias-lista">
        {top.map((d) => (
          <li key={d.linea_id}>
            <button
              type="button"
              className="budget-diferencia-item"
              onClick={() => onSeleccionarSeccion(d.seccion ?? undefined)}
            >
              <span className="budget-diferencia-nombre">{d.descripcion}</span>
              <span className={`budget-diferencia-monto ${d.diferenciaMicros >= 0n ? 'budget-diferencia-sobre' : 'budget-diferencia-bajo'}`}>
                {d.diferenciaMicros >= 0n ? '+' : ''}
                {formatoMicros(d.diferenciaMicros)}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
