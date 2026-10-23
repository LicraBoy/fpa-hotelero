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
 * Distribución mensual de la propuesta YA mensualizada del ciclo (spec §4.2.B), julio-junio. Es la
 * propuesta del ciclo en captura, no el Budget vigente: si hay líneas capturadas sin mensualizar
 * todavía, se avisa aparte (no se mezclan ambos datos en la misma curva).
 */
export function BudgetDistribucionMensualChart({ resumenMensual }: Props) {
  const [comoTabla, setComoTabla] = useState(false)
  const colores = useColoresTema()
  if (resumenMensual.por_periodo.length === 0) return null

  const periodos = resumenMensual.por_periodo.map((p) => etiquetaMes(p.periodo))
  const importesMicros = resumenMensual.por_periodo.map((p) => aMicros(p.propuesta) ?? 0n)
  const textoImporte = importesMicros.map((m) => formatoMicros(m))

  return (
    <section className="tarjeta budget-chart-contenedor" aria-label="Distribución mensual de la propuesta">
      <div className="budget-chart-cabecera">
        <div>
          <h3>Distribución mensual</h3>
          <p className="suave">Propuesta ya mensualizada, julio a junio</p>
        </div>
        <button type="button" className="boton boton-secundario" onClick={() => setComoTabla((v) => !v)}>
          {comoTabla ? 'Ver como gráfica' : 'Ver como tabla'}
        </button>
      </div>
      {resumenMensual.lineas_sin_mensualizar > 0 && (
        <p className="suave">
          {resumenMensual.lineas_sin_mensualizar}{' '}
          {resumenMensual.lineas_sin_mensualizar === 1
            ? 'línea capturada todavía no aporta aquí: le falta repartirse en los 12 meses.'
            : 'líneas capturadas todavía no aportan aquí: les falta repartirse en los 12 meses.'}
        </p>
      )}
      {comoTabla ? (
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
      ) : (
        <GraficoPlotly
          data={[
            {
              type: 'bar',
              name: 'Propuesta',
              x: periodos,
              y: importesMicros.map((m) => Number(m) / 1_000_000),
              customdata: textoImporte,
              marker: { color: colores.primario },
              hovertemplate: '%{x}<br>Propuesta: %{customdata}<extra></extra>',
            },
          ]}
          layout={{
            autosize: true,
            height: 280,
            margin: { l: 56, r: 16, t: 8, b: 32 },
            font: { family: 'inherit' },
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
          }}
          config={{ displayModeBar: false, responsive: true }}
          useResizeHandler
          className="budget-chart-plot"
        />
      )}
    </section>
  )
}
