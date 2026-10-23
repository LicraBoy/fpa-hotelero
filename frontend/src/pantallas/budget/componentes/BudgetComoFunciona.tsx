import { Icono } from '../../../componentes/Iconos'

interface Props {
  onIrACaptura: () => void
}

interface PasoFlujo {
  numero: number
  titulo: string
  detalle: string
  icono: 'objetivo' | 'presupuesto' | 'informe' | 'check'
}

const PASOS_FLUJO: PasoFlujo[] = [
  { numero: 1, titulo: 'Objetivo', detalle: 'Metas dirección', icono: 'objetivo' },
  { numero: 2, titulo: 'Captura', detalle: 'Carga por depto', icono: 'presupuesto' },
  { numero: 3, titulo: 'Revisión', detalle: 'Brechas y ajuste', icono: 'informe' },
  { numero: 4, titulo: 'Aprobado', detalle: 'Línea base oficial', icono: 'check' },
]

/**
 * Tarjeta interactiva "¿Cómo funciona el Budget?" (spec §3.7).
 * Reemplaza el banner ilustrado estático por un flujo visual claro y moderno
 * de las 4 fases del ciclo presupuestario hotelero, totalmente adaptado a modo claro/oscuro.
 */
export function BudgetComoFunciona({ onIrACaptura }: Props) {
  return (
    <section className="tarjeta budget-chart-contenedor budget-como-funciona" aria-label="Cómo funciona el Budget">
      <div className="budget-chart-cabecera">
        <div>
          <h3>¿Cómo funciona el Budget?</h3>
          <p className="suave">Ciclo del ejercicio presupuestario</p>
        </div>
        <Icono nombre="info" tamano={18} />
      </div>

      <div className="budget-como-funciona-cuerpo">
        <p className="budget-como-funciona-desc">
          El presupuesto se captura por departamento, se contrasta con el objetivo de Dirección
          y se consolida en un ciclo controlado de aprobación antes de publicarse como plan oficial.
        </p>

        <div className="budget-flujo-pasos" role="list" aria-label="Fases del ciclo presupuestario">
          {PASOS_FLUJO.map((paso, idx) => (
            <div key={paso.numero} className="budget-flujo-paso-item" role="listitem">
              <div className="budget-flujo-paso-nodo">
                <div className="budget-flujo-icono" data-step={paso.numero} title={`Paso ${paso.numero}: ${paso.titulo}`}>
                  <Icono nombre={paso.icono} tamano={15} />
                </div>
                <div className="budget-flujo-info">
                  <span className="budget-flujo-num">Fase {paso.numero}</span>
                  <strong className="budget-flujo-titulo">{paso.titulo}</strong>
                  <span className="budget-flujo-sub">{paso.detalle}</span>
                </div>
              </div>
              {idx < PASOS_FLUJO.length - 1 && (
                <div className="budget-flujo-conector" aria-hidden="true">
                  <span className="budget-flujo-flecha">›</span>
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="budget-como-funciona-enlace-wrap">
          <button
            type="button"
            className="budget-enlace-texto"
            onClick={onIrACaptura}
            title="Ir a captura para iniciar el registro de propuestas"
          >
            Iniciar captura de propuestas →
          </button>
        </div>
      </div>
    </section>
  )
}
