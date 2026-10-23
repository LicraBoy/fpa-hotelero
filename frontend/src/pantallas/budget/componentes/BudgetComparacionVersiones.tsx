import { useState } from 'react'
import { obtenerTipado } from '../../../api/cliente'
import type { components } from '../../../api/schema'
import { useDatos } from '../../../api/useDatos'
import { Cargando, EstadoVacio, MensajeError } from '../../../componentes/Insignia'
import { compararVersiones, formatoMicros } from '../calculo'

type VersionBudget = components['schemas']['VersionPlanSalida']

interface Props {
  hotelId: number
  versiones: readonly VersionBudget[]
  descripcionPorLinea: ReadonlyMap<number, string>
}

/**
 * Compara el anual de cada línea entre dos versiones de Budget (spec §7). No necesita un endpoint
 * nuevo: `GET /budget/versiones/{id}` ya trae las líneas completas de cualquier versión, así que la
 * comparación se arma en el cliente con `compararVersiones` (pura, con pruebas).
 */
export function BudgetComparacionVersiones({ hotelId, versiones, descripcionPorLinea }: Props) {
  const ordenadas = [...versiones].sort((a, b) => b.numero - a.numero)
  const [idA, setIdA] = useState(ordenadas[1]?.id ?? ordenadas[0]?.id ?? null)
  const [idB, setIdB] = useState(ordenadas[0]?.id ?? null)
  const [soloDiferencias, setSoloDiferencias] = useState(true)

  const detalleA = useDatos(
    () =>
      idA === null
        ? Promise.resolve(null)
        : obtenerTipado('/api/v1/hoteles/{hotel_id}/budget/versiones/{version_id}', {
            path: { hotel_id: hotelId, version_id: idA },
          }),
    [hotelId, idA],
  )
  const detalleB = useDatos(
    () =>
      idB === null
        ? Promise.resolve(null)
        : obtenerTipado('/api/v1/hoteles/{hotel_id}/budget/versiones/{version_id}', {
            path: { hotel_id: hotelId, version_id: idB },
          }),
    [hotelId, idB],
  )

  if (ordenadas.length < 2) {
    return <EstadoVacio>Hace falta al menos dos versiones guardadas para comparar.</EstadoVacio>
  }

  const diferencias =
    detalleA.datos && detalleB.datos ? compararVersiones(detalleA.datos.lineas, detalleB.datos.lineas) : null
  const filas = diferencias
    ? soloDiferencias
      ? diferencias.filter((d) => d.diferenciaMicros === null || d.diferenciaMicros !== 0n)
      : diferencias
    : null

  return (
    <div className="budget-resumen">
      <form className="barra-filtros" role="search" onSubmit={(e) => e.preventDefault()}>
        <div className="filtro-campo">
          <span className="filtro-etiqueta">Versión base</span>
          <select aria-label="Versión base" value={idA ?? ''} onChange={(e) => setIdA(Number(e.target.value))}>
            {ordenadas.map((v) => (
              <option key={v.id} value={v.id}>
                v{v.numero} · {v.nombre_archivo}
              </option>
            ))}
          </select>
        </div>
        <div className="filtro-campo">
          <span className="filtro-etiqueta">Comparar con</span>
          <select aria-label="Comparar con" value={idB ?? ''} onChange={(e) => setIdB(Number(e.target.value))}>
            {ordenadas.map((v) => (
              <option key={v.id} value={v.id}>
                v{v.numero} · {v.nombre_archivo}
              </option>
            ))}
          </select>
        </div>
        <label className="interruptor">
          <input
            type="checkbox"
            checked={soloDiferencias}
            onChange={(e) => setSoloDiferencias(e.target.checked)}
          />
          <span className="interruptor-pista" aria-hidden="true" />
          Solo líneas con diferencia
        </label>
      </form>

      {(detalleA.cargando || detalleB.cargando) && <Cargando />}
      {(detalleA.error || detalleB.error) && <MensajeError texto={detalleA.error ?? detalleB.error ?? ''} />}

      {filas && (
        <div className="tabla-variance-contenedor" role="region" aria-label="Comparación de versiones" tabIndex={0}>
          <table className="tabla-simple">
            <caption className="solo-lectores">Diferencia de anual entre las dos versiones elegidas.</caption>
            <thead>
              <tr>
                <th scope="col">Línea</th>
                <th scope="col">Versión base</th>
                <th scope="col">Comparar con</th>
                <th scope="col">Diferencia</th>
              </tr>
            </thead>
            <tbody>
              {filas.map((d) => (
                <tr key={d.linea_id}>
                  <td>{descripcionPorLinea.get(d.linea_id) ?? `Línea #${d.linea_id}`}</td>
                  <td className="num">{formatoMicros(d.anualA)}</td>
                  <td className="num">{formatoMicros(d.anualB)}</td>
                  <td className="num">{formatoMicros(d.diferenciaMicros)}</td>
                </tr>
              ))}
              {filas.length === 0 && (
                <tr>
                  <td colSpan={4}>No hay diferencias entre estas dos versiones.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
