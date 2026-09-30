import { useState } from 'react'
import { obtener } from '../api/cliente'
import type { Carga, CargaDetalle } from '../api/tipos'
import { useDatos } from '../api/useDatos'
import { formatoDinero } from '../util/dinero'
import { Cargando, Insignia, MensajeError } from './Insignia'
import { ReporteCalidadVista } from './ReporteCalidadVista'
import { SubirArchivo } from './SubirArchivo'

const NOMBRE_FUENTE: Record<string, string> = {
  con130: 'CON130',
  variance_base_datos: 'Variance',
}

interface Props {
  hotelId: number
  puedeCargar: boolean
  version: number
  alCambiar: () => void
}

export function PanelCargas({ hotelId, puedeCargar, version, alCambiar }: Props) {
  const [seleccionada, setSeleccionada] = useState<number | null>(null)
  const cargas = useDatos(
    () => obtener<Carga[]>(`/hoteles/${hotelId}/cargas`),
    [hotelId, version],
  )

  return (
    <>
      {puedeCargar && <SubirArchivo hotelId={hotelId} alCambiar={alCambiar} />}
      <section className="tarjeta" aria-labelledby="titulo-cargas">
        <h2 id="titulo-cargas">Cargas</h2>
        {cargas.cargando && <Cargando />}
        {cargas.error && <MensajeError texto={cargas.error} />}
        {cargas.datos && cargas.datos.length === 0 && (
          <p className="suave">Todavía no hay cargas en este hotel.</p>
        )}
        {cargas.datos && cargas.datos.length > 0 && (
          <div className="tabla-contenedor">
            <table className="tabla">
              <thead>
                <tr>
                  <th>Mes</th>
                  <th>Estado</th>
                  <th>Tipo</th>
                  <th>Archivo</th>
                  <th className="num">Movimientos</th>
                  <th className="num">Débito</th>
                  <th className="num">Crédito</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {cargas.datos.map((c) => (
                  <tr key={c.id} className={c.estado === 'reemplazada' ? 'fila-apagada' : undefined}>
                    <td>{c.periodo}</td>
                    <td>
                      <Insignia tono={c.estado === 'vigente' ? 'ok' : 'neutro'}>{c.estado}</Insignia>
                    </td>
                    <td>{NOMBRE_FUENTE[c.fuente] ?? c.fuente}</td>
                    <td>{c.nombre_archivo}</td>
                    <td className="num">{c.n_movimientos}</td>
                    <td className="num">{formatoDinero(c.total_debito)}</td>
                    <td className="num">{formatoDinero(c.total_credito)}</td>
                    <td>
                      <button
                        type="button"
                        className="boton boton-secundario"
                        onClick={() => setSeleccionada(seleccionada === c.id ? null : c.id)}
                        aria-expanded={seleccionada === c.id}
                      >
                        {seleccionada === c.id ? 'Ocultar calidad' : 'Ver calidad'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {seleccionada !== null && <DetalleCarga hotelId={hotelId} cargaId={seleccionada} />}
      </section>
    </>
  )
}

function DetalleCarga({ hotelId, cargaId }: { hotelId: number; cargaId: number }) {
  const detalle = useDatos(
    () => obtener<CargaDetalle>(`/hoteles/${hotelId}/cargas/${cargaId}`),
    [hotelId, cargaId],
  )
  if (detalle.cargando) return <Cargando />
  if (detalle.error) return <MensajeError texto={detalle.error} />
  const d = detalle.datos
  if (!d) return null
  return (
    <div className="detalle">
      <h3>
        Carga {d.periodo} · {d.nombre_archivo}
      </h3>
      <p className="suave">
        Del {d.fecha_min} al {d.fecha_max} · huella {d.sha256.slice(0, 12)}…
      </p>
      {d.controles ? (
        <ReporteCalidadVista reporte={d.controles} />
      ) : (
        <p className="suave">Esta carga no guardó reporte de calidad.</p>
      )}
    </div>
  )
}
