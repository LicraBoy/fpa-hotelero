import { useState } from 'react'
import { Icono } from '../../../componentes/Iconos'
import { aMicros, formatoMicros } from '../calculo'
import { AccionesInflacion } from './AccionesInflacion'
import { etiquetaMes, formatoPorcentaje, fraccionAPorcentaje } from '../hojaSeccion'

const signo = (m: bigint) => (m > 0n ? '+' : '')

/** Todo lo de la inflación que comparten la vista de cuentas y la de comparación anual. */
export interface EstadoInflacion {
  periodos: string[]
  /** Porcentajes tal como se escriben en pantalla (borrador). */
  inflacion: string[]
  setInflacion: (f: (a: string[]) => string[]) => void
  /** Fracciones en micros del borrador; `null` si el texto no es válido. */
  inflPantalla: (bigint | null)[]
  inflacionGuardada: (string | null)[]
  acumulada: bigint[]
  conInflacion: bigint[]
  estAct: (bigint | null)[]
  previo: (bigint | null)[]
  variacion: (bigint | null)[]
  variacionPct: (string | null)[]
  totalConInflacion: bigint | null
  totalEstAct: bigint | null
  totalPrevio: bigint | null
  anualVar: { diferencia: bigint; fraccion: bigint | null } | null
  invalida: boolean
  sucio: boolean
  guardando: boolean
  puedeEditar: boolean
  guardar: () => void
  descartar: () => void
  /** La inflación de esta hoja SÍ entra al Budget (cuenta por partidas); por omisión es informativa. */
  entraAlBudget?: boolean
}

interface FilaProps {
  etiqueta: string
  ayuda: string
  ayudaVisible: boolean
  alAlternarAyuda: () => void
  total?: bigint | null
  valores: readonly (bigint | null)[]
  conSigno?: boolean
  formato?: (v: bigint | null) => string
}

function FilaValores(p: FilaProps) {
  const f =
    p.formato ??
    ((v: bigint | null) => (v !== null && p.conSigno ? `${signo(v)}${formatoMicros(v)}` : formatoMicros(v)))
  return (
    <tr>
      <Concepto etiqueta={p.etiqueta} ayuda={p.ayuda} visible={p.ayudaVisible} alAlternar={p.alAlternarAyuda} />
      <td className="num col-anual celda-anual">{p.total === undefined ? '—' : f(p.total)}</td>
      {p.valores.map((v, i) => (
        <td key={i} className="num">
          {f(v)}
        </td>
      ))}
    </tr>
  )
}

function Concepto({
  etiqueta,
  ayuda,
  visible,
  alAlternar,
}: {
  etiqueta: string
  ayuda: string
  visible: boolean
  alAlternar: () => void
}) {
  return (
    <th scope="row" className="col-linea">
      <div className="concepto">
        <span className="concepto-textos">
          <span className="descripcion">{etiqueta}</span>
          {visible && <span className="hoja-ayuda">{ayuda}</span>}
        </span>
        {/* Va después del texto en el DOM (el nombre de la fila empieza por el concepto) y se pinta antes */}
        <button
          type="button"
          className="concepto-chevron"
          aria-expanded={visible}
          aria-label={`${visible ? 'Ocultar' : 'Mostrar'} la ayuda de ${etiqueta}`}
          onClick={alAlternar}
        >
          <Icono nombre="chevron" tamano={14} />
        </button>
      </div>
    </th>
  )
}

/**
 * La tabla «Inflación y comparativos» de la hoja de sección (meses en columnas) y su pareja
 * Descartar/Guardar inflación. La vista de comparación anual usa `TablaInflacionPorMes` con el mismo estado.
 */
