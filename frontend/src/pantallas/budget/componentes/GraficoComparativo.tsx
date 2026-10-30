import { useEffect, useId, useRef, useState, type KeyboardEvent, type MouseEvent, type ReactNode } from 'react'
import { aMicros, formatoMicros } from '../calculo'
import {
  acumuladoDe,
  barrasVariacion,
  escalaSimetrica,
  etiquetaMes,
  formatoEje,
  formatoPorcentaje,
  marcasEje,
  mesDesdeX,
  type SerieComparativo,
} from '../hojaSeccion'

const MICROS = 1_000_000n
const ALTO_BANDA = 64
const ARR = 12
const ABA = 22
const CAR = 6.6 // ancho aproximado de un carácter a 11-12 px, para dimensionar márgenes y tooltip

type Modo = 'mensual' | 'acumulado'

const dinero = (v: bigint) => `$ ${formatoMicros(v)}`
const conSigno = (v: bigint) => `${v > 0n ? '+' : ''}${formatoMicros(v)}`
const flecha = (v: bigint) => (v > 0n ? '▲' : v < 0n ? '▼' : '■')

interface Props {
  series: SerieComparativo[]
  periodos: string[]
  /** Fila «Variación» (Est-Act − Budget previo) por mes y su porcentaje; `null` si el mes no tiene dato. */
  variacion: (bigint | null)[]
  variacionPct: (string | null)[]
  /** Mes activo (índice) compartido con la tabla. */
  activo: number | null
  alActivar: (indice: number | null) => void
  /** Altura del gráfico principal (más alta al ampliar). */
  alto?: number
  /** Botones extra del encabezado de la tarjeta (p. ej. «Ampliar»). */
  acciones?: ReactNode
}

/**
 * Gráfico principal «Comparativo anual», dibujado a mano en SVG (sin librerías y sin `style=`: solo
 * atributos y clases). Mide su ancho real (ResizeObserver), con leyenda interactiva, vista Mensual /
 * Acumulado, tooltip por ratón y teclado y una banda de variación con el mismo eje X. Solo recibe series
 * con los doce meses (ver `seriesComparativo`): una serie incompleta no se dibuja y nunca se completa con
 * ceros. El dibujo usa `number` solo para coordenadas; las cifras siguen en BigInt.
 */
