import { construirRuta, type Bloque } from '../../ruta/ruta'

interface Props {
  periodo: string
  bloque: Bloque
  /** Último tramo (la pantalla actual), sin enlace. */
  actual: string
  /** Tramos intermedios con su enlace (p. ej. la línea desde la que se llegó). */
  intermedios?: { texto: string; href: string }[]
  /** Paso del recorrido, p. ej. «Paso 2 de 4 · Cuentas de la línea». */
  paso?: string
  /** A dónde regresa el botón «Volver» (la pantalla anterior del recorrido). */
  volver?: { texto: string; href: string }
}

/**
 * Migas de pan y botón «Volver»: Variance › mes › línea › cuenta › pantalla actual. Todo son
 * enlaces por hash (copiables), así que funcionan igual con un enlace pegado en otra pestaña.
 */
export function Migas({ periodo, bloque, actual, intermedios = [], paso, volver }: Props) {
  return (
    <nav className="migas" aria-label="Ruta de navegación">
      {volver && (
        <a className="boton boton-secundario boton-volver" href={volver.href}>
          ← Volver a {volver.texto}
        </a>
      )}
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
        {paso && <strong>{paso} · </strong>}
        {bloque === 'mes' ? 'Solo el mes' : 'Acumulado del año fiscal'}
      </p>
    </nav>
  )
}
