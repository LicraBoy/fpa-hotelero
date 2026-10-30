import { useEffect, useRef, useState, type FocusEvent } from 'react'
import { ErrorApi, enviarJson } from '../../../api/cliente'
import type { components } from '../../../api/schema'
import type { LineaEdicionBudget } from '../../../api/tipos'
import { Icono } from '../../../componentes/Iconos'
import { MensajeError } from '../../../componentes/Insignia'
import {
  aMicros,
  claveActual,
  claveCelda,
  diferenciaVsObjetivo,
  formatoMicros,
  sumarMicros,
  textoDeMicros,
  variacionPorcentual,
} from '../calculo'
import { formatoCuatroDecimales, fraseDiferencia, mesesConDato, promedioMicros } from '../detalleLinea'
import { GraficoPlotly } from './PlotlyLazy'
import { SelectorPerfilDistribucion } from './SelectorPerfilDistribucion'
import { useColoresTema } from './useColoresTema'

type LineaCaptura = components['schemas']['LineaCapturaSalida']
type Perfil = components['schemas']['PerfilSalida']
type LineaMensual = components['schemas']['LineaMensualSalida']

const MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
const etiquetaMes = (periodo: string) => `${MESES[Number(periodo.slice(5, 7)) - 1]} ${periodo.slice(2, 4)}`
const etiquetaMesCorta = (periodo: string) => MESES[Number(periodo.slice(5, 7)) - 1]
const dinero = (micros: bigint | null) => (micros === null ? '—' : `$ ${formatoMicros(micros)}`)
const enUnidades = (micros: bigint | null) => (micros === null ? null : Number(micros) / 1_000_000)

// Historial por línea: el backend solo audita el ciclo completo (ver «Actividad del ciclo»), así
// que no hay pestaña Historial: no se muestran eventos inventados.
type Pestana = 'resumen' | 'perfil' | 'notas'
type Serie = 'ambos' | 'budget' | 'actual'
const SERIES: { id: Serie; etiqueta: string }[] = [
  { id: 'ambos', etiqueta: 'Ambos' },
  { id: 'budget', etiqueta: 'Budget' },
  { id: 'actual', etiqueta: 'Actual' },
]

interface Props {
  linea: LineaEdicionBudget
  periodos: string[]
  ediciones: ReadonlyMap<string, string>
  budget: ReadonlyMap<string, bigint | null>
  alEditarActual: (linea: number, periodo: string, valor: string) => void
  puedeEditarBudget: boolean
  puedeEditarActual: boolean
  captura: LineaCaptura | undefined
  puedeObjetivo: boolean
  hotelId: number
  cicloId: number | null
  perfiles: Perfil[]
  puedeRellenarConPerfil: boolean
  alRellenarMeses: (linea: number, valores: LineaMensual[]) => void
  alCambiarCiclo: () => void
  /** Abre la tabla interna de la cuenta; `null` si esta línea no tiene. */
  alAbrirTabla?: (() => void) | null
  onCerrar?: () => void
}

/** ⓘ con una explicación que aparece al pasar el cursor o al enfocarlo (CSS puro, sin estilos en línea). */
function Ayuda({ texto }: { texto: string }) {
  return (
    <span className="ayuda-i" tabIndex={0} role="img" aria-label={texto} data-ayuda={texto}>
      <Icono nombre="info" tamano={13} />
    </span>
  )
}

/**
 * «Panel de línea»: el resumen de UNA línea para entenderla y justificarla. Una línea de dinero
 * muestra su propuesta, la frase contra el objetivo, la gráfica y el detalle por mes; una línea
 * **informativa** (tipo de cambio) no suma dinero: se promedia, y no tiene objetivo ni perfil.
 */