export function GraficoComparativo({ series, periodos, variacion, variacionPct, activo, alActivar, alto = 208, acciones }: Props) {
  const id = useId()
  const caja = useRef<HTMLDivElement>(null)
  const [ancho, setAncho] = useState(960)
  const [modo, setModo] = useState<Modo>('mensual')
  const [ocultas, setOcultas] = useState<ReadonlySet<string>>(new Set())

  useEffect(() => {
    const el = caja.current
    if (!el) return
    const medir = () => setAncho(Math.max(240, Math.floor(el.getBoundingClientRect().width)))
    medir()
    if (typeof ResizeObserver === 'undefined') return
    const obs = new ResizeObserver(medir)
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  const n = periodos.length
  const visibles = series.filter((s) => !ocultas.has(s.id))
  const valoresDe = (s: SerieComparativo) => (modo === 'acumulado' ? acumuladoDe(s.valores) : s.valores)
  const maximo = visibles.reduce((m, s) => valoresDe(s).reduce((a, v) => (v > a ? v : a), m), 0n)
  const marcas = marcasEje(maximo)
  const tope = Number(marcas[marcas.length - 1] / MICROS) || 1

  // Márgenes justos: etiquetas del eje a la izquierda y etiqueta directa del último valor a la derecha
  const izq = Math.ceil(Math.max(...marcas.map((m) => formatoEje(m).length), 2) * CAR) + 14
  const der =
    visibles.length > 0
      ? Math.ceil(Math.max(...visibles.map((s) => formatoEje(valoresDe(s)[n - 1] ?? 0n).length)) * CAR) + 12
      : 12
  const util = Math.max(1, ancho - izq - der)
  const x = (i: number) => izq + (n > 1 ? (i * util) / (n - 1) : 0)
  const y = (v: bigint) => ARR + (alto - ARR - ABA) * (1 - Number(v / MICROS) / tope)
  const base = alto - ABA
  const paso = n > 1 ? util / (n - 1) : util
  const saltoX = util < 640 ? 2 : 1

  const trazo = (vals: bigint[]) => vals.map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ')

  // Etiquetas directas al final de cada línea, separadas para que no se pisen
  const etiquetas = visibles
    .map((s) => {
      const v = valoresDe(s)[n - 1]
      return { s, v, y: y(v) + 4 }
    })
    .sort((a, b) => a.y - b.y)
  for (let i = 1; i < etiquetas.length; i++) {
    if (etiquetas[i].y - etiquetas[i - 1].y < 13) etiquetas[i].y = etiquetas[i - 1].y + 13
  }

  function alternar(sid: string) {
    setOcultas((o) => {
      const nuevo = new Set(o)
      if (nuevo.has(sid)) nuevo.delete(sid)
      else nuevo.add(sid)
      return nuevo
    })
  }

  function alMover(e: MouseEvent<SVGSVGElement>) {
    const r = e.currentTarget.getBoundingClientRect()
    alActivar(mesDesdeX(e.clientX - r.left, izq, ancho - der, n))
  }

  function alTeclear(e: KeyboardEvent<HTMLDivElement>) {
    const ir = (i: number | null) => {
      e.preventDefault()
      alActivar(i)
    }
    if (e.key === 'ArrowRight') ir(activo === null ? 0 : Math.min(n - 1, activo + 1))
    else if (e.key === 'ArrowLeft') ir(activo === null ? n - 1 : Math.max(0, activo - 1))
    else if (e.key === 'Home') ir(0)
    else if (e.key === 'End') ir(n - 1)
    else if (e.key === 'Escape') ir(null)
  }

  // Contenido del tooltip y del anuncio para lectores de pantalla: solo valores reales
  const mesActivo = activo !== null && activo >= 0 && activo < n ? activo : null
  const lineas: string[] = []
  if (mesActivo !== null) {
    for (const s of visibles) lineas.push(`${s.nombre}: ${dinero(valoresDe(s)[mesActivo])}`)
    const v = variacion[mesActivo]
    if (v !== null && v !== undefined) {
      const pct = variacionPct[mesActivo]
      const p = pct === null || pct === undefined ? null : aMicros(pct)
      lineas.push(`Variación del mes: ${flecha(v)} ${conSigno(v)}${p === null ? '' : ` (${formatoPorcentaje(p)})`}`)
    }
  }
  const anchoTip = Math.ceil(Math.max(...lineas.map((l) => l.length), 8) * CAR) + 20
  const altoTip = (lineas.length + 1) * 16 + 12
  const xTip =
    mesActivo === null ? 0 : x(mesActivo) + 12 + anchoTip > ancho - 4 ? Math.max(4, x(mesActivo) - 12 - anchoTip) : x(mesActivo) + 12

  const barras = barrasVariacion(variacion)
  const magnitud = escalaSimetrica(barras)
  const mitad = 22
  const cero = ALTO_BANDA / 2 + 8
  const altura = (v: bigint) => (magnitud === 0n ? 0 : (Number((v < 0n ? -v : v) / MICROS) / Number(magnitud / MICROS)) * mitad)
  const anchoBarra = Math.max(6, Math.min(28, paso * 0.5))

  return (
    <>
      <div className="graf-cabecera">
        <h3 className="hoja-subtitulo">Comparativo anual</h3>
        <ul className="graf-leyenda" aria-label="Series del gráfico">
          {series.map((s) => (
            <li key={s.id}>
              <button
                type="button"
                className={`graf-leyenda-boton graf-${s.id}`}
                aria-pressed={!ocultas.has(s.id)}
                onClick={() => alternar(s.id)}
              >
                <span className="graf-marca" aria-hidden="true" />
                {s.nombre}
              </button>
            </li>
          ))}
        </ul>
        <div className="graf-segmentado" role="group" aria-label="Vista del gráfico">
          <button type="button" aria-pressed={modo === 'mensual'} onClick={() => setModo('mensual')}>
            Mensual
          </button>
          <button type="button" aria-pressed={modo === 'acumulado'} onClick={() => setModo('acumulado')}>
            Acumulado
          </button>
        </div>
        {acciones}
      </div>

      {series.length === 0 ? (
        <p className="hoja-vacio">Sin datos suficientes para graficar.</p>
      ) : (
        <div
          ref={caja}
          className="graf-caja"
          role="group"
          tabIndex={0}
          aria-label="Gráfico del comparativo anual. Con las flechas izquierda y derecha se recorren los meses."
          onKeyDown={alTeclear}
          onBlur={() => alActivar(null)}
        >
          {visibles.length === 0 ? (
            <p className="hoja-vacio">Todas las series están ocultas: actívalas en la leyenda.</p>
          ) : (
            <svg
              className="grafico-comparativo"
              width={ancho}
              height={alto}
              viewBox={`0 0 ${ancho} ${alto}`}
              role="img"
              aria-labelledby={`${id}-t ${id}-d`}
              onMouseMove={alMover}
              onMouseLeave={() => alActivar(null)}
            >
              <title id={`${id}-t`}>Comparativo anual</title>
              <desc id={`${id}-d`}>
                Gráfico de líneas por mes ({modo === 'acumulado' ? 'acumulado' : 'mensual'}) de{' '}
                {visibles.map((s) => s.nombre).join(', ')}. Los mismos datos están en la tabla Inflación y comparativos.
              </desc>
              {marcas.map((m) => (
                <g key={String(m)}>
                  <line className="graf-rejilla" x1={izq} x2={ancho - der} y1={y(m)} y2={y(m)} stroke="currentColor" strokeWidth="1" />
                  <text className="graf-eje" x={izq - 8} y={y(m) + 4} textAnchor="end">
                    {formatoEje(m)}
                  </text>
                </g>
              ))}
              {periodos.map((per, i) =>
                i % saltoX === 0 ? (
                  <text key={per} className="graf-eje" x={x(i)} y={alto - 6} textAnchor="middle">
                    {etiquetaMes(per)}
                  </text>
                ) : null,
              )}
              {mesActivo !== null && (
                <line className="graf-guia" x1={x(mesActivo)} x2={x(mesActivo)} y1={ARR} y2={base} stroke="currentColor" strokeWidth="1" />
              )}
              {visibles.map((s) => {
                const vals = valoresDe(s)
                return (
                  <g key={s.id} className={`graf-serie graf-${s.id}`}>
                    {s.id === 'budget' && (
                      <path d={`${trazo(vals)} L${x(n - 1).toFixed(1)} ${base} L${x(0).toFixed(1)} ${base} Z`} fill="currentColor" fillOpacity="0.12" stroke="none" />
                    )}
                    <path
                      d={trazo(vals)}
                      fill="none"
                      stroke="currentColor"
                      strokeWidth={s.id === 'budget' ? 2.5 : 2}
                      strokeDasharray={s.id === 'previo' ? '5 4' : undefined}
                      strokeLinejoin="round"
                      strokeLinecap="round"
                    />
                    {mesActivo !== null && <circle cx={x(mesActivo)} cy={y(vals[mesActivo])} r="4" fill="currentColor" />}
                    <circle cx={x(n - 1)} cy={y(vals[n - 1])} r="2.8" fill="currentColor" />
                  </g>
                )
              })}
              {etiquetas.map(({ s, v, y: ey }) => (
                <text key={s.id} className="graf-etiqueta" x={x(n - 1) + 8} y={ey} textAnchor="start">
                  {formatoEje(v)}
                </text>
              ))}
              {mesActivo !== null && lineas.length > 0 && (
                <g className="graf-tooltip" role="presentation">
                  <rect className="graf-tooltip-sombra" x={xTip + 2} y={ARR + 2} width={anchoTip} height={altoTip} rx="8" />
                  <rect className="graf-tooltip-fondo" x={xTip} y={ARR} width={anchoTip} height={altoTip} rx="8" />
                  <text className="graf-tooltip-titulo" x={xTip + 10} y={ARR + 18}>
                    {etiquetaMes(periodos[mesActivo])}
                    {modo === 'acumulado' ? ' · acumulado' : ''}
                  </text>
                  {lineas.map((l, i) => (
                    <text key={l} className="graf-tooltip-linea" x={xTip + 10} y={ARR + 18 + 16 * (i + 1)}>
                      {l}
                    </text>
                  ))}
                </g>
              )}
            </svg>
          )}

          {/* Banda de variación: mismo eje X; sin barra en el mes sin dato */}
          <svg
            className="grafico-banda"
            width={ancho}
            height={ALTO_BANDA}
            viewBox={`0 0 ${ancho} ${ALTO_BANDA}`}
            role="img"
            aria-label="Variación mensual: Est-Act menos Budget del año previo"
            onMouseMove={alMover}
            onMouseLeave={() => alActivar(null)}
          >
            <text className="graf-eje" x={izq} y="10" textAnchor="start">
              Variación mensual (Est-Act − Budget previo)
            </text>
            <line className="graf-cero" x1={izq} x2={ancho - der} y1={cero} y2={cero} stroke="currentColor" strokeWidth="1" />
            {mesActivo !== null && (
              <rect className="graf-banda-activa" x={x(mesActivo) - paso / 2} y="14" width={paso} height={ALTO_BANDA - 16} />
            )}
            {barras.map((b) => {
              const h = altura(b.valor)
              return (
                <rect
                  key={b.indice}
                  className={`var-barra var-${b.signo}`}
                  x={x(b.indice) - anchoBarra / 2}
                  y={b.valor < 0n ? cero : cero - h}
                  width={anchoBarra}
                  height={Math.max(h, b.valor === 0n ? 0 : 1)}
                />
              )
            })}
          </svg>
          <p className="solo-lectores" aria-live="polite">
            {mesActivo === null ? '' : `${etiquetaMes(periodos[mesActivo])}. ${lineas.join('. ')}`}
          </p>
        </div>
      )}
    </>
  )
}
