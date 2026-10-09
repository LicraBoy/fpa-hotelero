import { useMemo, useState } from 'react'
import { obtenerTipado } from '../api/cliente'
import type { EventoAuditoria } from '../api/tipos'
import { useDatos } from '../api/useDatos'
import { EncabezadoPagina } from './EncabezadoPagina'
import { Cargando, EstadoVacio, Insignia, MensajeError } from './Insignia'

type Tono = 'ok' | 'aviso' | 'error' | 'info'

const TONO_ACCION: Record<string, Tono> = {
  'carga.creada': 'ok',
  'carga.reemplazada': 'aviso',
  'carga.duplicada': 'info',
  'carga.rechazada': 'error',
  'carga.archivo_rechazado': 'error',
}

// Lectura humana de cada tipo de evento (solo de los que el sistema ya registra)
const ETIQUETA_ACCION: Record<string, string> = {
  'carga.creada': 'Carga creada',
  'carga.reemplazada': 'Carga reemplazada',
  'carga.duplicada': 'Carga duplicada',
  'carga.rechazada': 'Carga rechazada',
  'carga.archivo_rechazado': 'Archivo rechazado',
}

const RESULTADO: Record<Tono, string> = {
  ok: 'Aceptada',
  aviso: 'Reemplazó lo anterior',
  info: 'Sin cambios',
  error: 'Rechazada',
}

function etiquetaAccion(accion: string): string {
  return ETIQUETA_ACCION[accion] ?? accion
}

function registro(detalle: Record<string, unknown> | null): string {
  if (!detalle) return ''
  const partes: string[] = []
  if (typeof detalle.archivo === 'string') partes.push(detalle.archivo)
  if (typeof detalle.periodo === 'string') partes.push(detalle.periodo)
  return partes.join(' · ')
}

function motivo(detalle: Record<string, unknown> | null): string {
  if (!detalle) return ''
  if (typeof detalle.motivo === 'string') return detalle.motivo
  if (Array.isArray(detalle.motivos)) return String(detalle.motivos[0] ?? '')
  return ''
}

/** Valor de un campo del detalle como TEXTO (nunca HTML): lo escribe el sistema, pero viene de archivos. */
function comoTexto(valor: unknown): string {
  if (valor === null || valor === undefined) return '—'
  if (typeof valor === 'string' || typeof valor === 'number' || typeof valor === 'boolean') return String(valor)
  return JSON.stringify(valor)
}

export function PanelAuditoria({ hotelId, version }: { hotelId: number; version: number }) {
  const eventos = useDatos(
    () => obtenerTipado('/api/v1/hoteles/{hotel_id}/auditoria', { path: { hotel_id: hotelId } }),
    [hotelId, version],
  )
  const [accion, setAccion] = useState('')
  const [elegido, setElegido] = useState<number | null>(null)

  const ordenados = useMemo(() => [...(eventos.datos ?? [])].reverse(), [eventos.datos])
  const acciones = useMemo(() => [...new Set(ordenados.map((e) => e.accion))].sort(), [ordenados])
  const visibles = accion === '' ? ordenados : ordenados.filter((e) => e.accion === accion)
  const detalle = visibles.find((e) => e.id === elegido) ?? null

  return (
    <section aria-labelledby="titulo-auditoria">
      <EncabezadoPagina
        id="titulo-auditoria"
        titulo="Bitácora de auditoría"
        subtitulo="Cada carga, reemplazo y rechazo queda registrado. No se puede editar ni borrar."
      />
      {eventos.cargando && <Cargando />}
      {eventos.error && <MensajeError texto={eventos.error} />}
      {eventos.datos && eventos.datos.length === 0 && <EstadoVacio>Sin eventos todavía.</EstadoVacio>}
      {eventos.datos && eventos.datos.length > 0 && (
        <>
          <div className="filtros">
            <label className="chip-filtro">
              Tipo de evento
              <select value={accion} onChange={(e) => setAccion(e.target.value)}>
                <option value="">Todos</option>
                {acciones.map((a) => (
                  <option key={a} value={a}>
                    {etiquetaAccion(a)}
                  </option>
                ))}
              </select>
            </label>
            <p className="suave" role="status">
              {visibles.length} de {ordenados.length} eventos, del más reciente al más antiguo.
            </p>
          </div>
          <div className="auditoria-cuerpo">
            <div className="tabla-contenedor tabla-alta tabla-marco">
              <table className="tabla">
                <thead>
                  <tr>
                    <th>Cuándo</th>
                    <th>Acción</th>
                    <th>Usuario</th>
                    <th>Registro</th>
                    <th>Resultado</th>
                  </tr>
                </thead>
                <tbody>
                  {visibles.map((e) => (
                    <FilaEvento key={e.id} evento={e} elegida={e.id === elegido} alElegir={() => setElegido(e.id)} />
                  ))}
                </tbody>
              </table>
            </div>
            <aside className="detalle-cuenta" aria-label="Detalle del evento">
              <DetalleEvento evento={detalle} />
            </aside>
          </div>
        </>
      )}
    </section>
  )
}

function FilaEvento({
  evento,
  elegida,
  alElegir,
}: {
  evento: EventoAuditoria
  elegida: boolean
  alElegir: () => void
}) {
  const tono = TONO_ACCION[evento.accion]
  return (
    <tr className={elegida ? 'fila-elegida' : undefined}>
      <td>
        <button type="button" className="enlace-fila" aria-pressed={elegida} onClick={alElegir}>
          {new Date(evento.creado_en).toLocaleString('es-MX')}
        </button>
      </td>
      <td>
        <Insignia tono={tono ?? 'neutro'}>{evento.accion}</Insignia>
      </td>
      <td>{evento.usuario_id ?? '—'}</td>
      <td>{registro(evento.detalle) || motivo(evento.detalle) || <span className="suave">—</span>}</td>
      <td>{tono ? RESULTADO[tono] : <span className="suave">—</span>}</td>
    </tr>
  )
}

/** Todo lo que el evento registró, tal cual: campo por campo y como texto. */
function DetalleEvento({ evento }: { evento: EventoAuditoria | null }) {
  if (!evento) return <EstadoVacio>Elige un evento para ver todo lo que registró.</EstadoVacio>
  const tono = TONO_ACCION[evento.accion]
  const campos = Object.entries(evento.detalle ?? {})
  return (
    <>
      <h3>{etiquetaAccion(evento.accion)}</h3>
      <p className="estados-cuenta">
        <Insignia tono={tono ?? 'neutro'}>{evento.accion}</Insignia>
      </p>
      <dl className="datos-cuenta">
        <dt>Cuándo</dt>
        <dd>{new Date(evento.creado_en).toLocaleString('es-MX')}</dd>
        <dt>Usuario</dt>
        <dd>{evento.usuario_id ?? '—'}</dd>
        <dt>Entidad</dt>
        <dd>
          {evento.entidad}
          {evento.entidad_id !== null && ` #${evento.entidad_id}`}
        </dd>
        {campos.map(([clave, valor]) => (
          <DatoEvento key={clave} clave={clave} valor={comoTexto(valor)} />
        ))}
      </dl>
    </>
  )
}

function DatoEvento({ clave, valor }: { clave: string; valor: string }) {
  return (
    <>
      <dt>{clave}</dt>
      <dd>{valor}</dd>
    </>
  )
}
