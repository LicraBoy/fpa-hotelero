import { Icono } from '../../../componentes/Iconos'

interface Props {
  lineasSinCapturar: number
  onIrACaptura: () => void
  onVerVersiones: () => void
}

/**
 * Tarjeta de Acciones Rápidas (spec §3.7 y referencia visual).
 * Accesos directos enriquecidos con contexto y diseño premium.
 */
export function BudgetAccionesRapidas({ lineasSinCapturar, onIrACaptura, onVerVersiones }: Props) {
  return (
    <section className="tarjeta budget-chart-contenedor budget-acciones-rapidas" aria-label="Acciones rápidas">
      <div className="budget-chart-cabecera">
        <div>
          <h3>Acciones rápidas</h3>
          <p className="suave">Accesos directos del módulo</p>
        </div>
        <Icono nombre="objetivo" tamano={18} />
      </div>

      <div className="budget-acciones-lista">
        <button
          type="button"
          className="budget-accion-card-btn"
          onClick={onIrACaptura}
          title="Abrir la pestaña de Captura para editar y copiar importes de Actual"
        >
          <span className="budget-accion-icono-wrap">
            <Icono nombre="presupuesto" tamano={16} />
          </span>
          <span className="budget-accion-textos">
            <span className="budget-accion-label">Copiar Actual a Budget</span>
            <span className="budget-accion-desc">Poblar base con datos reales</span>
          </span>
        </button>

        <button
          type="button"
          className="budget-accion-card-btn"
          onClick={onIrACaptura}
          title="Ir a Captura para aplicar perfiles de distribución estacional"
        >
          <span className="budget-accion-icono-wrap">
            <Icono nombre="calendario" tamano={16} />
          </span>
          <span className="budget-accion-textos">
            <span className="budget-accion-label">Aplicar distribución</span>
            <span className="budget-accion-desc">Curva de estacionalidad</span>
          </span>
        </button>

        <button
          type="button"
          className="budget-accion-card-btn"
          onClick={onVerVersiones}
          title="Consultar y comparar el historial de versiones del plan"
        >
          <span className="budget-accion-icono-wrap">
            <Icono nombre="auditoria" tamano={16} />
          </span>
          <span className="budget-accion-textos">
            <span className="budget-accion-label">Historial de versiones</span>
            <span className="budget-accion-desc">Auditar cambios y estados</span>
          </span>
        </button>

        <button
          type="button"
          className="budget-accion-card-btn"
          onClick={onIrACaptura}
          title="Ver distribución mensual por cuenta en la pestaña de Captura"
        >
          <span className="budget-accion-icono-wrap">
            <Icono nombre="exportar" tamano={16} />
          </span>
          <span className="budget-accion-textos">
            <span className="budget-accion-label">
              {lineasSinCapturar > 0
                ? `Líneas sin capturar (${lineasSinCapturar})`
                : 'Ver desglose mensual'}
            </span>
            <span className="budget-accion-desc">
              {lineasSinCapturar > 0 ? 'Pendientes de completar' : 'Revisión mensual por partida'}
            </span>
          </span>
        </button>
      </div>
    </section>
  )
}
