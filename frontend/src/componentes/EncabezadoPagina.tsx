import type { ReactNode } from 'react'

interface Props {
  /** `id` del título: lo usa la sección (`aria-labelledby`). */
  id: string
  titulo: string
  /** Contexto de la pantalla (periodo, versiones…), en una línea atenuada. */
  subtitulo?: ReactNode
  /** Acciones de la pantalla (exportar, guardar…), a la derecha. */
  acciones?: ReactNode
}

/** Encabezado de página: título, contexto y acciones siempre en el mismo sitio. */
export function EncabezadoPagina({ id, titulo, subtitulo, acciones }: Props) {
  return (
    <header className="encabezado-pagina">
      <div>
        <h2 id={id}>{titulo}</h2>
        {subtitulo && <p className="suave">{subtitulo}</p>}
      </div>
      {acciones && <div className="encabezado-acciones">{acciones}</div>}
    </header>
  )
}
