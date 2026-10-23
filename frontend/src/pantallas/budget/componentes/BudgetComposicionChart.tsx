import { useMemo, useState } from 'react'
import type { components } from '../../../api/schema'
import { aMicros, formatoMicros } from '../calculo'
import { GraficoPlotly } from './PlotlyLazy'
import { useColoresTema } from './useColoresTema'

type ResumenSeccion = components['schemas']['ResumenSeccionPresupuestoSalida']

interface Props {
  porSeccion: ResumenSeccion[]
  onIrACaptura?: () => void
}

/**
 * Estructura del presupuesto (spec §3.7 y referencia visual).
 * Donut chart a la izquierda con el monto total en el centro, y lista de departamentos
 * con porcentaje e importe formateado a la derecha.
 */
export function BudgetComposicionChart({ porSeccion, onIrACaptura }: Props) {
  const [comoTabla, setComoTabla] = useState(false)
  const colores = useColoresTema()

  const conPropuesta = useMemo(
    () => porSeccion.filter((s) => (aMicros(s.suma_propuesta) ?? 0n) > 0n),
    [porSeccion],
  )

  const { items, totalFormateado } = useMemo(() => {
    const ordenadas = [...conPropuesta].sort((a, b) => {
      const mA = aMicros(a.suma_propuesta) ?? 0n
      const mB = aMicros(b.suma_propuesta) ?? 0n
      return mA > mB ? -1 : mA < mB ? 1 : 0
    })

    const totalMicros = ordenadas.reduce((acc, s) => acc + (aMicros(s.suma_propuesta) ?? 0n), 0n)
    const totalNum = Number(totalMicros) / 1_000_000

    let lista: Array<{
      nombre: string
      montoMicros: bigint
      montoTexto: string
      valorNum: number
      pctTexto: string
      color: string
    }> = []

    if (ordenadas.length <= 5) {
      lista = ordenadas.map((s, idx) => {
        const m = aMicros(s.suma_propuesta) ?? 0n
        const pct = totalMicros > 0n ? (Number(m) / Number(totalMicros)) * 100 : 0
        return {
          nombre: s.seccion ?? 'Sin sección',
          montoMicros: m,
          montoTexto: formatoMicros(m),
          valorNum: Number(m) / 1_000_000,
          pctTexto: `${pct.toFixed(1)}%`,
          color: colores.paletaSerie[idx % colores.paletaSerie.length] ?? '#2563eb',
        }
      })
    } else {
      const top4 = ordenadas.slice(0, 4)
      const resto = ordenadas.slice(4)
      const sumaResto = resto.reduce((acc, s) => acc + (aMicros(s.suma_propuesta) ?? 0n), 0n)

      lista = top4.map((s, idx) => {
        const m = aMicros(s.suma_propuesta) ?? 0n
        const pct = totalMicros > 0n ? (Number(m) / Number(totalMicros)) * 100 : 0
        return {
          nombre: s.seccion ?? 'Sin sección',
          montoMicros: m,
          montoTexto: formatoMicros(m),
          valorNum: Number(m) / 1_000_000,
          pctTexto: `${pct.toFixed(1)}%`,
          color: colores.paletaSerie[idx % colores.paletaSerie.length] ?? '#2563eb',
        }
      })

      const pctResto = totalMicros > 0n ? (Number(sumaResto) / Number(totalMicros)) * 100 : 0
      lista.push({
        nombre: 'Otras secciones',
        montoMicros: sumaResto,
        montoTexto: formatoMicros(sumaResto),
        valorNum: Number(sumaResto) / 1_000_000,
        pctTexto: `${pctResto.toFixed(1)}%`,
        color: colores.suave,
      })
    }

    return {
      items: lista,
      totalFormateado: totalNum >= 1_000_000 ? `$${(totalNum / 1_000_000).toFixed(1)}M` : formatoMicros(totalMicros),
    }
  }, [conPropuesta, colores])

  return (
    <section className="tarjeta budget-chart-contenedor budget-composicion-card" aria-label="Estructura del presupuesto por sección">
      <div className="budget-chart-cabecera">
        <div>
          <h3>Estructura del presupuesto</h3>
          <p className="suave">Por departamento (monto anual)</p>
        </div>
        {conPropuesta.length > 0 && (
          <button
            type="button"
            className="boton boton-secundario boton-chico"
            onClick={() => setComoTabla((v) => !v)}
          >
            {comoTabla ? 'Ver como gráfica' : 'Ver como tabla'}
          </button>
        )}
      </div>

      {conPropuesta.length === 0 ? (
        <div className="budget-chart-vacio">
          <p className="suave">No hay importes de propuesta capturados todavía para graficar la composición.</p>
        </div>
      ) : comoTabla ? (
        <div className="budget-tabla-scroll">
          <table className="tabla-simple">
            <caption className="solo-lectores">Propuesta por sección.</caption>
            <thead>
              <tr>
                <th scope="col">Sección</th>
                <th scope="col">Participación</th>
                <th scope="col">Propuesta</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => (
                <tr key={it.nombre}>
                  <td>{it.nombre}</td>
                  <td className="num">{it.pctTexto}</td>
                  <td className="num">{it.montoTexto}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="budget-composicion-cuerpo">
          <div className="budget-composicion-grafico-wrap">
            <GraficoPlotly
              data={[
                {
                  type: 'pie',
                  labels: items.map((it) => it.nombre),
                  values: items.map((it) => it.valorNum),
                  customdata: items.map((it) => it.montoTexto),
                  hovertemplate: '<b>%{label}</b><br>%{customdata} (%{percent})<extra></extra>',
                  marker: {
                    colors: items.map((it) => it.color),
                    line: { color: colores.texto === '#e2e8f0' ? '#1e293b' : '#ffffff', width: 2 },
                  },
                  textinfo: 'percent',
                  textposition: 'outside',
                  textfont: { size: 10 },
                  pull: items.map((_, i) => (i === 0 ? 0.04 : 0)),
                  hole: 0.62,
                  rotation: -40,
                  direction: 'clockwise',
                },
              ]}
              layout={{
                autosize: true,
                height: 195,
                margin: { l: 8, r: 8, t: 8, b: 8 },
                font: { family: 'inherit' },
                showlegend: false,
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                annotations: [
                  {
                    font: { size: 14, family: 'inherit', color: colores.texto },
                    showarrow: false,
                    text: `<b>${totalFormateado}</b><br>Total Plan`,
                    x: 0.5,
                    y: 0.5,
                  },
                ],
              }}
              config={{ displayModeBar: false, responsive: true }}
              useResizeHandler
              className="budget-chart-plot"
            />
          </div>

          <div className="budget-composicion-lista">
            {items.map((it, idx) => (
              <div key={it.nombre} className="budget-comp-fila">
                <span className="budget-comp-dot" data-color-idx={idx} />
                <span className="budget-comp-nombre" title={it.nombre}>
                  {it.nombre}
                </span>
                <span className="budget-comp-pct suave">{it.pctTexto}</span>
                <span className="budget-comp-monto">{it.montoTexto}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="budget-card-pie">
        <button
          type="button"
          className="budget-enlace-texto"
          onClick={onIrACaptura}
          title="Ver desglose por cuenta en Captura"
        >
          Ver detalle por cuenta →
        </button>
      </div>
    </section>
  )
}
