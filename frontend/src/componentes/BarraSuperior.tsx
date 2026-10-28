import type { ReactNode } from 'react'
import { ConmutadorTema } from './ConmutadorTema'
import { EstadoApi } from './EstadoApi'
import { Icono } from './Iconos'

interface Props {
  /** Dónde está el usuario: «Budget Studio › Captura». Solo texto; la navegación va en la barra lateral. */
  ubicacion: string[]
  /** Ayuda contextual de la pantalla (popover del icono «?»); sin ayuda no se muestra el icono. */
  ayuda?: ReactNode
  /** Barra lateral plegada y cómo alternarla. */
  lateralPlegado: boolean
  alAlternarLateral: () => void
}

/** Barra superior discreta: migaja a la izquierda; ayuda, tema y estado de la API a la derecha. */
export function BarraSuperior({ ubicacion, ayuda, lateralPlegado, alAlternarLateral }: Props) {
  return (
    <header className="barra-superior">
      <div className="barra-izquierda">
        <button
          type="button"
          className="boton-icono boton-lateral"
          aria-label={lateralPlegado ? 'Expandir el menú lateral' : 'Contraer el menú lateral'}
          aria-pressed={lateralPlegado}
          title={lateralPlegado ? 'Expandir el menú lateral' : 'Contraer el menú lateral'}
          onClick={alAlternarLateral}
        >
          <Icono nombre="menu" />
        </button>
        <nav className="ubicacion" aria-label="Ubicación">
          <ol>
            {ubicacion.map((tramo, i) => (
              <li key={`${tramo}-${i}`} aria-current={i === ubicacion.length - 1 ? 'page' : undefined}>
                {i > 0 && <Icono nombre="chevron" tamano={14} />}
                {tramo}
              </li>
            ))}
          </ol>
        </nav>
      </div>
      <div className="barra-acciones">
        <EstadoApi />
        {ayuda && (
          <details className="ayuda-barra">
            <summary className="boton-icono" aria-label="Ayuda de esta pantalla" title="Ayuda">
              <Icono nombre="info" tamano={16} />
            </summary>
            <div className="ayuda-barra-panel" role="note">
              {ayuda}
            </div>
          </details>
        )}
        <ConmutadorTema />
      </div>
    </header>
  )
}
