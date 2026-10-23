import type { components } from '../../../api/schema'
import { Cargando, EstadoVacio, MensajeError } from '../../../componentes/Insignia'
import { BudgetAccionesRapidas } from './BudgetAccionesRapidas'
import { BudgetComoFunciona } from './BudgetComoFunciona'
import { BudgetComposicionChart } from './BudgetComposicionChart'
import { BudgetDistribucionMensualChart } from './BudgetDistribucionMensualChart'
import { BudgetKpiStrip } from './BudgetKpiStrip'
import { BudgetObjetivoVsPropuestaChart } from './BudgetObjetivoVsPropuestaChart'
import { BudgetPerfilTemporada } from './BudgetPerfilTemporada'
import { BudgetPrincipalesDiferencias } from './BudgetPrincipalesDiferencias'
import { BudgetResumenCiclo } from './BudgetResumenCiclo'
import type { PestanaBudget } from './BudgetTabs'

type ResumenCiclo = components['schemas']['ResumenPresupuestoSalida']
type ResumenMensual = components['schemas']['ResumenMensualCicloSalida']
type Ciclo = components['schemas']['CicloSalida']
type LineaCaptura = components['schemas']['LineaCapturaSalida']
type Perfil = components['schemas']['PerfilSalida']

interface Props {
  ciclo: Ciclo | null
  resumen: ResumenCiclo | null
  resumenMensual: ResumenMensual | null
  lineasCiclo: readonly LineaCaptura[]
  perfiles?: readonly Perfil[]
  cargando: boolean
  error: string | null
  onIrACaptura: (seccion?: string) => void
  onNavegarTab?: (pestana: PestanaBudget) => void
}

/**
 * Dashboard analítico de Budget Studio (spec §3 y referencia visual):
 * 1. Fila de cinco KPIs clave
 * 2. Fila de análisis en 3 columnas (Objetivo vs. propuesta, Principales diferencias, Resumen del ciclo)
 * 3. Fila de tendencia en 2 columnas (Distribución mensual julio-junio y Perfil de temporada)
 * 4. Fila inferior en 3 columnas (Composición del presupuesto, Cómo funciona Budget, Acciones rápidas)
 */
export function BudgetResumen({
  ciclo,
  resumen,
  resumenMensual,
  lineasCiclo,
  perfiles = [],
  cargando,
  error,
  onIrACaptura,
  onNavegarTab,
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

  const sinCapturar = resumen.total_lineas - resumen.lineas_capturadas

  return (
    <div className="budget-resumen">
      {/* 1. Primera fila: cinco KPI uniformes */}
      <BudgetKpiStrip
        resumen={resumen}
        tendenciaMensual={resumenMensual?.por_periodo}
        onVerLineasSinCapturar={() => onIrACaptura()}
      />

      {/* 2. Segunda fila: análisis en tres columnas (~48% / ~28% / ~24%) */}
      <div className="budget-analysis-grid">
        <BudgetObjetivoVsPropuestaChart
          porSeccion={resumen.por_seccion}
          onSeleccionarSeccion={onIrACaptura}
        />
        <BudgetPrincipalesDiferencias
          lineas={lineasCiclo}
          onSeleccionarSeccion={onIrACaptura}
        />
        <BudgetResumenCiclo
          ciclo={ciclo}
          resumen={resumen}
          onIrACaptura={() => onIrACaptura()}
        />
      </div>

      {/* 3. Tercera fila: distribución mensual y perfil estacional (~75% / ~25%) */}
      <div className="budget-trend-grid">
        <BudgetDistribucionMensualChart
          resumenMensual={resumenMensual ?? { por_periodo: [], lineas_sin_mensualizar: 0 }}
        />
        <BudgetPerfilTemporada
          perfiles={perfiles}
          onIrACaptura={() => onIrACaptura()}
        />
      </div>

      {/* 4. Cuarta fila: composición, cómo funciona y acciones rápidas */}
      <div className="budget-bottom-grid">
        <BudgetComposicionChart
          porSeccion={resumen.por_seccion}
          onIrACaptura={() => onIrACaptura()}
        />
        <BudgetComoFunciona onIrACaptura={() => onIrACaptura()} />
        <BudgetAccionesRapidas
          lineasSinCapturar={sinCapturar}
          onIrACaptura={() => onIrACaptura()}
          onVerVersiones={() => onNavegarTab?.('versiones')}
        />
      </div>
    </div>
  )
}
