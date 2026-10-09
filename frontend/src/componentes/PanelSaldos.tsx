import { useMemo, useState } from 'react'
import { obtenerTipado } from '../api/cliente'
import { useDatos } from '../api/useDatos'
import { formatoDinero, sumar } from '../util/dinero'
import { EncabezadoPagina } from './EncabezadoPagina'
import { Cargando, EstadoVacio, MensajeError } from './Insignia'

interface Props {
  hotelId: number
  version: number
  puedeVerCargas: boolean
}

export function PanelSaldos({ hotelId, version, puedeVerCargas }: Props) {
  const cargas = useDatos(
    () => (puedeVerCargas ? obtenerTipado('/api/v1/hoteles/{hotel_id}/cargas', { path: { hotel_id: hotelId } }) : Promise.resolve([])),
    [hotelId, version, puedeVerCargas],
  )
  const periodos = useMemo(
    () =>
      [...new Set((cargas.datos ?? []).filter((c) => c.estado === 'vigente').map((c) => c.periodo))]
        .sort()
        .reverse(),
    [cargas.datos],
  )
  const [elegido, setElegido] = useState('')
  // El mes activo se deriva: el elegido si sigue disponible, si no el más reciente.
  const periodo = periodos.includes(elegido) ? elegido : (periodos[0] ?? '')

  return (
    <section className="tarjeta" aria-labelledby="titulo-saldos">
      <EncabezadoPagina
        id="titulo-saldos"
        titulo="Saldos por cuenta"
        subtitulo="Débito, crédito y resultado de cada cuenta en el mes elegido."
      />
      {cargas.cargando && <Cargando />}
      {cargas.error && <MensajeError texto={cargas.error} />}
      {!cargas.cargando && periodos.length === 0 && (
        <EstadoVacio>Aún no hay meses cargados.</EstadoVacio>
      )}
      {periodos.length > 0 && (
        <>
          <label className="buscador">
            Mes
            <select value={periodo} onChange={(e) => setElegido(e.target.value)}>
              {periodos.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>
          {periodo && <TablaSaldos hotelId={hotelId} periodo={periodo} version={version} />}
        </>
      )}
    </section>
  )
}

function TablaSaldos({
  hotelId,
  periodo,
  version,
}: {
  hotelId: number
  periodo: string
  version: number
}) {
  const saldos = useDatos(
    () => obtenerTipado('/api/v1/hoteles/{hotel_id}/saldos', {
        path: { hotel_id: hotelId },
        query: { periodo },
      }),
    [hotelId, periodo, version],
  )
  const [consulta, setConsulta] = useState('')
  const filas = useMemo(() => {
    const q = consulta.trim().toLowerCase()
    return (saldos.datos ?? []).filter((s) => !q || s.cuenta_codigo.toLowerCase().includes(q))
  }, [saldos.datos, consulta])

  if (saldos.cargando) return <Cargando />
  if (saldos.error) return <MensajeError texto={saldos.error} />
  if (!saldos.datos) return null

  return (
    <>
      <label className="buscador">
        Filtrar por código de cuenta
        <input
          type="search"
          placeholder="Ej. 4001"
          value={consulta}
          onChange={(e) => setConsulta(e.target.value)}
        />
      </label>
      <div className="tabla-contenedor tabla-alta tabla-marco">
        <table className="tabla">
          <thead>
            <tr>
              <th>Cuenta</th>
              <th className="num">Movimientos</th>
              <th className="num">Débito</th>
              <th className="num">Crédito</th>
              <th className="num">Resultado (Débito − Crédito)</th>
            </tr>
          </thead>
          <tbody>
            {filas.map((s) => (
              <tr key={s.cuenta_codigo}>
                <td>
                  <code>{s.cuenta_codigo}</code>
                </td>
                <td className="num">{s.n_movimientos}</td>
                <td className="num">{formatoDinero(s.suma_debito)}</td>
                <td className="num">{formatoDinero(s.suma_credito)}</td>
                <td className="num">{formatoDinero(s.neto)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th>
                Total ({filas.length} cuentas{consulta.trim() ? ', filtradas' : ''})
              </th>
              <th className="num">{filas.reduce((a, s) => a + s.n_movimientos, 0)}</th>
              <th className="num">{sumar(filas.map((s) => s.suma_debito))}</th>
              <th className="num">{sumar(filas.map((s) => s.suma_credito))}</th>
              <th className="num">{sumar(filas.map((s) => s.neto))}</th>
            </tr>
          </tfoot>
        </table>
      </div>
    </>
  )
}