export function DetalleCapturaLinea({
  linea,
  periodos,
  ediciones,
  budget,
  alEditarActual,
  puedeEditarBudget,
  puedeEditarActual,
  captura,
  puedeObjetivo,
  hotelId,
  cicloId,
  perfiles,
  puedeRellenarConPerfil,
  alRellenarMeses,
  alCambiarCiclo,
  alAbrirTabla = null,
  onCerrar,
}: Props) {
  const informativa = linea.tipo === 'informativa'
  const [pestana, setPestana] = useState<Pestana>('resumen')
  const [serie, setSerie] = useState<Serie>('ambos')
  // El detalle por mes arranca abierto solo si el Actual se captura ahí (p. ej. el tipo de cambio)
  const [mesesAbierto, setMesesAbierto] = useState(puedeEditarActual)
  const calculados = periodos.map((per) => budget.get(claveCelda(linea.linea_id, per)) ?? null)
  // Actual vigente: lo que estás escribiendo manda sobre lo guardado (vacío = sin dato)
  const actuales = linea.meses.map((c) => {
    const editado = ediciones.get(claveActual(linea.linea_id, c.periodo))
    if (editado !== undefined) return editado.trim() === '' ? null : aMicros(editado)
    return c.actual === null ? null : aMicros(c.actual)
  })
  const anual = sumarMicros(calculados)
  const promBudget = promedioMicros(calculados)
  const promActual = promedioMicros(actuales)
  const objetivoMicros = captura?.objetivo != null ? aMicros(captura.objetivo) : null
  const diferencia =
    captura?.objetivo != null && anual !== null
      ? diferenciaVsObjetivo(captura.objetivo, textoDeMicros(anual))
      : null
  const pct = variacionPorcentual(objetivoMicros, anual)
  const frase = fraseDiferencia(captura?.objetivo ?? null, anual)
  const puedeRellenar =
    puedeRellenarConPerfil && linea.tipo === 'detalle' && cicloId !== null && perfiles.length > 0 && anual !== null
  const perfilAplicado = perfiles.find((x) => x.id === captura?.perfil_distribucion_id) ?? null
  const colores = useColoresTema()
  const signo = (m: bigint) => (m > 0n ? '+' : '')

  // Pestañas según el tipo de línea: la informativa no tiene perfil; Notas solo si hay captura
  const pestanas: { id: Pestana; etiqueta: string }[] = [
    { id: 'resumen', etiqueta: 'Resumen' },
    ...(informativa ? [] : [{ id: 'perfil' as const, etiqueta: 'Perfil' }]),
    ...(!informativa || captura ? [{ id: 'notas' as const, etiqueta: 'Notas' }] : []),
  ]

  // Esc cierra el cajón solo si el foco está dentro de él (en una celda de la tabla, Esc es de la celda)
  const cerrarRef = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    cerrarRef.current?.focus()
  }, [])

  const etiquetas = periodos.map(etiquetaMesCorta)
  // Dinero: miles/millones abreviados (60k, 1.2M) solo si hay cifras grandes; con cifras chicas, enteros
  const maximo = Math.max(0, ...calculados.map((v) => enUnidades(v) ?? 0), ...actuales.map((v) => enUnidades(v) ?? 0))
  const formatoEjeDinero = maximo >= 10_000 ? '~s' : ',.0f'
  // Sin ninguna cifra (todo vacío o en cero) una gráfica en blanco confunde: se avisa
  const hayCifras = [...calculados, ...actuales].some((v) => v !== null && v !== 0n)
  const colorBudget = '#1a4fd8'
  const colorActual = '#9db8f5'
  const trazas = informativa
    ? [
        ...(serie !== 'actual'
          ? [
              {
                type: 'scatter' as const,
                mode: 'lines+markers' as const,
                name: 'Budget',
                x: etiquetas,
                y: calculados.map(enUnidades),
                connectgaps: false,
                line: { color: colorBudget, width: 2 },
                marker: { color: colorBudget, size: 7 },
                hovertemplate: '%{x}: %{y:,.4f}<extra>Budget</extra>',
              },
            ]
          : []),
        ...(serie !== 'budget'
          ? [
              {
                type: 'scatter' as const,
                mode: 'lines+markers' as const,
                name: 'Actual',
                x: etiquetas,
                y: actuales.map(enUnidades),
                connectgaps: false,
                line: { color: '#f59e0b', width: 2 },
                marker: { color: '#f59e0b', size: 7 },
                hovertemplate: '%{x}: %{y:,.4f}<extra>Actual</extra>',
              },
            ]
          : []),
      ]
    : [
        ...(serie !== 'actual'
          ? [
              {
                type: 'bar' as const,
                name: 'Budget',
                x: etiquetas,
                y: calculados.map((v) => enUnidades(v) ?? 0),
                marker: { color: colorBudget },
                hovertemplate: '%{x}: %{y:,.2f}<extra>Budget</extra>',
              },
            ]
          : []),
        ...(serie !== 'budget'
          ? [
              {
                type: 'bar' as const,
                name: 'Actual',
                x: etiquetas,
                y: actuales.map((v) => enUnidades(v) ?? 0),
                marker: { color: colorActual },
                hovertemplate: '%{x}: %{y:,.2f}<extra>Actual</extra>',
              },
            ]
          : []),
      ]

  return (
    <aside
      className="cajon-linea"
      aria-label={`Panel de ${linea.descripcion}`}
      onKeyDown={(e) => {
        if (e.key === 'Escape' && onCerrar) {
          e.stopPropagation()
          onCerrar()
        }
      }}
    >
      <header className="cajon-cabecera">
        <span className="cajon-etiqueta">Panel de línea</span>
        {onCerrar && (
          <button
            ref={cerrarRef}
            type="button"
            className="boton-icono"
            onClick={onCerrar}
            aria-label="Ocultar el panel de línea"
            title="Cerrar (Esc)"
          >
            <Icono nombre="cerrar" tamano={18} />
          </button>
        )}
      </header>

      <div className="cajon-identidad">
        <span className="linea-icono linea-icono-grande" aria-hidden="true">
          <Icono nombre="presupuesto" tamano={20} />
        </span>
        <div className="cajon-titulos">
          <h3>{linea.descripcion}</h3>
          {linea.codigo_corporativo && <p className="codigo">{linea.codigo_corporativo}</p>}
        </div>
        <div className="cajon-chips">
          {informativa && (
            <span className="chip-gris">
              Línea informativa <Ayuda texto="No suma dinero: se promedia." />
            </span>
          )}
          <span className={puedeEditarBudget ? 'chip-verde' : 'chip-gris'}>
            {puedeEditarBudget ? 'Editable' : 'Solo lectura'}
          </span>
        </div>
      </div>

      <div className="cajon-tabs" role="tablist" aria-label="Secciones del detalle">
        {pestanas.map((p) => (
          <button
            key={p.id}
            type="button"
            role="tab"
            id={`panel-tab-${p.id}`}
            aria-selected={pestana === p.id}
            aria-controls={`panel-panel-${p.id}`}
            className={pestana === p.id ? 'cajon-tab cajon-tab-activa' : 'cajon-tab'}
            onClick={() => setPestana(p.id)}
          >
            {p.etiqueta}
          </button>
        ))}
      </div>

      {pestana === 'resumen' && (
        <div className="cajon-cuerpo" role="tabpanel" id="panel-panel-resumen" aria-labelledby="panel-tab-resumen">
          {informativa ? (
            <section className="cajon-hero" aria-label="Promedio del año">
              <h4>
                Promedio del año <Ayuda texto="Un tipo de cambio no se suma: se promedia. Solo cuentan los meses con dato." />
              </h4>
              <p className="cajon-cifra">{formatoCuatroDecimales(promBudget)}</p>
              <p className="cajon-subtitulo">
                Budget · Actual {formatoCuatroDecimales(promActual)} · {mesesConDato(actuales)} de {periodos.length} meses con
                dato
              </p>
            </section>
          ) : (
            <section className="cajon-hero" aria-label="Propuesta anual">
              <h4>
                Propuesta anual <Ayuda texto="Suma de los 12 meses de Budget de esta línea, con lo que ya escribiste." />
                {captura && (
                  <span className="chip-estado cajon-estado">
                    <span className={captura.estado === 'capturada' ? 'punto-verde' : 'punto-gris'} aria-hidden="true" />
                    {captura.estado === 'capturada' ? 'Completada' : 'Pendiente'}
                  </span>
                )}
              </h4>
              <p className="cajon-cifra">{dinero(anual)}</p>
              {captura && <p className={`cajon-frase cajon-frase-${frase.estado}`}>{frase.texto}</p>}
            </section>
          )}

          {!informativa && captura && (
            <dl className="cajon-indicadores" aria-label="Objetivo y diferencia">
              <div>
                <dt>
                  Objetivo anual <Ayuda texto="Lo que Dirección espera para esta línea. Haz clic en el valor para cambiarlo." />
                </dt>
                <dd>
                  {cicloId !== null ? (
                    <ObjetivoEditable
                      hotelId={hotelId}
                      cicloId={cicloId}
                      linea={linea.linea_id}
                      descripcion={linea.descripcion}
                      objetivo={captura.objetivo}
                      puedeEditar={puedeObjetivo}
                      alGuardar={alCambiarCiclo}
                    />
                  ) : (
                    dinero(objetivoMicros)
                  )}
                </dd>
              </div>
              <div>
                <dt>
                  Diferencia <Ayuda texto="Propuesta menos objetivo: + si te pasas, − si te quedas corto." />
                </dt>
                <dd className={`cajon-dif cajon-dif-${frase.estado}`}>
                  {diferencia?.diferenciaMicros != null ? (
                    <>
                      {signo(diferencia.diferenciaMicros)}
                      {dinero(diferencia.diferenciaMicros)}
                      {pct !== null && (
                        <span className="chip-gris chip-chico">
                          {pct > 0 ? '+' : ''}
                          {pct.toFixed(2)}%
                        </span>
                      )}
                    </>
                  ) : (
                    '—'
                  )}
                </dd>
              </div>
            </dl>
          )}

          <section className="cajon-grafica" aria-label="Distribución mensual">
            <div className="cajon-grafica-cabecera">
              <h4>Distribución mensual</h4>
              <div className="control-segmentado" role="group" aria-label="Qué mostrar en la gráfica">
                {SERIES.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    className={serie === s.id ? 'activo' : ''}
                    aria-pressed={serie === s.id}
                    onClick={() => setSerie(s.id)}
                  >
                    {s.etiqueta}
                  </button>
                ))}
              </div>
            </div>
            {hayCifras ? (
              <GraficoPlotly
                data={trazas}
                layout={{
                  autosize: true,
                  height: 220,
                  margin: { l: 48, r: 8, t: 8, b: 28 },
                  font: { family: 'inherit', size: 11, color: colores.texto },
                  barmode: 'group',
                  bargap: 0.25,
                  showlegend: false,
                  paper_bgcolor: 'transparent',
                  plot_bgcolor: 'transparent',
                  yaxis: {
                    // Informativa: el valor tal cual y el eje no arranca en 0, para que 17.04 y 18.00 no
                    // parezcan iguales.
                    tickformat: informativa ? ',.2f' : formatoEjeDinero,
                    gridcolor: 'rgba(100, 116, 139, 0.15)',
                    zeroline: false,
                    rangemode: informativa ? 'normal' : 'tozero',
                    tickfont: { size: 10, color: colores.texto },
                  },
                  xaxis: { showgrid: false, tickangle: 0, tickfont: { size: 10, color: colores.texto } },
                }}
                config={{ displayModeBar: false, responsive: true }}
                useResizeHandler
                className="budget-chart-plot"
              />
            ) : (
              <p className="cajon-vacio">Aún no hay cifras para graficar.</p>
            )}
            <p className="cajon-leyenda" aria-hidden="true" hidden={!hayCifras}>
              <span className="leyenda-budget">Budget</span>
              <span className={informativa ? 'leyenda-actual-linea' : 'leyenda-actual'}>Actual</span>
            </p>
          </section>

          <details className="cajon-meses" open={mesesAbierto} onToggle={(e) => setMesesAbierto(e.currentTarget.open)}>
            <summary>Ver detalle por mes</summary>
            <table className="cajon-tabla">
              <caption className="solo-lectores">Budget y Actual de {linea.descripcion}, mes por mes.</caption>
              <thead>
                <tr>
                  <th scope="col">Mes</th>
                  <th scope="col" className="num">
                    Budget
                  </th>
                  <th scope="col" className="num">
                    Actual
                  </th>
                  <th scope="col" className="num">
                    Dif.
                  </th>
                </tr>
              </thead>
              <tbody>
                {linea.meses.map((c, i) => {
                  const claveA = claveActual(linea.linea_id, c.periodo)
                  const editadoA = ediciones.get(claveA)
                  const invalidoA = editadoA !== undefined && editadoA.trim() !== '' && aMicros(editadoA) === null
                  const dif = actuales[i] !== null && calculados[i] !== null ? actuales[i] - calculados[i] : null
                  const cifra = informativa ? formatoCuatroDecimales : formatoMicros
                  return (
                    <tr key={c.periodo}>
                      <th scope="row">{etiquetaMes(c.periodo)}</th>
                      <td className="num">{cifra(calculados[i])}</td>
                      <td className="num">
                        {puedeEditarActual ? (
                          <input
                            type="text"
                            inputMode="decimal"
                            aria-label={`Actual de ${linea.descripcion}, ${etiquetaMes(c.periodo)}`}
                            aria-invalid={invalidoA || undefined}
                            className={invalidoA ? 'entrada-budget entrada-invalida' : 'entrada-budget'}
                            placeholder="—"
                            value={editadoA ?? (actuales[i] === null ? '' : textoDeMicros(actuales[i]))}
                            onChange={(e) => alEditarActual(linea.linea_id, c.periodo, e.target.value)}
                          />
                        ) : (
                          cifra(actuales[i])
                        )}
                      </td>
                      <td className="num cajon-dif-celda">{dif === null ? '—' : `${signo(dif)}${cifra(dif)}`}</td>
                    </tr>
                  )
                })}
              </tbody>
              <tfoot>
                {informativa ? (
                  <tr>
                    <th scope="row">Promedio</th>
                    <td className="num">{formatoCuatroDecimales(promBudget)}</td>
                    <td className="num">{formatoCuatroDecimales(promActual)}</td>
                    <td className="num">
                      {promBudget !== null && promActual !== null
                        ? `${signo(promActual - promBudget)}${formatoCuatroDecimales(promActual - promBudget)}`
                        : '—'}
                    </td>
                  </tr>
                ) : (
                  <tr>
                    <th scope="row">Total</th>
                    <td className="num">{formatoMicros(anual)}</td>
                    <td className="num">{formatoMicros(sumarMicros(actuales))}</td>
                    <td className="num" />
                  </tr>
                )}
              </tfoot>
            </table>
            {puedeEditarActual && (
              <p className="cajon-subtitulo">El Actual de esta línea se escribe a mano en la columna Actual.</p>
            )}
            {informativa && (
              <p className="cajon-subtitulo">
                El promedio solo cuenta los meses con dato `[POR VALIDAR]` con Contabilidad (promedio vs. cierre).
              </p>
            )}
          </details>

          <dl className="cajon-filas" aria-label="Perfil y nota">
            <div>
              <dt>
                Perfil de distribución <Ayuda texto="La plantilla con la que se repartió el año entre los meses." />
              </dt>
              <dd>
                {informativa ? (
                  <span className="suave">No aplica: no suma dinero</span>
                ) : perfilAplicado ? (
                  <span className="chip-perfil">{perfilAplicado.nombre}</span>
                ) : captura ? (
                  <span className="suave">Sin perfil: el año se capturó mes a mes</span>
                ) : (
                  <span className="suave">—</span>
                )}
              </dd>
            </div>
            <div>
              <dt>
                Nota <Ayuda texto="La justificación de por qué esta línea tiene este presupuesto." />
              </dt>
              <dd>
                {captura ? (
                  <>
                    <span className={captura.nota ? 'cajon-nota-texto' : 'suave'}>{captura.nota ?? 'Sin nota'}</span>{' '}
                    <button type="button" className="enlace-boton" onClick={() => setPestana('notas')}>
                      {puedeEditarBudget ? 'Editar' : 'Ver'}
                    </button>
                  </>
                ) : (
                  <span className="suave">Esta línea no se captura en el ciclo</span>
                )}
              </dd>
            </div>
          </dl>

          {alAbrirTabla && (
            <button type="button" className="accion-rapida" onClick={alAbrirTabla}>
              <Icono nombre="informe" tamano={18} />
              <span>Abrir las tablas de esta cuenta</span>
              <Icono nombre="chevron" tamano={16} />
            </button>
          )}
        </div>
      )}

      {pestana === 'perfil' && !informativa && (
        <div className="cajon-cuerpo" role="tabpanel" id="panel-panel-perfil" aria-labelledby="panel-tab-perfil">
          <section className="cajon-seccion" aria-label="Perfil de distribución">
            <h4>Perfil de distribución</h4>
            <p className="cajon-subtitulo">
              Reparte el total del año entre los 12 meses con una plantilla de porcentajes (por ejemplo, más peso en
              temporada alta). Elige un perfil, revisa la vista previa y pulsa Aplicar: los 12 meses se llenan solos.
              Si después cambias el total anual, vuelve a aplicarlo.
            </p>
            {puedeRellenar && cicloId !== null && anual !== null ? (
              <SelectorPerfilDistribucion
                hotelId={hotelId}
                cicloId={cicloId}
                linea={linea.linea_id}
                anual={textoDeMicros(anual)}
                perfiles={perfiles}
                periodos={periodos}
                alAplicar={(valores) => alRellenarMeses(linea.linea_id, valores)}
              />
            ) : (
              <p className="suave">
                {linea.tipo !== 'detalle'
                  ? 'Solo las líneas de detalle se reparten con un perfil.'
                  : perfiles.length === 0
                    ? 'No hay perfiles de distribución configurados para este hotel.'
                    : 'Captura primero la propuesta anual de esta línea para poder repartirla con un perfil.'}
              </p>
            )}
          </section>
        </div>
      )}

      {pestana === 'notas' && (
        <div className="cajon-cuerpo" role="tabpanel" id="panel-panel-notas" aria-labelledby="panel-tab-notas">
          <section className="cajon-seccion" aria-label="Nota de la línea">
            <h4>Nota de la línea</h4>
            <p className="cajon-subtitulo">La justificación de por qué esta línea tiene este presupuesto.</p>
            {cicloId !== null && captura ? (
              <NotaCaptura
                hotelId={hotelId}
                cicloId={cicloId}
                linea={linea.linea_id}
                notaInicial={captura.nota}
                anualActual={anual !== null ? textoDeMicros(anual) : (captura.propuesta_anual ?? null)}
                puedeEditar={puedeEditarBudget}
                alGuardar={alCambiarCiclo}
              />
            ) : (
              <p className="suave">
                {cicloId === null
                  ? 'Sin ciclo de presupuesto abierto, esta línea no tiene nota.'
                  : 'Esta línea no se captura en el ciclo, por eso no tiene nota.'}
              </p>
            )}
          </section>
        </div>
      )}
    </aside>
  )
}

