import type { ReactNode } from 'react'
import { ConmutadorTema } from './ConmutadorTema'
import { EstadoApi } from './EstadoApi'
import { Icono } from './Iconos'

interface Props {
  /** Dónde está el usuario: «Reportes › Variance». Solo texto; la navegación va en la barra lateral. */
  ubicacion: string[]
  /** Selector de hotel (solo si el usuario tiene hoteles). */
  hotel?: ReactNode
  nombreUsuario: string
  rol?: string
}

function iniciales(nombre: string): string {
  const letras = nombre
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0].toUpperCase())
  return letras.join('') || '?'
}

/** Barra superior: ubicación a la izquierda; hotel, estado de la API, tema y usuario a la derecha. */
export function BarraSuperior({ ubicacion, hotel, nombreUsuario, rol }: Props) {
  return (
    <header className="barra-superior">
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
      <div className="barra-acciones">
        {hotel}
        <EstadoApi />
        <ConmutadorTema />
        <div className="usuario">
          <span className="avatar" aria-hidden="true">
            {iniciales(nombreUsuario)}
          </span>
          <span className="usuario-datos">
            <strong>{nombreUsuario}</strong>
            {rol && <span className="suave">{rol}</span>}
          </span>
        </div>
      </div>
    </header>
  )
}
