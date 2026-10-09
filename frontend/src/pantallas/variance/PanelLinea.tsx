import { useEffect, useRef } from 'react'
import type { CifrasVariance, LineaVariance } from '../../api/tipos'
import { Icono } from '../../componentes/Iconos'
import { construirRuta, type Bloque } from '../../ruta/ruta'
import { maximoAbsoluto, porcentajeBarra } from '../../util/barras'
import { esDesfavorable, esFavorable, formatoContable, formatoPorcentaje } from '../../util/formato'
import { etiquetaMesLargo, etiquetaRangoMeses } from '../../util/periodos'

interface Props {
  linea: LineaVariance
  periodo: string
  periodosYtd: string[]
  anoFiscal: string
  /** Si el rol puede abrir el desglose, se ofrecen los enlaces a sus cuentas. */
  puedeDesglosar: boolean
  alCerrar: () => void
}

const TIPO: Record<string, string> = {
  detalle: 'Línea de detalle',
  subtotal: 'Subtotal',
  total: 'Total',
  informativa: 'Línea informativa',
}

function Barra({ valor, maximo, clase }: { valor: string | null; maximo: bigint; clase: string }) {
  const ancho = porcentajeBarra(valor, maximo)
  return (
    <svg className="barra-valor" viewBox="0 0 100 8" preserveAspectRatio="none" aria-hidden="true">
      <rect className="barra-fondo" x="0" y="0" width="100" height="8" rx="2" />
      {ancho > 0 && <rect className={clase} x="0" y="0" width={ancho} height="8" rx="2" />}
    </svg>
  )
}

function BloquePanel({
  titulo,
  contexto,
  cifras,
  enlace,
  textoEnlace,
}: {
  titulo: string
  contexto: string
  cifras: CifrasVariance
  enlace: string | null
  textoEnlace: string
}) {
  const maximo = maximoAbsoluto([cifras.actual, cifras.budget])
  const des = esDesfavorable(cifras.var)
  const fav = esFavorable(cifras.var)
  const tono = des ? 'desfavorable' : fav ? 'favorable' : ''
  return (
    <section className="panel-bloque" aria-label={`Detalle: ${titulo}`}>
      <h4>
        {titulo} <span className="suave">{contexto}</span>
      </h4>
      <div className="panel-fila">
        <span>Actual</span>
        <strong>{formatoContable(cifras.actual)}</strong>
        <Barra valor={cifras.actual} maximo={maximo} clase="barra-actual" />
      </div>
      <div className="panel-fila">
        <span>Presupuesto</span>
        <strong>{formatoContable(cifras.budget)}</strong>
        <Barra valor={cifras.budget} maximo={maximo} clase="barra-presupuesto" />
      </div>
      <div className="panel-fila panel-variacion">
        <span>Variación</span>
        <strong className={tono}>{formatoContable(cifras.var)}</strong>
        <span className={`var-pill ${tono}`}>{formatoPorcentaje(cifras.pct)}</span>
      </div>
      {enlace && (
        <a className="panel-enlace" href={enlace}>
          {textoEnlace}
        </a>
      )}
    </section>
  )
}

/**
 * Panel lateral con el detalle de una línea: Mes, Acumulado y Presupuesto anual, con barras Actual
 * contra Presupuesto. Solo usa las cifras que la línea ya trae; no consulta nada ni calcula Variance.
 */
export function PanelLinea({ linea, periodo, periodosYtd, anoFiscal, puedeDesglosar, alCerrar }: Props) {
  const cerrar = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    cerrar.current?.focus()
  }, [linea.linea_id])

  useEffect(() => {
    const alTeclear = (e: KeyboardEvent) => {
      if (e.key === 'Escape') alCerrar()
    }
    window.addEventListener('keydown', alTeclear)
    return () => window.removeEventListener('keydown', alTeclear)
  }, [alCerrar])

  const calculada = linea.tipo !== 'informativa'
  const enlace = (bloque: Bloque) =>
    puedeDesglosar && calculada
      ? construirRuta({ tipo: 'desglose', periodo, lineaId: linea.linea_id, bloque })
      : null

  return (
    <aside className="panel-linea" role="dialog" aria-modal="false" aria-label="Detalle de la línea">
      <header className="panel-cabecera">
        <div>
          <p className="panel-tipo">{TIPO[linea.tipo] ?? linea.tipo}</p>
          <h3>{linea.descripcion}</h3>
          {linea.codigo_corporativo && <code className="suave">{linea.codigo_corporativo}</code>}
        </div>
        <button ref={cerrar} type="button" className="boton-icono" aria-label="Cerrar detalle" onClick={alCerrar}>
          <Icono nombre="cerrar" />
        </button>
      </header>
      <BloquePanel
        titulo="Mes"
        contexto={etiquetaMesLargo(periodo)}
        cifras={linea.mes}
        enlace={enlace('mes')}
        textoEnlace="Ver cuentas del mes"
      />
      <BloquePanel
        titulo="Acumulado"
        contexto={`${etiquetaRangoMeses(periodosYtd)} · año fiscal ${anoFiscal}`}
        cifras={linea.ytd}
        enlace={enlace('ytd')}
        textoEnlace="Ver cuentas del acumulado"
      />
      <BloquePanel
        titulo="Presupuesto anual"
        contexto={anoFiscal}
        cifras={linea.anual}
        enlace={null}
        textoEnlace=""
      />
    </aside>
  )
}
