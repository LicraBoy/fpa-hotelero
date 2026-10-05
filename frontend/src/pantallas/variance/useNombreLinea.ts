import { obtenerTipado } from '../../api/cliente'
import { useDatos } from '../../api/useDatos'
import type { Bloque } from '../../ruta/ruta'

/**
 * Nombre de la línea del reporte desde la que se llegó a una cuenta o a un asiento (para las migas
 * y el botón «Volver»). Sin `lineaId` no consulta nada.
 */
export function useNombreLinea(
  hotelId: number,
  periodo: string,
  lineaId: number | undefined,
  bloque: Bloque,
): string | null {
  const datos = useDatos(
    () =>
      lineaId === undefined
        ? Promise.resolve(null)
        : obtenerTipado('/api/v1/hoteles/{hotel_id}/variance/lineas/{linea_id}/desglose', {
            path: { hotel_id: hotelId, linea_id: lineaId },
            query: { periodo, bloque },
          }),
    [hotelId, periodo, lineaId, bloque],
  )
  return datos.datos?.descripcion ?? null
}
