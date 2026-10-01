import type { CifrasVariance, LineaVariance } from '../../api/tipos'
import { construirRuta, type Bloque } from '../../ruta/ruta'
import { esDesfavorable, formatoContable, formatoPorcentaje } from '../../util/formato'
import type { GrupoSeccion } from './agrupar'

interface Props {
  grupos: GrupoSeccion[]
  periodo: string
  /** Si el rol puede abrir el desglose, las cifras de Actual son enlaces. */
  puedeDesglosar: boolean
  plegadas: ReadonlySet<number | null>
  alAlternar: (seccionId: number | null) => void
}

const BLOQUES: { clave: 'mes' | 'ytd' | 'anual'; titulo: string }[] = [
  { clave: 'mes', titulo: 'Mes' },
  { clave: 'ytd', titulo: 'Acumulado del año fiscal' },
  { clave: 'anual', titulo: 'Presupuesto anual' },
]
const SUBTITULOS = ['Actual', 'Presupuesto', 'Variación', '% var.'] as const
const COLUMNAS = 1 + BLOQUES.length * SUBTITULOS.length

function CeldaImporte({ valor }: { valor: string | null }) {
  return <td className="num">{formatoContable(valor)}</td>
}

function CeldasBloque({
  cifras,
  calculada,
  enlace,
  etiquetaEnlace,
}: {
  cifras: CifrasVariance
  /** Falso en las líneas informativas (p. ej. el tipo de cambio): el motor no calcula su Actual. */
  calculada: boolean
  enlace: string | null
  etiquetaEnlace: string
}) {
  if (!calculada) {
    return (
      <>
        <td className="num suave" title="El motor no calcula esta línea">
          —
        </td>
        <CeldaImporte valor={cifras.budget} />
        <td className="num suave">—</td>
        <td className="num suave">—</td>
      </>
    )
  }
  const desfavorable = esDesfavorable(cifras.var)
  return (
    <>
      <td className="num">
        {enlace ? (
          <a href={enlace} aria-label={etiquetaEnlace}>
            {formatoContable(cifras.actual)}
          </a>
        ) : (
          formatoContable(cifras.actual)
        )}
      </td>
      <CeldaImporte valor={cifras.budget} />
      <td className={desfavorable ? 'num desfavorable' : 'num'}>
        {desfavorable && (
          <>
            <span aria-hidden="true">▼ </span>
            <span className="solo-lectores">Desfavorable: </span>
          </>
        )}
        {formatoContable(cifras.var)}
      </td>
      <td className={desfavorable ? 'num desfavorable' : 'num'}>{formatoPorcentaje(cifras.pct)}</td>
    </>
  )
}

function FilaLinea({
  linea,
  periodo,
  puedeDesglosar,
}: {
  linea: LineaVariance
  periodo: string
  puedeDesglosar: boolean
}) {
  const calculada = linea.tipo !== 'informativa'
  const enlace = (bloque: Bloque) =>
    puedeDesglosar && calculada
      ? construirRuta({ tipo: 'desglose', periodo, lineaId: linea.linea_id, bloque })
      : null
  return (
    <tr className={`fila-${linea.tipo}`}>
      <th scope="row" className="col-linea">
        <span className="descripcion">{linea.descripcion}</span>
        {linea.codigo_corporativo && <span className="codigo suave"> {linea.codigo_corporativo}</span>}
      </th>
      <CeldasBloque
        calculada={calculada}
        cifras={linea.mes}
        enlace={enlace('mes')}
        etiquetaEnlace={`Ver el desglose de ${linea.descripcion}, mes`}
      />
      <CeldasBloque
        calculada={calculada}
        cifras={linea.ytd}
        enlace={enlace('ytd')}
        etiquetaEnlace={`Ver el desglose de ${linea.descripcion}, acumulado`}
      />
      <CeldasBloque
        calculada={calculada}
        cifras={linea.anual}
        // el Actual del bloque anual es el mismo acumulado: su desglose está en el bloque YTD
        enlace={null}
        etiquetaEnlace=''
      />
    </tr>
  )
}

/** Tabla del reporte: descripción fija a la izquierda, encabezados fijos, secciones plegables. */
export function TablaVariance({ grupos, periodo, puedeDesglosar, plegadas, alAlternar }: Props) {
  return (
    <div className="tabla-variance-contenedor" role="region" aria-label="Tabla de Variance" tabIndex={0}>
      <table className="tabla-variance">
        <caption className="solo-lectores">
          Variance de {periodo}: Actual, Presupuesto, Variación y porcentaje, por mes, acumulado y
          presupuesto anual. Una variación desfavorable lleva el símbolo ▼.
        </caption>
        <thead>
          <tr>
            <th scope="col" rowSpan={2} className="col-linea">
              Línea
            </th>
            {BLOQUES.map((b) => (
              <th key={b.clave} scope="colgroup" colSpan={SUBTITULOS.length} className="grupo-bloque">
                {b.titulo}
              </th>
            ))}
          </tr>
          <tr>
            {BLOQUES.flatMap((b) =>
              SUBTITULOS.map((s) => (
                <th key={`${b.clave}-${s}`} scope="col" className="num">
                  {s}
                </th>
              )),
            )}
          </tr>
        </thead>
        <tbody>
          {grupos.map((grupo, i) => {
            const id = grupo.seccion?.id ?? null
            const plegada = plegadas.has(id)
            const visibles = plegada
              ? grupo.lineas.filter((l) => l.tipo === 'total' || l.tipo === 'subtotal')
              : grupo.lineas
            return (
              <SeccionFilas key={`${id ?? 'sin'}-${i}`}>
                {grupo.seccion && (
                  <tr className="fila-seccion">
                    <th scope="rowgroup" colSpan={COLUMNAS} className="col-linea">
                      <button
                        type="button"
                        className="boton-seccion"
                        aria-expanded={!plegada}
                        onClick={() => alAlternar(id)}
                      >
                        <span aria-hidden="true">{plegada ? '▸' : '▾'} </span>
                        {grupo.seccion.descripcion}
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
