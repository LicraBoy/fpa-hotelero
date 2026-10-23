import { Component, lazy, Suspense, type ReactNode } from 'react'
import type { PlotParams } from 'react-plotly.js'

// Plotly completo pesa ~3.5MB y trae trazas que aquí no se usan (3D, mapas, estadística). Se usa el
// bundle parcial `plotly.js-basic-dist-min` (bar/scatter/pie) y se separa en su propio chunk de Vite
// (el `import()` dinámico), para que no viaje en el bundle principal de la pantalla.
const Plot = lazy(async () => {
  const [{ default: Plotly }, { default: createPlotlyComponent }] = await Promise.all([
    import('plotly.js-basic-dist-min'),
    import('react-plotly.js/factory'),
  ])
  return { default: createPlotlyComponent(Plotly) }
})

class LimiteErrorGrafico extends Component<{ children: ReactNode }, { fallo: boolean }> {
  state = { fallo: false }
  static getDerivedStateFromError() {
    return { fallo: true }
  }
  render() {
    if (this.state.fallo) {
      return <p className="suave estado-vacio">No se pudo cargar la gráfica. La tabla sigue disponible abajo.</p>
    }
    return this.props.children
  }
}

/** Envoltura de `react-plotly.js` con carga diferida y una caída accesible si el chunk no carga. */
export function GraficoPlotly(props: PlotParams) {
  return (
    <LimiteErrorGrafico>
      <Suspense fallback={<p className="suave estado-cargando">Cargando gráfica…</p>}>
        <Plot {...props} />
      </Suspense>
    </LimiteErrorGrafico>
  )
}
