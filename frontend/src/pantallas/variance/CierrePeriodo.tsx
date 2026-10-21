import { useState, type FormEvent } from 'react'
import { ErrorApi, enviarJson, obtenerTipado } from '../../api/cliente'
import type { components } from '../../api/schema'
import { useDatos } from '../../api/useDatos'
import { Insignia, MensajeError } from '../../componentes/Insignia'

type Cierre = components['schemas']['CierreSalida']

const ETIQUETA: Record<string, string> = {
  borrador: 'Borrador',
  comentado: 'Comentado',
  revisado: 'Revisado',
  aprobado: 'Aprobado',
  bloqueado: 'Bloqueado',
}
const TONO = {
  borrador: 'neutro',
  comentado: 'info',
  revisado: 'info',
  aprobado: 'ok',
  bloqueado: 'ok',
} as const

function fecha(iso: string): string {
  return new Date(iso).toLocaleString('es-MX', { dateStyle: 'medium', timeStyle: 'short' })
}

/** Fecha del último registro del historial (el más reciente, sin asumir su orden). */
function ultimaActualizacion(historial: Cierre['historial']): string | null {
  if (historial.length === 0) return null
  let masReciente = historial[0].creado_en
  for (const h of historial) if (h.creado_en > masReciente) masReciente = h.creado_en
  return fecha(masReciente)
}

interface Props {
  hotelId: number
  periodo: string
  /** Avisa que el estado cambió (el Variance puede pasar a calcularse con otras versiones). */
  alCambiar: () => void
}

/** Barra «Cierre»: estado del periodo, pasos que el rol puede dar, versiones congeladas e historial. */
export function CierrePeriodo({ hotelId, periodo, alCambiar }: Props) {
  const [version, setVersion] = useState(0)
  const cierre = useDatos(
    () =>
      obtenerTipado('/api/v1/hoteles/{hotel_id}/cierres/{periodo}', {
        path: { hotel_id: hotelId, periodo },
      }),
    [hotelId, periodo, version],
  )
  const [paso, setPaso] = useState<{ hacia: string; etiqueta: string; pide_nota: boolean } | null>(null)
  const [nota, setNota] = useState('')
  const [error, setError] = useState<string | null>(null)

  async function confirmar(e: FormEvent) {
    e.preventDefault()
    if (!paso) return
    setError(null)
    try {
      await enviarJson<Cierre>(
        'POST',
        `/api/v1/hoteles/${hotelId}/cierres/${periodo}/transiciones`,
        { hacia: paso.hacia, nota: nota.trim() === '' ? null : nota },
      )
      setPaso(null)
      setNota('')
      setVersion((v) => v + 1)
      alCambiar()
    } catch (err) {
      setError(err instanceof ErrorApi ? err.detalle : 'No se pudo cambiar el estado')
    }
  }

  const c = cierre.datos
  if (cierre.error) return <MensajeError texto={cierre.error} />
  if (!c) return null
  const cerrado = c.estado === 'aprobado' || c.estado === 'bloqueado'
  const actualizado = ultimaActualizacion(c.historial)
  return (
    <section className="cierre-periodo" aria-label="Cierre del periodo">
      <div className="cierre-estado">
        <strong>Cierre</strong>
        <Insignia tono={TONO[c.estado as keyof typeof TONO] ?? 'neutro'}>
          {ETIQUETA[c.estado] ?? c.estado}
        </Insignia>
        <span className="suave">Última actualización: {actualizado ?? '—'}</span>
        {c.comentarios_pendientes > 0 && !cerrado && (
          <span className="suave">{c.comentarios_pendientes} comentarios pendientes</span>
        )}
        {c.transiciones_posibles.map((t) => (
          <button
            key={t.hacia}
            type="button"
            className={t.hacia === 'borrador' ? 'boton boton-secundario' : 'boton'}
            onClick={() => {
              setError(null)
              setNota('')
              setPaso(t)
            }}
          >
            {t.etiqueta}
          </button>
        ))}
      </div>

      {paso && (
        <form className="formulario cierre-nota" onSubmit={(e) => void confirmar(e)}>
          <label>
            {paso.pide_nota ? 'Motivo (obligatorio)' : 'Nota (opcional)'}
            <textarea
              maxLength={1000}
              value={nota}
              onChange={(e) => setNota(e.target.value)}
              required={paso.pide_nota}
            />
          </label>
          <div className="acciones-formulario">
            <button type="submit" className="boton">
              Confirmar: {paso.etiqueta}
            </button>
            <button type="button" className="boton boton-secundario" onClick={() => setPaso(null)}>
              Cancelar
            </button>
          </div>
        </form>
      )}
      {error && <MensajeError texto={error} />}

      {cerrado && (
        <p className="suave">
          Cifras congeladas: mapeo v{c.version_mapeo_id}
          {c.version_plan_id !== null && c.version_plan_id !== undefined
            ? ` · Budget v${c.version_plan_id}`
            : ''}
          {c.huella_cifras ? ` · huella ${c.huella_cifras.slice(0, 12)}` : ''}. No se aceptan recargas
          de sus meses mientras siga {c.estado}.
        </p>
      )}

      {c.historial.length > 0 && (
        <details>
          <summary>
            Historial del cierre · {c.historial.length}{' '}
            {c.historial.length === 1 ? 'registro' : 'registros'} ↗
          </summary>
          <ul className="historial-cierre">
            {c.historial.map((h, i) => (
              <li key={i}>
                {fecha(h.creado_en)} · {ETIQUETA[h.desde] ?? h.desde} → {ETIQUETA[h.hacia] ?? h.hacia} ·{' '}
                {h.usuario}
                {h.nota ? ` — ${h.nota}` : ''}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  )
}
