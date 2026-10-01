import { construirRuta, type Bloque } from '../../ruta/ruta'

interface Props {
  periodo: string
  bloque: Bloque
  /** Último tramo (la pantalla actual), sin enlace. */
  actual: string
  /** Tramos intermedios con su enlace (p. ej. la línea desde la que se llegó). */
  intermedios?: { texto: string; href: string }[]
}

/** Migas de pan: Variance › mes › … › pantalla actual. Todo son enlaces por hash (copiables). */
export function Migas({ periodo, bloque, actual, intermedios = [] }: Props) {
  return (
    <nav className="migas" aria-label="Ruta de navegación">
      <ol>
        <li>
          <a href={construirRuta({ tipo: 'variance', periodo })}>Variance {periodo}</a>
        </li>
        {intermedios.map((m) => (
          <li key={m.href}>
            <a href={m.href}>{m.texto}</a>
          </li>
        ))}
        <li aria-current="page">{actual}</li>
      </ol>
      <p className="suave migas-bloque">
        {bloque === 'mes' ? 'Solo el mes' : 'Acumulado del año fiscal'}
      </p>
    </nav>
  )
}
