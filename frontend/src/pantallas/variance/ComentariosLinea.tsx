import { useState, type FormEvent } from 'react'
import {
  ErrorApi,
  descargarAdjuntoComentario,
  enviarJson,
  obtenerTipado,
  subirAdjuntoComentario,
} from '../../api/cliente'
import type { components } from '../../api/schema'
import { useDatos } from '../../api/useDatos'
import { Insignia, MensajeError } from '../../componentes/Insignia'
import { etiquetaMesLargo } from '../../util/periodos'

type Comentario = components['schemas']['ComentarioSalida']

interface Props {
  hotelId: number
  periodo: string
  lineaId: number
  /** Puede escribir comentarios (el servidor lo vuelve a comprobar). */
  puedeComentar: boolean
  /** Avisa que hubo un cambio (para refrescar los indicadores de la tabla). */
  alCambiar: () => void
}

const ETIQUETA_ESTATUS: Record<string, string> = {
  pendiente: 'Pendiente',
  explicado: 'Explicado',
  aprobado: 'Aprobado',
}
const TONO_ESTATUS = { pendiente: 'aviso', explicado: 'info', aprobado: 'ok' } as const
const MAX = 2000

function texto(e: unknown): string {
  return e instanceof ErrorApi ? e.detalle : 'No se pudo completar la acción'
}

function fecha(iso: string): string {
  return new Date(iso).toLocaleString('es-MX', { dateStyle: 'medium', timeStyle: 'short' })
}

