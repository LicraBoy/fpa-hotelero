import { obtenerTipado } from '../../api/cliente'
import { useDatos } from '../../api/useDatos'
import { Insignia, MensajeError } from '../../componentes/Insignia'

const ETIQUETA: Record<string, string> = {
  carga: 'Carga',
  mapeo: 'Mapeo',
  captura: 'Captura',
  comentario: 'Comentario',
  cierre: 'Cierre',
}

function fecha(iso: string): string {
  return new Date(iso).toLocaleString('es-MX', { dateStyle: 'medium', timeStyle: 'short' })
}

/** Cronología de lo que ha afectado la cifra de una línea: cargas, mapeo, capturas, comentarios, cierre. */
export function HistorialCifra({
  hotelId,
  periodo,
  lineaId,
}: {
  hotelId: number
  periodo: string
  lineaId: number
}) {
  const h = useDatos(
    () =>
      obtenerTipado('/api/v1/hoteles/{hotel_id}/variance/lineas/{linea_id}/historial', {
        path: { hotel_id: hotelId, linea_id: lineaId },
        query: { periodo },
      }),
    [hotelId, periodo, lineaId],
  )
  return (
    <details className="historial-cifra">
      <summary>Historial de la cifra</summary>
      {h.error && <MensajeError texto={h.error} />}
      {h.datos && h.datos.hechos.length === 0 && (
        <p className="suave">Todavía no hay movimientos registrados para esta cifra.</p>
      )}
      <ol className="historial-lista">
        {h.datos?.hechos.map((x, i) => (
          <li key={i}>
            <span className="suave">{fecha(x.fecha)}</span> <Insignia>{ETIQUETA[x.tipo] ?? x.tipo}</Insignia>{' '}
            {/* lo escriben personas o vienen de archivos: se muestra como texto */}
            <strong>{x.titulo}</strong>
            {x.usuario ? <span className="suave"> · {x.usuario}</span> : null}
            {x.detalle ? <div className="suave">{x.detalle}</div> : null}
          </li>
        ))}
      </ol>
    </details>
  )
}
