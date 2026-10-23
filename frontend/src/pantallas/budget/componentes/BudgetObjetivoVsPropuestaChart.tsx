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
 * Objetivo vs. Propuesta por sección (spec §4.2.A). El texto exacto del tooltip y de la tabla
 * alterna sale siempre de `formatoMicros` sobre los micros reales, nunca del `number` que Plotly
 * grafica (ese solo define la posición de la barra) — la gráfica nunca es la fuente de verdad de
 * una cifra. Los colores de las trazas son los tokens de la app, no la paleta por defecto de
 * Plotly, para que no se vea como una plantilla genérica.
 */
export function BudgetObjetivoVsPropuestaChart({ porSeccion, onSeleccionarSeccion }: Props) {
  const [comoTabla, setComoTabla] = useState(false)
  const serie = useMemo(() => serieObjetivoVsPropuesta(porSeccion), [porSeccion])
  const colores = useColoresTema()

  if (serie.length === 0) return null

  const secciones = serie.map((s) => s.seccion)
  const textoObjetivo = serie.map((s) => formatoMicros(s.objetivoMicros))
  const textoPropuesta = serie.map((s) => formatoMicros(s.propuestaMicros))

  return (
    <section className="tarjeta budget-chart-contenedor" aria-label="Objetivo vs. propuesta por sección">
      <div className="budget-chart-cabecera">
        <div>
          <h3>Objetivo vs. propuesta por sección</h3>
          <p className="suave">Por sección, en la moneda del reporte</p>
        </div>
        <button type="button" className="boton boton-secundario" onClick={() => setComoTabla((v) => !v)}>
          {comoTabla ? 'Ver como gráfica' : 'Ver como tabla'}
        </button>
      </div>
      {!comoTabla && (
        <ul className="budget-chart-leyenda">
          <li>
            <span className="budget-chart-punto" data-color="suave" /> Objetivo
          </li>
          <li>
            <span className="budget-chart-punto" data-color="primario" /> Propuesta
          </li>
        </ul>
      )}

      {comoTabla ? (
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
      ) : (
        <GraficoPlotly
          data={[
            {
              type: 'bar',
              orientation: 'h',
              name: 'Objetivo',
              x: serie.map((s) => s.objetivo),
              y: secciones,
              customdata: textoObjetivo,
              marker: { color: colores.suave },
              hovertemplate: '%{y}<br>Objetivo: %{customdata}<extra></extra>',
            },
            {
              type: 'bar',
              orientation: 'h',
              name: 'Propuesta',
              x: serie.map((s) => s.propuesta),
              y: secciones,
              customdata: textoPropuesta,
              marker: { color: colores.primario },
              hovertemplate: '%{y}<br>Propuesta: %{customdata}<extra></extra>',
            },
          ]}
          layout={{
            barmode: 'group',
            autosize: true,
            height: Math.max(260, serie.length * 70),
            margin: { l: 140, r: 16, t: 8, b: 32 },
            font: { family: 'inherit' },
            showlegend: false,
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
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
