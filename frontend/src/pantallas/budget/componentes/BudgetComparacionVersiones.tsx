import { useId, useMemo, useState } from 'react'
import { obtenerTipado } from '../../../api/cliente'
import type { components } from '../../../api/schema'
import { useDatos } from '../../../api/useDatos'
import { Icono } from '../../../componentes/Iconos'
import { EstadoVacio, MensajeError } from '../../../componentes/Insignia'
import {
  calcularTotalesComparacion,
  compararVersionesDetallado,
  formatoMicros,
  type DiferenciaVersionDetallada,
  type TipoCambioVersion,
} from '../calculo'
import { BudgetTablaSkeleton } from './BudgetSkeletons'

type VersionBudget = components['schemas']['VersionPlanSalida']

interface Props {
  hotelId: number
  versiones: readonly VersionBudget[]
  descripcionPorLinea: ReadonlyMap<number, string>
  versionInicialA?: number | null
  versionInicialB?: number | null
  onVolverATimeline?: () => void
}

type FiltroCambio = 'todos' | 'diferencias' | 'modificadas' | 'nuevas_eliminadas'

const ETIQUETAS_TIPO: Record<TipoCambioVersion, { etiqueta: string; clase: string; simbolo: string }> = {
  nueva: { etiqueta: 'Nueva', clase: 'budget-pill-nueva', simbolo: '+' },
  eliminada: { etiqueta: 'Eliminada', clase: 'budget-pill-eliminada', simbolo: '−' },
  modificada: { etiqueta: 'Modificada', clase: 'budget-pill-modificada', simbolo: 'Δ' },
  sin_cambio: { etiqueta: 'Sin cambio', clase: 'budget-pill-sincambio', simbolo: '=' },
  incompleta: { etiqueta: 'Sin dato', clase: 'budget-pill-neutro', simbolo: '—' },
}

/**
 * Comparador de Versiones de Budget Studio (spec §3, §7 y WCAG 2.1 AA).
 * Concilia importes anuales entre dos versiones inmutables usando los contratos de API existentes.
 * Proporciona totales de control, desglose por línea, diferencias absolutas y porcentuales.
 */
