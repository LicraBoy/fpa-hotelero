import { useEffect, useMemo, useRef, useState } from 'react'
import { flushSync } from 'react-dom'
import { ErrorApi, enviarJson, obtenerTipado } from '../../../api/cliente'
import type { components } from '../../../api/schema'
import type { LineaEdicionBudget } from '../../../api/tipos'
import { useDatos } from '../../../api/useDatos'
import { Icono } from '../../../componentes/Iconos'
import { TarjetaIndicador } from './HojaUi'
import { Cargando, MensajeError } from '../../../componentes/Insignia'
import { aMicros, formatoMicros, textoDeMicros } from '../calculo'
import {
  aCuerpoApi,
  aplicarFactorATodos,
  celdasDesdeApi,
  hayCambios,
  importeDeCelda,
  type CeldaEditable,
  type VariacionMes,
} from '../detalleCuenta'
import {
  cambiosPorMes,
  claseSigno,
  erroresDeCeldas,
  formatoCampo,
  indicadoresDe,
  mesesModificados,
  rangoDePeriodos,
  variacionDelMes,
} from '../editorCuenta'

type LineaMensual = components['schemas']['LineaMensualSalida']

const MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
const etiquetaMes = (periodo: string) => `${MESES[Number(periodo.slice(5, 7)) - 1]} ${periodo.slice(2, 4)}`
const dinero = (micros: bigint | null) => (micros === null ? '—' : `$ ${formatoMicros(micros)}`)
const conSigno = (m: bigint) => `${m > 0n ? '+' : ''}${formatoMicros(m)}`
const porcentaje = (p: number | null) => (p === null ? '—' : `${p > 0 ? '+' : ''}${p.toFixed(2)}%`)
// Inflación del año fiscal (hoja `Dates` del Excel de Contraloría). `[POR VALIDAR]`
const FACTOR_POR_OMISION = '1.05'
const plural = (n: number, uno: string, varios: string) => `${n} ${n === 1 ? uno : varios}`

interface Props {
  hotelId: number
  cicloId: number
  linea: LineaEdicionBudget
  seccion: string
  /** Ejercicio fiscal real («2026/27») y sus doce periodos. */
  anoFiscal: string
  periodos: string[]
  /** Las cuentas de la misma sección, en orden, para ir a la anterior y a la siguiente. */
  hermanas: LineaEdicionBudget[]
  puedeEditar: boolean
  alElegirLinea: (lineaId: number) => void
  /** Vuelve a la hoja de la sección. */
  alVolver: () => void
  /** Se guardó el detalle: los meses ya quedaron mensualizados en el ciclo. */
  alGuardar: (lineaId: number, valores: LineaMensual[]) => void
  /** Pasa la cuenta a partidas (solo en las secciones que lo admiten). */
  alDetallar?: (lineaId: number) => Promise<void>
}

/**
 * Editor mensual de una cuenta: es una vista propia a todo el ancho, no un bloque debajo
 * de la hoja. Encabezado compacto, indicadores (solo con datos válidos), herramientas, la tabla de
 * doce meses —el elemento principal— con su total y una barra de estado con los cambios, los errores
 * y el guardado. Guardar manda siempre los doce meses (no es parcial). Cálculo en `detalleCuenta.ts`
 * y presentación en `editorCuenta.ts`, sin tocar `calculo.ts`.
 */
export function TablaInternaLinea(p: Props) {
  // El mensaje y los cambios pendientes viven aquí: guardar recarga la tabla (y la remonta).
  const [mensaje, setMensaje] = useState<string | null>(null)
  const [pendiente, setPendiente] = useState(false)
  const detalle = useDatos(
    () =>
      obtenerTipado('/api/v1/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}/lineas/{linea_id}/detalle', {
        path: { hotel_id: p.hotelId, ciclo_id: p.cicloId, linea_id: p.linea.linea_id },
      }),
    [p.hotelId, p.cicloId, p.linea.linea_id],
  )

  // Salir de la cuenta (otra cuenta o volver a la hoja) con cambios sin guardar pide confirmación
  function intentar(accion: () => void) {
    if (pendiente && !window.confirm('Tienes cambios sin guardar en esta cuenta. ¿Descartarlos?')) return
    accion()
  }

  return (
    <section className="editor-cuenta" aria-label={`Editor mensual de ${p.linea.descripcion}`}>
      <Encabezado {...p} intentar={intentar} />
      {detalle.cargando && !detalle.datos && <Cargando texto="Cargando la cuenta…" />}
      {detalle.error && <MensajeError texto={detalle.error} />}
      {detalle.datos && (
        <EditorTabla
          key={`${p.linea.linea_id}-${detalle.datos.map((d) => d.importe).join('|')}`}
          {...p}
          guardadas={detalle.datos}
          recargar={detalle.recargar}
          mensaje={mensaje}
          setMensaje={setMensaje}
          alCambiarPendiente={setPendiente}
        />
      )}
    </section>
  )
}

