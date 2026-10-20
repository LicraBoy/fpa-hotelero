import { useEffect, useState } from 'react'
import { ErrorApi, obtenerTipado } from '../../api/cliente'
import type { MovimientoDetalle, PaginaMovimientos } from '../../api/tipos'
import { ContextoDrilldown } from '../../componentes/ContextoDrilldown'
import { EncabezadoPagina } from '../../componentes/EncabezadoPagina'
import { Cargando, EstadoVacio, Insignia, MensajeError } from '../../componentes/Insignia'
import { construirRuta, type Bloque } from '../../ruta/ruta'
import { aCentavos, aTextoPlano, sumarCentavos } from '../../util/dinero'
import { formatoContable } from '../../util/formato'
import { Migas } from './Migas'
import { useNombreLinea } from './useNombreLinea'

interface Props {
  hotelId: number
  periodo: string
  codigo: string
  bloque: Bloque
  /** Línea del reporte desde la que se llegó (para las migas y «Volver»). */
  lineaId?: number
  /** Quien tiene el acceso limitado a sus secciones no puede abrir asientos (mezclan secciones). */
  puedeVerAsiento?: boolean
}

const POR_PAGINA = 50

/** Movimientos de una cuenta, de 50 en 50 con "Cargar más" (paginación por cursor). */
export function Movimientos({ hotelId, periodo, codigo, bloque, lineaId, puedeVerAsiento = true }: Props) {
  const nombreLinea = useNombreLinea(hotelId, periodo, lineaId, bloque)
  const rutaLinea =
    lineaId === undefined ? null : construirRuta({ tipo: 'desglose', periodo, lineaId, bloque })
  const [movimientos, setMovimientos] = useState<MovimientoDetalle[]>([])
  const [primera, setPrimera] = useState<PaginaMovimientos | null>(null)
  const [cursor, setCursor] = useState<string | null>(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState<string | null>(null)

  function pedir(cursorPagina: string | null, reiniciar: boolean) {
    setCargando(true)
    return obtenerTipado('/api/v1/hoteles/{hotel_id}/variance/cuentas/{cuenta_codigo}/movimientos', {
      path: { hotel_id: hotelId, cuenta_codigo: codigo },
      query: { periodo, bloque, limite: POR_PAGINA, cursor: cursorPagina ?? undefined },
    })
      .then((pagina) => {
        setError(null)
        if (reiniciar) setPrimera(pagina)
        setMovimientos((anteriores) =>
          reiniciar ? pagina.movimientos : [...anteriores, ...pagina.movimientos],
        )
        setCursor(pagina.siguiente_cursor)
      })
      .catch((e: unknown) => {
        setError(e instanceof ErrorApi ? e.detalle : 'No se pudieron cargar los movimientos')
      })
      .finally(() => setCargando(false))
  }

  useEffect(() => {
    setMovimientos([])
    setPrimera(null)
    setCursor(null)
    void pedir(null, true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hotelId, periodo, codigo, bloque])

  const resumen = primera?.resumen
  const sumaCentavos = sumarCentavos(movimientos.map((m) => m.neto))
  const sumaMostrada = aTextoPlano(sumaCentavos)
  const completo = cursor === null && !cargando && primera !== null
  const cuadra =
    completo && resumen !== undefined && sumaCentavos === aCentavos(resumen.neto)
  const faltan = resumen ? resumen.n_movimientos - movimientos.length : 0

  return (
    <section aria-labelledby="titulo-movimientos">
      <Migas
        periodo={periodo}
        bloque={bloque}
        actual={`Cuenta ${codigo}`}
        intermedios={rutaLinea ? [{ texto: nombreLinea ?? 'Línea', href: rutaLinea }] : []}
        paso="Paso 2 de 3 · Movimientos de la cuenta"
        volver={
          rutaLinea
            ? { texto: nombreLinea ?? 'la línea', href: rutaLinea }
            : { texto: `Variance ${periodo}`, href: construirRuta({ tipo: 'variance', periodo }) }
        }
      />
      <EncabezadoPagina
        id="titulo-movimientos"
        titulo={`Movimientos de ${codigo}${primera?.descripcion ? ` · ${primera.descripcion}` : ''}`}
        subtitulo={`${periodo} · ${bloque === 'mes' ? 'solo el mes' : 'acumulado del año fiscal'}`}
      />
      <ContextoDrilldown
        datos={[
          { etiqueta: 'Reporte', valor: 'Variance' },
          { etiqueta: 'Periodo', valor: periodo },
          { etiqueta: 'Bloque', valor: bloque === 'mes' ? 'Solo el mes' : 'Acumulado del año fiscal' },
          ...(nombreLinea ? [{ etiqueta: 'Línea', valor: nombreLinea }] : []),
          { etiqueta: 'Cuenta', valor: codigo },
        ]}
      />
      {error && <MensajeError texto={error} />}
      {primera === null && cargando && <Cargando />}
      {resumen && (
        <>
          <p className="cuadre" role="status" aria-label="Cuadre de la cuenta">
            <span>
              Mostrados <strong>{movimientos.length}</strong> de{' '}
              <strong>{resumen.n_movimientos}</strong>
            </span>{' '}
            <span>
              Suma mostrada: <strong>{formatoContable(sumaMostrada)}</strong>
            </span>{' '}
            <span>
              Neto de la cuenta: <strong>{formatoContable(resumen.neto)}</strong>
            </span>{' '}
            {completo ? (
              <Insignia tono={cuadra ? 'ok' : 'error'}>
                {cuadra ? 'Cuadra con el neto de la cuenta' : 'No cuadra'}
              </Insignia>
            ) : (
              <Insignia tono="aviso">Faltan {faltan} por cargar</Insignia>
            )}
          </p>
          {movimientos.length === 0 && !cargando ? (
            <EstadoVacio>La cuenta no tiene movimientos en este periodo.</EstadoVacio>
          ) : (
            <div
              className="tabla-variance-contenedor"
              role="region"
              aria-label="Movimientos"
              tabIndex={0}
            >
              <table className="tabla-simple">
                <thead>
                  <tr>
                    <th scope="col">Fecha</th>
                    <th scope="col">Asiento</th>
                    <th scope="col">Concepto</th>
                    <th scope="col" className="num">
                      Débito
                    </th>
                    <th scope="col" className="num">
                      Crédito
                    </th>
                    <th scope="col" className="num">
                      Neto
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {movimientos.map((m) => (
                    <tr key={m.id}>
                      <td>{m.fecha}</td>
                      <th scope="row">
                        {puedeVerAsiento ? (
                          <a
                            href={construirRuta({
                              tipo: 'asiento',
                              periodo: m.periodo,
                              asiento: m.asiento,
                              cuenta: codigo,
                              bloque,
                              ...(lineaId === undefined ? {} : { lineaId }),
                            })}
                          >
                            {m.asiento}
                          </a>
                        ) : (
                          m.asiento
                        )}
                      </th>
                      {/* El concepto lo escribe un tercero: se muestra como texto, nunca como HTML */}
                      <td>{m.concepto}</td>
                      <td className="num">{formatoContable(m.debito)}</td>
                      <td className="num">{formatoContable(m.credito)}</td>
                      <td className="num">{formatoContable(m.neto)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {cursor !== null && (
            <p>
              <button type="button" className="boton" disabled={cargando} onClick={() => void pedir(cursor, false)}>
                {cargando
                  ? 'Cargando…'
                  : `Cargar más (${Math.min(POR_PAGINA, faltan)} de ${faltan} restantes)`}
              </button>
            </p>
          )}
        </>
      )}
    </section>
  )
}
