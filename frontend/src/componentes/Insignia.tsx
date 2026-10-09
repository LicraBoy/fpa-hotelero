import type { ReactNode } from 'react'

export type Tono = 'ok' | 'aviso' | 'error' | 'info' | 'neutro'

export function Insignia({ tono = 'neutro', children }: { tono?: Tono; children: ReactNode }) {
  return <span className={`insignia insignia-${tono}`}>{children}</span>
}

/** Estado de carga: misma presentación en todas las pantallas. */
export function Cargando({ texto = 'Cargando…' }: { texto?: string }) {
  return <p className="estado estado-cargando">{texto}</p>
}

/** Estado vacío: todavía no hay datos (distinto de un error). */
export function EstadoVacio({ children }: { children: ReactNode }) {
  return <p className="estado estado-vacio">{children}</p>
}

export function MensajeError({ texto }: { texto: string }) {
  return (
    <p className="mensaje mensaje-error" role="alert">
      {texto}
    </p>
  )
}
