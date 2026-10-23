import type { components } from '../../../api/schema'
import { aMicros, formatoMicros, principalesDiferencias } from '../calculo'

type LineaCaptura = components['schemas']['LineaCapturaSalida']

interface Props {
  lineas: readonly LineaCaptura[]
  onSeleccionarSeccion: (seccion?: string) => void
}

/**
 * Desviaciones vs. Objetivo (spec §3.5 y referencia visual).
 * Muestra las líneas con mayor desviación absoluta entre propuesta y objetivo
 * en una tabla compacta con línea, porcentaje de variación y monto.
 */
export function BudgetPrincipalesDiferencias({ lineas, onSeleccionarSeccion }: Props) {
  const top = principalesDiferencias(lineas, 5)
  const lineasPorId = new Map(lineas.map((l) => [l.linea_id, l]))

  return (
    <section className="tarjeta budget-chart-contenedor budget-diferencias" aria-label="Desviaciones vs. objetivo">
      <div className="budget-chart-cabecera">
        <div>
          <h3>Desviaciones vs. Objetivo</h3>
          <p className="suave">Top 5 líneas con mayor variación</p>
        </div>
      </div>

      {top.length === 0 ? (
        <div className="budget-diferencias-vacio">
          <p className="suave">No hay desviaciones registradas frente al objetivo.</p>
        </div>
      ) : (
        <div className="budget-diferencias-cuerpo">
          <div className="budget-diferencias-encabezado">
            <span>Línea</span>
            <span>Var. %</span>
            <span>Monto</span>
          </div>
          <ul className="budget-diferencias-lista">
            {top.map((d) => {
              const linea = lineasPorId.get(d.linea_id)
              const objMicros = linea?.objetivo ? aMicros(linea.objetivo) : null
              const pct =
                objMicros && objMicros !== 0n
                  ? (Number(d.diferenciaMicros) / Number(objMicros)) * 100
                  : null
              const pctTexto = pct !== null ? `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%` : '—'
              const esPositiva = d.diferenciaMicros > 0n
              const esNegativa = d.diferenciaMicros < 0n

              return (
                <li key={d.linea_id}>
                  <button
                    type="button"
                    className="budget-diferencia-item"
                    onClick={() => onSeleccionarSeccion(d.seccion ?? undefined)}
                    title={`Ver sección ${d.seccion ?? 'general'} en Captura`}
                  >
                    <span className="budget-diferencia-nombre" title={d.descripcion}>
                      {d.descripcion}
                    </span>
                    <span
                      className={`budget-diferencia-pill ${
                        esNegativa ? 'negativo' : esPositiva ? 'positivo' : 'neutral'
                      }`}
                    >
                      {pctTexto}
                    </span>
                    <span
                      className={`budget-diferencia-monto ${
                        esPositiva ? 'budget-diferencia-sobre' : esNegativa ? 'budget-diferencia-bajo' : ''
                      }`}
                    >
                      {esPositiva ? '+' : ''}
                      {formatoMicros(d.diferenciaMicros)}
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      )}

      <div className="budget-card-pie">
        <button
          type="button"
          className="budget-enlace-texto"
          onClick={() => onSeleccionarSeccion()}
          title="Abrir la pestaña de Captura para revisar todas las líneas"
        >
          Ver todas las desviaciones →
        </button>
      </div>
    </section>
  )
}
