import type { components } from '../../../api/schema'

type Ciclo = components['schemas']['CicloSalida']
type ResumenCiclo = components['schemas']['ResumenPresupuestoSalida']

interface Props {
  ciclo: Ciclo
  resumen: ResumenCiclo
  onIrACaptura?: () => void
}

const ETIQUETA_ESTADO: Record<string, string> = {
  borrador: 'Borrador',
  enviado: 'Enviado',
  revision: 'Revisión',
  aprobado: 'Aprobado',
  bloqueado: 'Bloqueado',
}

/**
 * Tarjeta de Resumen del Ciclo (spec §3.5 y referencia visual).
 * Ocupa la columna derecha de la fila de análisis con estado actual, barra de progreso
 * de cobertura de captura, lista de próximas acciones y botón de acción.
 */
export function BudgetResumenCiclo({ ciclo, resumen, onIrACaptura }: Props) {
  const sinCapturar = resumen.total_lineas - resumen.lineas_capturadas
  const coberturaNum = Number.parseFloat(resumen.cobertura_pct) || 0

  return (
    <section className="tarjeta budget-chart-contenedor budget-resumen-ciclo-card" aria-label="Resumen del ciclo">
      <div className="budget-chart-cabecera">
        <div>
          <h3>Resumen del ciclo</h3>
          <p className="suave">Ciclo #{ciclo.numero}</p>
        </div>
        <span className="budget-estado-tag">
          {ETIQUETA_ESTADO[ciclo.estado] ?? ciclo.estado}
        </span>
      </div>

      <div className="budget-resumen-ciclo-cuerpo">
        <div className="budget-ciclo-progreso-bloque">
          <div className="budget-ciclo-progreso-cabecera">
            <span className="budget-ciclo-progreso-lineas">
              <strong>{resumen.lineas_capturadas}</strong> de {resumen.total_lineas} líneas capturadas
            </span>
            <span className="budget-ciclo-progreso-pct">{resumen.cobertura_pct}%</span>
          </div>
          <progress
            value={coberturaNum}
            max={100}
            className="budget-ciclo-progress-bar"
            aria-label={`Cobertura del ciclo: ${resumen.cobertura_pct}%`}
          />
        </div>

        <div className="budget-ciclo-checklist-bloque">
          <span className="budget-ciclo-metrica-etiqueta">Próximas acciones</span>
          <ul className="budget-ciclo-checklist">
            <li className={resumen.lineas_capturadas > 0 ? 'hecho' : ''}>
              <span className="budget-checklist-icon">✓</span>
              <span>Revisar propuestas capturadas</span>
            </li>
            <li className={sinCapturar === 0 ? 'hecho' : ''}>
              <span className="budget-checklist-icon">{sinCapturar === 0 ? '✓' : '○'}</span>
              <span>
                {sinCapturar === 0
                  ? 'Todas las líneas tienen propuesta'
                  : `Capturar ${sinCapturar} líneas pendientes`}
              </span>
            </li>
            <li>
              <span className="budget-checklist-icon">○</span>
              <span>{ciclo.transiciones_posibles[0]?.etiqueta ?? 'Ciclo completado'}</span>
            </li>
          </ul>
        </div>
      </div>

      <div className="budget-card-pie">
        <button
          type="button"
          className="boton boton-secundario boton-chico budget-btn-full"
          onClick={onIrACaptura}
          title="Ir a la pestaña de Captura para revisar o editar líneas"
        >
          {sinCapturar > 0 ? `Capturar líneas pendientes (${sinCapturar})` : 'Ver detalle de captura'}
        </button>
      </div>
    </section>
  )
}