function Encabezado(p: Props & { intentar: (accion: () => void) => void }) {
  const i = p.hermanas.findIndex((l) => l.linea_id === p.linea.linea_id)
  const anterior = i > 0 ? p.hermanas[i - 1] : null
  const siguiente = i >= 0 && i < p.hermanas.length - 1 ? p.hermanas[i + 1] : null
  const rango = rangoDePeriodos(p.periodos)
  return (
    <header className="ec-cabecera">
      {/* Un solo botón de regreso: a la Hoja de sección (pide confirmar si hay cambios sin guardar) */}
      <nav aria-label="Ruta de la cuenta" className="ec-migas">
        <button
          type="button"
          className="hoja-volver"
          onClick={() => p.intentar(p.alVolver)}
          aria-label="Volver a la Hoja de sección"
        >
          <Icono nombre="volver" tamano={14} />
          Hoja de sección
        </button>
        <span className="etiqueta-pantalla">Editor mensual</span>
      </nav>

      <div className="ec-titulos">
        <h2 title={p.linea.descripcion}>{p.linea.descripcion}</h2>
        <p className="ec-meta">
          {p.linea.codigo_corporativo && <span>Código: {p.linea.codigo_corporativo}</span>}
          <span title={rango ?? undefined}>Ejercicio fiscal {p.anoFiscal}</span>
        </p>
      </div>

      <div className="ec-navegacion">
        <label className="ec-selector">
          <span className="solo-lectores">Ir a otra cuenta</span>
          <Icono nombre="chevron" tamano={14} />
          <select
            aria-label="Ir a otra cuenta"
            value={p.linea.linea_id}
            onChange={(e) => {
              const id = Number(e.target.value)
              p.intentar(() => p.alElegirLinea(id))
            }}
          >
            {p.hermanas.map((l) => (
              <option key={l.linea_id} value={l.linea_id}>
                {l.descripcion}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="ec-boton-nav"
          disabled={!anterior}
          onClick={() => anterior && p.intentar(() => p.alElegirLinea(anterior.linea_id))}
        >
          ‹ Anterior
        </button>
        <span className="ec-contador">
          {i + 1} de {p.hermanas.length}
        </span>
        <button
          type="button"
          className="ec-boton-nav"
          disabled={!siguiente}
          onClick={() => siguiente && p.intentar(() => p.alElegirLinea(siguiente.linea_id))}
        >
          Siguiente ›
        </button>
      </div>
    </header>
  )
}

function EditorTabla({
  hotelId,
  cicloId,
  linea,
  periodos,
  puedeEditar,
  alGuardar,
  guardadas,
  recargar,
  mensaje,
  setMensaje,
  alCambiarPendiente,
  alDetallar,
}: Props & {
  guardadas: components['schemas']['CeldaDetalleSalida'][]
  recargar: () => void
  mensaje: string | null
  setMensaje: (m: string | null) => void
  alCambiarPendiente: (pendiente: boolean) => void
}) {
  const inicial = useMemo(() => celdasDesdeApi(periodos, guardadas, FACTOR_POR_OMISION), [periodos, guardadas])
  const [celdas, setCeldas] = useState<CeldaEditable[]>(inicial)
  const [factorGlobal, setFactorGlobal] = useState(FACTOR_POR_OMISION)
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Campo con el foco (solo para pintar: sin foco se ve formateado, con foco el valor completo)
  const [enfocado, setEnfocado] = useState<string | null>(null)
  // Al entrar en un campo se ve su valor completo y queda seleccionado (escribir lo reemplaza)
  function alEnfocar(e: React.FocusEvent<HTMLInputElement>, clave: string) {
    const campo = e.currentTarget
    // Se pinta el valor completo ya, antes de seleccionar (si no, el cambio de texto quitaría la selección)
    flushSync(() => setEnfocado(clave))
    campo.select()
  }
  const resumenErrores = useRef<HTMLElement>(null)
  const listaErrores = useRef<HTMLUListElement>(null)

  const importes = celdas.map(importeDeCelda)
  const ind = useMemo(() => indicadoresDe(celdas), [celdas])
  const sucio = hayCambios(celdas, inicial)
  const nCambios = cambiosPorMes(celdas, inicial)
  const modificados = mesesModificados(celdas, inicial)
  // Un dato que falta solo es error cuando ya hay cambios (guardar exige los doce meses completos)
  const errores = useMemo(
    () => erroresDeCeldas(celdas).filter((e) => e.tipo === 'invalido' || sucio),
    [celdas, sucio],
  )
  const puedeGuardar = sucio && !guardando && ind.budgetAnual !== null && errores.length === 0
  const factorGlobalValido = aMicros(factorGlobal) !== null && factorGlobal.trim() !== ''

  // El padre pide confirmación al salir si hay cambios sin guardar
  useEffect(() => {
    alCambiarPendiente(sucio)
    return () => alCambiarPendiente(false)
  }, [sucio, alCambiarPendiente])

  function cambiar(i: number, parche: Partial<CeldaEditable>) {
    setCeldas((actual) => actual.map((c, j) => (j === i ? { ...c, ...parche } : c)))
    setMensaje(null)
  }

  async function guardar() {
    const cuerpo = aCuerpoApi(celdas)
    if ('error' in cuerpo) {
      setError(cuerpo.error)
      return
    }
    setGuardando(true)
    setError(null)
    try {
      await enviarJson(
        'PUT',
        `/api/v1/hoteles/${hotelId}/presupuesto/ciclos/${cicloId}/lineas/${linea.linea_id}/detalle`,
        cuerpo,
      )
      const valores: LineaMensual[] = celdas.map((c) => ({
        periodo: c.periodo,
        importe: textoDeMicros(importeDeCelda(c) ?? 0n),
      }))
      alGuardar(linea.linea_id, valores)
      // Solo después de la respuesta del backend se anuncia el guardado
      setMensaje('Guardado. La línea quedó mensualizada en el ciclo.')
      recargar()
    } catch (e) {
      setError(e instanceof ErrorApi ? e.detalle : 'No se pudo guardar el editor mensual')
    } finally {
      setGuardando(false)
    }
  }

  const descartar = () => {
    setCeldas(inicial)
    setError(null)
  }

  return (
    <>
      {(ind.budgetAnual !== null || ind.baseAnual !== null) && (
        <div className="hoja-indicadores ec-indicadores" role="group" aria-label="Resumen de la cuenta">
          {ind.budgetAnual !== null && (
            <TarjetaIndicador tono="azul" icono="baseDatos" etiqueta="Budget anual">
              {dinero(ind.budgetAnual)}
            </TarjetaIndicador>
          )}
          {ind.baseAnual !== null && (
            <TarjetaIndicador tono="verde" icono="flechaArriba" etiqueta="Base anual (Est-Act previo)">
              {dinero(ind.baseAnual)}
            </TarjetaIndicador>
          )}
          {ind.variacion && (
            <TarjetaIndicador
              tono={ind.variacion.diferencia === 0n ? 'neutro' : ind.variacion.diferencia < 0n ? 'rojo' : 'verde'}
              icono={ind.variacion.diferencia < 0n ? 'tendenciaAbajo' : 'tendenciaArriba'}
              etiqueta="Variación vs base"
            >
              <span className={`ec-signo-${claseSigno(ind.variacion.diferencia)}`}>{conSigno(ind.variacion.diferencia)}</span>
              {ind.variacion.porcentaje !== null && (
                <span className={`ec-chip ec-chip-${claseSigno(ind.variacion.diferencia)}`}>{porcentaje(ind.variacion.porcentaje)}</span>
              )}
            </TarjetaIndicador>
          )}
          {ind.promedioMensual !== null && (
            <TarjetaIndicador tono="morado" icono="calendario" etiqueta="Promedio mensual">
              {dinero(ind.promedioMensual)}
            </TarjetaIndicador>
          )}
        </div>
      )}

      {puedeEditar && (
        <div className="ec-herramientas" role="toolbar" aria-label="Herramientas de la tabla">
          <label className="ec-factor">
            <span>Factor para todos los meses</span>
            <input
              type="text"
              inputMode="decimal"
              aria-label="Factor para todos los meses"
              value={factorGlobal}
              onChange={(e) => setFactorGlobal(e.target.value)}
            />
          </label>
          <button
            type="button"
            className="ec-boton-secundario"
            disabled={!factorGlobalValido}
            onClick={() => setCeldas((c) => aplicarFactorATodos(c, factorGlobal.trim()))}
          >
            Aplicar a los 12 meses
          </button>
          <span className="ec-divisor" aria-hidden="true" />
          <button type="button" className="ec-boton-neutro" disabled={!sucio || guardando} onClick={descartar}>
            Descartar cambios
          </button>
          {alDetallar && (
            <button
              type="button"
              className="ec-boton-secundario"
              disabled={sucio || guardando}
              title="Captura esta cuenta por partidas (cantidad × costo, reparto mensual e inflación) y conserva sus importes actuales en una sola partida «Importe actual». Si la cuenta tiene hoja de detalle en el Excel, ábrela y usa «Importar partidas del Excel» para traer sus partidas."
              onClick={() => void alDetallar(linea.linea_id)}
            >
              Detallar por partidas
            </button>
          )}
          <span className="ec-separador" aria-hidden="true" />
          <button type="button" className="ec-boton-primario" disabled={!puedeGuardar} onClick={() => void guardar()}>
            <Icono nombre="guardar" tamano={15} />
            {guardando ? 'Guardando…' : 'Guardar tabla'}
          </button>
        </div>
      )}

      {error && <MensajeError texto={error} />}
      {mensaje && (
        <p className="mensaje mensaje-ok" role="status">
          {mensaje}
        </p>
      )}

      <div className="ec-tabla-tarjeta" role="region" aria-label="Meses de la cuenta" tabIndex={0}>
        <table className="ec-tabla">
          <caption className="solo-lectores">
            Budget de {linea.descripcion} por mes: la base (Est-Act del año previo) por un factor.
          </caption>
          <thead>
            <tr>
              <th scope="col" className="ec-col-mes">
                Mes
              </th>
              <th scope="col" className="num ec-col-base">
                Base (Est-Act previo)
              </th>
              <th scope="col" className="num ec-col-param">
                Parámetro
              </th>
              <th scope="col" className="num ec-col-cifra">
                Budget calculado
              </th>
              <th scope="col" className="num ec-col-cifra">
                Variación
              </th>
              <th scope="col" className="num ec-col-cifra">
                Variación %
              </th>
            </tr>
          </thead>
          <tbody>
            {celdas.map((c, i) => {
              const importe = importes[i]
              const v: VariacionMes | null = variacionDelMes(c)
              const mes = etiquetaMes(c.periodo)
              const invalida = (t: string) => t.trim() !== '' && aMicros(t) === null
              const esFactor = c.metodo === 'factor'
              const textoParametro = esFactor ? c.factor : c.montoFijo
              const parametroInvalido = invalida(textoParametro)
              const claveBase = `${c.periodo}:base`
              const claveParam = `${c.periodo}:param`
              const signoV = claseSigno(v?.diferencia ?? null)
              return (
                <tr key={c.periodo} className={modificados[i] ? 'ec-fila-modificada' : undefined}>
                  <th scope="row" className="ec-col-mes">
                    {modificados[i] && <span className="ec-punto ec-punto-naranja" aria-hidden="true" />}
                    {mes}
                    {modificados[i] && <span className="solo-lectores"> (modificado)</span>}
                  </th>
                  <td className="num ec-col-base">
                    {!esFactor ? (
                      puedeEditar ? (
                        <button
                          type="button"
                          className="ec-fijo-pasar"
                          title="Este mes viene como monto fijo. Pásalo a Base × factor para capturar su base."
                          onClick={() => cambiar(i, { metodo: 'factor' })}
                        >
                          Pasar a Base × factor
                        </button>
                      ) : (
                        <span>—</span>
                      )
                    ) : puedeEditar ? (
                      <span className="ec-campo">
                        <input
                          type="text"
                          inputMode="decimal"
                          className={invalida(c.base) ? 'ec-entrada ec-invalida' : 'ec-entrada'}
                          aria-label={`Base de ${mes}`}
                          aria-invalid={invalida(c.base) || undefined}
                          aria-describedby={invalida(c.base) ? `err-${claveBase}` : undefined}
                          placeholder="—"
                          value={enfocado === claveBase ? c.base : formatoCampo(c.base, 'importe')}
                          onFocus={(e) => alEnfocar(e, claveBase)}
                          onBlur={() => setEnfocado(null)}
                          onChange={(e) => cambiar(i, { base: e.target.value })}
                        />
                        {invalida(c.base) && (
                          <>
                            <Icono nombre="alerta" tamano={13} />
                            <span id={`err-${claveBase}`} className="solo-lectores">
                              La base no es un importe válido
                            </span>
                          </>
                        )}
                      </span>
                    ) : (
                      <span>{c.base === '' ? '—' : formatoMicros(aMicros(c.base))}</span>
                    )}
                  </td>
                  <td className="num ec-col-param">
                    {!esFactor ? (
                      <span className="ec-fijo" title="Monto fijo importado: no se edita aquí">
                        <span className="ec-fijo-etiqueta">Monto fijo</span>
                        {formatoCampo(textoParametro, 'importe')}
                      </span>
                    ) : puedeEditar ? (
                      <span className="ec-campo">
                        <input
                          type="text"
                          inputMode="decimal"
                          className={parametroInvalido ? 'ec-entrada ec-invalida' : 'ec-entrada'}
                          aria-label={`Factor de ${mes}`}
                          aria-invalid={parametroInvalido || undefined}
                          aria-describedby={parametroInvalido ? `err-${claveParam}` : undefined}
                          placeholder="—"
                          value={enfocado === claveParam ? textoParametro : formatoCampo(textoParametro, 'factor')}
                          onFocus={(e) => alEnfocar(e, claveParam)}
                          onBlur={() => setEnfocado(null)}
                          onChange={(e) => cambiar(i, { factor: e.target.value })}
                        />
                        {parametroInvalido && (
                          <>
                            <Icono nombre="alerta" tamano={13} />
                            <span id={`err-${claveParam}`} className="solo-lectores">
                              El factor no es un número válido
                            </span>
                          </>
                        )}
                      </span>
                    ) : (
                      <span>{textoParametro === '' ? '—' : formatoCampo(textoParametro, 'factor')}</span>
                    )}
                  </td>
                  <td className="num ec-col-cifra ec-budget">{formatoMicros(importe)}</td>
                  <td className={`num ec-col-cifra ec-signo-${signoV}`}>{v ? conSigno(v.diferencia) : '—'}</td>
                  <td className={`num ec-col-cifra ec-signo-${signoV}`}>{v ? porcentaje(v.porcentaje) : '—'}</td>
                </tr>
              )
            })}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row" className="ec-col-mes">
                Total
              </th>
              <td className="num ec-col-base">{ind.baseAnual === null ? '—' : formatoMicros(ind.baseAnual)}</td>
              <td className="ec-col-param" />
              <td className="num ec-col-cifra ec-budget">{formatoMicros(ind.budgetAnual)}</td>
              <td className={`num ec-col-cifra ec-signo-${claseSigno(ind.variacion?.diferencia ?? null)}`}>
                {ind.variacion ? conSigno(ind.variacion.diferencia) : '—'}
              </td>
              <td className={`num ec-col-cifra ec-signo-${claseSigno(ind.variacion?.diferencia ?? null)}`}>
                {ind.variacion ? porcentaje(ind.variacion.porcentaje) : '—'}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      {puedeEditar && (sucio || errores.length > 0) && (
        <div className="ec-barra">
          <span className="ec-barra-estado" aria-live="polite">
            <span className="ec-punto ec-punto-naranja" aria-hidden="true" />
            <span className="ec-barra-texto">
              <strong>{plural(nCambios, 'cambio pendiente', 'cambios pendientes')}</strong> en 1 línea
            </span>
          </span>
          <span className="ec-barra-estado">
            <span className="ec-punto ec-punto-rojo" aria-hidden="true" />
            {errores.length > 0 ? (
              <details
                className="ec-errores"
                onToggle={(e) => {
                  // El foco sigue al usuario: a la lista al abrirla y de vuelta al resumen al cerrarla
                  if (e.currentTarget.open) listaErrores.current?.focus()
                  else resumenErrores.current?.focus()
                }}
              >
                <summary ref={resumenErrores}>{plural(errores.length, 'error de validación', 'errores de validación')}</summary>
                <ul ref={listaErrores} tabIndex={-1}>
                  {errores.map((e) => (
                    <li key={`${e.periodo}-${e.campo}-${e.tipo}`}>
                      {etiquetaMes(e.periodo)}: {e.texto}
                    </li>
                  ))}
                </ul>
              </details>
            ) : (
              <span className="ec-barra-errores">0 errores de validación</span>
            )}
          </span>
          <span className="ec-separador" aria-hidden="true" />
          <button type="button" className="ec-boton-neutro" disabled={!sucio || guardando} onClick={descartar}>
            Descartar cambios
          </button>
          <button type="button" className="ec-boton-primario" disabled={!puedeGuardar} onClick={() => void guardar()}>
            {guardando ? 'Guardando…' : 'Guardar cambios'}
          </button>
        </div>
      )}
    </>
  )
}
