import type { ReactNode } from 'react'

type Tono = 'neutro' | 'favorable' | 'desfavorable'

interface Props {
  titulo: string
  /** La cifra o el dato principal (ya formateado). */
  valor: ReactNode
  /** Qué línea o qué periodo explica la cifra. */
  detalle?: ReactNode
  tono?: Tono
  /** Contenido adicional bajo el detalle (p. ej. una barra de distribución). */
  extra?: ReactNode
}

/** Tarjeta compacta de resumen: un dato, su contexto y, si aplica, su sentido (favorable/desfavorable). */
export function TarjetaKpi({ titulo, valor, detalle, tono = 'neutro', extra }: Props) {
  return (
    <article className={`kpi kpi-${tono}`}>
      <p className="kpi-titulo">{titulo}</p>
      <p className="kpi-valor">{valor}</p>
      {detalle && <p className="kpi-detalle">{detalle}</p>}
      {extra}
    </article>
  )
}
