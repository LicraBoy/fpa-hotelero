import { obtenerTipado } from '../api/cliente'
import { useDatos } from '../api/useDatos'
import { Insignia } from './Insignia'

/** Estado de la cadena de hashes de la bitácora: íntegra o alterada, con el hash a anotar aparte. */
export function IntegridadAuditoria({ hotelId, version }: { hotelId: number; version: number }) {
  const r = useDatos(
    () =>
      obtenerTipado('/api/v1/hoteles/{hotel_id}/auditoria/verificar', { path: { hotel_id: hotelId } }),
    [hotelId, version],
  )
  return (
    <div className="integridad" role="status" aria-label="Integridad de la bitácora">
      {r.cargando && <span className="suave">Verificando la cadena…</span>}
      {r.error && <Insignia tono="error">No se pudo verificar</Insignia>}
      {r.datos &&
        (r.datos.integra ? (
          <Insignia tono="ok">Cadena íntegra</Insignia>
        ) : (
          <Insignia tono="error">Cadena alterada</Insignia>
        ))}
      {r.datos && (
        <span className="suave">
          {r.datos.eventos} eventos · último hash <code>{r.datos.ultimo_hash.slice(0, 12)}</code>
          {r.datos.motivo ? ` · evento ${r.datos.primer_alterado_id}: ${r.datos.motivo}` : ''}
        </span>
      )}
      <button type="button" className="boton boton-secundario" onClick={r.recargar}>
        Verificar de nuevo
      </button>
    </div>
  )
}
