import { useState, type FormEvent } from 'react'
import { ErrorApi, enviarJson, obtenerTipado } from '../../api/cliente'
import type { components } from '../../api/schema'
import { useDatos } from '../../api/useDatos'
import { Icono } from '../../componentes/Iconos'
import { MensajeError } from '../../componentes/Insignia'
import { ESTADOS_CICLO, estadoRelativo } from './calculo'

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
  /** Lleva a la pestaña Versiones (chip «Budget vN»). */
  onVerVersiones: () => void
}

/**
 * Panel horizontal compacto del ciclo presupuestario (spec §3.3 y referencia visual):
 * Stepper horizontal numerado de 5 etapas, transiciones autorizadas, anillo circular de cobertura y modales contextuales.
 */
export function CicloPresupuesto({ hotelId, cicloId, alCambiar, onVerVersiones }: Props) {
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
  const [mostrarHistorial, setMostrarHistorial] = useState(false)

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
  const principal = c.transiciones_posibles.find((t) => t.hacia !== 'borrador') ?? c.transiciones_posibles[0] ?? null
  const secundarias = c.transiciones_posibles.filter((t) => t !== principal)
  function abrirPaso(t: { hacia: string; etiqueta: string; pide_nota: boolean }) {
    setError(null)
    setNota('')
    setPaso(t)
  }


  return (
    <>
      <section
        className="budget-ciclo-card budget-ciclo-compacto budget-ciclo-mini"
        aria-label={`Ciclo de presupuesto #${c.numero}: etapa ${ETIQUETA[c.estado] ?? c.estado}`}
      >
        <div className="budget-ciclo-stepper-wrap">
          <ol className="budget-ciclo-stepper" aria-label="Etapas del ciclo de presupuesto">
            {ESTADOS_CICLO.map((pasoItem, i) => {
              const estado = estadoRelativo(pasoItem, c.estado)
              return (
                <li key={pasoItem} className="budget-ciclo-paso" data-estado={estado}>
                  <span className="budget-ciclo-circulo" aria-hidden="true">
                    {estado === 'completado' ? <Icono nombre="check" tamano={14} /> : i + 1}
                  </span>
                  <div className="budget-ciclo-info">
                    <span className="budget-ciclo-etiqueta">{ETIQUETA[pasoItem] ?? pasoItem}</span>
                    {estado === 'actual' && r && (
                      <span className="budget-ciclo-subtexto">
                        {r.lineas_capturadas}/{r.total_lineas} líneas
                      </span>
                    )}
                  </div>
                </li>
              )
            })}
          </ol>
        </div>

        <div className="ciclo-caja-acciones">
          {c.version_plan_resultante_id !== null && (
            <button
              type="button"
              className="ciclo-chip-version"
              onClick={onVerVersiones}
              title="Plan oficial resultante: ver versiones"
            >
              <Icono nombre="presupuesto" tamano={16} />
              <span>Budget v{c.version_plan_resultante_id}</span>
              <Icono nombre="chevron" tamano={13} />
            </button>
          )}

          {principal && (
            <button
              type="button"
              className="boton boton-primario ciclo-boton-primario"
              onClick={() => abrirPaso(principal)}
            >
              <Icono nombre="exportar" tamano={16} />
              {principal.etiqueta}
            </button>
          )}

          {c.historial.length > 0 && (
            <button
              type="button"
              className="boton boton-secundario budget-btn-actividad"
              onClick={() => setMostrarHistorial(true)}
              title="Consultar quién movió el ciclo, cuándo y por qué"
            >
              <Icono nombre="auditoria" tamano={15} />
              <span>Actividad del ciclo</span>
            </button>
          )}

          {secundarias.length > 0 && (
            <details className="menu-flotante ciclo-menu-mas">
              <summary className="boton-icono" aria-label="Más acciones del ciclo" title="Más acciones">
                <span aria-hidden="true">⋮</span>
              </summary>
              <div className="menu-flotante-panel ciclo-menu-panel">
                {secundarias.map((t) => (
                  <button key={t.hacia} type="button" className="boton boton-secundario" onClick={() => abrirPaso(t)}>
                    {t.etiqueta}
                  </button>
                ))}
              </div>
            </details>
          )}
        </div>
      </section>

      {/* Modal accesible para confirmar transición con motivo */}
      {paso && (
        <div className="budget-modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="modal-transicion-titulo">
          <div className="budget-modal">
            <h3 id="modal-transicion-titulo">Confirmar: {paso.etiqueta}</h3>
            <p className="suave">
              {paso.pide_nota
                ? 'Esta acción requiere indicar un motivo para la bitácora de auditoría.'
                : 'Puedes agregar una nota explicativa opcional para este cambio de etapa.'}
            </p>
            <form onSubmit={(e) => void confirmar(e)}>
              <div className="formulario">
                <label>
                  <span>{paso.pide_nota ? 'Motivo (obligatorio)' : 'Nota (opcional)'}</span>
                  <textarea
                    rows={3}
                    maxLength={1000}
                    value={nota}
                    onChange={(e) => setNota(e.target.value)}
                    required={paso.pide_nota}
                    autoFocus
                  />
                </label>
                {error && <MensajeError texto={error} />}
                <div className="acciones-formulario">
                  <button type="submit" className="boton">
                    Confirmar {paso.etiqueta}
                  </button>
                  <button
                    type="button"
                    className="boton boton-secundario"
                    onClick={() => {
                      setPaso(null)
                      setError(null)
                    }}
                  >
                    Cancelar
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal accesible para ver el historial de transiciones */}
      {mostrarHistorial && (
        <div className="budget-modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="modal-historial-titulo">
          <div className="budget-modal budget-modal-ancho">
            <div className="budget-modal-cabecera">
              <h3 id="modal-historial-titulo">Actividad del ciclo #{c.numero}</h3>
              <button
                type="button"
                className="boton-icono"
                onClick={() => setMostrarHistorial(false)}
                aria-label="Cerrar historial"
              >
                <Icono nombre="cerrar" tamano={18} />
              </button>
            </div>
            <ul className="budget-historial-lista">
              {c.historial.map((h, i) => (
                <li key={i} className="budget-historial-item">
                  <div className="budget-historial-estados">
                    {ETIQUETA[h.desde] ?? h.desde} → {ETIQUETA[h.hacia] ?? h.hacia}
                  </div>
                  <div className="budget-historial-meta">
                    {fecha(h.creado_en)} · {h.usuario}
                  </div>
                  {h.nota && <div className="budget-historial-nota">{h.nota}</div>}
                </li>
              ))}
            </ul>
            <div className="budget-modal-pie">
              <button type="button" className="boton boton-secundario" onClick={() => setMostrarHistorial(false)}>
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
