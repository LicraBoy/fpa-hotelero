import { useState, type FormEvent } from 'react'
import { ErrorApi, enviarJson, obtenerTipado } from '../../api/cliente'
import type { components } from '../../api/schema'
import { useDatos } from '../../api/useDatos'
import { MensajeError } from '../../componentes/Insignia'
import { aMicros, ESTADOS_CICLO, estadoRelativo, formatoMicros } from './calculo'

type Ciclo = components['schemas']['CicloSalida']

const ETIQUETA: Record<string, string> = {
  borrador: 'Borrador',
  enviado: 'Enviado',
  revision: 'Revisión',
  aprobado: 'Aprobado',
  bloqueado: 'Bloqueado',
}

function fecha(iso: string): string {
  return new Date(iso).toLocaleString('es-MX', { dateStyle: 'medium', timeStyle: 'short' })
}

interface Props {
  hotelId: number
  cicloId: number
  /** Avisa que el ciclo cambió de estado (la captura puede dejar de ser editable). */
  alCambiar: () => void
}

/** Estado del ciclo de presupuesto: insignia, transiciones posibles, cobertura y historial. Se
 * monta arriba de la grilla de Budget (Fase 7 fusionada con la pantalla de Budget). */
export function CicloPresupuesto({ hotelId, cicloId, alCambiar }: Props) {
  const [version, setVersion] = useState(0)
  const ciclo = useDatos(
    () =>
      obtenerTipado('/api/v1/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}', {
        path: { hotel_id: hotelId, ciclo_id: cicloId },
      }),
    [hotelId, cicloId, version],
  )
  const resumen = useDatos(
    () =>
      obtenerTipado('/api/v1/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}/resumen', {
        path: { hotel_id: hotelId, ciclo_id: cicloId },
      }),
    [hotelId, cicloId, version],
  )
  const [paso, setPaso] = useState<{ hacia: string; etiqueta: string; pide_nota: boolean } | null>(null)
  const [nota, setNota] = useState('')
  const [error, setError] = useState<string | null>(null)

  async function confirmar(e: FormEvent) {
    e.preventDefault()
    if (!paso) return
    setError(null)
    try {
      await enviarJson<Ciclo>(
        'POST',
        `/api/v1/hoteles/${hotelId}/presupuesto/ciclos/${cicloId}/transiciones`,
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

  const c = ciclo.datos
  if (ciclo.error) return <MensajeError texto={ciclo.error} />
  if (!c) return null
  const r = resumen.datos

  return (
    <section className="cierre-periodo budget-stepper-seccion" aria-label="Estado del ciclo de presupuesto">
      <ol className="budget-stepper" aria-label={`Ciclo de presupuesto #${c.numero}`}>
        {ESTADOS_CICLO.map((paso, i) => {
          const estado = estadoRelativo(paso, c.estado)
          return (
            <li key={paso} data-estado={estado}>
              <span className="budget-stepper-circulo" aria-hidden="true">
                {i + 1}
              </span>
              <span className="budget-stepper-etiqueta">
                {ETIQUETA[paso] ?? paso}
                {estado === 'actual' && r && (
                  <small>
                    {r.lineas_capturadas} de {r.total_lineas} líneas
                  </small>
                )}
              </span>
            </li>
          )
        })}
      </ol>
      <div className="cierre-estado">
        {c.version_plan_resultante_id !== null && (
          <span className="suave">Budget generado: versión {c.version_plan_resultante_id}</span>
        )}
        {c.transiciones_posibles.map((t) => (
          <button
            key={t.hacia}
            type="button"
            aria-label={`Confirmar transición a ${t.etiqueta}`}
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

      {r && (
        <p className="suave">
          Cobertura: {r.lineas_capturadas} de {r.total_lineas} líneas capturadas ({r.cobertura_pct}
          %). Objetivo: {formatoMicros(aMicros(r.suma_objetivo))} · Propuesta:{' '}
          {formatoMicros(aMicros(r.suma_propuesta))}.
        </p>
      )}

      {c.historial.length > 0 && (
        <details>
          <summary>
            Historial del ciclo · {c.historial.length}{' '}
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
