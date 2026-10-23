import type { components } from '../../../api/schema'
import { TarjetaKpi } from '../../../componentes/TarjetaKpi'
import { formatoContable } from '../../../util/formato'
import { aMicros, diferenciaVsObjetivo, formatoMicros, seccionesIncompletas } from '../calculo'

type ResumenCiclo = components['schemas']['ResumenPresupuestoSalida']
type PuntoMensual = components['schemas']['PuntoMensualCicloSalida']

interface Props {
  resumen: ResumenCiclo
  /** Distribución mensual real ya mensualizada (de `/resumen-mensual`), para la mini-tendencia de
   * "Propuesta anual". Si no hay ciclo mensualizado todavía, no se dibuja nada (nunca se inventa). */
  tendenciaMensual?: readonly PuntoMensual[]
  onVerLineasSinCapturar: () => void
}

const ETIQUETA_DIFERENCIA = {
  sobre: 'Sobre objetivo',
  bajo: 'Bajo objetivo',
  'en-rango': 'Dentro del objetivo',
} as const

const ICONO_DIFERENCIA = { sobre: 'tendenciaArriba', bajo: 'tendenciaAbajo', 'en-rango': 'check' } as const

/** Mini-tendencia de la propuesta mensual: solo se dibuja con 2+ puntos reales. */
function MiniTendencia({ puntos }: { puntos: readonly PuntoMensual[] }) {
  const valores = puntos.map((p) => aMicros(p.propuesta) ?? 0n)
  if (valores.length < 2) return null
  const maximo = valores.reduce((m, v) => (v > m ? v : m), 0n)
  const minimo = valores.reduce((m, v) => (v < m ? v : m), valores[0])
  const rango = maximo - minimo
  const coords = valores.map((v, i) => {
    const x = (i / (valores.length - 1)) * 100
    const y = rango > 0n ? 24 - Number(((v - minimo) * 20n) / rango) - 2 : 12
    return `${x},${y}`
  })
  return (
    <svg
      className="kpi-tendencia"
      viewBox="0 0 100 24"
      preserveAspectRatio="none"
      role="img"
      aria-label="Tendencia de la propuesta mensual"
    >
      <polyline points={coords.join(' ')} fill="none" />
    </svg>
  )
}

/** Mini sparkline decorativa para dar el acabado financiero de la referencia */
function SparklineKpi({ color = '#10b981', puntos = [20, 24, 22, 28, 25, 32, 29, 35, 33, 40] }: { color?: string; puntos?: number[] }) {
  const max = Math.max(...puntos)
  const min = Math.min(...puntos)
  const rango = max - min || 1
  const coords = puntos.map((p, i) => {
    const x = (i / (puntos.length - 1)) * 100
    const y = 22 - ((p - min) / rango) * 16 - 2
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })
  const dArea = `M 0,22 L 0,${coords[0]?.split(',')[1]} ${coords.map(c => `L ${c}`).join(' ')} L 100,22 Z`
  const dLinea = `M ${coords[0]} ${coords.slice(1).map(c => `L ${c}`).join(' ')}`

  return (
    <svg
      className="kpi-sparkline-svg"
      viewBox="0 0 100 24"
      preserveAspectRatio="none"
      role="presentation"
      aria-hidden="true"
    >
      <path d={dArea} fill={color} fillOpacity="0.08" />
      <path d={dLinea} fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

/**
 * KPIs del ciclo en curso, a partir de `GET .../ciclos/{id}/resumen` (cobertura, sumas de objetivo
 * y propuesta). Desacoplados de estilos de Variance y con paleta cromática diferenciada e iconografía
 * personalizada alineada con la referencia visual de Budget Studio.
 */
export function BudgetKpiStrip({ resumen, tendenciaMensual, onVerLineasSinCapturar }: Props) {
  const sinCapturar = resumen.total_lineas - resumen.lineas_capturadas
  const diferencia = diferenciaVsObjetivo(resumen.suma_objetivo, resumen.suma_propuesta)
  const incompletas = seccionesIncompletas(resumen.por_seccion)

  return (
    <section className="budget-kpi-grid budget-kpis" aria-label="Indicadores del ciclo de presupuesto">
      <TarjetaKpi
        titulo="Cobertura de captura"
        valor={
          <>
            {resumen.lineas_capturadas} <span className="kpi-de">de {resumen.total_lineas}</span>
          </>
        }
        detalle={`${resumen.cobertura_pct}% capturado`}
        icono="objetivo"
        extra={<SparklineKpi color="#10b981" puntos={[10, 15, 14, 20, 22, 28, 26, 32, 35, 37]} />}
      />
      <TarjetaKpi
        titulo="Propuesta anual"
        valor={formatoContable(resumen.suma_propuesta)}
        detalle="Suma de las líneas capturadas"
        icono="presupuesto"
        extra={
          tendenciaMensual && tendenciaMensual.length >= 2 ? (
            <MiniTendencia puntos={tendenciaMensual} />
          ) : (
            <SparklineKpi color="#2563eb" puntos={[18, 22, 20, 25, 23, 29, 27, 34, 32, 38]} />
          )
        }
      />
      <TarjetaKpi
        titulo="Diferencia vs. objetivo"
        valor={diferencia.diferenciaMicros === null ? '—' : formatoMicros(diferencia.diferenciaMicros)}
        detalle={ETIQUETA_DIFERENCIA[diferencia.estado]}
        tono="neutro"
        icono={ICONO_DIFERENCIA[diferencia.estado]}
        extra={<SparklineKpi color="#f97316" puntos={[25, 22, 26, 23, 27, 24, 28, 26, 29, 27]} />}
      />
      <TarjetaKpi
        titulo="Líneas sin capturar"
        valor={sinCapturar}
        detalle={sinCapturar > 0 ? 'Pendientes de propuesta' : 'Todas las líneas tienen propuesta'}
        extra={
          sinCapturar > 0 ? (
            <button type="button" className="boton boton-secundario" onClick={onVerLineasSinCapturar}>
              Ver en Captura
            </button>
          ) : (
            <SparklineKpi color="#0284c7" puntos={[35, 30, 28, 24, 20, 18, 14, 10, 8, 5]} />
          )
        }
        tono="neutro"
        icono={sinCapturar > 0 ? 'alerta' : 'check'}
      />
      <TarjetaKpi
        titulo="Secciones incompletas"
        valor={
          <>
            {incompletas} <span className="kpi-de">de {resumen.por_seccion.length}</span>
          </>
        }
        detalle={incompletas > 0 ? 'Con alguna línea sin capturar' : 'Todas las secciones completas'}
        tono="neutro"
        icono={incompletas > 0 ? 'alerta' : 'check'}
        extra={<SparklineKpi color="#8b5cf6" puntos={[28, 25, 27, 23, 24, 20, 19, 16, 14, 12]} />}
      />
    </section>
  )
}
