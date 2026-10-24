/**
 * Skeletons compactos para Budget Studio (especificación §4 y WCAG 2.1 AA).
 * Respetan las dimensiones exactas de tarjetas, timeline y tablas para evitar
 * saltos de página (Cumulative Layout Shift - CLS) durante la carga asíncrona.
 */

interface SkeletonProps {
  filas?: number
  ariaLabel?: string
}

export function BudgetTablaSkeleton({ filas = 6, ariaLabel = 'Cargando datos de la tabla…' }: SkeletonProps) {
  return (
    <div
      className="budget-skeleton-contenedor"
      role="status"
      aria-live="polite"
      aria-label={ariaLabel}
    >
      <div className="budget-skeleton-cabecera-tabla" />
      <div className="budget-skeleton-filas">
        {Array.from({ length: filas }).map((_, i) => (
          <div key={i} className="budget-skeleton-fila">
            <div className="budget-skeleton-celda budget-skeleton-celda-texto" />
            <div className="budget-skeleton-celda budget-skeleton-celda-num" />
            <div className="budget-skeleton-celda budget-skeleton-celda-num" />
            <div className="budget-skeleton-celda budget-skeleton-celda-num" />
          </div>
        ))}
      </div>
      <span className="solo-lectores">Cargando información, por favor espere...</span>
    </div>
  )
}

export function BudgetTimelineSkeleton({ filas = 3, ariaLabel = 'Cargando historial de versiones…' }: SkeletonProps) {
  return (
    <div
      className="budget-skeleton-timeline"
      role="status"
      aria-live="polite"
      aria-label={ariaLabel}
    >
      {Array.from({ length: filas }).map((_, i) => (
        <div key={i} className="budget-skeleton-timeline-item">
          <div className="budget-skeleton-timeline-nodo" />
          <div className="budget-skeleton-timeline-tarjeta">
            <div className="budget-skeleton-linea budget-skeleton-linea-titulo" />
            <div className="budget-skeleton-linea budget-skeleton-linea-sub" />
            <div className="budget-skeleton-linea budget-skeleton-linea-corta" />
          </div>
        </div>
      ))}
      <span className="solo-lectores">Cargando versiones históricas...</span>
    </div>
  )
}

export function BudgetKpiSkeleton() {
  return (
    <div className="budget-kpi-grid" role="status" aria-label="Cargando indicadores clave…">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="kpi budget-skeleton-kpi">
          <div className="budget-skeleton-linea budget-skeleton-linea-sub" />
          <div className="budget-skeleton-linea budget-skeleton-linea-valor" />
          <div className="budget-skeleton-linea budget-skeleton-linea-corta" />
        </div>
      ))}
      <span className="solo-lectores">Cargando indicadores de presupuesto...</span>
    </div>
  )
}
