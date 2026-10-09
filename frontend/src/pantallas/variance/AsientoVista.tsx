import { obtenerTipado } from '../../api/cliente'
import { useDatos } from '../../api/useDatos'
import { EncabezadoPagina } from '../../componentes/EncabezadoPagina'
import { Cargando, Insignia, MensajeError } from '../../componentes/Insignia'
import { construirRuta, type Bloque } from '../../ruta/ruta'
import { formatoContable } from '../../util/formato'
import { Migas } from './Migas'
import { useNombreLinea } from './useNombreLinea'

interface Props {
  hotelId: number
  periodo: string
  asiento: string
  /** De dónde se llegó (para las migas y «Volver»); sin ellos, el recorrido empieza aquí. */
  cuenta?: string
  lineaId?: number
  bloque?: Bloque
}

/** Todas las líneas de un asiento: el último paso del recorrido, hasta el documento contable. */
export function AsientoVista({ hotelId, periodo, asiento, cuenta, lineaId, bloque = 'mes' }: Props) {
  const nombreLinea = useNombreLinea(hotelId, periodo, lineaId, bloque)
  const rutaLinea =
    lineaId === undefined ? null : construirRuta({ tipo: 'desglose', periodo, lineaId, bloque })
  const rutaCuenta =
    cuenta === undefined
      ? null
      : construirRuta({
          tipo: 'cuenta',
          periodo,
          codigo: cuenta,
          bloque,
          ...(lineaId === undefined ? {} : { lineaId }),
        })
  const intermedios = [
    ...(rutaLinea ? [{ texto: nombreLinea ?? 'Línea', href: rutaLinea }] : []),
    ...(rutaCuenta ? [{ texto: `Cuenta ${cuenta}`, href: rutaCuenta }] : []),
  ]
  const datos = useDatos(
    () =>
      obtenerTipado('/api/v1/hoteles/{hotel_id}/asientos/{asiento}', {
        path: { hotel_id: hotelId, asiento },
        query: { periodo },
      }),
    [hotelId, periodo, asiento],
  )
  const a = datos.datos
  return (
    <section aria-labelledby="titulo-asiento">
      <Migas
        periodo={periodo}
        bloque={bloque}
        actual={`Asiento ${asiento}`}
        intermedios={intermedios}
        paso="Paso 3 de 3 · Líneas del asiento"
        volver={
          rutaCuenta
            ? { texto: `la cuenta ${cuenta}`, href: rutaCuenta }
            : { texto: `Variance ${periodo}`, href: construirRuta({ tipo: 'variance', periodo }) }
        }
      />
      <EncabezadoPagina
        id="titulo-asiento"
        titulo={`Asiento ${asiento}`}
        subtitulo={`${periodo} · todas las líneas del asiento`}
      />
      {datos.cargando && <Cargando />}
      {datos.error && <MensajeError texto={datos.error} />}
      {a && (
        <>
          <p className="cuadre" role="status" aria-label="Totales del asiento">
            <span>
              Débito: <strong>{formatoContable(a.debito)}</strong>
            </span>{' '}
            <span>
              Crédito: <strong>{formatoContable(a.credito)}</strong>
            </span>{' '}
            <Insignia tono={a.cuadra ? 'ok' : 'info'}>
              {a.cuadra ? 'Débito = Crédito' : 'Solo cuentas de resultados'}
            </Insignia>
            {a.truncado && <Insignia tono="aviso">Se muestran las primeras líneas</Insignia>}
          </p>
          <div className="tabla-marco">
          <table className="tabla-simple" aria-label="Líneas del asiento">
            <thead>
              <tr>
                <th scope="col">Fecha</th>
                <th scope="col">Cuenta</th>
                <th scope="col">Concepto</th>
                <th scope="col" className="num">
                  Débito
                </th>
                <th scope="col" className="num">
                  Crédito
                </th>
              </tr>
            </thead>
            <tbody>
              {a.movimientos.map((m) => (
                <tr key={m.id}>
                  <td>{m.fecha}</td>
                  <th scope="row">
                    <a
                      href={construirRuta({
                        tipo: 'cuenta',
                        periodo,
                        codigo: m.cuenta_codigo,
                        bloque,
                        ...(lineaId === undefined ? {} : { lineaId }),
                      })}
                    >
                      {m.cuenta_codigo}
                    </a>{' '}
                    <span className="suave">{m.cuenta_descripcion}</span>
                  </th>
                  <td>{m.concepto}</td>
                  <td className="num">{formatoContable(m.debito)}</td>
                  <td className="num">{formatoContable(m.credito)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
          {!a.cuadra && (
            <p className="suave nota-pie">
              El reporte trae solo las cuentas de resultados (ingresos, costos y gastos), por eso un
              asiento puede no cuadrar aquí: el resto de sus líneas está en cuentas de balance.
            </p>
          )}
        </>
      )}
    </section>
  )
}
