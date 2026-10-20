import type { MouseEvent } from 'react'
import type { CifrasVariance, LineaVariance } from '../../api/tipos'
import { Icono } from '../../componentes/Iconos'
import { construirRuta, type Bloque } from '../../ruta/ruta'
import { esDesfavorable, esFavorable, formatoContable, formatoPorcentaje } from '../../util/formato'
import { etiquetaMesLargo, etiquetaRangoMeses } from '../../util/periodos'
import { resumirVariance } from '../../util/resumenVariance'
import { anclaDeSeccion, trozosResaltados, type GrupoSeccion } from './agrupar'

interface Props {
  grupos: GrupoSeccion[]
  periodo: string
  /** Meses del acumulado y año fiscal: dan contexto a los encabezados de grupo. */
  periodosYtd: string[]
  anoFiscal: string
  /** Si el rol puede abrir el desglose, las cifras de Actual son enlaces. */
  puedeDesglosar: boolean
  plegadas: ReadonlySet<number | null>
  alAlternar: (seccionId: number | null) => void
  /** Texto buscado: se resalta en la descripción de cada línea y no se pliegan las secciones. */
  busqueda?: string
  /** Línea desde la que se volvió del desglose: se resalta y se deja a la vista. */
  lineaDestacada?: number | null
  /** Línea abierta en el panel lateral. */
  lineaSeleccionada?: number | null
  alSeleccionar?: (lineaId: number) => void
  compacta?: boolean
  /** Hilos de comentarios por línea (suma de mes y acumulado) para el indicador de la fila. */
  comentarios?: Record<number, { total: number; pendientes: number }>
}

type ClaveBloque = 'mes' | 'ytd' | 'anual'

const SUBTITULOS = ['Actual', 'Presupuesto', 'Variación', '% var.'] as const
const COLUMNAS = 1 + 3 * SUBTITULOS.length

/** Clases de una celda: el color de su bloque y, la primera de cada bloque, su borde izquierdo. */
const celda = (bloque: ClaveBloque, i: number, extra = '') =>
  `num bloque-${bloque}${i === 0 ? ' inicio-bloque' : ''}${extra ? ` ${extra}` : ''}`

function CeldaImporte({ valor, bloque }: { valor: string | null; bloque: ClaveBloque }) {
  return <td className={celda(bloque, 1)}>{formatoContable(valor)}</td>
}

function CeldasBloque({
  bloque,
  cifras,
  calculada,
  enlace,
  etiquetaEnlace,
}: {
  bloque: ClaveBloque
  cifras: CifrasVariance
  /** Falso en las líneas informativas (p. ej. el tipo de cambio): el motor no calcula su Actual. */
  calculada: boolean
  enlace: string | null
  etiquetaEnlace: string
}) {
  if (!calculada) {
    return (
      <>
        <td className={celda(bloque, 0, 'suave')} title="El motor no calcula esta línea">
          —
        </td>
        <CeldaImporte valor={cifras.budget} bloque={bloque} />
        <td className={celda(bloque, 2, 'suave')}>—</td>
        <td className={celda(bloque, 3, 'suave')}>—</td>
      </>
    )
  }
  const desfavorable = esDesfavorable(cifras.var)
  // El sentido (favorable / desfavorable) ya lo define la regla del reporte: aquí solo se pinta
  const sentido = desfavorable ? 'desfavorable' : esFavorable(cifras.var) ? 'favorable' : ''
  return (
    <>
      <td className={celda(bloque, 0)}>
        {enlace ? (
          <a href={enlace} aria-label={etiquetaEnlace}>
            {formatoContable(cifras.actual)}
          </a>
        ) : (
          formatoContable(cifras.actual)
        )}
      </td>
      <CeldaImporte valor={cifras.budget} bloque={bloque} />
      <td className={celda(bloque, 2, sentido)}>
        {desfavorable && (
          <>
            <span aria-hidden="true">▼ </span>
            <span className="solo-lectores">Desfavorable: </span>
          </>
        )}
        {formatoContable(cifras.var)}
      </td>
      <td className={celda(bloque, 3, `col-pct ${sentido}`.trim())}>
        <span className="var-pill">{formatoPorcentaje(cifras.pct)}</span>
      </td>
    </>
  )
}

/** La descripción con lo buscado resaltado. Pinta texto, nunca HTML. */
function Resaltado({ texto, busqueda }: { texto: string; busqueda: string }) {
  return (
    <>
      {trozosResaltados(texto, busqueda).map((t, i) =>
        t.coincide ? (
          <mark key={i} className="coincidencia">
            {t.texto}
          </mark>
        ) : (
          <span key={i}>{t.texto}</span>
        ),
      )}
    </>
  )
}

