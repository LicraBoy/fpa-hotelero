import { obtener } from '../api/cliente'
import type { EventoAuditoria } from '../api/tipos'
import { useDatos } from '../api/useDatos'
import { Cargando, Insignia, MensajeError } from './Insignia'

const TONO_ACCION: Record<string, 'ok' | 'aviso' | 'error' | 'info'> = {
  'carga.creada': 'ok',
  'carga.reemplazada': 'aviso',
  'carga.duplicada': 'info',
  'carga.rechazada': 'error',
  'carga.archivo_rechazado': 'error',
}

function resumen(detalle: Record<string, unknown> | null): string {
  if (!detalle) return ''
  const partes: string[] = []
  if (typeof detalle.archivo === 'string') partes.push(detalle.archivo)
  if (typeof detalle.periodo === 'string') partes.push(detalle.periodo)
  if (typeof detalle.motivo === 'string') partes.push(detalle.motivo)
  if (Array.isArray(detalle.motivos)) partes.push(String(detalle.motivos[0] ?? ''))
  return partes.filter(Boolean).join(' · ')
}

export function PanelAuditoria({ hotelId, version }: { hotelId: number; version: number }) {
  const eventos = useDatos(
    () => obtener<EventoAuditoria[]>(`/hoteles/${hotelId}/auditoria`),
    [hotelId, version],
  )
  return (
    <section className="tarjeta" aria-labelledby="titulo-auditoria">
      <h2 id="titulo-auditoria">Bitácora de auditoría</h2>
      <p className="suave">Cada carga, reemplazo y rechazo queda registrado. No se puede editar ni borrar.</p>
      {eventos.cargando && <Cargando />}
      {eventos.error && <MensajeError texto={eventos.error} />}
      {eventos.datos && eventos.datos.length === 0 && <p className="suave">Sin eventos todavía.</p>}
      {eventos.datos && eventos.datos.length > 0 && (
        <div className="tabla-contenedor tabla-alta">
          <table className="tabla">
            <thead>
              <tr>
                <th>Cuándo</th>
                <th>Acción</th>
                <th>Usuario</th>
                <th>Detalle</th>
              </tr>
            </thead>
            <tbody>
              {[...eventos.datos].reverse().map((e) => (
                <tr key={e.id}>
                  <td>{new Date(e.creado_en).toLocaleString('es-MX')}</td>
                  <td>
                    <Insignia tono={TONO_ACCION[e.accion] ?? 'neutro'}>{e.accion}</Insignia>
                  </td>
                  <td>{e.usuario_id ?? '—'}</td>
                  <td>{resumen(e.detalle)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