/**
 * Objetivo anual con edición en línea: se ve como un valor; al hacer clic aparece el campo. Enter
 * guarda, Esc cancela. Es el mismo `PUT …/objetivo` de antes (solo con permiso de objetivo y con el
 * ciclo en captura; el servidor lo valida).
 */
function ObjetivoEditable({
  hotelId,
  cicloId,
  linea,
  descripcion,
  objetivo,
  puedeEditar,
  alGuardar,
}: {
  hotelId: number
  cicloId: number
  linea: number
  descripcion: string
  objetivo: string | null
  puedeEditar: boolean
  alGuardar: () => void
}) {
  const [editando, setEditando] = useState(false)
  const [valor, setValor] = useState(objetivo ?? '')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const micros = objetivo === null ? null : aMicros(objetivo)

  function cancelar() {
    setEditando(false)
    setValor(objetivo ?? '')
    setError(null)
  }

  async function guardar() {
    if (valor.trim() !== '' && aMicros(valor) === null) {
      setError('Escribe un importe válido')
      return
    }
    setGuardando(true)
    setError(null)
    try {
      await enviarJson(
        'PUT',
        `/api/v1/hoteles/${hotelId}/presupuesto/ciclos/${cicloId}/lineas/${linea}/objetivo`,
        { objetivo: valor.trim() === '' ? null : valor },
      )
      setEditando(false)
      alGuardar()
    } catch (e) {
      setError(e instanceof ErrorApi ? e.detalle : 'No se pudo guardar el objetivo')
    } finally {
      setGuardando(false)
    }
  }

  if (!puedeEditar) return <span>{dinero(micros)}</span>

  if (!editando) {
    return (
      <button
        type="button"
        className="valor-editable"
        aria-label={`Objetivo de ${descripcion}: ${dinero(micros)}. Cambiar`}
        onClick={() => setEditando(true)}
      >
        {micros === null ? 'Definir objetivo' : dinero(micros)}
      </button>
    )
  }

  return (
    <span
      className="campo-en-linea"
      onBlur={(e: FocusEvent<HTMLSpanElement>) => {
        // Se cancela solo si el foco sale del campo (no al pasar al botón Guardar)
        if (!e.currentTarget.contains(e.relatedTarget)) cancelar()
      }}
    >
      <input
        type="text"
        inputMode="decimal"
        aria-label={`Objetivo de ${descripcion}`}
        aria-invalid={error ? true : undefined}
        value={valor}
        disabled={guardando}
        // eslint-disable-next-line jsx-a11y/no-autofocus
        autoFocus
        onChange={(e) => setValor(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault()
            void guardar()
          } else if (e.key === 'Escape') {
            e.preventDefault()
            e.stopPropagation() // Esc cancela la edición, no cierra el cajón
            cancelar()
          }
        }}
      />
      <button type="button" className="boton-icono" aria-label="Guardar objetivo" disabled={guardando} onClick={() => void guardar()}>
        <Icono nombre="check" tamano={16} />
      </button>
      {error && <span className="campo-error">{error}</span>}
    </span>
  )
}

