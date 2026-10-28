import { useEffect, useRef } from 'react'
import { aMicros, formatoMicros } from '../calculo'
import {
  etiquetaMes,
  extremosDe,
  formatoPorcentaje,
  fraccionAPorcentaje,
  nivelCalor,
  porcentajeBarra,
  superaUmbral,
} from '../hojaSeccion'
import { AccionesInflacion } from './AccionesInflacion'
import { AyudaTooltip } from './HojaUi'
import type { EstadoInflacion } from './TablaInflacion'

/** Variación % por encima de la cual se marca el mes con una bandera. `[POR VALIDAR]` (100 %). */
const UMBRAL_ALTO = 1_000_000n

const signo = (m: bigint) => (m > 0n ? '+' : '')
const clase = (m: bigint | null) => (m === null || m === 0n ? 'cero' : m > 0n ? 'pos' : 'neg')
const flecha = (m: bigint) => (m > 0n ? '▲' : m < 0n ? '▼' : '')

const AYUDAS = {
  infl: '% que se espera de aumento cada mes. Hoy 0 en el Excel.',
  acum: 'Suma de la inflación de los meses hasta ése.',
  conInfl: 'Total del mes × (1 + inflación del mes).',
  estAct: 'Lo real (más estimado) del año anterior. Del Excel por ahora.',
  previo: 'Lo que se presupuestó el año anterior. Del Excel por ahora.',
  variacion: 'Est-Act − Budget previo: cuánto se pasó (+) o se quedó corto (−) el año anterior.',
  variacionPct: 'Variación ÷ Budget previo.',
}

const maximo = (valores: readonly (bigint | null)[]) =>
  valores.reduce<bigint>((m, v) => (v !== null && v > m ? v : m), 0n)

/** Una celda de cifras con mini-barra proporcional al máximo de su columna y su insignia de pico. */
function CeldaBarra({
  valor,
  max,
  serie,
  pico,
}: {
  valor: bigint | null
  max: bigint
  serie: 'budget' | 'estAct' | 'previo'
  pico: 'max' | 'min' | null
}) {
  if (valor === null) return <td className="tm-c tm-num tm-vacia">—</td>
  return (
    <td className="tm-c tm-num">
      <span className="tm-valor">
        {pico && (
          <span className={`tm-pico tm-pico-${pico}`} title={pico === 'max' ? 'Mes de mayor valor' : 'Mes de menor valor'}>
            {pico === 'max' ? 'máx' : 'mín'}
          </span>
        )}
        {formatoMicros(valor)}
      </span>
      <svg className={`tm-barra tm-barra-${serie}`} viewBox="0 0 100 4" preserveAspectRatio="none" aria-hidden="true" focusable="false">
        <rect className="tm-barra-fondo" width="100" height="4" rx="2" />
        <rect className="tm-barra-valor" width={porcentajeBarra(valor, max)} height="4" rx="2" />
      </svg>
    </td>
  )
}

/**
 * La tabla «Inflación y comparativos» con los meses en filas: cada concepto es una columna ancha, agrupada
 * por color (Supuestos · Resultado · Año previo · Variación). Mapa de calor en Variación, mini-barras en las
 * cifras (con el color de su serie en el gráfico), insignias máx/mín y bandera de variación alta. Usa el
 * mismo estado de inflación que siempre y se sincroniza con el gráfico: el mes activo resalta su fila.
 * El color nunca va solo: signo, flechas y texto lo acompañan.
 */
