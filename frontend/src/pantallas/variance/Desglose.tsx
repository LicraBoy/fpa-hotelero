import { obtenerTipado } from '../../api/cliente'
import { useDatos } from '../../api/useDatos'
import { ContextoDrilldown } from '../../componentes/ContextoDrilldown'
import { EncabezadoPagina } from '../../componentes/EncabezadoPagina'
import { Icono } from '../../componentes/Iconos'
import { Cargando, Insignia, MensajeError } from '../../componentes/Insignia'
import { construirRuta, type Bloque } from '../../ruta/ruta'
import { porcentajeBarra } from '../../util/barras'
import { aCentavos, aTextoPlano, negar, sumarCentavos } from '../../util/dinero'
import { formatoContable } from '../../util/formato'
import { Migas } from './Migas'

interface Props {
  hotelId: number
  periodo: string
  lineaId: number
  bloque: Bloque
}

/** Qué hay detrás de una cifra: las cuentas de una línea o los componentes de un total. */
export function Desglose({ hotelId, periodo, lineaId, bloque }: Props) {
  const datos = useDatos(
    () =>
      obtenerTipado('/api/v1/hoteles/{hotel_id}/variance/lineas/{linea_id}/desglose', {
        path: { hotel_id: hotelId, linea_id: lineaId },
        query: { periodo, bloque },
      }),
    [hotelId, periodo, lineaId, bloque],
  )
  const d = datos.datos

  // La suma se vuelve a calcular aquí, con enteros exactos: no se confía solo en el `cuadra` del
  // servidor.
  const sumaCuentas = d ? sumarCentavos(d.cuentas.map((c) => c.aporte)) : 0n
  const sumaComponentes = d
    ? sumarCentavos(d.componentes.map((c) => (c.signo < 0 ? negar(c.importe) : c.importe)))
    : 0n
  const sumaCentavos = d && d.componentes.length > 0 ? sumaComponentes : sumaCuentas
  // Peso de cada cuenta en la línea: |aporte| ÷ Σ|aportes| (solo geometría de la barra, con enteros)
  const sumaAbsAportes = d
    ? d.cuentas.reduce((n, c) => {
        const a = aCentavos(c.aporte)
        return n + (a < 0n ? -a : a)
      }, 0n)
    : 0n
  const suma = aTextoPlano(sumaCentavos)
  const cuadra = d !== null && sumaCentavos === aCentavos(d.cifra)

  return (
    <section aria-labelledby="titulo-desglose">
      <Migas
        periodo={periodo}
        bloque={bloque}
        actual={d?.descripcion ?? 'Desglose'}
        paso={`Paso 1 de 3 · ${d && d.componentes.length > 0 ? 'Componentes del total' : 'Cuentas de la línea'}`}
        volver={{ texto: `Variance ${periodo}`, href: construirRuta({ tipo: 'variance', periodo }) }}
      />
      <EncabezadoPagina
        id="titulo-desglose"
        titulo={`Desglose: ${d?.descripcion ?? '…'}`}
        subtitulo={
          <>
            {d?.codigo_corporativo && <span className="codigo">{d.codigo_corporativo} · </span>}
            {periodo} · {bloque === 'mes' ? 'solo el mes' : 'acumulado del año fiscal'}
          </>
        }
      />
      <ContextoDrilldown
        datos={[
          { etiqueta: 'Reporte', valor: 'Variance' },
          { etiqueta: 'Periodo', valor: periodo },
          { etiqueta: 'Bloque', valor: bloque === 'mes' ? 'Solo el mes' : 'Acumulado del año fiscal' },
          { etiqueta: 'Nivel', valor: d && d.componentes.length > 0 ? 'Componentes del total' : 'Cuentas de la línea' },
        ]}
      />
      {datos.cargando && <Cargando />}
      {datos.error && <MensajeError texto={datos.error} />}
      {d && (
        <>
          <p className="cuadre" role="status">
            <span>
              Cifra del reporte: <strong>{formatoContable(d.cifra)}</strong>
            </span>{' '}
            <span>
              Suma de lo mostrado: <strong>{formatoContable(suma)}</strong>
            </span>{' '}
            <Insignia tono={cuadra ? 'ok' : 'error'}>{cuadra ? 'Cuadra' : 'No cuadra'}</Insignia>
          </p>

          {d.motivos_cero.length > 0 && (
            <div className="por-que-cero" role="note" aria-label="Por qué está en 0">
              <strong>
                <Icono nombre="alerta" tamano={16} /> Por qué el Actual está en 0
              </strong>
              <ul>
                {d.motivos_cero.map((m) => (
                  <li key={m.codigo}>{m.texto}</li>
                ))}
              </ul>
            </div>
          )}

          {d.componentes.length > 0 ? (
            <div className="tabla-marco">
            <table className="tabla-simple" aria-label="Componentes del total">
              <thead>
                <tr>
                  <th scope="col">Línea</th>
                  <th scope="col">Tipo</th>
                  <th scope="col" className="num">
                    Signo
                  </th>
                  <th scope="col" className="num">
                    Importe
                  </th>
                </tr>
              </thead>
              <tbody>
                {d.componentes.map((c) => (
                  <tr key={c.linea_id}>
                    <th scope="row">
                      <a href={construirRuta({ tipo: 'desglose', periodo, lineaId: c.linea_id, bloque })}>
                        {c.descripcion}
                      </a>
                    </th>
                    <td>{c.tipo}</td>
                    <td className="num">{c.signo > 0 ? '+' : '−'}</td>
                    <td className="num">{formatoContable(c.importe)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          ) : d.cuentas.length > 0 ? (
            <div className="tabla-marco">
            <table className="tabla-simple" aria-label="Cuentas de la línea">
              <thead>
                <tr>
                  <th scope="col">Cuenta</th>
                  <th scope="col">Nombre</th>
                  <th scope="col" className="num">
                    Signo
                  </th>
                  <th scope="col" className="num">
                    Neto (Débito − Crédito)
                  </th>
                  <th scope="col" className="num">
                    Aporte a la línea
                  </th>
                  <th scope="col">Peso en la línea</th>
                  <th scope="col" className="num">
                    Movimientos
                  </th>
                  <th scope="col">Estado</th>
                </tr>
              </thead>
              <tbody>
                {d.cuentas.map((c) => (
                  <tr key={c.cuenta_codigo}>
                    <th scope="row">
                      <a
                        href={construirRuta({
                          tipo: 'cuenta',
                          periodo,
                          codigo: c.cuenta_codigo,
                          bloque,
                          lineaId,
                        })}
                      >
                        {c.cuenta_codigo}
                      </a>
                    </th>
                    <td>{c.descripcion ?? <span className="suave">sin nombre en el catálogo</span>}</td>
                    <td className="num">{c.signo > 0 ? '+' : '−'}</td>
                    <td className="num">{formatoContable(c.neto)}</td>
                    <td className="num">{formatoContable(c.aporte)}</td>
                    <td>
                      <PesoCuenta aporte={c.aporte} total={sumaAbsAportes} />
                    </td>
                    <td className="num">{c.n_movimientos}</td>
                    <td>
                      {c.estado === 'sin_movimientos' && (
                        <Insignia tono="aviso">Sin movimientos en el periodo</Insignia>
                      )}
                      {c.estado === 'no_en_catalogo' && (
                        <Insignia tono="aviso">No está en el catálogo</Insignia>
                      )}
                      {c.nota && <Insignia tono="neutro">{c.nota}</Insignia>}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <th scope="row" colSpan={4}>
                    Suma
                  </th>
                  <td className="num">{formatoContable(aTextoPlano(sumaCuentas))}</td>
                  <td colSpan={3} />
                </tr>
              </tfoot>
            </table>
            </div>
          ) : (
            <p className="suave">
              Esta línea no tiene cuentas vinculadas ni se calcula como un total.
            </p>
          )}
          <p className="suave nota-pie">
            El signo indica cómo entra la cuenta a la línea: las cuentas de ingreso (Acreedoras)
            restan su neto y las de gasto (Deudoras) lo suman.
          </p>
        </>
      )}
    </section>
  )
}

/** Barra con el peso de una cuenta en su línea (|aporte| ÷ Σ|aportes|). */
function PesoCuenta({ aporte, total }: { aporte: string; total: bigint }) {
  const ancho = porcentajeBarra(aporte, total)
  return (
    <span className="peso-cuenta">
      <svg className="barra-valor" viewBox="0 0 100 8" preserveAspectRatio="none" aria-hidden="true">
        <rect className="barra-fondo" x="0" y="0" width="100" height="8" rx="2" />
        {ancho > 0 && <rect className="barra-actual" x="0" y="0" width={ancho} height="8" rx="2" />}
      </svg>
      <span className="peso-texto">{ancho.toFixed(1)}%</span>
    </span>
  )
}