export function BudgetComparacionVersiones({
  hotelId,
  versiones,
  descripcionPorLinea,
  versionInicialA,
  versionInicialB,
  onVolverATimeline,
}: Props) {
  const ordenadas = useMemo(() => [...versiones].sort((a, b) => b.numero - a.numero), [versiones])

  const [idA, setIdA] = useState<number | null>(() => {
    if (versionInicialA && ordenadas.some((v) => v.id === versionInicialA)) return versionInicialA
    return ordenadas[1]?.id ?? ordenadas[0]?.id ?? null
  })

  const [idB, setIdB] = useState<number | null>(() => {
    if (versionInicialB && ordenadas.some((v) => v.id === versionInicialB)) return versionInicialB
    return ordenadas[0]?.id ?? null
  })

  const [filtroTipo, setFiltroTipo] = useState<FiltroCambio>('diferencias')
  const [busqueda, setBusqueda] = useState('')

  const searchInputId = useId()
  const liveRegionId = useId()

  const detalleA = useDatos(
    () =>
      idA === null
        ? Promise.resolve(null)
        : obtenerTipado('/api/v1/hoteles/{hotel_id}/budget/versiones/{version_id}', {
            path: { hotel_id: hotelId, version_id: idA },
          }),
    [hotelId, idA],
  )

  const detalleB = useDatos(
    () =>
      idB === null
        ? Promise.resolve(null)
        : obtenerTipado('/api/v1/hoteles/{hotel_id}/budget/versiones/{version_id}', {
            path: { hotel_id: hotelId, version_id: idB },
          }),
    [hotelId, idB],
  )

  const versionObjetoA = useMemo(() => ordenadas.find((v) => v.id === idA) ?? null, [ordenadas, idA])
  const versionObjetoB = useMemo(() => ordenadas.find((v) => v.id === idB) ?? null, [ordenadas, idB])

  const todasLasDiferencias = useMemo<DiferenciaVersionDetallada[] | null>(() => {
    if (!detalleA.datos || !detalleB.datos) return null
    return compararVersionesDetallado(detalleA.datos.lineas, detalleB.datos.lineas)
  }, [detalleA.datos, detalleB.datos])

  const totalesControl = useMemo(() => {
    if (!todasLasDiferencias) return null
    return calcularTotalesComparacion(todasLasDiferencias)
  }, [todasLasDiferencias])

  const filasFiltradas = useMemo(() => {
    if (!todasLasDiferencias) return []
    const termino = busqueda.trim().toLowerCase()

    return todasLasDiferencias.filter((fila) => {
      // 1. Filtro por tipo de cambio
      if (filtroTipo === 'diferencias') {
        if (fila.tipo === 'sin_cambio') return false
      } else if (filtroTipo === 'modificadas') {
        if (fila.tipo !== 'modificada') return false
      } else if (filtroTipo === 'nuevas_eliminadas') {
        if (fila.tipo !== 'nueva' && fila.tipo !== 'eliminada') return false
      }

      // 2. Filtro por texto / descripción
      if (termino !== '') {
        const desc = (descripcionPorLinea.get(fila.linea_id) ?? '').toLowerCase()
        const idTexto = String(fila.linea_id)
        if (!desc.includes(termino) && !idTexto.includes(termino)) return false
      }

      return true
    })
  }, [todasLasDiferencias, filtroTipo, busqueda, descripcionPorLinea])

  if (ordenadas.length < 2) {
    return (
      <section className="tarjeta budget-chart-contenedor">
        <EstadoVacio>
          Se requieren al menos dos versiones registradas de Budget para realizar una comparación financiera.
        </EstadoVacio>
      </section>
    )
  }

  const esMismaVersion = idA !== null && idB !== null && idA === idB
  const esEjercicioDistinto =
    !esMismaVersion &&
    versionObjetoA !== null &&
    versionObjetoB !== null &&
    versionObjetoA.ano_fiscal !== versionObjetoB.ano_fiscal
  const cargando = detalleA.cargando || detalleB.cargando
  const errorTexto = detalleA.error ?? detalleB.error ?? null

  return (
    <div className="budget-comparacion-espacio" aria-label="Comparador de versiones de Budget">
      {/* Barra de control y selección de versiones */}
      <section className="tarjeta budget-comparacion-cabecera-card" aria-label="Selección de versiones a comparar">
        <div className="budget-comparacion-controles">
          <div className="budget-comparacion-select-bloque">
            <label htmlFor="selector-version-a" className="budget-comparacion-label">
              <span className="budget-comparacion-badge-tag base">Versión Base (A)</span>
            </label>
            <select
              id="selector-version-a"
              className="budget-comparacion-select"
              value={idA ?? ''}
              onChange={(e) => setIdA(Number(e.target.value))}
              aria-label="Seleccionar versión base A"
            >
              {ordenadas.map((v) => (
                <option key={v.id} value={v.id}>
                  v{v.numero} · {v.ano_fiscal} · {v.nombre_archivo} {v.estado === 'vigente' ? '(Vigente)' : ''}
                </option>
              ))}
            </select>
          </div>

          <div className="budget-comparacion-conector" aria-hidden="true">
            <span className="budget-comparacion-vs">vs</span>
          </div>

          <div className="budget-comparacion-select-bloque">
            <label htmlFor="selector-version-b" className="budget-comparacion-label">
              <span className="budget-comparacion-badge-tag comparar">Versión a Comparar (B)</span>
            </label>
            <select
              id="selector-version-b"
              className="budget-comparacion-select"
              value={idB ?? ''}
              onChange={(e) => setIdB(Number(e.target.value))}
              aria-label="Seleccionar versión de contraste B"
            >
              {ordenadas.map((v) => (
                <option key={v.id} value={v.id}>
                  v{v.numero} · {v.ano_fiscal} · {v.nombre_archivo} {v.estado === 'vigente' ? '(Vigente)' : ''}
                </option>
              ))}
            </select>
          </div>

          {onVolverATimeline && (
            <button
              type="button"
              className="boton boton-secundario boton-chico budget-comparacion-volver-btn"
              onClick={onVolverATimeline}
            >
              Volver al historial
            </button>
          )}
        </div>

        {esMismaVersion && (
          <p className="mensaje mensaje-aviso budget-aviso-misma-version" role="status">
            Has seleccionado la misma versión en ambos extremos. Elige versiones distintas para evaluar las variaciones.
          </p>
        )}
        {esEjercicioDistinto && (
          <p className="mensaje mensaje-aviso budget-aviso-misma-version" role="status">
            v{versionObjetoA?.numero} es del ejercicio {versionObjetoA?.ano_fiscal} y v{versionObjetoB?.numero} del
            ejercicio {versionObjetoB?.ano_fiscal}: son presupuestos de periodos distintos. La comparación línea por
            línea sigue siendo matemáticamente exacta, pero una diferencia aquí no representa una revisión del mismo
            plan, sino dos ejercicios distintos.
          </p>
        )}
      </section>

      {/* Estados de Carga y Error */}
      {cargando && <BudgetTablaSkeleton filas={7} ariaLabel="Calculando comparación de versiones..." />}

      {errorTexto && (
        <div className="tarjeta budget-error-card">
          <MensajeError texto={errorTexto} />
          <button
            type="button"
            className="boton boton-secundario boton-chico"
            onClick={() => {
              detalleA.recargar()
              detalleB.recargar()
            }}
          >
            Reintentar carga de versiones
          </button>
        </div>
      )}

      {/* Panel de Totales de Control */}
      {!cargando && !errorTexto && totalesControl && (
        <section className="budget-comparacion-totales-strip" aria-label="Totales de control y conciliación">
          <div className="budget-total-card">
            <span className="budget-total-label">Total v{versionObjetoA?.numero ?? 'A'} (Base)</span>
            <strong className="budget-total-valor">{formatoMicros(totalesControl.totalA)}</strong>
            <span className="budget-total-sub">{versionObjetoA?.nombre_archivo ?? '—'}</span>
          </div>

          <div className="budget-total-card">
            <span className="budget-total-label">Total v{versionObjetoB?.numero ?? 'B'} (Comparada)</span>
            <strong className="budget-total-valor">{formatoMicros(totalesControl.totalB)}</strong>
            <span className="budget-total-sub">{versionObjetoB?.nombre_archivo ?? '—'}</span>
          </div>

          <div className="budget-total-card destacado">
            <span className="budget-total-label">Variación Neta</span>
            <strong
              className={`budget-total-valor ${
                totalesControl.diferenciaNeta !== null && totalesControl.diferenciaNeta > 0n
                  ? 'positivo'
                  : totalesControl.diferenciaNeta !== null && totalesControl.diferenciaNeta < 0n
                    ? 'negativo'
                    : ''
              }`}
            >
              {totalesControl.diferenciaNeta !== null && totalesControl.diferenciaNeta > 0n ? '+' : ''}
              {formatoMicros(totalesControl.diferenciaNeta)}
            </strong>
            <span className="budget-total-sub">
              {totalesControl.diferenciaPct !== null
                ? `${totalesControl.diferenciaPct >= 0 ? '+' : ''}${totalesControl.diferenciaPct.toFixed(2)}%`
                : 'Sin base'}
            </span>
          </div>

          <div className="budget-total-card balance-conteos">
            <span className="budget-total-label">Balance de Líneas</span>
            <div className="budget-conteos-grid">
              <span className="budget-conteo-tag mod">
                <strong>{totalesControl.conteoModificadas}</strong> modificadas
              </span>
              <span className="budget-conteo-tag nueva">
                <strong>{totalesControl.conteoNuevas}</strong> nuevas
              </span>
              <span className="budget-conteo-tag elim">
                <strong>{totalesControl.conteoEliminadas}</strong> eliminadas
              </span>
              <span className="budget-conteo-tag s-c">
                <strong>{totalesControl.conteoSinCambio}</strong> sin cambio
              </span>
            </div>
          </div>
        </section>
      )}

      {/* Barra de Filtros y Búsqueda */}
      {!cargando && !errorTexto && todasLasDiferencias && (
        <section className="tarjeta budget-comparacion-filtros-card" aria-label="Filtros de comparación">
          <div className="budget-filtros-comparador-wrap">
            <div className="budget-filtro-chips" role="radiogroup" aria-label="Filtrar por tipo de cambio">
              <button
                type="button"
                className={`chip ${filtroTipo === 'diferencias' ? 'chip-activo' : ''}`}
                role="radio"
                aria-checked={filtroTipo === 'diferencias'}
                onClick={() => setFiltroTipo('diferencias')}
              >
                Solo con diferencias ({totalesControl ? totalesControl.conteoTotal - totalesControl.conteoSinCambio : 0})
              </button>
              <button
                type="button"
                className={`chip ${filtroTipo === 'todos' ? 'chip-activo' : ''}`}
                role="radio"
                aria-checked={filtroTipo === 'todos'}
                onClick={() => setFiltroTipo('todos')}
              >
                Todas las líneas ({totalesControl?.conteoTotal ?? 0})
              </button>
              <button
                type="button"
                className={`chip ${filtroTipo === 'modificadas' ? 'chip-activo' : ''}`}
                role="radio"
                aria-checked={filtroTipo === 'modificadas'}
                onClick={() => setFiltroTipo('modificadas')}
              >
                Solo modificadas ({totalesControl?.conteoModificadas ?? 0})
              </button>
              <button
                type="button"
                className={`chip ${filtroTipo === 'nuevas_eliminadas' ? 'chip-activo' : ''}`}
                role="radio"
                aria-checked={filtroTipo === 'nuevas_eliminadas'}
                onClick={() => setFiltroTipo('nuevas_eliminadas')}
              >
                Nuevas o Eliminadas ({(totalesControl?.conteoNuevas ?? 0) + (totalesControl?.conteoEliminadas ?? 0)})
              </button>
            </div>

            <div className="budget-comparacion-busqueda">
              <label htmlFor={searchInputId} className="solo-lectores">
                Buscar línea en la comparación
              </label>
              <span className="campo-busqueda">
                <Icono nombre="buscar" tamano={15} />
                <input
                  id={searchInputId}
                  type="search"
                  placeholder="Buscar por nombre o número de línea…"
                  value={busqueda}
                  onChange={(e) => setBusqueda(e.target.value)}
                />
              </span>
            </div>
          </div>

          <div id={liveRegionId} className="solo-lectores" aria-live="polite">
            Mostrando {filasFiltradas.length} líneas comparadas.
          </div>
        </section>
      )}

      {/* Tabla Comparativa de Líneas */}
      {!cargando && !errorTexto && todasLasDiferencias && (
        <section
          className="tarjeta budget-chart-contenedor budget-tabla-comparativa-wrap"
          role="region"
          aria-label="Tabla de comparación de líneas entre versiones"
          tabIndex={0}
        >
          <div className="budget-tabla-scroll">
            <table className="tabla-simple budget-tabla-comparativa">
              <caption className="solo-lectores">
                Comparativa de importes anuales entre la versión {versionObjetoA?.numero} y la versión{' '}
                {versionObjetoB?.numero}, con diferencias monetarias y porcentuales.
              </caption>
              <thead>
                <tr>
                  <th scope="col" className="budget-col-linea">Línea de Presupuesto</th>
                  <th scope="col" className="budget-col-tipo budget-celda-centro">Tipo</th>
                  <th scope="col" className="num budget-col-base">
                    v{versionObjetoA?.numero ?? 'A'} (Base)
                  </th>
                  <th scope="col" className="num budget-col-comp">
                    v{versionObjetoB?.numero ?? 'B'} (Comparada)
                  </th>
                  <th scope="col" className="num budget-col-diff">
                    Diferencia
                  </th>
                </tr>
              </thead>
              <tbody>
                {filasFiltradas.map((fila) => {
                  const metaTipo = ETIQUETAS_TIPO[fila.tipo]
                  const descripcion = descripcionPorLinea.get(fila.linea_id) ?? `Línea #${fila.linea_id}`
                  const tieneDiferencia = fila.diferenciaMicros !== null && fila.diferenciaMicros !== 0n
                  const esPositiva = fila.diferenciaMicros !== null && fila.diferenciaMicros > 0n
                  const esNegativa = fila.diferenciaMicros !== null && fila.diferenciaMicros < 0n

                  return (
                    <tr key={fila.linea_id} className={tieneDiferencia ? 'budget-fila-con-cambio' : ''}>
                      <td>
                        <div className="budget-linea-celda">
                          <strong className="budget-linea-nombre">{descripcion}</strong>
                          <span className="budget-linea-id suave">ID #{fila.linea_id}</span>
                        </div>
                      </td>
                      <td className="budget-celda-centro">
                        <span className={`budget-tipo-pill ${metaTipo.clase}`} title={metaTipo.etiqueta}>
                          <span className="budget-tipo-simbolo" aria-hidden="true">{metaTipo.simbolo}</span>
                          {metaTipo.etiqueta}
                        </span>
                      </td>
                      <td className="num">
                        {fila.anualA !== null ? (
                          formatoMicros(fila.anualA)
                        ) : (
                          <span className="suave" title="No existía en la versión base">—</span>
                        )}
                      </td>
                      <td className="num">
                        {fila.anualB !== null ? (
                          formatoMicros(fila.anualB)
                        ) : (
                          <span className="suave" title="No existe en la versión comparada">—</span>
                        )}
                      </td>
                      <td className="num">
                        {fila.diferenciaMicros !== null ? (
                          <div className="budget-diff-monto-wrap">
                            <span
                              className={`budget-diff-monto ${
                                esPositiva ? 'positivo' : esNegativa ? 'negativo' : 'neutro'
                              }`}
                            >
                              {esPositiva ? '+' : ''}
                              {formatoMicros(fila.diferenciaMicros)}
                            </span>
                            {fila.diferenciaPct !== null && (
                              <span
                                className={`budget-diff-pct suave ${
                                  esPositiva ? 'pct-positivo' : esNegativa ? 'pct-negativo' : ''
                                }`}
                              >
                                {fila.diferenciaPct >= 0 ? '+' : ''}
                                {fila.diferenciaPct.toFixed(1)}%
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="suave">—</span>
                        )}
                      </td>
                    </tr>
                  )
                })}

                {filasFiltradas.length === 0 && (
                  <tr>
                    <td colSpan={5} className="budget-tabla-vacia-td">
                      <p className="suave">No se encontraron líneas que coincidan con el filtro aplicado.</p>
                    </td>
                  </tr>
                )}
              </tbody>
              {totalesControl && (
                <tfoot>
                  <tr className="budget-tabla-tfoot-total">
                    <th scope="row">Totales de control conciliados</th>
                    <td className="budget-celda-centro">
                      <span className="budget-tipo-pill budget-pill-neutro">Conciliación</span>
                    </td>
                    <td className="num">
                      <strong>{formatoMicros(totalesControl.totalA)}</strong>
                    </td>
                    <td className="num">
                      <strong>{formatoMicros(totalesControl.totalB)}</strong>
                    </td>
                    <td className="num">
                      <div className="budget-diff-monto-wrap">
                        <strong
                          className={`budget-diff-monto ${
                            totalesControl.diferenciaNeta !== null && totalesControl.diferenciaNeta > 0n
                              ? 'positivo'
                              : totalesControl.diferenciaNeta !== null && totalesControl.diferenciaNeta < 0n
                                ? 'negativo'
                                : 'neutro'
                          }`}
                        >
                          {totalesControl.diferenciaNeta !== null && totalesControl.diferenciaNeta > 0n ? '+' : ''}
                          {formatoMicros(totalesControl.diferenciaNeta)}
                        </strong>
                        {totalesControl.diferenciaPct !== null && (
                          <span className="budget-diff-pct suave">
                            {totalesControl.diferenciaPct >= 0 ? '+' : ''}
                            {totalesControl.diferenciaPct.toFixed(1)}%
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        </section>
      )}
    </div>
  )
}