function FilaLinea({
  linea,
  periodo,
  puedeDesglosar,
  busqueda,
  destacada,
  seleccionada,
  alSeleccionar,
  comentarios,
}: {
  linea: LineaVariance
  periodo: string
  puedeDesglosar: boolean
  busqueda: string
  destacada: boolean
  seleccionada: boolean
  alSeleccionar?: (lineaId: number) => void
  comentarios?: { total: number; pendientes: number }
}) {
  const calculada = linea.tipo !== 'informativa'
  const enlace = (bloque: Bloque) =>
    puedeDesglosar && calculada
      ? construirRuta({ tipo: 'desglose', periodo, lineaId: linea.linea_id, bloque })
      : null
  // Pulsar la fila abre el panel, salvo que se pulse un enlace o un botón de la propia fila
  const alPulsar = (e: MouseEvent<HTMLTableRowElement>) => {
    if ((e.target as HTMLElement).closest('a, button')) return
    alSeleccionar?.(linea.linea_id)
  }
  const clases = [
    `fila-${linea.tipo}`,
    destacada ? 'fila-origen' : '',
    seleccionada ? 'fila-seleccionada' : '',
    alSeleccionar ? 'fila-pulsable' : '',
  ]
    .filter(Boolean)
    .join(' ')
  return (
    // La fila entera es pulsable con el ratón; el teclado usa el botón de detalle de la propia fila
    <tr id={`linea-${linea.linea_id}`} className={clases} onClick={alPulsar}>
      <th scope="row" className="col-linea" title={linea.descripcion}>
        <span className="linea-contenido">
          <span className="descripcion" id={`linea-${linea.linea_id}-nombre`}>
            <Resaltado texto={linea.descripcion} busqueda={busqueda} />
          </span>
          {linea.codigo_corporativo && <span className="codigo">{linea.codigo_corporativo}</span>}
          {comentarios && comentarios.total > 0 && (
            <span
              className={comentarios.pendientes > 0 ? 'marca-comentarios pendientes' : 'marca-comentarios'}
              role="img"
              aria-label={`${comentarios.total} comentarios, ${comentarios.pendientes} pendientes`}
              title={`${comentarios.total} comentarios, ${comentarios.pendientes} pendientes`}
            >
              <Icono nombre="comentario" tamano={13} />
              {comentarios.total}
            </span>
          )}
          {alSeleccionar && (
            <button
              type="button"
              className="boton-detalle"
              aria-label="Ver detalle de la línea"
              aria-describedby={`linea-${linea.linea_id}-nombre`}
              aria-pressed={seleccionada}
              onClick={() => alSeleccionar(linea.linea_id)}
            >
              <Icono nombre="info" tamano={15} />
            </button>
          )}
        </span>
      </th>
      <CeldasBloque
        bloque="mes"
        // el tipo de cambio trae su Actual del mes capturado (no calculado): se muestra, sin desglose
        calculada={calculada || linea.capturada}
        cifras={linea.mes}
        enlace={enlace('mes')}
        etiquetaEnlace={`Ver el desglose de ${linea.descripcion}, mes`}
      />
      <CeldasBloque
        bloque="ytd"
        // el acumulado del tipo de cambio es el promedio de los meses capturados: se muestra si hay
        calculada={calculada || linea.ytd.var !== null}
        cifras={linea.ytd}
        enlace={enlace('ytd')}
        etiquetaEnlace={`Ver el desglose de ${linea.descripcion}, acumulado`}
      />
      <CeldasBloque
        bloque="anual"
        calculada={calculada || linea.anual.var !== null}
        cifras={linea.anual}
        // el Actual del bloque anual es el mismo acumulado: su desglose está en el bloque YTD
        enlace={null}
        etiquetaEnlace=""
      />
    </tr>
  )
}

