import { obtenerTipado } from '../api/cliente'
import { useDatos } from '../api/useDatos'
import { EncabezadoPagina } from './EncabezadoPagina'
import { Cargando, EstadoVacio, Insignia, MensajeError } from './Insignia'

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
    () => obtenerTipado('/api/v1/hoteles/{hotel_id}/auditoria', { path: { hotel_id: hotelId } }),
    [hotelId, version],
  )
  return (
    <section className="tarjeta" aria-labelledby="titulo-auditoria">
      <EncabezadoPagina
        id="titulo-auditoria"
        titulo="Bitácora de auditoría"
        subtitulo="Cada carga, reemplazo y rechazo queda registrado. No se puede editar ni borrar."
      />
      {eventos.cargando && <Cargando />}
      {eventos.error && <MensajeError texto={eventos.error} />}
      {eventos.datos && eventos.datos.length === 0 && <EstadoVacio>Sin eventos todavía.</EstadoVacio>}
      {eventos.datos && eventos.datos.length > 0 && (
        <div className="tabla-contenedor tabla-alta tabla-marco">
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
