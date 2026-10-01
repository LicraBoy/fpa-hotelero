import { useRuta } from '../../ruta/useRuta'

/** Pantalla de Variance. La tabla llega en la sub-fase 4.4; aquí queda el marco con su ruta. */
export function PanelVariance() {
  const { ruta } = useRuta()
  return (
    <section className="panel" aria-label="Variance">
      <h2>Variance</h2>
      <p className="suave">
        Ruta actual: <span>{ruta.tipo}</span>. La tabla del reporte se construye en la sub-fase 4.4.
      </p>
    </section>
  )
}
