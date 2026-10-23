import type { components } from '../../../api/schema'
import { Insignia } from '../../../componentes/Insignia'

type Ciclo = components['schemas']['CicloSalida']
type ResumenCiclo = components['schemas']['ResumenPresupuestoSalida']

interface Props {
  ciclo: Ciclo
  resumen: ResumenCiclo
}

const ETIQUETA_ESTADO: Record<string, string> = {
  borrador: 'Borrador',
  enviado: 'Enviado',
  revision: 'Revisión',
  aprobado: 'Aprobado',
  bloqueado: 'Bloqueado',
}

/**
 * Tarjeta compacta de "resumen del ciclo" para la columna lateral del Resumen (spec 9.1.5). No
 * duplica el flujo de transición del ciclo (eso ya lo hace `CicloPresupuesto`, siempre visible
 * arriba de las pestañas): aquí solo se resume en texto, sin botones de acción propios.
 */
export function BudgetResumenCiclo({ ciclo, resumen }: Props) {
  return (
    <section className="tarjeta budget-resumen-ciclo" aria-label="Resumen del ciclo">
      <h3>Resumen del ciclo</h3>
      <p>
        <Insignia tono={ciclo.estado === 'bloqueado' || ciclo.estado === 'aprobado' ? 'ok' : 'info'}>
          {ETIQUETA_ESTADO[ciclo.estado] ?? ciclo.estado}
        </Insignia>
      </p>
      <p className="suave">
        {resumen.lineas_capturadas} de {resumen.total_lineas} líneas capturadas ({resumen.cobertura_pct}%)
      </p>
      {ciclo.transiciones_posibles.length > 0 && (
        <p className="suave">
          Próximo paso: {ciclo.transiciones_posibles.map((t) => t.etiqueta).join(' o ')}
        </p>
      )}
    </section>
  )
}