export function TablaInflacionPorMes({
  e,
  mesActivo,
  alActivarMes,
  enfocarPrimero,
}: {
  e: EstadoInflacion
  mesActivo: number | null
  alActivarMes: (indice: number | null) => void
  enfocarPrimero?: boolean
}) {
  const primero = useRef<HTMLInputElement>(null)
  useEffect(() => {
    if (enfocarPrimero) primero.current?.focus()
  }, [enfocarPrimero])

  const maxConInfl = maximo(e.conInflacion)
  const maxEst = maximo(e.estAct)
  const maxPrev = maximo(e.previo)
  const maxVar = e.variacion.reduce<bigint>((m, v) => (v !== null && (v < 0n ? -v : v) > m ? (v < 0n ? -v : v) : m), 0n)
  const picosConInfl = extremosDe(e.conInflacion)
  const picosEst = extremosDe(e.estAct)
  const picosPrev = extremosDe(e.previo)
  const acumFinal = e.acumulada.length > 0 ? e.acumulada[e.acumulada.length - 1] : null
  const pico = (p: { max: number | null; min: number | null }, i: number): 'max' | 'min' | null =>
    p.max === i ? 'max' : p.min === i ? 'min' : null

  return (
    <>
      <div className="tm-contenedor" role="region" aria-label="Inflación y comparativos" tabIndex={0}>
        <table className="tm-tabla">
          <caption className="solo-lectores">
            Inflación y comparativos por mes: supuestos de inflación, total con inflación, Est-Act y Budget del año
            previo y su variación.
          </caption>
          <thead>
            <tr className="tm-grupos">
              <td />
              <th scope="colgroup" colSpan={2} className="tm-grupo tm-g-supuestos">
                Supuestos
              </th>
              <th scope="colgroup" className="tm-grupo tm-g-resultado">
                Resultado
              </th>
              <th scope="colgroup" colSpan={2} className="tm-grupo tm-g-previo">
                Año previo
              </th>
              <th scope="colgroup" colSpan={2} className="tm-grupo tm-g-variacion">
                Variación
              </th>
            </tr>
            <tr className="tm-cols">
              <th scope="col" className="tm-mes">
                Mes
              </th>
              <th scope="col" className="tm-num tm-g-supuestos">
                Inflación mensual <AyudaTooltip etiqueta="Qué es la inflación mensual" texto={AYUDAS.infl} />
              </th>
              <th scope="col" className="tm-num tm-g-supuestos">
                Inflación acumulada <AyudaTooltip etiqueta="Qué es la inflación acumulada" texto={AYUDAS.acum} />
              </th>
              <th scope="col" className="tm-num tm-g-resultado">
                Total con inflación <AyudaTooltip etiqueta="Qué es el total con inflación" texto={AYUDAS.conInfl} />
              </th>
              <th scope="col" className="tm-num tm-g-previo">
                Est-Act año previo <AyudaTooltip etiqueta="Qué es el Est-Act del año previo" texto={AYUDAS.estAct} />
              </th>
              <th scope="col" className="tm-num tm-g-previo">
                Budget año previo <AyudaTooltip etiqueta="Qué es el Budget del año previo" texto={AYUDAS.previo} />
              </th>
              <th scope="col" className="tm-num tm-g-variacion">
                Variación <AyudaTooltip etiqueta="Qué es la variación" texto={AYUDAS.variacion} />
              </th>
              <th scope="col" className="tm-num tm-g-variacion">
                Variación % <AyudaTooltip etiqueta="Qué es la variación porcentual" texto={AYUDAS.variacionPct} />
              </th>
            </tr>
          </thead>
          <tbody>
            {e.periodos.map((per, i) => {
              const v = e.variacion[i]
              const pctTexto = e.variacionPct[i]
              const pct = pctTexto === null || pctTexto === undefined ? null : (aMicros(pctTexto) ?? null)
              const nivel = nivelCalor(v, maxVar)
              return (
                <tr
                  key={per}
                  className={mesActivo === i ? 'tm-fila tm-fila-activa' : 'tm-fila'}
                  onMouseEnter={() => alActivarMes(i)}
                  onMouseLeave={() => alActivarMes(null)}
                >
                  <th
                    scope="row"
                    className="tm-mes"
                    tabIndex={0}
                    onFocus={() => alActivarMes(i)}
                    onBlur={() => alActivarMes(null)}
                  >
                    {etiquetaMes(per)}
                  </th>
                  <td className={e.puedeEditar ? 'tm-c tm-num tm-editable' : 'tm-c tm-num'}>
                    {e.puedeEditar ? (
                      <span className="entrada-sufijo">
                        <input
                          ref={i === 0 ? primero : undefined}
                          type="text"
                          inputMode="decimal"
                          className={e.inflPantalla[i] === null ? 'entrada-budget entrada-invalida' : 'entrada-budget'}
                          aria-label={`Inflación de ${etiquetaMes(per)} (%)`}
                          aria-invalid={e.inflPantalla[i] === null || undefined}
                          value={e.inflacion[i]}
                          placeholder="0"
                          onChange={(ev) => e.setInflacion((a) => a.map((x, j) => (j === i ? ev.target.value : x)))}
                        />
                        <span aria-hidden="true">%</span>
                      </span>
                    ) : (
                      <span>{fraccionAPorcentaje(e.inflacionGuardada[i]) || '0'}%</span>
                    )}
                  </td>
                  <td className="tm-c tm-num tm-suave">{formatoPorcentaje(e.acumulada[i])}</td>
                  <CeldaBarra valor={e.conInflacion[i]} max={maxConInfl} serie="budget" pico={pico(picosConInfl, i)} />
                  <CeldaBarra valor={e.estAct[i]} max={maxEst} serie="estAct" pico={pico(picosEst, i)} />
                  <CeldaBarra valor={e.previo[i]} max={maxPrev} serie="previo" pico={pico(picosPrev, i)} />
                  {v === null ? (
                    <td className="tm-c tm-num tm-vacia">—</td>
                  ) : (
                    <td className={`tm-c tm-num tm-calor tm-calor-${clase(v)}-${nivel}`}>
                      <span className={`tm-flecha tm-flecha-${clase(v)}`} aria-hidden="true">
                        {flecha(v)}
                      </span>{' '}
                      {signo(v)}
                      {formatoMicros(v)}
                    </td>
                  )}
                  <td className="tm-c tm-num">
                    {pct === null ? (
                      '—'
                    ) : (
                      <>
                        {superaUmbral(pct, UMBRAL_ALTO) && (
                          <span className="tm-bandera" title="Variación mayor a 100 %">
                            ⚑ &gt;100 %
                          </span>
                        )}
                        <span className={`tm-signo-${clase(pct)}`}>
                          {signo(pct)}
                          {formatoPorcentaje(pct)}
                        </span>
                      </>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
          <tfoot>
            <tr className="tm-total">
              <th scope="row" className="tm-mes">
                Total
              </th>
              <td className="tm-c tm-num">—</td>
              <td className="tm-c tm-num">{acumFinal === null ? '—' : formatoPorcentaje(acumFinal)}</td>
              <td className="tm-c tm-num">{formatoMicros(e.totalConInflacion)}</td>
              <td className="tm-c tm-num">{formatoMicros(e.totalEstAct)}</td>
              <td className="tm-c tm-num">{formatoMicros(e.totalPrevio)}</td>
              <td className="tm-c tm-num">
                {e.anualVar ? (
                  <span className={`tm-signo-${clase(e.anualVar.diferencia)}`}>
                    <span aria-hidden="true">{flecha(e.anualVar.diferencia)}</span> {signo(e.anualVar.diferencia)}
                    {formatoMicros(e.anualVar.diferencia)}
                  </span>
                ) : (
                  '—'
                )}
              </td>
              <td className="tm-c tm-num">
                {e.anualVar ? (
                  <span className={`tm-signo-${clase(e.anualVar.diferencia)}`}>
                    {e.anualVar.fraccion === null ? '—' : `${signo(e.anualVar.fraccion)}${formatoPorcentaje(e.anualVar.fraccion)}`}
                  </span>
                ) : (
                  '—'
                )}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      <p className="tm-nota">
        Las barras comparan cada mes con el más alto de su columna. <span className="tm-pico tm-pico-max">máx</span>{' '}
        <span className="tm-pico tm-pico-min">mín</span> marcan el mes más alto y el más bajo. En Variación, el color es
        más fuerte cuanto más se aleja de cero (▲ el año previo se pasó, ▼ se quedó corto).
      </p>

      <AccionesInflacion e={e} fija />
    </>
  )
}
