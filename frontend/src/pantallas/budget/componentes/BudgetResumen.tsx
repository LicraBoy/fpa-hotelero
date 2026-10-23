import type { components } from '../../../api/schema'
import { Cargando, EstadoVacio, MensajeError } from '../../../componentes/Insignia'
import { BudgetAlertas } from './BudgetAlertas'
import { BudgetComposicionChart } from './BudgetComposicionChart'
import { BudgetDistribucionMensualChart } from './BudgetDistribucionMensualChart'
import { BudgetKpiStrip } from './BudgetKpiStrip'
import { BudgetObjetivoVsPropuestaChart } from './BudgetObjetivoVsPropuestaChart'
import { BudgetPrincipalesDiferencias } from './BudgetPrincipalesDiferencias'
import { BudgetResumenCiclo } from './BudgetResumenCiclo'

type ResumenCiclo = components['schemas']['ResumenPresupuestoSalida']
type ResumenMensual = components['schemas']['ResumenMensualCicloSalida']
type Ciclo = components['schemas']['CicloSalida']
type LineaCaptura = components['schemas']['LineaCapturaSalida']

interface Props {
  ciclo: Ciclo | null
  resumen: ResumenCiclo | null
  resumenMensual: ResumenMensual | null
  lineasCiclo: readonly LineaCaptura[]
  cargando: boolean
  error: string | null
  onIrACaptura: (seccion?: string) => void
}

/**
 * Pestaña Resumen: KPIs + gráfica + alertas, todo real (nada de cifras de relleno). Si no hay ciclo
 * abierto o no tiene líneas, se explica por qué en vez de mostrar una tira de ceros (spec §4.1/§9).
 */
export function BudgetResumen({
  ciclo,
  resumen,
  resumenMensual,
  lineasCiclo,
  cargando,
  error,
  onIrACaptura,
}: Props) {
  if (ciclo === null) {
    return (
      <EstadoVacio>
        Todavía no hay un ciclo de presupuesto abierto para este año fiscal: ábrelo para ver su
        avance aquí.
      </EstadoVacio>
    )
  }
  if (cargando && !resumen) return <Cargando />
  if (error) return <MensajeError texto={error} />
  if (!resumen || resumen.total_lineas === 0) {
    return <EstadoVacio>El ciclo todavía no tiene líneas de captura.</EstadoVacio>
  }

  return (
    <div className="budget-resumen">
      <BudgetKpiStrip
        resumen={resumen}
        tendenciaMensual={resumenMensual?.por_periodo}
        onVerLineasSinCapturar={() => onIrACaptura()}
      />
      <div className="budget-resumen-fila">
        <BudgetObjetivoVsPropuestaChart porSeccion={resumen.por_seccion} onSeleccionarSeccion={onIrACaptura} />
        <BudgetPrincipalesDiferencias lineas={lineasCiclo} onSeleccionarSeccion={onIrACaptura} />
        <div className="budget-resumen-lateral">
          <BudgetResumenCiclo ciclo={ciclo} resumen={resumen} />
          <BudgetAlertas
            resumen={resumen}
            resumenMensual={resumenMensual}
            ciclo={ciclo}
            onVerLineasSinCapturar={() => onIrACaptura()}
          />
        </div>
      </div>
      {resumenMensual && <BudgetDistribucionMensualChart resumenMensual={resumenMensual} />}
      <BudgetComposicionChart porSeccion={resumen.por_seccion} />
    </div>
  )
}
