import { useRef, type KeyboardEvent } from 'react'

export type PestanaBudget = 'resumen' | 'captura' | 'versiones'

const PESTANAS: { id: PestanaBudget; etiqueta: string }[] = [
  { id: 'resumen', etiqueta: 'Resumen' },
  { id: 'captura', etiqueta: 'Captura' },
  { id: 'versiones', etiqueta: 'Versiones' },
]

interface Props {
  activa: PestanaBudget
  onCambiar: (p: PestanaBudget) => void
}

/**
 * Pestañas de Budget Studio. No hay mecanismo de tabs en el resto del repo: se construye a mano,
 * accesible (role="tablist"/"tab"/"tabpanel"), con activación manual (Enter/Espacio) para que
 * navegar con flechas no dispare de inmediato el render de las gráficas de Resumen.
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
          {p.etiqueta}
        </button>
      ))}
    </div>
  )
}
