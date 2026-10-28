import { useMemo, useState } from 'react'
import { ErrorApi, enviarJson } from '../../../api/cliente'
import type { components } from '../../../api/schema'
import { Icono } from '../../../componentes/Iconos'
import { MensajeError } from '../../../componentes/Insignia'
import { aMicros, formatoMicros, textoDeMicros } from '../calculo'
import { etiquetaMes } from '../hojaSeccion'
import {
  controlSuma,
  cuerpoPartidas,
  erroresDePartida,
  extendidoDe,
  mesesDe,
  partidaCambio,
  partidaNueva,
  repartirMensual,
  type MetodoPartida,
  type PartidaEditable,
} from '../partidas'
import { TarjetaIndicador } from './HojaUi'

type HojaCuentaSalida = components['schemas']['HojaCuentaSalida']
const dinero = (m: bigint | null) => (m === null ? '—' : `$ ${formatoMicros(m)}`)

interface Props {
  hotelId: number
  cicloId: number
  lineaId: number
  /** Nombre de la cuenta (la «Hoja de cuenta» a la que se regresa). */
  cuenta: string
  /** Las partidas guardadas de la cuenta, en orden. */
  partidas: PartidaEditable[]
  /** Índice de la partida que se edita; `-1` = una partida nueva. */
  indice: number
  /** Inflación de la cuenta por periodo (fracciones, como las guarda la API): viaja con las partidas. */
  inflacion: Record<string, string>
  periodos: string[]
  puedeEditar: boolean
  alElegir: (indice: number) => void
  alVolver: () => void
  /** Se guardó (o se eliminó) la partida: la hoja de la cuenta ya puede volver a leerse. */
  alGuardado: (mensaje: string, hoja: HojaCuentaSalida | null) => void
}

/**
 * Editor de partida: una partida de una cuenta por partidas (cantidad, unidad, costo y cómo se reparte en
 * los meses). El costo extendido es cantidad × costo (calculado); `Mensual` lo reparte entre 12 meses y
 * `Estacional` deja capturar cada mes, con el control «la suma de meses cuadra con el extendido». Guardar
 * manda TODAS las partidas de la cuenta juntas (con su inflación): es una sola operación.
 */
