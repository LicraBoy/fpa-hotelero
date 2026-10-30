import { useMemo, useState } from 'react'
import { ErrorApi, enviarJson } from '../../../api/cliente'
import type { components } from '../../../api/schema'
import { Icono } from '../../../componentes/Iconos'
import { MensajeError } from '../../../componentes/Insignia'
import { aMicros, formatoMicros, textoDeMicros } from '../calculo'
import {
  conSigno,
  costoTexto,
  cuerpoConsumo,
  diferencia,
  mesCambio,
  microsDe,
  sumaDe,
  titulosBloques,
  totalDeMes,
  type BloqueConsumo,
  type MesEditable,
} from '../consumo'
import { etiquetaMes } from '../hojaSeccion'

type HojaCuentaSalida = components['schemas']['HojaCuentaSalida']
type ConsumoSalida = components['schemas']['ConsumoSalida']

interface Props {
  hotelId: number
  cicloId: number
  lineaId: number
  consumo: ConsumoSalida
  periodos: string[]
  puedeEditar: boolean
  /** Se guardó: la hoja de la cuenta ya puede volver a leerse. */
  alGuardado: (mensaje: string, hoja: HojaCuentaSalida | null) => void
}

const BLOQUES_SOLO_LECTURA: BloqueConsumo[] = ['real_prev', 'budget_prev', 'est_act']
const unidades = (m: bigint | null) => (m === null ? '—' : formatoMicros(m))

/**
 * Consumo mensual de una cuenta de consumo (Diesel, Gas, Electricity, Water): los cuatro bloques de la hoja
 * del Excel (Real, Budget previo, Est-Act y Budget) con unidades, costo unitario y total por mes, sus totales
 * y las variaciones del Budget contra el Est-Act y contra el Budget previo. Solo el Budget se edita: cada mes
 * es unidades × costo unitario y el Budget de la cuenta se recalcula al guardar.
 */
