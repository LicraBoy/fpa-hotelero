import type { components } from '../../../api/schema'

type ResumenCiclo = components['schemas']['ResumenPresupuestoSalida']
type ResumenMensual = components['schemas']['ResumenMensualCicloSalida']
type Ciclo = components['schemas']['CicloSalida']

interface Props {
  resumen: ResumenCiclo
  resumenMensual: ResumenMensual | null
  ciclo: Ciclo
  onVerLineasSinCapturar: () => void
}

/**
 * Alertas de Resumen (spec §4.3). No incluye "distribución mensual que no cuadra con el anual"
 * como excepción aparte: el modelo ya lo impide (`capturar_propuesta` borra el reparto mensual en
 * cuanto cambia el anual, `fijar_importes_mensuales` exige la suma exacta) — la única forma real de
 * quedar pendiente es no tener reparto mensual todavía, que es justo lo que cuenta
 * `lineas_sin_mensualizar`.
 */
export function BudgetAlertas({ resumen, resumenMensual, ciclo, onVerLineasSinCapturar }: Props) {
  const sinCapturar = resumen.total_lineas - resumen.lineas_capturadas
  const avisos: { texto: string; accion?: { etiqueta: string; onClick: () => void } }[] = []

  if (sinCapturar > 0) {
    avisos.push({
      texto: `${sinCapturar} ${sinCapturar === 1 ? 'línea sin capturar' : 'líneas sin capturar'}.`,
      accion: { etiqueta: 'Ir a Captura', onClick: onVerLineasSinCapturar },
    })
  }
  if (resumenMensual && resumenMensual.lineas_sin_mensualizar > 0) {
    avisos.push({
      texto:
        `${resumenMensual.lineas_sin_mensualizar} ` +
        (resumenMensual.lineas_sin_mensualizar === 1
          ? 'línea capturada sin repartir en los 12 meses.'
          : 'líneas capturadas sin repartir en los 12 meses.'),
      accion: { etiqueta: 'Ir a Captura', onClick: onVerLineasSinCapturar },
    })
  }
  if (ciclo.estado === 'enviado') {
    avisos.push({ texto: 'Ciclo enviado, pendiente de revisión.' })
  }

  if (avisos.length === 0) return null

  return (
    <details className="avisos" open>
      <summary>
        <span className="aviso-bandeja-titulo">Pendientes del ciclo</span>
        <span className="suave aviso-bandeja-conteo">
          {avisos.length} {avisos.length === 1 ? 'aviso' : 'avisos'}
        </span>
      </summary>
      <ul className="mensaje mensaje-aviso advertencias" role="status" aria-label="Pendientes">
        {avisos.map((a) => (
          <li key={a.texto}>
            {a.texto}{' '}
            {a.accion && (
              <button type="button" className="boton boton-secundario" onClick={a.accion.onClick}>
                {a.accion.etiqueta}
              </button>
            )}
          </li>
        ))}
      </ul>
    </details>
  )
}