function Hilo({
  c,
  hotelId,
  yoId,
  asignables,
  puedeResolver,
  puedeComentar,
  alCambiar,
  alError,
}: {
  c: Comentario
  hotelId: number
  yoId: number | undefined
  asignables: Record<string, string>
  puedeResolver: boolean
  puedeComentar: boolean
  alCambiar: () => void
  alError: (mensaje: string | null) => void
}) {
  const base = `/api/v1/hoteles/${hotelId}/comentarios/${c.id}`
  const [respuesta, setRespuesta] = useState('')
  const [editando, setEditando] = useState<{ id: number; texto: string } | null>(null)

  async function llamar(fn: () => Promise<unknown>) {
    alError(null)
    try {
      await fn()
      alCambiar()
    } catch (e) {
      alError(texto(e))
    }
  }

  function responder(e: FormEvent) {
    e.preventDefault()
    void llamar(async () => {
      await enviarJson('POST', `${base}/respuestas`, { texto: respuesta })
      setRespuesta('')
    })
  }

  function guardarEdicion(e: FormEvent) {
    e.preventDefault()
    if (!editando) return
    void llamar(async () => {
      await enviarJson('PATCH', `/api/v1/hoteles/${hotelId}/comentarios/${editando.id}`, {
        texto: editando.texto,
      })
      setEditando(null)
    })
  }

  const propio = (autorId: number) => yoId !== undefined && autorId === yoId

  return (
    <article className="hilo" aria-label={`Comentario de ${c.autor}`}>
      <div className="hilo-meta">
        <strong>{c.autor}</strong>
        <span>{fecha(c.creado_en)}</span>
        <Insignia tono="neutro">{c.bloque === 'mes' ? 'Mes' : 'Acumulado'}</Insignia>
        <Insignia tono={TONO_ESTATUS[c.estatus as keyof typeof TONO_ESTATUS] ?? 'neutro'}>
          {ETIQUETA_ESTATUS[c.estatus] ?? c.estatus}
        </Insignia>
        {c.editado && <span>(editado)</span>}
      </div>

      {editando?.id === c.id ? (
        <form onSubmit={guardarEdicion}>
          <textarea
            aria-label="Editar comentario"
            maxLength={MAX}
            value={editando.texto}
            onChange={(e) => setEditando({ id: c.id, texto: e.target.value })}
            required
          />
          <div className="hilo-acciones">
            <button type="submit" className="boton">
              Guardar
            </button>
            <button type="button" className="boton boton-secundario" onClick={() => setEditando(null)}>
              Cancelar
            </button>
          </div>
        </form>
      ) : (
        // Lo escribe una persona: se muestra como texto, nunca como HTML
        <p className="hilo-texto">{c.texto}</p>
      )}

      <div className="hilo-acciones">
        {propio(c.autor_id) && editando?.id !== c.id && (
          <button
            type="button"
            className="boton boton-secundario"
            onClick={() => setEditando({ id: c.id, texto: c.texto })}
          >
            Editar
          </button>
        )}
        {puedeComentar && (
          <>
            <label className="solo-lectores" htmlFor={`estatus-${c.id}`}>
              Estatus
            </label>
            <select
              id={`estatus-${c.id}`}
              value={c.estatus}
              onChange={(e) =>
                void llamar(() => enviarJson('PUT', `${base}/estatus`, { estatus: e.target.value }))
              }
            >
              <option value="pendiente">Pendiente</option>
              <option value="explicado">Explicado</option>
              <option value="aprobado" disabled={!puedeResolver && c.estatus !== 'aprobado'}>
                Aprobado
              </option>
            </select>
            <label className="solo-lectores" htmlFor={`resp-${c.id}`}>
              Responsable
            </label>
            <select
              id={`resp-${c.id}`}
              value={c.responsable_id ?? ''}
              onChange={(e) =>
                void llamar(() =>
                  enviarJson('PUT', `${base}/responsable`, {
                    responsable_id: e.target.value === '' ? null : Number(e.target.value),
                  }),
                )
              }
            >
              <option value="">Sin responsable</option>
              {Object.entries(asignables).map(([id, nombre]) => (
                <option key={id} value={id}>
                  {nombre}
                </option>
              ))}
            </select>
          </>
        )}
        {!puedeComentar && c.responsable && <span className="suave">Responsable: {c.responsable}</span>}
      </div>

      {c.adjuntos.length > 0 && (
        <ul className="lista-adjuntos">
          {c.adjuntos.map((a) => (
            <li key={a.id}>
              <button
                type="button"
                className="boton boton-secundario"
                onClick={() =>
                  void llamar(() => descargarAdjuntoComentario(hotelId, c.id, a.id, a.nombre))
                }
              >
                {a.nombre}
              </button>
              <span className="suave"> · {Math.max(1, Math.round(a.tamano / 1024))} KB · {a.autor}</span>
            </li>
          ))}
        </ul>
      )}
      {puedeComentar && (
        <label className="boton boton-secundario">
          Adjuntar evidencia
          <input
            type="file"
            className="solo-lectores"
            accept=".pdf,.png,.jpg,.jpeg,.xlsx"
            onChange={(e) => {
              const archivo = e.target.files?.[0]
              e.target.value = ''
              if (archivo) void llamar(() => subirAdjuntoComentario(hotelId, c.id, archivo))
            }}
          />
        </label>
      )}

      {c.respuestas.map((r) => (
        <div key={r.id} className="hilo-respuesta">
          <div className="hilo-meta">
            <strong>{r.autor}</strong>
            <span>{fecha(r.creado_en)}</span>
            {r.editado && <span>(editado)</span>}
          </div>
          {editando?.id === r.id ? (
            <form onSubmit={guardarEdicion}>
              <textarea
                aria-label="Editar respuesta"
                maxLength={MAX}
                value={editando.texto}
                onChange={(e) => setEditando({ id: r.id, texto: e.target.value })}
                required
              />
              <div className="hilo-acciones">
                <button type="submit" className="boton">
                  Guardar
                </button>
                <button type="button" className="boton boton-secundario" onClick={() => setEditando(null)}>
                  Cancelar
                </button>
              </div>
            </form>
          ) : (
            <p className="hilo-texto">{r.texto}</p>
          )}
          {propio(r.autor_id) && editando?.id !== r.id && (
            <button
              type="button"
              className="boton boton-secundario"
              onClick={() => setEditando({ id: r.id, texto: r.texto })}
            >
              Editar respuesta
            </button>
          )}
        </div>
      ))}

      {puedeComentar && (
        <form onSubmit={responder}>
          <textarea
            aria-label="Responder"
            placeholder="Responder…"
            maxLength={MAX}
            value={respuesta}
            onChange={(e) => setRespuesta(e.target.value)}
            required
          />
          <button type="submit" className="boton boton-secundario">
            Responder
          </button>
        </form>
      )}
    </article>
  )
}

