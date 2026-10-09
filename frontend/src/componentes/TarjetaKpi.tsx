import type { ReactNode } from 'react'
import { Icono, type NombreIcono } from './Iconos'

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
  /** Icono decorativo en el recuadro de la esquina. */
  icono?: NombreIcono
}

/** Tarjeta compacta de resumen: un dato, su contexto y, si aplica, su sentido (favorable/desfavorable). */
export function TarjetaKpi({ titulo, valor, detalle, tono = 'neutro', extra, icono }: Props) {
  return (
    <article className={`kpi kpi-${tono}`}>
      <div className="kpi-cabecera">
        <p className="kpi-titulo">{titulo}</p>
        {icono && (
          <span className="kpi-icono">
            <Icono nombre={icono} tamano={18} />
          </span>
        )}
      </div>
      <p className="kpi-valor">{valor}</p>
      {detalle && <p className="kpi-detalle">{detalle}</p>}
      {extra}
    </article>
  )
}
