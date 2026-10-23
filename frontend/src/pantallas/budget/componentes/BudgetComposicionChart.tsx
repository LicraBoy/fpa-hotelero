import { useState } from 'react'
import type { components } from '../../../api/schema'
import { aMicros, formatoMicros } from '../calculo'
import { GraficoPlotly } from './PlotlyLazy'
import { useColoresTema } from './useColoresTema'

type ResumenSeccion = components['schemas']['ResumenSeccionPresupuestoSalida']

interface Props {
  porSeccion: ResumenSeccion[]
}

/** Composición de la propuesta por sección (spec 9.1.7, "composición del presupuesto"). */
export function BudgetComposicionChart({ porSeccion }: Props) {
  const [comoTabla, setComoTabla] = useState(false)
  const colores = useColoresTema()
  const conPropuesta = porSeccion.filter((s) => (aMicros(s.suma_propuesta) ?? 0n) > 0n)
  if (conPropuesta.length === 0) return null

  const etiquetas = conPropuesta.map((s) => s.seccion ?? 'Sin sección')
  const montos = conPropuesta.map((s) => aMicros(s.suma_propuesta) ?? 0n)
  const textoMontos = montos.map((m) => formatoMicros(m))
  const valoresGrafica = montos.map((m) => Number(m) / 1_000_000)
  const colorPorSeccion = etiquetas.map((_, i) => colores.paletaSerie[i % colores.paletaSerie.length])

  return (
    <section className="tarjeta budget-chart-contenedor" aria-label="Composición del presupuesto por sección">
      <div className="budget-chart-cabecera">
        <div>
          <h3>Composición del presupuesto</h3>
          <p className="suave">Propuesta por sección</p>
        </div>
        <button type="button" className="boton boton-secundario" onClick={() => setComoTabla((v) => !v)}>
          {comoTabla ? 'Ver como gráfica' : 'Ver como tabla'}
        </button>
      </div>

      {comoTabla ? (
        <table className="tabla-simple">
          <caption className="solo-lectores">Propuesta por sección.</caption>
          <thead>
            <tr>
              <th scope="col">Sección</th>
              <th scope="col">Propuesta</th>
            </tr>
          </thead>
          <tbody>
            {etiquetas.map((e, i) => (
              <tr key={e}>
                <td>{e}</td>
                <td className="num">{textoMontos[i]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <GraficoPlotly
          data={[
            {
              type: 'pie',
              labels: etiquetas,
              values: valoresGrafica,
              customdata: textoMontos,
              hovertemplate: '%{label}<br>%{customdata}<extra></extra>',
              marker: { colors: colorPorSeccion },
              textinfo: 'label+percent',
              hole: 0.5,
            },
          ]}
          layout={{
            autosize: true,
            height: 280,
            margin: { l: 8, r: 8, t: 8, b: 8 },
            font: { family: 'inherit' },
            showlegend: false,
            paper_bgcolor: 'transparent',
          }}
          config={{ displayModeBar: false, responsive: true }}
          useResizeHandler
          className="budget-chart-plot"
        />
      )}
    </section>
  )
}