/** Hilos de comentarios de una línea en un periodo, con captura de uno nuevo. */
export function ComentariosLinea({ hotelId, periodo, lineaId, puedeComentar, alCambiar }: Props) {
  const [version, setVersion] = useState(0)
  const lista = useDatos(
    () =>
      obtenerTipado('/api/v1/hoteles/{hotel_id}/comentarios', {
        path: { hotel_id: hotelId },
        query: { periodo, linea_id: lineaId },
      }),
    [hotelId, periodo, lineaId, version],
  )
  const yo = useDatos(() => obtenerTipado('/api/v1/yo', {}), [hotelId])
  const [nuevo, setNuevo] = useState('')
  const [bloque, setBloque] = useState<'mes' | 'ytd'>('mes')
  const [responsable, setResponsable] = useState('')
  const [error, setError] = useState<string | null>(null)

  function recargar() {
    setVersion((v) => v + 1)
    alCambiar()
  }

  async function crear(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await enviarJson('POST', `/api/v1/hoteles/${hotelId}/comentarios`, {
        linea_id: lineaId,
        periodo,
        bloque,
        texto: nuevo,
        responsable_id: responsable === '' ? null : Number(responsable),
      })
      setNuevo('')
      recargar()
    } catch (err) {
      setError(texto(err))
    }
  }

  const datos = lista.datos
  return (
    <section className="comentarios-linea" aria-label="Comentarios">
      <h4>
        Comentarios <span className="suave">{etiquetaMesLargo(periodo)}</span>
      </h4>
      {lista.error && <MensajeError texto={lista.error} />}
      {error && <MensajeError texto={error} />}
      {datos && datos.comentarios.length === 0 && (
        <p className="suave">Todavía no hay comentarios para esta línea.</p>
      )}
      {datos?.comentarios.map((c) => (
        <Hilo
          key={c.id}
          c={c}
          hotelId={hotelId}
          yoId={yo.datos?.usuario_id}
          asignables={datos.asignables}
          puedeResolver={datos.puede_resolver}
          puedeComentar={puedeComentar}
          alCambiar={recargar}
          alError={setError}
        />
      ))}
      {puedeComentar && datos && (
        <form className="formulario" onSubmit={(e) => void crear(e)}>
          <label>
            Nuevo comentario
            <textarea
              maxLength={MAX}
              value={nuevo}
              onChange={(e) => setNuevo(e.target.value)}
              required
            />
            <span className="suave">{nuevo.length}/{MAX}</span>
          </label>
          <label>
            Aplica a
            <select
              aria-label="Aplica a"
              value={bloque}
              onChange={(e) => setBloque(e.target.value === 'ytd' ? 'ytd' : 'mes')}
            >
              <option value="mes">Mes</option>
              <option value="ytd">Acumulado</option>
            </select>
          </label>
          <label>
            Responsable de explicarlo
            <select
              aria-label="Responsable de explicarlo"
              value={responsable}
              onChange={(e) => setResponsable(e.target.value)}
            >
              <option value="">Sin asignar</option>
              {Object.entries(datos.asignables).map(([id, nombre]) => (
                <option key={id} value={id}>
                  {nombre}
                </option>
              ))}
            </select>
          </label>
          <button type="submit" className="boton">
            Comentar
          </button>
        </form>
      )}
    </section>
  )
}