export function EditorPartida(p: Props) {
  const original = useMemo(() => (p.indice >= 0 ? p.partidas[p.indice] : partidaNueva()), [p.indice, p.partidas])
  const [b, setB] = useState<PartidaEditable>(original)
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const nueva = p.indice < 0
  const extendido = extendidoDe(b.cantidad, b.costo)
  const meses = mesesDe(b)
  const control = controlSuma(b)
  const errores = erroresDePartida(b)
  const sucio = nueva ? JSON.stringify(b) !== JSON.stringify(partidaNueva()) : partidaCambio(b, original)
  const puedeGuardar = p.puedeEditar && !guardando && errores.length === 0 && (nueva || sucio)
  const importada = b.metodo === 'importada'
  const editaMeses = p.puedeEditar && b.metodo === 'estacional'
  const total = meses === null ? null : meses.reduce((s, x) => s + x, 0n)

  // Salir (otra partida o volver a la hoja de la cuenta) con cambios sin guardar pide confirmación
  const intentar = (accion: () => void) => {
    if (sucio && !window.confirm('Tienes cambios sin guardar en esta partida. ¿Descartarlos?')) return
    accion()
  }

  function cambiar(parche: Partial<PartidaEditable>) {
    setB((a) => ({ ...a, ...parche }))
  }

  function elegirMetodo(metodo: MetodoPartida) {
    if (metodo === b.metodo) return
    // Al pasar a estacional se parte del reparto parejo actual, para no empezar de ceros
    if (metodo === 'estacional' && b.metodo === 'mensual' && extendido !== null) {
      cambiar({ metodo, meses: repartirMensual(extendido).map(textoDeMicros) })
    } else cambiar({ metodo })
  }

  async function enviar(lista: PartidaEditable[], mensaje: string) {
    const cuerpo = cuerpoPartidas(lista, p.inflacion)
    if ('error' in cuerpo) {
      setError(cuerpo.error)
      return
    }
    setGuardando(true)
    setError(null)
    try {
      const hoja = await enviarJson<HojaCuentaSalida>(
        'PUT',
        `/api/v1/hoteles/${p.hotelId}/presupuesto/ciclos/${p.cicloId}/lineas/${p.lineaId}/partidas`,
        cuerpo,
      )
      p.alGuardado(mensaje, hoja)
    } catch (e) {
      setError(e instanceof ErrorApi ? e.detalle : 'No se pudo guardar la partida')
    } finally {
      setGuardando(false)
    }
  }

  const guardar = () =>
    void enviar(
      nueva ? [...p.partidas, b] : p.partidas.map((x, i) => (i === p.indice ? b : x)),
      'Partida guardada. El Budget de la cuenta se recalculó con la inflación.',
    )
  const eliminar = () => {
    if (!window.confirm(`¿Eliminar la partida «${original.concepto}»?`)) return
    void enviar(p.partidas.filter((_, i) => i !== p.indice), 'Partida eliminada. El Budget de la cuenta se recalculó.')
  }

  const anterior = p.indice > 0 ? p.indice - 1 : null
  const siguiente = p.indice >= 0 && p.indice < p.partidas.length - 1 ? p.indice + 1 : null
  const invalido = (campo: string) => errores.some((e) => e.campo === campo) && b[campo as 'concepto'] !== undefined

  return (
    <section className="editor-cuenta editor-partida" aria-label={`Editor de la partida ${b.concepto || 'nueva'}`}>
      <header className="ec-cabecera">
        <nav aria-label="Ruta de la partida" className="ec-migas">
          <button type="button" className="hoja-volver" onClick={() => intentar(p.alVolver)} aria-label="Volver a la Hoja de cuenta">
            <Icono nombre="volver" tamano={14} />
            {p.cuenta}
          </button>
          <span className="etiqueta-pantalla">Editor de partida</span>
        </nav>
        <div className="ec-titulos">
          <h2 title={b.concepto}>{b.concepto.trim() || 'Nueva partida'}</h2>
          <p className="ec-meta">
            <span>{nueva ? 'Partida nueva' : `Partida ${p.indice + 1} de ${p.partidas.length}`}</span>
          </p>
        </div>
        {!nueva && p.partidas.length > 1 && (
          <div className="ec-navegacion">
            <button type="button" className="ec-boton-nav" disabled={anterior === null} onClick={() => anterior !== null && intentar(() => p.alElegir(anterior))}>
              ‹ Anterior
            </button>
            <span className="ec-contador">
              {p.indice + 1} de {p.partidas.length}
            </span>
            <button type="button" className="ec-boton-nav" disabled={siguiente === null} onClick={() => siguiente !== null && intentar(() => p.alElegir(siguiente))}>
              Siguiente ›
            </button>
          </div>
        )}
      </header>

      <div className="hoja-indicadores ec-indicadores" role="group" aria-label="Resumen de la partida">
        <TarjetaIndicador tono="azul" icono="baseDatos" etiqueta="Costo extendido (cantidad × costo)">
          {dinero(extendido)}
        </TarjetaIndicador>
        <TarjetaIndicador tono="verde" icono="calendario" etiqueta="Suma de los 12 meses">
          {dinero(total)}
        </TarjetaIndicador>
        <TarjetaIndicador
          tono={control === null || control === 0n ? 'neutro' : 'naranja'}
          icono={control === null || control === 0n ? 'check' : 'alerta'}
          etiqueta="Control de la distribución"
        >
          {control === null ? '—' : control === 0n ? 'Cuadra' : control < 0n ? `Falta ${dinero(-control)}` : `Excede ${dinero(control)}`}
        </TarjetaIndicador>
      </div>

      <div className="ep-campos">
        <label className="ep-campo ep-concepto">
          <span>Concepto</span>
          <input
            type="text"
            aria-label="Concepto de la partida"
            value={b.concepto}
            disabled={!p.puedeEditar}
            aria-invalid={invalido('concepto') || undefined}
            onChange={(e) => cambiar({ concepto: e.target.value })}
          />
        </label>
        <label className="ep-campo">
          <span>Cantidad</span>
          <input type="text" inputMode="decimal" aria-label="Cantidad" value={b.cantidad} disabled={!p.puedeEditar} aria-invalid={invalido('cantidad') || undefined} onChange={(e) => cambiar({ cantidad: e.target.value })} />
        </label>
        <label className="ep-campo">
          <span>Unidad de medida</span>
          <input type="text" aria-label="Unidad de medida" value={b.unidad} disabled={!p.puedeEditar} maxLength={20} onChange={(e) => cambiar({ unidad: e.target.value })} />
        </label>
        <label className="ep-campo">
          <span>Costo unitario</span>
          <input type="text" inputMode="decimal" aria-label="Costo unitario" value={b.costo} disabled={!p.puedeEditar} aria-invalid={invalido('costo') || undefined} onChange={(e) => cambiar({ costo: e.target.value })} />
        </label>
        <div className="ep-campo">
          <span>Distribución</span>
          <div className="graf-segmentado" role="group" aria-label="Distribución de la partida">
            <button type="button" aria-pressed={b.metodo === 'mensual'} disabled={!p.puedeEditar} onClick={() => elegirMetodo('mensual')}>
              Mensual
            </button>
            <button type="button" aria-pressed={b.metodo === 'estacional'} disabled={!p.puedeEditar} onClick={() => elegirMetodo('estacional')}>
              Estacional
            </button>
            {importada && (
              <button type="button" aria-pressed="true" disabled>
                Importada
              </button>
            )}
          </div>
        </div>
      </div>
      <p className="ep-ayuda">
        {b.metodo === 'mensual'
          ? 'Mensual: el costo extendido se reparte en partes iguales entre los 12 meses.'
          : importada
            ? 'Importada: los meses vienen del Excel (p. ej. repartidos por una estadística). Pasa a Estacional para editarlos.'
            : 'Estacional: captura cuánto cae en cada mes; la suma debe cuadrar con el costo extendido.'}
      </p>

      {error && <MensajeError texto={error} />}

      <div className="ec-tabla-tarjeta" role="region" aria-label="Meses de la partida" tabIndex={0}>
        <table className="ec-tabla ep-tabla">
          <caption className="solo-lectores">Importe de la partida en cada mes del año fiscal.</caption>
          <thead>
            <tr>
              <th scope="col" className="ec-col-mes">
                Mes
              </th>
              <th scope="col" className="num">
                Importe
              </th>
              <th scope="col" className="num">
                % del extendido
              </th>
            </tr>
          </thead>
          <tbody>
            {p.periodos.map((per, i) => {
              const m = meses === null ? null : meses[i]
              const mes = etiquetaMes(per)
              return (
                <tr key={per}>
                  <th scope="row" className="ec-col-mes">
                    {mes}
                  </th>
                  <td className="num">
                    {editaMeses ? (
                      <span className="ec-campo">
                        <input
                          type="text"
                          inputMode="decimal"
                          className={b.meses[i].trim() !== '' && aMicros(b.meses[i]) === null ? 'ec-entrada ec-invalida' : 'ec-entrada'}
                          aria-label={`Importe de ${mes}`}
                          placeholder="0"
                          value={b.meses[i]}
                          onChange={(e) => cambiar({ meses: b.meses.map((x, j) => (j === i ? e.target.value : x)) })}
                        />
                      </span>
                    ) : (
                      <span>{m === null ? '—' : formatoMicros(m)}</span>
                    )}
                  </td>
                  <td className="num ec-signo-cero">
                    {m === null || extendido === null || extendido === 0n ? '—' : `${(Number((m * 10000n) / extendido) / 100).toFixed(2)}%`}
                  </td>
                </tr>
              )
            })}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row" className="ec-col-mes">
                Total
              </th>
              <td className="num">{total === null ? '—' : formatoMicros(total)}</td>
              <td className="num">{extendido === null || extendido === 0n || total === null ? '—' : `${(Number((total * 10000n) / extendido) / 100).toFixed(2)}%`}</td>
            </tr>
          </tfoot>
        </table>
      </div>

      {p.puedeEditar && (
        <div className="ec-barra ep-barra">
          <span className="ec-barra-estado" aria-live="polite">
            {errores.length > 0 ? (
              <>
                <span className="ec-punto ec-punto-rojo" aria-hidden="true" />
                <span className="ec-barra-texto">
                  <strong>{errores[0].texto}</strong>
                  {errores.length > 1 ? ` (y ${errores.length - 1} más)` : ''}
                </span>
              </>
            ) : sucio || nueva ? (
              <>
                <span className="ec-punto ec-punto-naranja" aria-hidden="true" />
                <span className="ec-barra-texto">
                  <strong>{nueva ? 'Partida nueva' : 'Cambios sin guardar'}</strong>
                </span>
              </>
            ) : (
              <span className="ec-barra-texto">Sin cambios</span>
            )}
          </span>
          <span className="ec-separador" aria-hidden="true" />
          {!nueva && (
            <button type="button" className="ec-boton-neutro" disabled={guardando} onClick={eliminar}>
              Eliminar partida
            </button>
          )}
          <button type="button" className="ec-boton-neutro" disabled={!sucio || guardando} onClick={() => setB(original)}>
            Descartar cambios
          </button>
          <button type="button" className="ec-boton-primario" disabled={!puedeGuardar} onClick={guardar}>
            <Icono nombre="guardar" tamano={15} />
            {guardando ? 'Guardando…' : 'Guardar partida'}
          </button>
        </div>
      )}
    </section>
  )
}
