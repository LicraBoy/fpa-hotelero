import type { ReactNode } from 'react'

export type Tono = 'ok' | 'aviso' | 'error' | 'info' | 'neutro'

export function Insignia({ tono = 'neutro', children }: { tono?: Tono; children: ReactNode }) {
  return <span className={`insignia insignia-${tono}`}>{children}</span>
}

export function Cargando({ texto = 'Cargando…' }: { texto?: string }) {
  return <p className="suave">{texto}</p>
}

export function MensajeError({ texto }: { texto: string }) {
  return (
    <p className="mensaje mensaje-error" role="alert">
      {texto}
    </p>
  )
}