export function TablaInflacion({ e }: { e: EstadoInflacion }) {
  const [ocultas, setOcultas] = useState<ReadonlySet<string>>(new Set())
  const alterna = (k: string) =>
    setOcultas((o) => {
      const n = new Set(o)
      if (n.has(k)) n.delete(k)
      else n.add(k)
      return n
    })
  const fila = (k: string) => ({ ayudaVisible: !ocultas.has(k), alAlternarAyuda: () => alterna(k) })

  return (
    <>
      <div className="tabla-variance-contenedor hoja-bloque-contenedor" role="region" aria-label="Inflación y comparativos" tabIndex={0}>
        <table className="tabla-variance hoja-tabla hoja-bloque">
          <thead>
            <tr>
              <th scope="col" className="col-linea">
                Concepto
              </th>
              <th scope="col" className="num col-anual">
                Total
              </th>
              {e.periodos.map((per) => (
                <th key={per} scope="col" className="num col-mes">
                  {etiquetaMes(per)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <Concepto
                etiqueta="Inflación mensual"
                ayuda={
                  e.entraAlBudget
                    ? '% de aumento de cada mes. En esta cuenta sí entra al Budget.'
                    : '% que se espera de aumento cada mes. Hoy 0 en el Excel.'
                }
                visible={!ocultas.has('infl')}
                alAlternar={() => alterna('infl')}
              />
              <td className="num col-anual">—</td>
              {e.inflacion.map((t, i) => (
                <td key={e.periodos[i]} className="num">
                  {e.puedeEditar ? (
                    <span className="entrada-sufijo">
                      <input
                        type="text"
                        inputMode="decimal"
                        className={e.inflPantalla[i] === null ? 'entrada-budget entrada-invalida' : 'entrada-budget'}
                        aria-label={`Inflación de ${etiquetaMes(e.periodos[i])} (%)`}
                        aria-invalid={e.inflPantalla[i] === null || undefined}
                        value={t}
                        placeholder="0"
                        onChange={(ev) => e.setInflacion((a) => a.map((x, j) => (j === i ? ev.target.value : x)))}
                      />
                      <span aria-hidden="true">%</span>
                    </span>
                  ) : (
                    <span>{fraccionAPorcentaje(e.inflacionGuardada[i]) || '0'}%</span>
                  )}
                </td>
              ))}
            </tr>
            <FilaValores
              etiqueta="Inflación acumulada"
              ayuda="Suma de la inflación de los meses hasta ése."
              valores={e.acumulada}
              formato={(v) => formatoPorcentaje(v)}
              {...fila('acum')}
            />
            <FilaValores
              etiqueta="Total con inflación"
              ayuda="Total del mes × (1 + inflación del mes)."
              total={e.totalConInflacion}
              valores={e.conInflacion}
              {...fila('conInfl')}
            />
            <FilaValores
              etiqueta="Est-Act año previo"
              ayuda="Lo real (más estimado) del año anterior. Del Excel por ahora."
              total={e.totalEstAct}
              valores={e.estAct}
              {...fila('estAct')}
            />
            <FilaValores
              etiqueta="Budget año previo"
              ayuda="Lo que se presupuestó el año anterior. Del Excel por ahora."
              total={e.totalPrevio}
              valores={e.previo}
              {...fila('previo')}
            />
            <FilaValores
              etiqueta="Variación"
              ayuda="Est-Act − Budget previo: cuánto se pasó (+) o se quedó corto (−) el año anterior."
              total={e.anualVar ? e.anualVar.diferencia : null}
              valores={e.variacion}
              conSigno
              {...fila('var')}
            />
            <tr>
              <Concepto
                etiqueta="Variación %"
                ayuda="Variación ÷ Budget previo."
                visible={!ocultas.has('varPct')}
                alAlternar={() => alterna('varPct')}
              />
              <td className="num col-anual celda-anual">{e.anualVar ? formatoPorcentaje(e.anualVar.fraccion) : '—'}</td>
              {e.variacionPct.map((t, i) => (
                <td key={e.periodos[i]} className="num">
                  {formatoPorcentaje(t === null ? null : (aMicros(t) ?? null))}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>

      <AccionesInflacion e={e} />
    </>
  )
}
