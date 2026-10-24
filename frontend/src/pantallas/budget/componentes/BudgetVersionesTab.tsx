import { useId, useMemo, useRef, useState } from 'react'
import { obtenerTipado } from '../../../api/cliente'
import type { components } from '../../../api/schema'
import { useDatos } from '../../../api/useDatos'
import { Icono } from '../../../componentes/Iconos'
import { EstadoVacio, Insignia, MensajeError } from '../../../componentes/Insignia'
import { aMicros, formatoMicros, sumarMicros } from '../calculo'
import { BudgetComparacionVersiones } from './BudgetComparacionVersiones'
import { BudgetTablaSkeleton, BudgetTimelineSkeleton } from './BudgetSkeletons'

type VersionBudget = components['schemas']['VersionPlanSalida']

interface Props {
  hotelId: number
  versiones: VersionBudget[]
  descripcionPorLinea: ReadonlyMap<number, string>
  cargando?: boolean
}

type ModalidadVersiones = 'timeline' | 'tabla' | 'comparar'

function formatearFecha(iso: string): string {
  try {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso
    return new Intl.DateTimeFormat('es-MX', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(d)
  } catch {
    return iso
  }
}

/**
 * Pestaña Versiones: Time Machine financiero e historial de solo lectura (spec §7).
 * Presenta el timeline cronológico inmutable de VersionPlan, la vista tabular y
 * el comparador multi-versión. Una versión histórica nunca se edita desde la interfaz.
 */
export function BudgetVersionesTab({ hotelId, versiones, descripcionPorLinea, cargando = false }: Props) {
  const [modalidad, setModalidad] = useState<ModalidadVersiones>('timeline')
  const [versionSeleccionadaId, setVersionSeleccionadaId] = useState<number | null>(null)
  const [compararPreseleccionA, setCompararPreseleccionA] = useState<number | null>(null)
  const [compararPreseleccionB, setCompararPreseleccionB] = useState<number | null>(null)

  const botonUltimoVerRef = useRef<HTMLButtonElement | null>(null)

  const ordenadas = useMemo(() => [...versiones].sort((a, b) => b.numero - a.numero), [versiones])
  const vigente = useMemo(() => ordenadas.find((v) => v.estado === 'vigente') ?? null, [ordenadas])

  if (cargando && versiones.length === 0) {
    return (
      <section className="tarjeta budget-chart-contenedor" aria-label="Cargando historial de versiones">
        <BudgetTimelineSkeleton filas={3} />
      </section>
    )
  }

  if (versiones.length === 0) {
    return (
      <section className="tarjeta budget-chart-contenedor">
        <EstadoVacio>Todavía no hay versiones de Budget registradas en este hotel.</EstadoVacio>
      </section>
    )
  }

  function abrirConsulta(versionId: number, btnElem?: HTMLButtonElement | null) {
    if (btnElem) botonUltimoVerRef.current = btnElem
    setVersionSeleccionadaId(versionId)
  }

  function cerrarConsulta() {
    setVersionSeleccionadaId(null)
    setTimeout(() => {
      botonUltimoVerRef.current?.focus()
    }, 50)
  }

  function irACompararCon(versionId: number) {
    setCompararPreseleccionA(versionId)
    setCompararPreseleccionB(vigente && vigente.id !== versionId ? vigente.id : (ordenadas.find((v) => v.id !== versionId)?.id ?? null))
    setModalidad('comparar')
  }

  return (
    <div className="budget-versiones-espacio" aria-label="Espacio de versiones y auditoría de Budget">
      {/* Selector de vistas */}
      <div className="budget-versiones-toolbar">
        <div className="selector-bloque" role="group" aria-label="Modalidad de visualización de Versiones">
          <button
            type="button"
            className={modalidad === 'timeline' ? 'chip chip-activo' : 'chip'}
            aria-pressed={modalidad === 'timeline'}
            onClick={() => setModalidad('timeline')}
          >
            Línea de tiempo (Timeline)
          </button>
          <button
            type="button"
            className={modalidad === 'tabla' ? 'chip chip-activo' : 'chip'}
            aria-pressed={modalidad === 'tabla'}
            onClick={() => setModalidad('tabla')}
          >
            Historial tabular
          </button>
          <button
            type="button"
            className={modalidad === 'comparar' ? 'chip chip-activo' : 'chip'}
            aria-pressed={modalidad === 'comparar'}
            onClick={() => setModalidad('comparar')}
          >
            Comparar versiones
          </button>
        </div>

        <div className="budget-versiones-resumen-badges">
          <span className="suave budget-versiones-conteo">
            {ordenadas.length} {ordenadas.length === 1 ? 'versión registrada' : 'versiones registradas'}
          </span>
          {vigente && (
            <span className="budget-badge-vigente-top">
              Oficial vigente: <strong>v{vigente.numero}</strong> ({vigente.ano_fiscal})
            </span>
          )}
        </div>
      </div>

      {modalidad === 'comparar' ? (
        <BudgetComparacionVersiones
          hotelId={hotelId}
          versiones={ordenadas}
          descripcionPorLinea={descripcionPorLinea}
          versionInicialA={compararPreseleccionA}
          versionInicialB={compararPreseleccionB}
          onVolverATimeline={() => setModalidad('timeline')}
        />
      ) : (
        <>
          {/* VISTA 1: Timeline cronológico interactivo */}
          {modalidad === 'timeline' && (
            <section
              className="tarjeta budget-chart-contenedor budget-timeline-contenedor"
              aria-label="Línea de tiempo histórica de versiones"
            >
              <div className="budget-chart-cabecera">
                <div>
                  <h3>Línea de tiempo de versiones (Time Machine)</h3>
                  <p className="suave">Historial cronológico inmutable de versiones de plan financiero</p>
                </div>
              </div>

              <div className="budget-timeline-arbol" role="feed" aria-label="Entradas de versiones">
                {ordenadas.map((v, index) => {
                  const esVig = v.estado === 'vigente'
                  const shaCorto = v.sha256 ? `${v.sha256.slice(0, 8)}…` : null
                  const esSeleccionada = versionSeleccionadaId === v.id

                  return (
                    <article
                      key={v.id}
                      className={`budget-timeline-item ${esVig ? 'vigente' : 'historica'} ${
                        esSeleccionada ? 'seleccionada' : ''
                      }`}
                      aria-label={`Versión ${v.numero}, ${esVig ? 'oficial vigente' : 'histórica'}`}
                    >
                      {/* Nodo del timeline */}
                      <div className="budget-timeline-nodo-linea" aria-hidden="true">
                        <span className="budget-timeline-nodo-circulo">
                          {esVig ? '★' : index + 1}
                        </span>
                      </div>

                      {/* Tarjeta de la versión */}
                      <div className="budget-timeline-card">
                        <div className="budget-timeline-card-header">
                          <div className="budget-timeline-card-titulo">
                            <span className="budget-timeline-v-num">v{v.numero}</span>
                            <span className="budget-timeline-ano-tag">{v.ano_fiscal}</span>
                            <Insignia tono={esVig ? 'ok' : 'neutro'}>
                              {esVig ? 'Oficial vigente' : 'Histórica'}
                            </Insignia>
                          </div>
                          <time className="budget-timeline-fecha suave" dateTime={v.creada_en}>
                            {formatearFecha(v.creada_en)}
                          </time>
                        </div>

                        <div className="budget-timeline-card-cuerpo">
                          <div className="budget-timeline-meta-grid">
                            <div className="budget-timeline-meta-col">
                              <span className="budget-meta-label">Archivo origen</span>
                              <strong className="budget-meta-val" title={v.nombre_archivo}>
                                {v.nombre_archivo}
                              </strong>
                            </div>
                            <div className="budget-timeline-meta-col">
                              <span className="budget-meta-label">Periodo corte</span>
                              <span className="budget-meta-val">{v.periodo_corte}</span>
                            </div>
                            <div className="budget-timeline-meta-col">
                              <span className="budget-meta-label">Líneas</span>
                              <span className="budget-meta-val">{v.n_lineas}</span>
                            </div>
                            {shaCorto && (
                              <div className="budget-timeline-meta-col">
                                <span className="budget-meta-label">Integridad (SHA)</span>
                                <code className="budget-meta-sha" title={v.sha256}>
                                  {shaCorto}
                                </code>
                              </div>
                            )}
                          </div>
                        </div>

                        <div className="budget-timeline-card-acciones">
                          <button
                            type="button"
                            className="boton boton-secundario boton-chico"
                            onClick={(e) =>
                              esSeleccionada ? cerrarConsulta() : abrirConsulta(v.id, e.currentTarget)
                            }
                            aria-expanded={esSeleccionada}
                            aria-controls="panel-detalle-version-consultada"
                          >
                            {esSeleccionada ? 'Ocultar consulta' : 'Consultar contenido'}
                          </button>
                          <button
                            type="button"
                            className="boton boton-secundario boton-chico"
                            onClick={() => irACompararCon(v.id)}
                            title={`Comparar versión v${v.numero} con otra versión`}
                          >
                            Comparar versión →
                          </button>
                        </div>
                      </div>
                    </article>
                  )
                })}
              </div>
            </section>
          )}

          {/* VISTA 2: Historial tabular clásico */}
          {modalidad === 'tabla' && (
            <section
              className="tarjeta budget-chart-contenedor"
              role="region"
              aria-label="Tabla histórica de versiones de Budget"
              tabIndex={0}
            >
              <div className="budget-chart-cabecera">
                <div>
                  <h3>Historial tabular de versiones</h3>
                  <p className="suave">Consulta en lista completa de registros</p>
                </div>
              </div>
              <div className="budget-tabla-scroll">
                <table className="tabla-simple">
                  <caption className="solo-lectores">
                    Historial de versiones de Budget, más reciente primero.
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Versión</th>
                      <th scope="col">Año fiscal</th>
                      <th scope="col">Archivo</th>
                      <th scope="col">Estado</th>
                      <th scope="col">Corte</th>
                      <th scope="col">Líneas</th>
                      <th scope="col">Fecha creación</th>
                      <th scope="col">
                        <span className="solo-lectores">Acciones</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {ordenadas.map((v) => (
                      <tr key={v.id} className={versionSeleccionadaId === v.id ? 'fila-seleccionada' : ''}>
                        <td>
                          <strong>v{v.numero}</strong>
                        </td>
                        <td>{v.ano_fiscal}</td>
                        <td title={v.nombre_archivo}>{v.nombre_archivo}</td>
                        <td>
                          <Insignia tono={v.estado === 'vigente' ? 'ok' : 'neutro'}>
                            {v.estado === 'vigente' ? 'Vigente' : 'Histórica'}
                          </Insignia>
                        </td>
                        <td>{v.periodo_corte}</td>
                        <td className="num">{v.n_lineas}</td>
                        <td>{formatearFecha(v.creada_en)}</td>
                        <td>
                          <div className="budget-tabla-acciones-celda">
                            <button
                              type="button"
                              className="boton boton-secundario boton-chico"
                              onClick={(e) =>
                                versionSeleccionadaId === v.id
                                  ? cerrarConsulta()
                                  : abrirConsulta(v.id, e.currentTarget)
                              }
                            >
                              {versionSeleccionadaId === v.id ? 'Ocultar' : 'Consultar'}
                            </button>
                            <button
                              type="button"
                              className="boton boton-secundario boton-chico"
                              onClick={() => irACompararCon(v.id)}
                            >
                              Comparar
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {/* Panel de Detalle / Consulta de solo lectura */}
          {versionSeleccionadaId !== null && (
            <DetalleVersionModal
              hotelId={hotelId}
              versionId={versionSeleccionadaId}
              versionMeta={ordenadas.find((v) => v.id === versionSeleccionadaId) ?? null}
              esVigente={vigente?.id === versionSeleccionadaId}
              descripcionPorLinea={descripcionPorLinea}
              onCerrar={cerrarConsulta}
            />
          )}
        </>
      )}
    </div>
  )
}

/**
 * Consulta de solo lectura de una versión inmutable (spec §7).
 * Cero campos editables. Totales de control en pie de tabla y filtro interno.
 */
function DetalleVersionModal({
  hotelId,
  versionId,
  versionMeta,
  esVigente,
  descripcionPorLinea,
  onCerrar,
}: {
  hotelId: number
  versionId: number
  versionMeta: VersionBudget | null
  esVigente: boolean
  descripcionPorLinea: ReadonlyMap<number, string>
  onCerrar: () => void
}) {
  const [filtroTexto, setFiltroTexto] = useState('')
  const busquedaInputId = useId()

  const detalle = useDatos(
    () =>
      obtenerTipado('/api/v1/hoteles/{hotel_id}/budget/versiones/{version_id}', {
        path: { hotel_id: hotelId, version_id: versionId },
      }),
    [hotelId, versionId],
  )

  const datos = detalle.datos

  const lineasProcesadas = useMemo(() => {
    if (!datos?.lineas) return []
    const termino = filtroTexto.trim().toLowerCase()
    return datos.lineas.filter((l) => {
      if (termino === '') return true
      const desc = (descripcionPorLinea.get(l.linea_id) ?? '').toLowerCase()
      return desc.includes(termino) || String(l.linea_id).includes(termino)
    })
  }, [datos, filtroTexto, descripcionPorLinea])

  const totales = useMemo(() => {
    if (!datos?.lineas) return null
    const mesMicros = sumarMicros(datos.lineas.map((l) => (l.mes === null ? null : aMicros(l.mes))))
    const ytdMicros = sumarMicros(datos.lineas.map((l) => (l.ytd === null ? null : aMicros(l.ytd))))
    const anualMicros = sumarMicros(datos.lineas.map((l) => (l.anual === null ? null : aMicros(l.anual))))
    return { mesMicros, ytdMicros, anualMicros }
  }, [datos])

  return (
    <section
      id="panel-detalle-version-consultada"
      className="tarjeta budget-detalle-version-card"
      aria-label={`Detalle de solo lectura de la versión ${versionMeta?.numero ?? versionId}`}
    >
      <div className="budget-detalle-version-cabecera">
        <div className="budget-detalle-titulos">
          <div className="budget-detalle-badges">
            <span className="budget-version-num-pill">
              Versión v{versionMeta?.numero ?? versionId}
            </span>
            <Insignia tono={esVigente ? 'ok' : 'aviso'}>
              {esVigente ? 'Versión oficial vigente' : 'MODO HISTÓRICO · SOLO LECTURA'}
            </Insignia>
          </div>
          <p className="suave budget-detalle-sub">
            {versionMeta?.nombre_archivo} · Ejercicio {versionMeta?.ano_fiscal} (Corte {versionMeta?.periodo_corte})
          </p>
        </div>

        <button
          type="button"
          className="boton boton-secundario boton-chico"
          onClick={onCerrar}
          aria-label="Cerrar consulta de versión"
        >
          Cerrar consulta ✕
        </button>
      </div>

      <div className="budget-aviso-solo-lectura" role="note">
        <Icono nombre="info" tamano={16} />
        <span>
          Esta versión es inmutable para preservar la trazabilidad contable. Para usarla como base de un nuevo plan,
          el flujo debe iniciarse mediante Captura.
        </span>
      </div>

      {detalle.cargando && <BudgetTablaSkeleton filas={6} ariaLabel="Cargando partidas de la versión..." />}

      {detalle.error && (
        <div className="budget-error-bloque">
          <MensajeError texto={detalle.error} />
          <button
            type="button"
            className="boton boton-secundario boton-chico"
            onClick={() => detalle.recargar()}
          >
            Reintentar carga
          </button>
        </div>
      )}

      {datos && (
        <>
          <div className="budget-detalle-filtros-fila">
            <div className="budget-detalle-busqueda">
              <label htmlFor={busquedaInputId} className="solo-lectores">
                Buscar línea en esta versión
              </label>
              <span className="campo-busqueda">
                <Icono nombre="buscar" tamano={15} />
                <input
                  id={busquedaInputId}
                  type="search"
                  placeholder="Filtrar líneas de la versión…"
                  value={filtroTexto}
                  onChange={(e) => setFiltroTexto(e.target.value)}
                />
              </span>
            </div>
            <span className="suave budget-detalle-contador">
              Mostrando {lineasProcesadas.length} de {datos.lineas.length} líneas
            </span>
          </div>

          <div
            className="budget-tabla-scroll"
            role="region"
            aria-label={`Líneas de la versión ${versionMeta?.numero ?? versionId}`}
            tabIndex={0}
          >
            <table className="tabla-simple">
              <caption className="solo-lectores">
                Importes de mes, acumulado y anual de cada línea en la versión {versionMeta?.numero}. Solo lectura.
              </caption>
              <thead>
                <tr>
                  <th scope="col" className="budget-col-linea-det">Línea de Presupuesto</th>
                  <th scope="col" className="num budget-col-num-det">Mes</th>
                  <th scope="col" className="num budget-col-num-det">Acumulado (YTD)</th>
                  <th scope="col" className="num budget-col-num-det">Anual</th>
                </tr>
              </thead>
              <tbody>
                {lineasProcesadas.map((l) => (
                  <tr key={l.linea_id}>
                    <td>
                      <div className="budget-linea-celda">
                        <strong className="budget-linea-nombre">
                          {descripcionPorLinea.get(l.linea_id) ?? `Línea #${l.linea_id}`}
                        </strong>
                        <span className="budget-linea-id suave">ID #{l.linea_id}</span>
                      </div>
                    </td>
                    <td className="num">{formatoMicros(l.mes === null ? null : aMicros(l.mes))}</td>
                    <td className="num">{formatoMicros(l.ytd === null ? null : aMicros(l.ytd))}</td>
                    <td className="num">{formatoMicros(l.anual === null ? null : aMicros(l.anual))}</td>
                  </tr>
                ))}
                {lineasProcesadas.length === 0 && (
                  <tr>
                    <td colSpan={4} className="budget-tabla-vacia-td">
                      <p className="suave">No hay líneas que coincidan con la búsqueda.</p>
                    </td>
                  </tr>
                )}
              </tbody>
              {totales && (
                <tfoot>
                  <tr className="budget-tabla-tfoot-total">
                    <th scope="row">Total consolidado</th>
                    <td className="num">
                      <strong>{formatoMicros(totales.mesMicros)}</strong>
                    </td>
                    <td className="num">
                      <strong>{formatoMicros(totales.ytdMicros)}</strong>
                    </td>
                    <td className="num">
                      <strong>{formatoMicros(totales.anualMicros)}</strong>
                    </td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        </>
      )}
    </section>
  )
}