/** Tabla del reporte: descripción fija a la izquierda, encabezados fijos, secciones plegables. */
export function TablaVariance({
  grupos,
  periodo,
  periodosYtd,
  anoFiscal,
  puedeDesglosar,
  plegadas,
  alAlternar,
  busqueda = '',
  lineaDestacada = null,
  lineaSeleccionada = null,
  alSeleccionar,
  compacta = false,
  comentarios,
}: Props) {
  const buscando = busqueda.trim() !== ''
  const grupos3: { clave: ClaveBloque; titulo: string; contexto: string }[] = [
    { clave: 'mes', titulo: 'Mes', contexto: etiquetaMesLargo(periodo) },
    {
      clave: 'ytd',
      titulo: 'Acumulado del año fiscal',
      contexto: `${etiquetaRangoMeses(periodosYtd)} · ${anoFiscal}`,
    },
    { clave: 'anual', titulo: 'Presupuesto anual', contexto: anoFiscal },
  ]
  return (
    <div
      className={compacta ? 'tabla-variance-contenedor densidad-compacta' : 'tabla-variance-contenedor'}
      role="region"
      aria-label="Tabla de Variance"
      tabIndex={0}
    >
      <table className="tabla-variance">
        <caption className="solo-lectores">
          Variance de {periodo}: Actual, Presupuesto, Variación y porcentaje, por mes, acumulado y
          presupuesto anual. Una variación desfavorable lleva el símbolo ▼ y una favorable el ▲.
        </caption>
        <thead>
          <tr>
            <th scope="col" rowSpan={2} className="col-linea">
              Línea
            </th>
            {grupos3.map((b) => (
              <th
                key={b.clave}
                scope="colgroup"
                colSpan={SUBTITULOS.length}
                className={`grupo-bloque bloque-${b.clave}`}
              >
                <span className="grupo-titulo">{b.titulo}</span>
                <span className="grupo-contexto">{b.contexto}</span>
              </th>
            ))}
          </tr>
          <tr>
            {grupos3.flatMap((b) =>
              SUBTITULOS.map((s, i) => (
                <th
                  key={`${b.clave}-${s}`}
                  scope="col"
                  className={`num bloque-${b.clave}${i === 0 ? ' inicio-bloque' : ''}`}
                >
                  {s}
                </th>
              )),
            )}
          </tr>
        </thead>
        <tbody>
          {grupos.map((grupo, i) => {
            const id = grupo.seccion?.id ?? null
            // al buscar se ve todo lo encontrado: no se pliega nada
            const plegada = !buscando && plegadas.has(id)
            const visibles = plegada
              ? grupo.lineas.filter((l) => l.tipo === 'total' || l.tipo === 'subtotal')
              : grupo.lineas
            const resumen = resumirVariance(grupo.lineas)
            return (
              <SeccionFilas key={`${id ?? 'sin'}-${i}`}>
                {grupo.seccion && (
                  <tr className="fila-seccion" id={anclaDeSeccion(id)}>
                    <th scope="rowgroup" colSpan={COLUMNAS} className="col-linea">
                      <button
                        type="button"
                        className="boton-seccion"
                        aria-expanded={!plegada}
                        onClick={() => alAlternar(id)}
                      >
                        <span className="chevron-seccion" aria-hidden="true">
                          {plegada ? '▸' : '▾'}
                        </span>
                        <span className="nombre-seccion">{grupo.seccion.descripcion}</span>
                        <span className="suave cuenta-seccion">
                          {grupo.lineas.length} {grupo.lineas.length === 1 ? 'línea' : 'líneas'}
                        </span>
                        {resumen.desfavorables > 0 && (
                          <span className="chip-desfavorables">
                            {resumen.desfavorables}{' '}
                            {resumen.desfavorables === 1 ? 'desfavorable' : 'desfavorables'}
                          </span>
                        )}
                      </button>
                    </th>
                  </tr>
                )}
                {visibles.map((l) => (
                  <FilaLinea
                    key={l.linea_id}
                    linea={l}
                    periodo={periodo}
                    puedeDesglosar={puedeDesglosar}
                    busqueda={busqueda}
                    destacada={l.linea_id === lineaDestacada}
                    seleccionada={l.linea_id === lineaSeleccionada}
                    alSeleccionar={alSeleccionar}
                    comentarios={comentarios?.[l.linea_id]}
                  />
                ))}
              </SeccionFilas>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function SeccionFilas({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}

/** Qué significan las columnas y los colores: va arriba de la tabla. */
export function LeyendaVariance() {
  return (
    <div className="leyenda-variance" role="note" aria-label="Cómo leer la tabla">
      <span className="leyenda-bloque bloque-mes">Mes</span>
      <span className="leyenda-bloque bloque-ytd">Acumulado del año fiscal</span>
      <span className="leyenda-bloque bloque-anual">Presupuesto anual</span>
      <span>
        <span className="ley-fav">▲ favorable</span> ·{' '}
        <span className="ley-des">▼ desfavorable</span> · «—» = sin dato
      </span>
    </div>
  )
}
