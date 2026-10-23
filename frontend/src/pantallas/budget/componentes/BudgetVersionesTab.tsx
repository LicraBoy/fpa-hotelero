import { useState } from 'react'
import { obtenerTipado } from '../../../api/cliente'
import type { components } from '../../../api/schema'
import { useDatos } from '../../../api/useDatos'
import { Cargando, EstadoVacio, Insignia, MensajeError } from '../../../componentes/Insignia'
import { aMicros, formatoMicros } from '../calculo'
import { BudgetComparacionVersiones } from './BudgetComparacionVersiones'

type VersionBudget = components['schemas']['VersionPlanSalida']

interface Props {
  hotelId: number
  versiones: VersionBudget[]
  /** linea_id -> descripción, de la vista de edición ya cargada (sin pedirlo de nuevo). */
  descripcionPorLinea: ReadonlyMap<number, string>
}

/**
 * Pestaña Versiones: historial y "Time Machine" de solo lectura (spec §7). Abrir una versión
 * antigua nunca la edita — solo consulta `GET /budget/versiones/{id}`; para usarla como base de un
 * Budget nuevo se sigue el flujo normal de Captura (guardar una versión nueva), no desde aquí.
 */
export function BudgetVersionesTab({ hotelId, versiones, descripcionPorLinea }: Props) {
  const [seleccionada, setSeleccionada] = useState<number | null>(null)
  const [vista, setVista] = useState<'detalle' | 'comparar'>('detalle')

  if (versiones.length === 0) {
    return <EstadoVacio>Todavía no hay versiones de Budget guardadas.</EstadoVacio>
  }
  const ordenadas = [...versiones].sort((a, b) => b.numero - a.numero)
  const vigente = ordenadas.find((v) => v.estado === 'vigente') ?? null

  return (
    <div className="budget-resumen">
      <div className="selector-bloque" role="group" aria-label="Vista de Versiones">
        <button
          type="button"
          className={vista === 'detalle' ? 'chip chip-activo' : 'chip'}
          aria-pressed={vista === 'detalle'}
          onClick={() => setVista('detalle')}
        >
          Ver detalle
        </button>
        <button
          type="button"
          className={vista === 'comparar' ? 'chip chip-activo' : 'chip'}
          aria-pressed={vista === 'comparar'}
          onClick={() => setVista('comparar')}
        >
          Comparar versiones
        </button>
      </div>

      {vista === 'comparar' ? (
        <BudgetComparacionVersiones hotelId={hotelId} versiones={ordenadas} descripcionPorLinea={descripcionPorLinea} />
      ) : (
        <>
      <div className="tabla-variance-contenedor" role="region" aria-label="Versiones de Budget" tabIndex={0}>
        <table className="tabla-simple">
          <caption className="solo-lectores">Historial de versiones de Budget, más reciente primero.</caption>
          <thead>
            <tr>
              <th scope="col">Versión</th>
              <th scope="col">Año fiscal</th>
              <th scope="col">Archivo</th>
              <th scope="col">Estado</th>
              <th scope="col">Periodo de corte</th>
              <th scope="col">
                <span className="solo-lectores">Acciones</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {ordenadas.map((v) => (
              <tr key={v.id} className={seleccionada === v.id ? 'fila-seleccionada' : ''}>
                <td>{v.numero}</td>
                <td>{v.ano_fiscal}</td>
                <td>{v.nombre_archivo}</td>
                <td>
                  <Insignia tono={v.estado === 'vigente' ? 'ok' : 'neutro'}>
                    {v.estado === 'vigente' ? 'Vigente' : 'Histórica'}
                  </Insignia>
                </td>
                <td>{v.periodo_corte}</td>
                <td>
                  <button
                    type="button"
                    className="boton boton-secundario"
                    onClick={() => setSeleccionada(seleccionada === v.id ? null : v.id)}
                  >
                    {seleccionada === v.id ? 'Ocultar' : 'Ver'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {seleccionada !== null && (
        <DetalleVersion
          hotelId={hotelId}
          versionId={seleccionada}
          esVigente={vigente?.id === seleccionada}
          descripcionPorLinea={descripcionPorLinea}
          onCerrar={() => setSeleccionada(null)}
        />
      )}
        </>
      )}
    </div>
  )
}

function DetalleVersion({
  hotelId,
  versionId,
  esVigente,
  descripcionPorLinea,
  onCerrar,
}: {
  hotelId: number
  versionId: number
  esVigente: boolean
  descripcionPorLinea: ReadonlyMap<number, string>
  onCerrar: () => void
}) {
  const detalle = useDatos(
    () =>
      obtenerTipado('/api/v1/hoteles/{hotel_id}/budget/versiones/{version_id}', {
        path: { hotel_id: hotelId, version_id: versionId },
      }),
    [hotelId, versionId],
  )

  return (
    <section className="tarjeta" aria-label={`Detalle de la versión ${versionId}`}>
      <div className="budget-chart-cabecera">
        <Insignia tono={esVigente ? 'ok' : 'aviso'}>
          {esVigente ? 'Versión vigente' : 'MODO HISTÓRICO · SOLO LECTURA'}
        </Insignia>
        <button type="button" className="boton boton-secundario" onClick={onCerrar}>
          Cerrar
        </button>
      </div>
      {detalle.cargando && <Cargando />}
      {detalle.error && <MensajeError texto={detalle.error} />}
      {detalle.datos && (
        <div className="tabla-variance-contenedor" role="region" aria-label="Líneas de la versión" tabIndex={0}>
          <table className="tabla-simple">
            <caption className="solo-lectores">
              Importes de mes, acumulado y anual de cada línea en esta versión. Solo lectura.
            </caption>
            <thead>
              <tr>
                <th scope="col">Línea</th>
                <th scope="col">Mes</th>
                <th scope="col">Acumulado</th>
                <th scope="col">Anual</th>
              </tr>
            </thead>
            <tbody>
              {detalle.datos.lineas.map((l) => (
                <tr key={l.linea_id}>
                  <td>{descripcionPorLinea.get(l.linea_id) ?? `Línea #${l.linea_id}`}</td>
                  <td className="num">{formatoMicros(l.mes === null ? null : aMicros(l.mes))}</td>
                  <td className="num">{formatoMicros(l.ytd === null ? null : aMicros(l.ytd))}</td>
                  <td className="num">{formatoMicros(l.anual === null ? null : aMicros(l.anual))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
