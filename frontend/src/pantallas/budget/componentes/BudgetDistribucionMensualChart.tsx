import { useState } from 'react'
import type { components } from '../../../api/schema'
import { aMicros, formatoMicros } from '../calculo'
import { GraficoPlotly } from './PlotlyLazy'
import { useColoresTema } from './useColoresTema'

type ResumenMensual = components['schemas']['ResumenMensualCicloSalida']

interface Props {
  resumenMensual: ResumenMensual
}

const MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
const etiquetaMes = (periodo: string) => `${MESES[Number(periodo.slice(5, 7)) - 1]} ${periodo.slice(2, 4)}`

/**
 * Distribución mensual de la propuesta (spec §3.6, §4.2.B y referencia visual).
 * Gráfico financiero profesional en Plotly combinando barras mensuales con línea de tendencia
 * suave (spline) y marcadores, aprovechando al máximo la biblioteca gráfica.
 */
export function BudgetDistribucionMensualChart({ resumenMensual }: Props) {
  const [comoTabla, setComoTabla] = useState(false)
  const colores = useColoresTema()

  const periodos = resumenMensual.por_periodo.map((p) => etiquetaMes(p.periodo))
  const importesMicros = resumenMensual.por_periodo.map((p) => aMicros(p.propuesta) ?? 0n)
  const textoImporte = importesMicros.map((m) => formatoMicros(m))
  const valoresMillones = importesMicros.map((m) => Number(m) / 1_000_000)
  const tieneDatos = resumenMensual.por_periodo.length > 0

  return (
    <section className="tarjeta budget-chart-contenedor budget-distribucion-mensual-card" aria-label="Distribución mensual de la propuesta">
      <div className="budget-chart-cabecera">
        <div>
          <h3>Distribución mensual</h3>
          <p className="suave">Propuesta por periodo fiscal (Julio a Junio)</p>
        </div>
        {tieneDatos && (
          <button
            type="button"
            className="boton boton-secundario boton-chico"
            onClick={() => setComoTabla((v) => !v)}
          >
            {comoTabla ? 'Ver como gráfica' : 'Ver como tabla'}
          </button>
        )}
      </div>

      {!tieneDatos ? (
        <div className="budget-chart-vacio">
          <p className="suave">No hay datos mensualizados disponibles en este ciclo para graficar la distribución.</p>
        </div>
      ) : (
        <>
          {resumenMensual.lineas_sin_mensualizar > 0 && (
            <p className="suave budget-distribucion-aviso">
              {resumenMensual.lineas_sin_mensualizar}{' '}
              {resumenMensual.lineas_sin_mensualizar === 1
                ? 'línea capturada todavía no aporta aquí: le falta repartirse en los 12 meses.'
                : 'líneas capturadas todavía no aportan aquí: les falta repartirse en los 12 meses.'}
            </p>
          )}

          {comoTabla ? (
            <div className="budget-tabla-scroll">
              <table className="tabla-simple">
                <caption className="solo-lectores">Propuesta mensualizada del ciclo, julio a junio.</caption>
                <thead>
                  <tr>
                    <th scope="col">Mes</th>
                    <th scope="col">Propuesta</th>
                  </tr>
                </thead>
                <tbody>
                  {resumenMensual.por_periodo.map((p, i) => (
                    <tr key={p.periodo}>
                      <td>{periodos[i]}</td>
                      <td className="num">{textoImporte[i]}</td>
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
                  name: 'Propuesta',
                  x: periodos,
                  y: valoresMillones,
                  customdata: textoImporte,
                  marker: {
                    color: periodos.map((_, i) => {
                      const quarterColors = ['#2563eb', '#3b82f6', '#0284c7', '#0ea5e9']
                      return quarterColors[Math.floor(i / 3) % quarterColors.length]
                    }),
                    opacity: 0.88,
                    line: { width: 0 },
                  },
                  hovertemplate: '<b>%{x}</b><br>Propuesta: %{customdata}<extra></extra>',
                },
                {
                  type: 'scatter',
                  mode: 'lines+markers',
                  name: 'Tendencia',
                  x: periodos,
                  y: valoresMillones,
                  customdata: textoImporte,
                  line: {
                    shape: 'spline',
                    color: '#10b981',
                    width: 2.5,
                    smoothing: 1.2,
                  },
                  fill: 'tozeroy',
                  fillcolor: 'rgba(16, 185, 129, 0.06)',
                  marker: {
                    size: 7,
                    color: '#10b981',
                    symbol: 'circle',
                    line: { width: 2, color: '#ffffff' },
                  },
                  hovertemplate: '<b>%{x} (Tendencia)</b>: %{customdata}<extra></extra>',
                },
              ]}
              layout={{
                autosize: true,
                height: 260,
                margin: { l: 48, r: 16, t: 12, b: 32 },
                font: { family: 'inherit', color: colores.texto },
                showlegend: true,
                legend: {
                  orientation: 'h',
                  x: 0.5,
                  xanchor: 'center',
                  y: -0.2,
                  font: { size: 11, color: colores.texto },
                },
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                yaxis: {
                  ticksuffix: 'M',
                  gridcolor: 'rgba(100, 116, 139, 0.10)',
                  zeroline: false,
                  tickfont: { color: colores.texto, size: 10 },
                },
                xaxis: {
                  showgrid: false,
                  tickfont: { color: colores.texto, size: 10 },
                },
                hovermode: 'x unified',
              }}
              config={{ displayModeBar: false, responsive: true }}
              useResizeHandler
              className="budget-chart-plot"
            />
          )}
        </>
      )}
    </section>
  )
}
