import type { components } from '../../../api/schema'
import { EstadoVacio, MensajeError } from '../../../componentes/Insignia'
import { BudgetAccionesRapidas } from './BudgetAccionesRapidas'
import { BudgetComoFunciona } from './BudgetComoFunciona'
import { BudgetDistribucionMensualChart } from './BudgetDistribucionMensualChart'
import { BudgetKpiStrip } from './BudgetKpiStrip'
import { BudgetPrincipalesDiferencias } from './BudgetPrincipalesDiferencias'
import { BudgetResumenCiclo } from './BudgetResumenCiclo'
import { BudgetKpiSkeleton, BudgetTablaSkeleton } from './BudgetSkeletons'
import type { PestanaBudget } from './BudgetTabs'
import { BudgetVariacionSeccionChart } from './BudgetVariacionSeccionChart'

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
  onNavegarTab?: (pestana: PestanaBudget) => void
}

/**
 * Dashboard analítico de Budget Studio (spec §3 y referencia visual, simplificado tras
 * revisión de diseño — ver docs/TRASPASO u opinión de contralor de oct-2026):
 * 1. Fila de cinco KPIs clave
 * 2. Fila de análisis en 3 columnas (Variación por sección, Principales diferencias, Resumen del ciclo)
 * 3. Distribución mensual (ancho completo; "Perfil de temporada" se movió a Captura, es una
 *    herramienta de configuración, no un resultado del ciclo)
 * 4. Fila inferior en 2 columnas (Cómo funciona Budget, Acciones rápidas)
 */
export function BudgetResumen({
  ciclo,
  resumen,
  resumenMensual,
  lineasCiclo,
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
  if (cargando && !resumen) {
    return (
      <div className="budget-resumen" aria-label="Cargando resumen del presupuesto">
        <BudgetKpiSkeleton />
        <BudgetTablaSkeleton filas={5} ariaLabel="Cargando métricas del ciclo…" />
      </div>
    )
  }
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
        <BudgetVariacionSeccionChart
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

      {/* 3. Tercera fila: distribución mensual, ancho completo */}
      <div className="budget-trend-grid budget-trend-grid-unica">
        <BudgetDistribucionMensualChart
          resumenMensual={resumenMensual ?? { por_periodo: [], por_seccion: [], lineas_sin_mensualizar: 0 }}
        />
      </div>

      {/* 4. Cuarta fila: cómo funciona y acciones rápidas */}
      <div className="budget-bottom-grid">
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
