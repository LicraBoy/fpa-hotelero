import { useMemo, useState } from 'react'
import { ErrorApi, enviarJson } from '../../../api/cliente'
import type { components } from '../../../api/schema'
import { MensajeError } from '../../../componentes/Insignia'
import { aMicros, formatoMicros, repartirConPerfil } from '../calculo'

type Perfil = components['schemas']['PerfilSalida']
type LineaMensual = components['schemas']['LineaMensualSalida']

const MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
/** «0.083333» (fracción del año) -> «8.33 %». Solo para mostrar: el reparto se calcula en micros. */
const porcentaje = (peso: string) => `${(Number(peso) * 100).toFixed(2)} %`
const etiquetaMes = (periodo: string) => `${MESES[Number(periodo.slice(5, 7)) - 1]} ${periodo.slice(2, 4)}`

interface Props {
  hotelId: number
  cicloId: number
  linea: number
  anual: string
  perfiles: Perfil[]
  periodos: string[]
  alAplicar: (valores: LineaMensual[]) => void
}

/**
 * "Rellenar con perfil…" con vista previa antes de aplicar (spec §5.3): el reparto que se muestra
 * sale de `repartirConPerfil`, que calca al micro el algoritmo del backend (`repartir()` en
 * `presupuesto_distribucion.py`) — nunca difiere de lo que de verdad se va a guardar. Aplicar un
 * perfil solo mensualiza esta línea; no toca el presupuesto de ninguna otra.
 */
export function SelectorPerfilDistribucion({ hotelId, cicloId, linea, anual, perfiles, periodos, alAplicar }: Props) {
  const [abierto, setAbierto] = useState(false)
  const [perfilId, setPerfilId] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const perfil = perfiles.find((p) => String(p.id) === perfilId) ?? null
  const anualMicros = aMicros(anual)
  const previsto = useMemo(
    () => (perfil && anualMicros !== null ? repartirConPerfil(anualMicros, perfil.pesos) : null),
    [perfil, anualMicros],
  )

  async function aplicar() {
    if (!perfilId) return
    setEnviando(true)
    setError(null)
    try {
      await enviarJson('PUT', `/api/v1/hoteles/${hotelId}/presupuesto/ciclos/${cicloId}/lineas/${linea}`, {
        propuesta_anual: anual,
        nota: null,
      })
      const r = await enviarJson<LineaMensual[]>(
        'POST',
        `/api/v1/hoteles/${hotelId}/presupuesto/ciclos/${cicloId}/lineas/${linea}/prorrateo`,
        { perfil_distribucion_id: Number(perfilId) },
      )
      if (r) alAplicar(r)
      setAbierto(false)
      setPerfilId('')
    } catch (e) {
      setError(e instanceof ErrorApi ? e.detalle : 'No se pudo prorratear')
    } finally {
      setEnviando(false)
    }
  }

  if (!abierto) {
    return (
      <button
        type="button"
        className="boton boton-secundario"
        onClick={() => setAbierto(true)}
        title={`Repartir ${anual} en los ${periodos.length} meses según un perfil`}
      >
        Rellenar con perfil…
      </button>
    )
  }

  const maximo = previsto ? previsto.reduce((m, v) => (v > m ? v : m), 1n) : 1n

  return (
    <span className="selector-perfil">
      <span className="campo-con-boton">
        <select
          aria-label="Perfil de distribución"
          value={perfilId}
          disabled={enviando}
          onChange={(e) => setPerfilId(e.target.value)}
        >
          <option value="">Elige un perfil…</option>
          {perfiles.map((pf) => (
            <option key={pf.id} value={pf.id}>
              {pf.nombre}
            </option>
          ))}
        </select>
        <button type="button" className="boton boton-secundario" disabled={!perfilId || enviando} onClick={() => void aplicar()}>
          {enviando ? 'Aplicando…' : 'Aplicar'}
        </button>
        <button type="button" className="boton boton-secundario" onClick={() => setAbierto(false)}>
          Cancelar
        </button>
      </span>

      {!perfil && <p className="cajon-subtitulo">Elige un perfil para ver cómo se reparte el año mes por mes.</p>}
      {perfil && previsto && (
        <div className="vista-previa-perfil" role="group" aria-label={`Vista previa de ${perfil.nombre}`}>
          <svg
            className="mini-perfil"
            viewBox="0 0 120 32"
            preserveAspectRatio="none"
            role="img"
            aria-label={periodos.map((p, i) => `${etiquetaMes(p)}: ${formatoMicros(previsto[i])}`).join(', ')}
          >
            {previsto.map((v, i) => {
              const alto = maximo > 0n ? Number((v * 28n) / maximo) : 0
              return (
                <rect
                  key={periodos[i]}
                  className="mini-perfil-barra"
                  x={i * 10 + 1}
                  y={30 - alto}
                  width={8}
                  height={Math.max(alto, 1)}
                />
              )
            })}
          </svg>
          <ul className="previa-meses" aria-label={`Reparto previsto del perfil ${perfil.nombre}, por mes`}>
            {previsto.map((v, i) => (
              <li key={periodos[i]}>
                <span className="previa-mes">{etiquetaMes(periodos[i])}</span>
                <span className="previa-importe">{formatoMicros(v)}</span>
                <span className="previa-peso">{porcentaje(perfil.pesos[i])}</span>
              </li>
            ))}
          </ul>
          <p className="previa-total">
            <span>Total del año</span>
            <strong>{formatoMicros(previsto.reduce((acc, x) => acc + x, 0n))}</strong>
          </p>
        </div>
      )}
      {error && <MensajeError texto={error} />}
    </span>
  )
}