/**
 * Nota de la línea: reusa el mismo `PUT .../lineas/{linea}` que guarda la propuesta anual (acepta
 * `propuesta_anual`+`nota` juntos, sin actualización parcial) — por eso siempre reenvía el anual
 * vigente junto con la nota, para no borrar sin querer una propuesta ya capturada.
 */
function NotaCaptura({
  hotelId,
  cicloId,
  linea,
  notaInicial,
  anualActual,
  puedeEditar,
  alGuardar,
}: {
  hotelId: number
  cicloId: number
  linea: number
  notaInicial: string | null
  anualActual: string | null
  puedeEditar: boolean
  alGuardar: () => void
}) {
  const [valor, setValor] = useState(notaInicial ?? '')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const cambio = valor !== (notaInicial ?? '')

  if (!puedeEditar) return <p className="suave">{notaInicial ?? 'Sin nota.'}</p>

  async function guardar() {
    setGuardando(true)
    setError(null)
    try {
      await enviarJson('PUT', `/api/v1/hoteles/${hotelId}/presupuesto/ciclos/${cicloId}/lineas/${linea}`, {
        propuesta_anual: anualActual,
        nota: valor.trim() === '' ? null : valor,
      })
      alGuardar()
    } catch (e) {
      setError(e instanceof ErrorApi ? e.detalle : 'No se pudo guardar la nota')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="cajon-nota">
      <label>
        <span className="solo-lectores">Nota de la línea</span>
        <textarea
          rows={4}
          maxLength={1000}
          value={valor}
          onChange={(e) => setValor(e.target.value)}
          placeholder="Justificación del presupuesto de esta línea…"
        />
      </label>
      <button type="button" className="boton boton-secundario" disabled={!cambio || guardando} onClick={() => void guardar()}>
        {guardando ? 'Guardando…' : 'Guardar nota'}
      </button>
      {error && <MensajeError texto={error} />}
    </div>
  )
}
