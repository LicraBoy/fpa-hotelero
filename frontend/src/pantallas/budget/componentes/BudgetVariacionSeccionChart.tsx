import { useMemo, useState } from 'react'
import type { components } from '../../../api/schema'
import { formatoMicros, serieObjetivoVsPropuesta } from '../calculo'
import { GraficoPlotly } from './PlotlyLazy'
import { useColoresTema } from './useColoresTema'

type ResumenSeccion = components['schemas']['ResumenSeccionPresupuestoSalida']

interface Props {
  porSeccion: ResumenSeccion[]
  onSeleccionarSeccion?: (seccion: string) => void
}

/**
 * Variación por sección (fusiona lo que antes eran dos tarjetas — "Objetivo vs.
 * Propuesta" en barras agrupadas y "Estructura del presupuesto" en donut — en una
 * sola barra horizontal: una tarjeta, una lectura. Ordenada por desviación absoluta
 * (mayor variación primero, igual que "Desviaciones vs. Objetivo"), con la
 * participación de cada sección en el total de la propuesta como etiqueta, no como
 * gráfico aparte.
 */
export function BudgetVariacionSeccionChart({ porSeccion, onSeleccionarSeccion }: Props) {
  const [comoTabla, setComoTabla] = useState(false)
  const colores = useColoresTema()
  const serie = useMemo(() => serieObjetivoVsPropuesta(porSeccion), [porSeccion])

  const { ordenada, totalPropuestaMicros } = useMemo(() => {
    const total = serie.reduce((acc, s) => acc + s.propuestaMicros, 0n)
    const orden = [...serie].sort((a, b) => {
      const absA = a.diferenciaMicros < 0n ? -a.diferenciaMicros : a.diferenciaMicros
      const absB = b.diferenciaMicros < 0n ? -b.diferenciaMicros : b.diferenciaMicros
      return absB > absA ? 1 : absB < absA ? -1 : 0
    })
    return { ordenada: orden, totalPropuestaMicros: total }
  }, [serie])

  const participacion = (propuestaMicros: bigint) =>
    totalPropuestaMicros > 0n ? (Number(propuestaMicros) / Number(totalPropuestaMicros)) * 100 : 0

  return (
    <section className="tarjeta budget-chart-contenedor" aria-label="Variación por sección">
      <div className="budget-chart-cabecera">
        <div>
          <h3>Variación por sección</h3>
          <p className="suave">Propuesta vs. objetivo, ordenado por mayor desviación</p>
        </div>
        <button
          type="button"
          className="boton boton-secundario boton-chico"
          onClick={() => setComoTabla((v) => !v)}
        >
          {comoTabla ? 'Ver como gráfica' : 'Ver como tabla'}
        </button>
      </div>

      {serie.length === 0 ? (
        <div className="budget-chart-vacio">
          <p className="suave">No hay datos de objetivo ni propuesta para mostrar.</p>
        </div>
      ) : comoTabla ? (
        <div className="budget-tabla-scroll">
          <table className="tabla-simple">
            <caption className="solo-lectores">
              Objetivo, propuesta, diferencia y participación por sección.
            </caption>
            <thead>
              <tr>
                <th scope="col">Sección</th>
                <th scope="col">Objetivo</th>
                <th scope="col">Propuesta</th>
                <th scope="col">Diferencia</th>
                <th scope="col">Participación</th>
              </tr>
            </thead>
            <tbody>
              {ordenada.map((s) => (
                <tr key={s.seccion}>
                  <td>{s.seccion}</td>
                  <td className="num">{formatoMicros(s.objetivoMicros)}</td>
                  <td className="num">{formatoMicros(s.propuestaMicros)}</td>
                  <td className="num">{formatoMicros(s.diferenciaMicros)}</td>
                  <td className="num">{participacion(s.propuestaMicros).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <GraficoPlotly
          data={[
            {
              type: 'bar',
              orientation: 'h',
              name: 'Diferencia (propuesta − objetivo)',
              y: ordenada.map((s) => s.seccion),
              x: ordenada.map((s) => Number(s.diferenciaMicros) / 1_000_000),
              customdata: ordenada.map((s) => [
                formatoMicros(s.objetivoMicros),
                formatoMicros(s.propuestaMicros),
                formatoMicros(s.diferenciaMicros),
                `${participacion(s.propuestaMicros).toFixed(1)}%`,
              ]),
              marker: {
                color: '#2563eb',
                opacity: 0.88,
              },
              hovertemplate:
                '<b>%{y}</b><br>' +
                'Objetivo: %{customdata[0]}<br>' +
                'Propuesta: %{customdata[1]}<br>' +
                'Diferencia: %{customdata[2]}<br>' +
                'Participación en la propuesta total: %{customdata[3]}<extra></extra>',
            },
          ]}
          layout={{
            autosize: true,
            height: Math.max(220, ordenada.length * 42),
            margin: { l: 140, r: 24, t: 8, b: 32 },
            font: { family: 'inherit', color: colores.texto },
            showlegend: false,
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            xaxis: {
              ticksuffix: 'M',
              gridcolor: 'rgba(100, 116, 139, 0.12)',
              zeroline: true,
              zerolinecolor: 'rgba(100, 116, 139, 0.3)',
              tickfont: { color: colores.texto, size: 10 },
            },
            yaxis: {
              autorange: 'reversed',
              showgrid: false,
              tickfont: { color: colores.texto, size: 10 },
            },
          }}
          config={{ displayModeBar: false, responsive: true }}
          useResizeHandler
          className="budget-chart-plot"
          onClick={(e) => {
            const punto = e.points?.[0]
            const seccion = typeof punto?.y === 'string' ? punto.y : null
            if (seccion && onSeleccionarSeccion) onSeleccionarSeccion(seccion)
          }}
        />
      )}
    </section>
  )
}
