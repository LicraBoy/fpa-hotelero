import { Fragment, useMemo, useState } from 'react'
import { obtenerTipado } from '../../api/cliente'
import { useDatos } from '../../api/useDatos'
import { EncabezadoPagina } from '../../componentes/EncabezadoPagina'
import { Cargando, EstadoVacio, MensajeError } from '../../componentes/Insignia'
import { TarjetaKpi } from '../../componentes/TarjetaKpi'
import { construirRuta } from '../../ruta/ruta'
import { esDesfavorable, esFavorable, formatoContable } from '../../util/formato'

interface Props {
  hotelId: number
  puedeVerCargas: boolean
  puedeDesglosar: boolean
}

type Bloque = 'mes' | 'ytd'

const ETIQUETA_TIPO: Record<string, string> = {
  ingreso: 'Ingreso',
  nomina: 'Nómina',
  operacion: 'Operación',
  costo: 'Costo',
  otros: 'Otros',
  sin_tipo: 'Sin tipo',
}

/** Importes del Variance agrupados por el departamento de cada cuenta (catálogo oficial de Novohit). */
export function PanelDepartamentos({ hotelId, puedeVerCargas, puedeDesglosar }: Props) {
  const cargas = useDatos(
    () =>
      puedeVerCargas
        ? obtenerTipado('/api/v1/hoteles/{hotel_id}/cargas', { path: { hotel_id: hotelId } })
        : Promise.resolve([]),
    [hotelId, puedeVerCargas],
  )
  const periodos = useMemo(
    () =>
      [...new Set((cargas.datos ?? []).filter((c) => c.estado === 'vigente').map((c) => c.periodo))]
        .sort()
        .reverse(),
    [cargas.datos],
  )
  const [elegido, setElegido] = useState('')
  const periodo = periodos.includes(elegido) ? elegido : (periodos[0] ?? '')
  const [bloque, setBloque] = useState<Bloque>('mes')

  return (
    <section aria-labelledby="titulo-departamentos">
      <EncabezadoPagina
        id="titulo-departamentos"
        titulo="Por departamento"
        subtitulo="Importes del Variance agrupados por el departamento que el catálogo de Novohit asigna a cada cuenta."
      />
      {cargas.cargando && <Cargando />}
      {cargas.error && <MensajeError texto={cargas.error} />}
      {!cargas.cargando && periodos.length === 0 && <EstadoVacio>Aún no hay meses cargados.</EstadoVacio>}
      {periodos.length > 0 && (
        <>
          <div className="filtros">
            <label className="chip-filtro">
              Mes
              <select value={periodo} onChange={(e) => setElegido(e.target.value)}>
                {periodos.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </label>
            <div className="selector-bloque" role="group" aria-label="Importe a mostrar">
              {(['mes', 'ytd'] as const).map((b) => (
                <button
                  key={b}
                  type="button"
                  className={b === bloque ? 'chip chip-activo' : 'chip'}
                  aria-pressed={b === bloque}
                  onClick={() => setBloque(b)}
                >
                  {b === 'mes' ? 'Mes' : 'Acumulado'}
                </button>
              ))}
            </div>
          </div>
          {periodo && (
            <Tabla hotelId={hotelId} periodo={periodo} bloque={bloque} puedeDesglosar={puedeDesglosar} />
          )}
        </>
      )}
    </section>
  )
}

function Tabla({
  hotelId,
  periodo,
  bloque,
  puedeDesglosar,
}: {
  hotelId: number
  periodo: string
  bloque: Bloque
  puedeDesglosar: boolean
}) {
  const datos = useDatos(
    () =>
      obtenerTipado('/api/v1/hoteles/{hotel_id}/variance/departamentos', {
        path: { hotel_id: hotelId },
        query: { periodo },
      }),
    [hotelId, periodo],
  )
  const [abiertos, setAbiertos] = useState<ReadonlySet<string>>(new Set())

  if (datos.cargando) return <Cargando />
  if (datos.error) return <MensajeError texto={datos.error} />
  const d = datos.datos
  if (!d) return null

  const clave = (x: string | null) => x ?? '__sin__'
  const alternar = (x: string | null) =>
    setAbiertos((previos) => {
      const nuevo = new Set(previos)
      if (!nuevo.delete(clave(x))) nuevo.add(clave(x))
      return nuevo
    })
  // Solo se muestran los tipos que algún departamento usa
  const tipos = d.tipos.filter((t) => d.total.por_tipo[t] !== undefined)
  const nombre = (x: string | null) => x ?? 'Sin departamento'
  const conDepto = d.departamentos.filter((x) => x.departamento !== null).length

  return (
    <>
      <section className="kpis" aria-label="Resumen por departamento">
        <TarjetaKpi titulo="Departamentos" valor={conDepto} detalle={`con cuentas vinculadas en ${periodo}`} icono="catalogo" />
        <TarjetaKpi
          titulo="Cuentas sin departamento"
          valor={d.cuentas_sin_departamento}
          detalle={`de ${d.cuentas_vinculadas} cuentas vinculadas`}
          tono={d.cuentas_sin_departamento > 0 ? 'desfavorable' : 'neutro'}
          icono="alerta"
        />
        <TarjetaKpi
          titulo="Cuentas sin tipo"
          valor={d.cuentas_sin_tipo}
          detalle="sin ingreso, nómina, operación ni costo"
          tono={d.cuentas_sin_tipo > 0 ? 'desfavorable' : 'neutro'}
          icono="alerta"
        />
      </section>

      {d.periodos_sin_datos.length > 0 && (
        <p className="mensaje mensaje-aviso" role="status">
          Sin carga en {d.periodos_sin_datos.join(', ')}: el acumulado está incompleto.
        </p>
      )}

      <div className="tabla-variance-contenedor" role="region" aria-label="Tabla de departamentos" tabIndex={0}>
        <table className="tabla-variance tabla-departamentos">
          <caption className="solo-lectores">
            Importes por departamento, {bloque === 'mes' ? 'del mes' : 'acumulado del año fiscal'}
          </caption>
          <thead>
            <tr>
              <th scope="col" className="col-linea">
                Departamento
              </th>
              {tipos.map((t) => (
                <th key={t} scope="col" className="num">
                  {ETIQUETA_TIPO[t] ?? t}
                </th>
              ))}
              <th scope="col" className="num inicio-resumen">
                Gasto
              </th>
              <th scope="col" className="num">
                Resultado
              </th>
            </tr>
          </thead>
          <tbody>
            {d.departamentos.map((f) => {
              const abierto = abiertos.has(clave(f.departamento))
              const desfavorable = esDesfavorable(f.resultado[bloque])
              const sentido = desfavorable ? 'desfavorable' : esFavorable(f.resultado[bloque]) ? 'favorable' : ''
              return (
                <Fragment key={clave(f.departamento)}>
                  <tr className={f.departamento === null ? 'fila-sin-departamento' : 'fila-departamento'}>
                    <th scope="row" className="col-linea">
                      <button
                        type="button"
                        className="boton-pliegue"
                        aria-expanded={abierto}
                        disabled={!d.detalle_de_cuentas}
                        onClick={() => alternar(f.departamento)}
                      >
                        <span aria-hidden="true">{abierto ? '▾' : '▸'}</span> {nombre(f.departamento)}
                      </button>
                      <span className="suave"> · {f.n_cuentas === 1 ? '1 cuenta' : `${f.n_cuentas} cuentas`}</span>
                    </th>
                    {tipos.map((t) => (
                      <td key={t} className="num">
                        {formatoContable(f.por_tipo[t]?.[bloque])}
                      </td>
                    ))}
                    <td className="num inicio-resumen">{formatoContable(f.gasto[bloque])}</td>
                    <td className={`num ${sentido}`.trim()}>
                      {desfavorable && (
                        <>
                          <span aria-hidden="true">▼ </span>
                          <span className="solo-lectores">Desfavorable: </span>
                        </>
                      )}
                      <strong>{formatoContable(f.resultado[bloque])}</strong>
                    </td>
                  </tr>
                  {abierto &&
                    f.cuentas.map((c) => (
                      <tr key={c.codigo} className="fila-cuenta">
                        <td className="col-linea fila-cuenta-nombre">
                          {puedeDesglosar ? (
                            <a href={construirRuta({ tipo: 'cuenta', periodo, codigo: c.codigo, bloque })}>
                              <code>{c.codigo}</code>
                            </a>
                          ) : (
                            <code>{c.codigo}</code>
                          )}{' '}
                          {c.descripcion ?? ''}
                        </td>
                        <td colSpan={tipos.length} className="suave">
                          {ETIQUETA_TIPO[c.tipo] ?? c.tipo}
                          {c.n_lineas > 1 ? ` · en ${c.n_lineas} líneas` : ''}
                        </td>
                        <td className="num inicio-resumen" colSpan={2}>
                          {formatoContable(bloque === 'mes' ? c.mes : c.ytd)}
                        </td>
                      </tr>
                    ))}
                </Fragment>
              )
            })}
          </tbody>
          <tfoot>
            <tr className="fila-total">
              <th scope="row" className="col-linea">
                Total ({d.cuentas_vinculadas} cuentas vinculadas)
              </th>
              {tipos.map((t) => (
                <td key={t} className="num">
                  {formatoContable(d.total.por_tipo[t]?.[bloque])}
                </td>
              ))}
              <td className="num inicio-resumen">{formatoContable(d.total.gasto[bloque])}</td>
              <td className="num">{formatoContable(d.total.resultado[bloque])}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      <p className="suave nota-pie">
        Resultado = ingreso − gasto. Solo se agrupan las cuentas vinculadas en el mapeo {d.version_mapeo_id}. El
        departamento y el tipo vienen del catálogo oficial de Novohit: lo que no lo trae aparece como «Sin
        departamento» o «Sin tipo». El Budget y la variación no se calculan por departamento (el Budget es
        por línea del reporte).
      </p>
    </>
  )
}
