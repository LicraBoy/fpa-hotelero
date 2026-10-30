import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { Icono, type NombreIcono } from '../../../componentes/Iconos'

export type TonoIndicador = 'azul' | 'verde' | 'morado' | 'naranja' | 'celeste' | 'rojo' | 'neutro' | 'positivo' | 'negativo'

/**
 * Tarjeta de indicador: icono en círculo tintado, etiqueta y valor. El tinte es decorativo: el signo
 * de un importe siempre va en el texto del valor.
 */
export function TarjetaIndicador({
  tono,
  icono,
  etiqueta,
  children,
  nota,
  compacto,
}: {
  compacto?: boolean
  tono: TonoIndicador
  icono: NombreIcono
  etiqueta: string
  children: ReactNode
  nota?: ReactNode
}) {
  return (
    <div className={`hi-tarjeta hi-${tono}${compacto ? ' hi-compacto' : ''}`}>
      <span className="hi-icono" aria-hidden="true">
        <Icono nombre={icono} tamano={compacto ? 18 : 22} />
      </span>
      <div className="hi-textos">
        <span className="hi-etiqueta">{etiqueta}</span>
        <strong className="hi-valor">{children}</strong>
        {nota && <span className="hi-nota">{nota}</span>}
      </div>
    </div>
  )
}

/** Icono ⓘ con un tooltip accesible por foco y por hover (el texto va en `aria-describedby`). */
export function AyudaTooltip({ etiqueta, texto }: { etiqueta: string; texto: ReactNode }) {
  const id = useId()
  return (
    <span className="ayuda-tooltip">
      <button type="button" className="ayuda-tooltip-boton" aria-label={etiqueta} aria-describedby={id}>
        <Icono nombre="info" tamano={15} />
      </button>
      <span role="tooltip" id={id} className="ayuda-tooltip-texto">
        {texto}
      </span>
    </span>
  )
}

export interface OpcionMenu {
  etiqueta: string
  alElegir: () => void
}

/** Menú «⋯» de acciones: se cierra con Esc, al elegir o al hacer clic fuera. */
export function MenuMas({ opciones }: { opciones: OpcionMenu[] }) {
  const [abierto, setAbierto] = useState(false)
  const raiz = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!abierto) return
    const fuera = (e: MouseEvent) => {
      if (raiz.current && !raiz.current.contains(e.target as Node)) setAbierto(false)
    }
    const tecla = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setAbierto(false)
    }
    document.addEventListener('mousedown', fuera)
    document.addEventListener('keydown', tecla)
    return () => {
      document.removeEventListener('mousedown', fuera)
      document.removeEventListener('keydown', tecla)
    }
  }, [abierto])
  return (
    <div className="menu-mas" ref={raiz}>
      <button
        type="button"
        className="boton-icono menu-mas-boton"
        aria-label="Más acciones"
        aria-haspopup="menu"
        aria-expanded={abierto}
        onClick={() => setAbierto((a) => !a)}
      >
        <Icono nombre="mas" tamano={18} />
      </button>
      {abierto && (
        <div role="menu" className="menu-mas-lista">
          {opciones.map((o) => (
            <button
              key={o.etiqueta}
              type="button"
              role="menuitem"
              onClick={() => {
                setAbierto(false)
                o.alElegir()
              }}
            >
              {o.etiqueta}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