export function HojaConsumo(p: Props) {
  const titulos = titulosBloques(p.periodos)
  const originales = useMemo<MesEditable[]>(
    () =>
      p.consumo.budget.map((m) => ({
        unidades: m.unidades === null ? '' : textoDeMicros(aMicros(m.unidades) ?? 0n),
        costo: m.costo_unitario === null ? '' : textoDeMicros(aMicros(m.costo_unitario) ?? 0n),
      })),
    [p.consumo],
  )
  const [editados, setEditados] = useState<MesEditable[]>(originales)
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const cambiados = editados.map((m, i) => mesCambio(m, originales[i]))
  const sucio = cambiados.some(Boolean)
  const puedeGuardar = p.puedeEditar && sucio && !guardando

  // Total de cada mes del Budget: el guardado si no se tocó; unidades × costo si se editó
  const totalBudget = (i: number): bigint | null =>
    cambiados[i] ? totalDeMes(editados[i].unidades, editados[i].costo) : microsDe(p.consumo.budget[i].total)
  const unidadesBudget = (i: number): bigint | null => (cambiados[i] ? microsDe(editados[i].unidades) : microsDe(p.consumo.budget[i].unidades))
  const costoBudget = (i: number): bigint | null => (cambiados[i] ? microsDe(editados[i].costo) : microsDe(p.consumo.budget[i].costo_unitario))

  const unidadesDe = (b: BloqueConsumo) => p.periodos.map((_, i) => (b === 'budget' ? unidadesBudget(i) : microsDe(p.consumo[b][i].unidades)))
  const totalesDe = (b: BloqueConsumo) => p.periodos.map((_, i) => (b === 'budget' ? totalBudget(i) : microsDe(p.consumo[b][i].total)))
  const sumaUnidades = (b: BloqueConsumo) => sumaDe(unidadesDe(b))
  const sumaTotal = (b: BloqueConsumo) => sumaDe(totalesDe(b))
  // costo unitario promedio ponderado = total / unidades (solo informativo)
  const costoPromedio = (b: BloqueConsumo): bigint | null => {
    const u = sumaUnidades(b)
    const t = sumaTotal(b)
    return u === null || t === null || u === 0n ? null : (t * 1_000_000n) / u
  }

  const unidadesMes = (b: BloqueConsumo, i: number) => unidadesDe(b)[i]
  const totalMes = (b: BloqueConsumo, i: number) => totalesDe(b)[i]
  const budgetTotal = sumaTotal('budget')
  const estActTotal = sumaTotal('est_act')
  const previoTotal = sumaTotal('budget_prev')
  const budgetUnidades = sumaUnidades('budget')
  const estActUnidades = sumaUnidades('est_act')

  function cambiar(i: number, parche: Partial<MesEditable>) {
    setEditados((a) => a.map((m, j) => (j === i ? { ...m, ...parche } : m)))
  }

  async function guardar() {
    const cuerpo = cuerpoConsumo(p.periodos, editados, originales)
    if ('error' in cuerpo) {
      setError(cuerpo.error)
      return
    }
    setGuardando(true)
    setError(null)
    try {
      const hoja = await enviarJson<HojaCuentaSalida>(
        'PUT',
        `/api/v1/hoteles/${p.hotelId}/presupuesto/ciclos/${p.cicloId}/lineas/${p.lineaId}/consumo`,
        cuerpo,
      )
      p.alGuardado('Consumo guardado. El Budget de la cuenta se recalculó (unidades × costo unitario).', hoja)
    } catch (e) {
      setError(e instanceof ErrorApi ? e.detalle : 'No se pudo guardar el consumo')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <section className="hoja-tarjeta hc-tarjeta" aria-labelledby="hc-titulo">
      <div className="hoja-inflacion-cabecera">
        <h3 id="hc-titulo" className="hoja-subtitulo">
          Consumo mensual ({p.consumo.unidad})
        </h3>
        <p className="hc-ayuda">
          Cada mes: unidades × costo unitario = total. {p.puedeEditar ? `Se editan solo las unidades y el costo de ${titulos.budget}; los demás bloques vienen del Excel.` : 'Solo lectura.'}
        </p>
      </div>
      {error && <MensajeError texto={error} />}
      <div className="ec-tabla-tarjeta hc-region" role="region" aria-label="Consumo mensual" tabIndex={0}>
        <table className="ec-tabla hc-tabla">
          <caption className="solo-lectores">
            Unidades, costo unitario y total de cada mes en los bloques {Object.values(titulos).join(', ')}, y las variaciones del Budget.
          </caption>
          <thead>
            <tr>
              <th scope="col" rowSpan={2} className="ec-col-mes">
                Mes
              </th>
              {(['real_prev', 'budget_prev', 'est_act', 'budget'] as BloqueConsumo[]).map((b) => (
                <th key={b} scope="colgroup" colSpan={3} className={b === 'budget' ? 'hc-grupo hc-grupo-budget' : 'hc-grupo'}>
                  {titulos[b]}
                </th>
              ))}
              <th scope="colgroup" colSpan={3} className="hc-grupo">
                Variación del Budget
              </th>
            </tr>
            <tr>
              {(['real_prev', 'budget_prev', 'est_act', 'budget'] as BloqueConsumo[]).flatMap((b) => [
                <th key={`${b}-u`} scope="col" className="num">
                  {p.consumo.unidad}
                </th>,
                <th key={`${b}-c`} scope="col" className="num">
                  Costo
                </th>,
                <th key={`${b}-t`} scope="col" className="num">
                  Total
                </th>,
              ])}
              <th scope="col" className="num">
                {p.consumo.unidad} vs Est-Act
              </th>
              <th scope="col" className="num">
                $ vs Est-Act
              </th>
              <th scope="col" className="num">
                $ vs Budget prev.
              </th>
            </tr>
          </thead>
          <tbody>
            {p.periodos.map((per, i) => {
              const mes = etiquetaMes(per)
              return (
                <tr key={per} className={cambiados[i] ? 'hc-fila-cambiada' : undefined}>
                  <th scope="row" className="ec-col-mes">
                    {mes}
                  </th>
                  {BLOQUES_SOLO_LECTURA.flatMap((b) => [
                    <td key={`${b}-u`} className="num">
                      {unidades(microsDe(p.consumo[b][i].unidades))}
                    </td>,
                    <td key={`${b}-c`} className="num">
                      {costoTexto(microsDe(p.consumo[b][i].costo_unitario))}
                    </td>,
                    <td key={`${b}-t`} className="num">
                      {unidades(microsDe(p.consumo[b][i].total))}
                    </td>,
                  ])}
                  <td className="num hc-celda-budget">
                    {p.puedeEditar ? (
                      <input
                        type="text"
                        inputMode="decimal"
                        className={
                          editados[i].unidades.trim() !== '' && aMicros(editados[i].unidades) === null ? 'ec-entrada ec-invalida' : 'ec-entrada'
                        }
                        aria-label={`${p.consumo.unidad} de ${mes}`}
                        value={editados[i].unidades}
                        onChange={(e) => cambiar(i, { unidades: e.target.value })}
                      />
                    ) : (
                      unidades(unidadesBudget(i))
                    )}
                  </td>
                  <td className="num hc-celda-budget">
                    {p.puedeEditar ? (
                      <input
                        type="text"
                        inputMode="decimal"
                        className={editados[i].costo.trim() !== '' && aMicros(editados[i].costo) === null ? 'ec-entrada ec-invalida' : 'ec-entrada'}
                        aria-label={`Costo unitario de ${mes}`}
                        value={editados[i].costo}
                        onChange={(e) => cambiar(i, { costo: e.target.value })}
                      />
                    ) : (
                      costoTexto(costoBudget(i))
                    )}
                  </td>
                  <td className="num hc-celda-budget">{unidades(totalBudget(i))}</td>
                  <td className="num">{conSigno(diferencia(unidadesMes('budget', i), unidadesMes('est_act', i)))}</td>
                  <td className="num">{conSigno(diferencia(totalMes('budget', i), totalMes('est_act', i)))}</td>
                  <td className="num">{conSigno(diferencia(totalMes('budget', i), totalMes('budget_prev', i)))}</td>
                </tr>
              )
            })}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row" className="ec-col-mes">
                Total
              </th>
              {(['real_prev', 'budget_prev', 'est_act', 'budget'] as BloqueConsumo[]).flatMap((b) => [
                <td key={`${b}-u`} className="num">
                  {unidades(sumaUnidades(b))}
                </td>,
                <td key={`${b}-c`} className="num">
                  {costoTexto(costoPromedio(b))}
                </td>,
                <td key={`${b}-t`} className="num">
                  {unidades(sumaTotal(b))}
                </td>,
              ])}
              <td className="num">{conSigno(diferencia(budgetUnidades, estActUnidades))}</td>
              <td className="num">{conSigno(diferencia(budgetTotal, estActTotal))}</td>
              <td className="num">{conSigno(diferencia(budgetTotal, previoTotal))}</td>
            </tr>
          </tfoot>
        </table>
      </div>

      {p.puedeEditar && (
        <div className="ec-barra ep-barra">
          <span className="ec-barra-estado" aria-live="polite">
            {sucio ? (
              <>
                <span className="ec-punto ec-punto-naranja" aria-hidden="true" />
                <span className="ec-barra-texto">
                  <strong>Cambios sin guardar</strong> ({cambiados.filter(Boolean).length} {cambiados.filter(Boolean).length === 1 ? 'mes' : 'meses'})
                </span>
              </>
            ) : (
              <span className="ec-barra-texto">Sin cambios</span>
            )}
          </span>
          <span className="ec-separador" aria-hidden="true" />
          <button
            type="button"
            className="ec-boton-neutro"
            disabled={!sucio || guardando}
            onClick={() => {
              setEditados(originales)
              setError(null)
            }}
          >
            Descartar cambios
          </button>
          <button type="button" className="ec-boton-primario" disabled={!puedeGuardar} onClick={() => void guardar()}>
            <Icono nombre="guardar" tamano={15} />
            {guardando ? 'Guardando…' : 'Guardar consumo'}
          </button>
        </div>
      )}
    </section>
  )
}
