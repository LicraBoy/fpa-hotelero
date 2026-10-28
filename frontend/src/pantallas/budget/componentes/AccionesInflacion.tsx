import { Icono } from '../../../componentes/Iconos'
import { fraccionAPorcentaje } from '../hojaSeccion'
import type { EstadoInflacion } from './TablaInflacion'

/**
 * Barra de acciones de la inflación (la usan las dos tablas): a la izquierda dice en qué estado está
 * (sin cambios o cuántos meses cambiaron) y recuerda que es informativa; a la derecha, Descartar y Guardar
 * con el mismo estado y los mismos handlers de siempre. Naranja = pendiente, igual que en el Editor mensual.
 */
export function AccionesInflacion({ e, fija }: { e: EstadoInflacion; fija?: boolean }) {
  if (!e.puedeEditar) return null
  const cambiados = e.inflacion.filter((t, i) => t !== fraccionAPorcentaje(e.inflacionGuardada[i])).length
  const clases = ['acciones-inflacion', e.sucio ? 'acciones-inflacion-pendiente' : '', fija ? 'acciones-inflacion-fija' : '']
    .filter(Boolean)
    .join(' ')
  return (
    <div className={clases}>
      <span className="acciones-inflacion-estado" role="status">
        {e.sucio ? (
          <>
            <span className="acciones-inflacion-punto" aria-hidden="true" />
            <strong>{cambiados === 1 ? '1 mes con cambios' : `${cambiados} meses con cambios`}</strong> sin guardar
          </>
        ) : (
          <>
            <Icono nombre="info" tamano={15} />
            {e.entraAlBudget
              ? 'Sin cambios. La inflación de esta cuenta sí entra al Budget.'
              : 'Sin cambios. La inflación es informativa: no modifica el Budget.'}
          </>
        )}
      </span>
      <span className="acciones-inflacion-botones">
        <button type="button" className="acciones-descartar" disabled={!e.sucio} onClick={e.descartar}>
          Descartar
          <span className="solo-lectores"> inflación</span>
        </button>
        <button type="button" className="acciones-guardar" disabled={!e.sucio || e.invalida || e.guardando} onClick={e.guardar}>
          <Icono nombre="guardar" tamano={15} />
          {e.guardando ? 'Guardando…' : 'Guardar inflación'}
        </button>
      </span>
    </div>
  )
}
