import { useRef, type KeyboardEvent } from 'react'
import { Icono, type NombreIcono } from '../../../componentes/Iconos'

export type PestanaBudget = 'resumen' | 'captura' | 'versiones'

const PESTANAS: { id: PestanaBudget; etiqueta: string; icono: NombreIcono }[] = [
  { id: 'resumen', etiqueta: 'Resumen', icono: 'informe' },
  { id: 'captura', etiqueta: 'Captura', icono: 'presupuesto' },
  { id: 'versiones', etiqueta: 'Versiones', icono: 'auditoria' },
]

interface Props {
  activa: PestanaBudget
  onCambiar: (p: PestanaBudget) => void
}

/**
 * Pestañas de Budget Studio: Segmented control moderno estilo Linear/Ramp.
 */
export function BudgetTabs({ activa, onCambiar }: Props) {
  const refs = useRef<Record<PestanaBudget, HTMLButtonElement | null>>({
    resumen: null,
    captura: null,
    versiones: null,
  })

  function alTeclado(e: KeyboardEvent, i: number) {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return
    e.preventDefault()
    const siguiente = (i + (e.key === 'ArrowRight' ? 1 : -1) + PESTANAS.length) % PESTANAS.length
    refs.current[PESTANAS[siguiente].id]?.focus()
  }

  return (
    <div className="budget-tabs" role="tablist" aria-label="Secciones de Budget">
      {PESTANAS.map((p, i) => (
        <button
          key={p.id}
          ref={(el) => {
            refs.current[p.id] = el
          }}
          type="button"
          role="tab"
          id={`budget-tab-${p.id}`}
          aria-selected={activa === p.id}
          aria-controls={`budget-panel-${p.id}`}
          tabIndex={activa === p.id ? 0 : -1}
          className="budget-tab"
          onClick={() => onCambiar(p.id)}
          onKeyDown={(e) => alTeclado(e, i)}
        >
          <Icono nombre={p.icono} tamano={15} />
          <span>{p.etiqueta}</span>
        </button>
      ))}
    </div>
  )
}
