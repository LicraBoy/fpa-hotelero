import type { ReactNode } from 'react'
import { puede, type Permiso } from '../permisos'

/**
 * Monta la pantalla solo si el rol tiene el permiso. Sin permiso muestra "Sin acceso" y **no se
 * monta nada**: ninguna consulta sale al servidor. (El servidor autoriza igual y siempre: esto
 * solo evita mostrar pantallas que de todos modos responderían 403.)
 */
export function RutaProtegida({
  rol,
  permiso,
  children,
}: {
  rol: string | undefined
  permiso: Permiso
  children: ReactNode
}) {
  if (!puede(rol, permiso)) return <SinAcceso />
  return <>{children}</>
}

/** Aviso cuando el rol no puede abrir la pantalla; no se consulta nada al servidor. */
export function SinAcceso() {
  return (
    <section className="mensaje mensaje-aviso" role="alert" aria-label="Sin acceso">
      <strong>Sin acceso.</strong> Tu rol no tiene permiso para ver esta pantalla.
    </section>
  )
}
