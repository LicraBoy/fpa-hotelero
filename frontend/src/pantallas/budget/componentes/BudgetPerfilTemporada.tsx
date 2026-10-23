import { useState } from 'react'
import type { components } from '../../../api/schema'
import { Icono } from '../../../componentes/Iconos'
import { GraficoPlotly } from './PlotlyLazy'
import { useColoresTema } from './useColoresTema'

type Perfil = components['schemas']['PerfilSalida']

const MESES_FISCALES = ['Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun']

interface Props {
  perfiles: readonly Perfil[]
  onIrACaptura: () => void
}

/**
 * Tarjeta de Perfil de Temporada / Distribución Estacional (spec §3.6 y referencia visual).
 * Aprovecha Plotly con barras de fondo + curva spline con área degradada y marcadores circulares.
 */
export function BudgetPerfilTemporada({ perfiles, onIrACaptura }: Props) {
  const colores = useColoresTema()
  const [perfilSeleccionadoId, setPerfilSeleccionadoId] = useState<number>(
    perfiles[0]?.id ?? 0,
  )

  const perfilActivo = perfiles.find((p) => p.id === perfilSeleccionadoId) ?? perfiles[0] ?? null

  const pesosNumericos = perfilActivo
    ? perfilActivo.pesos.map((p) => Number(p) || 0)
    : []

  const pesosPct = pesosNumericos.map((p) => +(p * 100).toFixed(1))

  return (
    <section className="tarjeta budget-chart-contenedor budget-perfil-card" aria-label="Perfil de temporada">
      <div className="budget-chart-cabecera">
        <div>
          <h3>Perfil de temporada</h3>
          <p className="suave">Prorrateo estacional aplicado</p>
        </div>
        <Icono nombre="calendario" tamano={18} />
      </div>

      {perfiles.length === 0 ? (
        <div className="budget-perfil-vacio">
          <p className="suave">No hay perfiles de distribución configurados para este hotel.</p>
        </div>
      ) : (
        <div className="budget-perfil-cuerpo">
          <div className="budget-perfil-selector-wrap">
            <label htmlFor="selector-perfil-temporada" className="solo-lectores">
              Seleccionar perfil de distribución
            </label>
            <select
              id="selector-perfil-temporada"
              value={perfilActivo?.id ?? ''}
              onChange={(e) => setPerfilSeleccionadoId(Number(e.target.value))}
              className="budget-perfil-select"
            >
              {perfiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nombre} {p.es_sistema ? '(Sistema)' : ''}
                </option>
              ))}
            </select>
          </div>

          <div className="budget-perfil-grafico-wrap" aria-label="Curva de distribución por mes fiscal">
            {pesosPct.length > 0 && (
              <GraficoPlotly
                data={[
                  {
                    type: 'bar',
                    name: 'Perfil aplicado',
                    x: MESES_FISCALES,
                    y: pesosPct,
                    marker: {
                      color: 'rgba(37, 99, 235, 0.15)',
                      line: { width: 0 },
                    },
                    hovertemplate: '<b>%{x}</b>: %{y}%<extra></extra>',
                  },
                  {
                    type: 'scatter',
                    mode: 'lines+markers',
                    name: 'Distribución mensual',
                    x: MESES_FISCALES,
                    y: pesosPct,
                    line: {
                      shape: 'spline',
                      color: '#2563eb',
                      width: 2.5,
                      smoothing: 1.3,
                    },
                    fill: 'tozeroy',
                    fillcolor: 'rgba(37, 99, 235, 0.08)',
                    marker: {
                      size: 7,
                      color: '#2563eb',
                      symbol: 'circle',
                      line: { width: 2, color: '#ffffff' },
                    },
                    hovertemplate: '<b>%{x}</b>: %{y}%<extra></extra>',
                  },
                ]}
                layout={{
                  autosize: true,
                  height: 130,
                  margin: { l: 28, r: 8, t: 4, b: 24 },
                  font: { family: 'inherit', size: 9, color: colores.texto },
                  showlegend: false,
                  paper_bgcolor: 'transparent',
                  plot_bgcolor: 'transparent',
                  yaxis: {
                    ticksuffix: '%',
                    showgrid: true,
                    gridcolor: 'rgba(100, 116, 139, 0.08)',
                    zeroline: false,
                    tickfont: { color: colores.texto, size: 8 },
                  },
                  xaxis: {
                    showgrid: false,
                    tickfont: { color: colores.texto, size: 8 },
                  },
                }}
                config={{ displayModeBar: false, responsive: true, staticPlot: false }}
                useResizeHandler
                className="budget-chart-plot"
              />
            )}
          </div>

          <div className="budget-perfil-leyenda-wrap">
            <span className="budget-perfil-leyenda-item">
              <span className="budget-perfil-dot-azul" /> Perfil aplicado
            </span>
            <span className="budget-perfil-leyenda-item">
              <span className="budget-perfil-dot-linea" /> Distribución mensual
            </span>
          </div>

          <div className="budget-perfil-pie">
            <span className="budget-perfil-detalle suave">
              {perfilActivo ? `${perfilActivo.pesos.length} meses configurados` : ''}
            </span>
            <button
              type="button"
              className="boton boton-secundario boton-chico"
              onClick={onIrACaptura}
              title="Ir a Captura para aplicar perfiles a líneas específicas"
            >
              Aplicar en captura
            </button>
          </div>
        </div>
      )}
    </section>
  )
}
