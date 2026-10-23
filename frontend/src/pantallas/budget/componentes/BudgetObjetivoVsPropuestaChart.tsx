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

const formatoCompacto = (n: number) => {
  if (n <= 0) return ''
  const millones = n / 1_000_000
  if (millones >= 1) return `$${millones.toFixed(1)}M`
  if (millones >= 0.1) return `$${millones.toFixed(2)}M`
  if (n >= 1000) return `$${(n / 1000).toFixed(0)}k`
  return `$${n.toFixed(0)}`
}

/**
 * Objetivo vs. Propuesta por sección (spec §4.2.A y referencia visual).
 * Gráfico de barras verticales agrupadas con etiquetas de valor superiores
 * y paleta coordinada azul/verde de alta fidelidad financiera.
 */
export function BudgetObjetivoVsPropuestaChart({ porSeccion, onSeleccionarSeccion }: Props) {
  const [comoTabla, setComoTabla] = useState(false)
  const serie = useMemo(() => serieObjetivoVsPropuesta(porSeccion), [porSeccion])
  const colores = useColoresTema()

  const serieTop = useMemo(() => {
    if (serie.length <= 5) return serie
    const ordenadas = [...serie].sort((a, b) => {
      const maxA = Math.max(a.propuesta, a.objetivo)
      const maxB = Math.max(b.propuesta, b.objetivo)
      return maxB - maxA
    })

    const top = ordenadas.slice(0, 5)
    const resto = ordenadas.slice(5)

    const objetivoResto = resto.reduce((acc, s) => acc + s.objetivo, 0)
    const propuestaResto = resto.reduce((acc, s) => acc + s.propuesta, 0)
    const objetivoRestoMicros = resto.reduce((acc, s) => acc + s.objetivoMicros, 0n)
    const propuestaRestoMicros = resto.reduce((acc, s) => acc + s.propuestaMicros, 0n)
    const diferenciaMicros = propuestaRestoMicros - objetivoRestoMicros
    const diferenciaPct =
      objetivoRestoMicros !== 0n ? Number((diferenciaMicros * 10_000n) / objetivoRestoMicros) / 100 : null

    top.push({
      seccion: 'Otras',
      objetivo: objetivoResto,
      propuesta: propuestaResto,
      objetivoMicros: objetivoRestoMicros,
      propuestaMicros: propuestaRestoMicros,
      diferenciaMicros,
      diferenciaPct,
    })
    return top
  }, [serie])

  return (
    <section className="tarjeta budget-chart-contenedor" aria-label="Objetivo vs. propuesta por sección">
      <div className="budget-chart-cabecera">
        <div>
          <h3>Objetivo vs. Propuesta</h3>
          <p className="suave">Por departamento principal</p>
        </div>
        <button
          type="button"
          className="boton boton-secundario boton-chico"
          onClick={() => setComoTabla((v) => !v)}
        >
          {comoTabla ? 'Ver como gráfica' : 'Ver como tabla'}
        </button>
      </div>

      {!comoTabla && (
        <div className="budget-chart-subcabecera">
          <span className="suave budget-chart-subtexto">Comparativa por departamento (Millones)</span>
        </div>
      )}

      {serie.length === 0 ? (
        <div className="budget-chart-vacio">
          <p className="suave">No hay datos de objetivo ni propuesta para mostrar.</p>
        </div>
      ) : comoTabla ? (
        <div className="budget-tabla-scroll">
          <table className="tabla-simple">
            <caption className="solo-lectores">Objetivo y propuesta por sección, con su diferencia.</caption>
            <thead>
              <tr>
                <th scope="col">Sección</th>
                <th scope="col">Objetivo</th>
                <th scope="col">Propuesta</th>
                <th scope="col">Diferencia</th>
              </tr>
            </thead>
            <tbody>
              {serie.map((s) => (
                <tr key={s.seccion}>
                  <td>{s.seccion}</td>
                  <td className="num">{formatoMicros(s.objetivoMicros)}</td>
                  <td className="num">{formatoMicros(s.propuestaMicros)}</td>
                  <td className="num">{formatoMicros(s.diferenciaMicros)}</td>
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
              name: 'Objetivo',
              x: serieTop.map((s) => s.seccion.length > 15 ? `${s.seccion.slice(0, 13)}…` : s.seccion),
              y: serieTop.map((s) => +(s.objetivo / 1_000_000).toFixed(2)),
              text: serieTop.map((s) => formatoCompacto(s.objetivo)),
              textposition: 'outside',
              textfont: { size: 10, color: colores.texto },
              cliponaxis: false,
              customdata: serieTop.map((s) => [s.seccion, formatoMicros(s.objetivoMicros)]),
              marker: {
                color: '#2563eb',
                opacity: 0.92,
              },
              hovertemplate: '<b>%{customdata[0]} (Objetivo)</b><br>Monto: %{customdata[1]}<extra></extra>',
            },
            {
              type: 'bar',
              name: 'Propuesta',
              x: serieTop.map((s) => s.seccion.length > 15 ? `${s.seccion.slice(0, 13)}…` : s.seccion),
              y: serieTop.map((s) => +(s.propuesta / 1_000_000).toFixed(2)),
              text: serieTop.map((s) => formatoCompacto(s.propuesta)),
              textposition: 'outside',
              textfont: { size: 10, color: colores.texto },
              cliponaxis: false,
              customdata: serieTop.map((s) => [s.seccion, formatoMicros(s.propuestaMicros)]),
              marker: {
                color: '#10b981',
                opacity: 0.92,
              },
              hovertemplate: '<b>%{customdata[0]} (Propuesta)</b><br>Monto: %{customdata[1]}<extra></extra>',
            },
          ]}
          layout={{
            barmode: 'group',
            bargap: 0.26,
            bargroupgap: 0.08,
            autosize: true,
            height: 250,
            margin: { l: 44, r: 12, t: 28, b: 36 },
            font: { family: 'inherit', color: colores.texto },
            showlegend: true,
            legend: {
              orientation: 'h',
              x: 0.98,
              xanchor: 'right',
              y: 1.18,
              font: { size: 11, color: colores.texto },
            },
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            yaxis: {
              ticksuffix: 'M',
              gridcolor: 'rgba(100, 116, 139, 0.12)',
              zeroline: false,
              tickfont: { color: colores.texto, size: 10 },
            },
            xaxis: {
              tickangle: -10,
              showgrid: false,
              tickfont: { color: colores.texto, size: 10 },
            },
          }}
          config={{ displayModeBar: false, responsive: true }}
          useResizeHandler
          className="budget-chart-plot"
          onClick={(e) => {
            const punto = e.points?.[0]
            const seccion = Array.isArray(punto?.customdata)
              ? (punto.customdata[0] as string)
              : typeof punto?.x === 'string'
                ? punto.x
                : null
            if (seccion && seccion !== 'Otras' && onSeleccionarSeccion) {
              onSeleccionarSeccion(seccion)
            }
          }}
        />
      )}
    </section>
  )
}
