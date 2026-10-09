import { useEffect, useMemo, useState } from 'react'
import { ErrorApi, descargarVarianceExcel, obtenerTipado } from '../../api/cliente'
import { useDatos } from '../../api/useDatos'
import { BarraApilada } from '../../componentes/BarraApilada'
import { EncabezadoPagina } from '../../componentes/EncabezadoPagina'
import { Icono } from '../../componentes/Iconos'
import { Cargando, Insignia, MensajeError } from '../../componentes/Insignia'
import { TarjetaKpi } from '../../componentes/TarjetaKpi'
import { puede } from '../../permisos'
import { formatoContable } from '../../util/formato'
import { resumirVariance } from '../../util/resumenVariance'
import { useRuta } from '../../ruta/useRuta'
import {
  agruparPorSeccion,
  anclaDeSeccion,
  etiquetasDeSecciones,
  sinLineasVacias,
} from './agrupar'
import { AsientoVista } from './AsientoVista'
import { Desglose } from './Desglose'
import { Movimientos } from './Movimientos'
import { PanelLinea } from './PanelLinea'
import { LeyendaVariance, TablaVariance } from './TablaVariance'

/** Filtros y plegado de la tabla: viven en `PanelVariance` para sobrevivir al ir y volver del desglose. */
function useFiltrosVariance() {
  const [seccionId, setSeccionId] = useState<number | null>(null)
  const [soloTotales, setSoloTotales] = useState(false)
  // Por omisión se ocultan las líneas sin Actual ni Presupuesto (con aviso de cuántas son)
  const [ocultarVacias, setOcultarVacias] = useState(true)
  const [textoBusqueda, setTextoBusqueda] = useState('')
  const [plegadas, setPlegadas] = useState<ReadonlySet<number | null>>(new Set())
  return {
    seccionId,
    setSeccionId,
    soloTotales,
    setSoloTotales,
    ocultarVacias,
    setOcultarVacias,
    textoBusqueda,
    setTextoBusqueda,
    plegadas,
    setPlegadas,
  }
}
type FiltrosVariance = ReturnType<typeof useFiltrosVariance>

interface Props {
  hotelId: number
  rol: string | undefined
  /** Abre la pestaña Budget (solo si el rol puede editarlo). */
  alIrABudget?: () => void
}

const ESPERA_BUSQUEDA_MS = 300
// Texto con el que la API avisa que no hay mapeo aprobado (servicios/actual.py, version_de_mapeo)
const SIN_MAPEO = /No hay un mapeo aprobado/

/** El mes no tiene Budget cuando ninguna línea trae Presupuesto del mes. */
function sinBudgetEnElMes(lineas: { mes: { budget: string | null } }[]): boolean {
  return lineas.length > 0 && lineas.every((l) => l.mes.budget === null)
}

/** Pantalla de Variance: el reporte del mes, el acumulado del año fiscal y el Budget anual. */
function ReporteVariance({
  hotelId,
  rol,
  alIrABudget,
  filtros,
  lineaOrigen,
}: Props & { filtros: FiltrosVariance; lineaOrigen: number | null }) {
  const { ruta, navegar } = useRuta()
  const rutaPeriodo = ruta.tipo === 'variance' ? ruta.periodo : null

  const cargas = useDatos(
    () => obtenerTipado('/api/v1/hoteles/{hotel_id}/cargas', { path: { hotel_id: hotelId } }),
    [hotelId],
  )
  const periodos = useMemo(
    () =>
      [...new Set((cargas.datos ?? []).filter((c) => c.estado === 'vigente').map((c) => c.periodo))]
        .sort()
        .reverse(),
    [cargas.datos],
  )
  // El Budget vigente dice de qué mes es el reporte armado: ahí hay mapeo, Budget y movimientos.
  // Si ese mes no está entre los cargados, se usa el más reciente.
  const presupuestos = useDatos(
    () => obtenerTipado('/api/v1/hoteles/{hotel_id}/budget/versiones', { path: { hotel_id: hotelId } }),
    [hotelId],
  )
  const mesDelBudget = useMemo(
    () =>
      (presupuestos.datos ?? [])
        .filter((v) => v.estado === 'vigente')
        .sort((a, b) => b.numero - a.numero)[0]?.periodo_corte,
    [presupuestos.datos],
  )
  // El mes activo se deriva: el de la ruta si existe; si no, el del Budget vigente; si no, el más
  // reciente cargado. Se espera a conocer el Budget para no abrir primero en otro mes.
  const porOmision =
    mesDelBudget && periodos.includes(mesDelBudget) ? mesDelBudget : (periodos[0] ?? '')
  const periodo =
    rutaPeriodo && periodos.includes(rutaPeriodo) ? rutaPeriodo : presupuestos.cargando ? '' : porOmision

  const {
    seccionId,
    setSeccionId,
    soloTotales,
    setSoloTotales,
    ocultarVacias,
    setOcultarVacias,
    textoBusqueda,
    setTextoBusqueda,
    plegadas,
    setPlegadas,
  } = filtros
  const [busqueda, setBusqueda] = useState(textoBusqueda.trim())
  const [exportando, setExportando] = useState(false)
  // Línea abierta en el panel lateral y densidad de la tabla (solo presentación)
  const [lineaPanel, setLineaPanel] = useState<number | null>(null)
  const [compacta, setCompacta] = useState(false)
  const [errorExportar, setErrorExportar] = useState<string | null>(null)

  useEffect(() => {
    const espera = setTimeout(() => setBusqueda(textoBusqueda.trim()), ESPERA_BUSQUEDA_MS)
    return () => clearTimeout(espera)
  }, [textoBusqueda])

  const variance = useDatos(
    () =>
      periodo === ''
        ? Promise.resolve(null)
        : obtenerTipado('/api/v1/hoteles/{hotel_id}/variance', {
            path: { hotel_id: hotelId },
            query: {
              periodo,
              seccion_id: seccionId ?? undefined,
              tipo: soloTotales ? ['total', 'subtotal'] : undefined,
              q: busqueda === '' ? undefined : busqueda,
            },
          }),
    [hotelId, periodo, seccionId, soloTotales, busqueda],
  )

  const { grupos, ocultas } = useMemo(() => {
    const todos = variance.datos
      ? agruparPorSeccion(variance.datos.lineas, variance.datos.secciones)
      : []
    return ocultarVacias ? sinLineasVacias(todos) : { grupos: todos, ocultas: 0 }
  }, [variance.datos, ocultarVacias])
  const resumen = useMemo(() => (variance.datos ? resumirVariance(variance.datos.lineas) : null), [variance.datos])
  const encontradas = grupos.reduce((n, g) => n + g.lineas.length, 0)
  const etiquetas = etiquetasDeSecciones(grupos.map((g) => g.seccion?.descripcion ?? 'Sin sección'))

  // Salta a una sección (y la despliega si estaba plegada)
  function irASeccion(id: number | null) {
    setPlegadas((anteriores) => {
      if (!anteriores.has(id)) return anteriores
      const nuevas = new Set(anteriores)
      nuevas.delete(id)
      return nuevas
    })
    setTimeout(() => {
      document.getElementById(anclaDeSeccion(id))?.scrollIntoView({ block: 'start' })
    }, 0)
  }

  // Descarga el Excel con los mismos filtros que se ven en pantalla
  async function exportar() {
    setExportando(true)
    setErrorExportar(null)
    try {
      const { archivo, nombre } = await descargarVarianceExcel({
        path: { hotel_id: hotelId },
        query: {
          periodo,
          seccion_id: seccionId ?? undefined,
          tipo: soloTotales ? ['total', 'subtotal'] : undefined,
          q: busqueda === '' ? undefined : busqueda,
        },
      })
      const url = URL.createObjectURL(archivo)
      const enlace = document.createElement('a')
      enlace.href = url
      enlace.download = nombre
      enlace.click()
      URL.revokeObjectURL(url)
    } catch (e: unknown) {
      setErrorExportar(e instanceof ErrorApi ? e.detalle : 'No se pudo exportar el reporte')
    } finally {
      setExportando(false)
    }
  }

  function alternar(id: number | null) {
    setPlegadas((anteriores) => {
      const nuevas = new Set(anteriores)
      if (nuevas.has(id)) nuevas.delete(id)
      else nuevas.add(id)
      return nuevas
    })
  }

  const datos = variance.datos
  // Al volver del desglose, la línea de la que se venía queda a la vista y resaltada
  const hayDatos = datos !== null
  useEffect(() => {
    if (lineaOrigen === null || !hayDatos) return
    document.getElementById(`linea-${lineaOrigen}`)?.scrollIntoView({ block: 'center' })
  }, [lineaOrigen, hayDatos])
  return (
    <section aria-labelledby="titulo-variance">
      <EncabezadoPagina
        id="titulo-variance"
        titulo="Variance"
        subtitulo={
          datos ? (
            <>
              Año fiscal <strong>{datos.ano_fiscal}</strong> · acumulado de{' '}
              {datos.periodos_ytd.join(', ')} · mapeo v{datos.version_mapeo_id}
              {datos.version_plan_id !== null ? ` · Budget v${datos.version_plan_id}` : ''}{' '}
              {datos.periodos_sin_datos.length > 0 && (
                <Insignia tono="aviso">Acumulado incompleto</Insignia>
              )}
            </>
          ) : undefined
        }
        acciones={
          <button
            type="button"
            className="boton"
            disabled={exportando || periodo === ''}
            onClick={() => void exportar()}
          >
            {exportando ? 'Exportando…' : 'Exportar a Excel'}
          </button>
        }
      />
      <form className="filtros" role="search" onSubmit={(e) => e.preventDefault()}>
        <label className="chip-filtro">
          Mes
          <select
            aria-label="Mes"
            value={periodo}
            onChange={(e) => navegar({ tipo: 'variance', periodo: e.target.value })}
            disabled={periodos.length === 0}
          >
            {periodos.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
        <label className="chip-filtro">
          Sección
          <select
            aria-label="Sección"
            value={seccionId ?? ''}
            onChange={(e) => setSeccionId(e.target.value === '' ? null : Number(e.target.value))}
          >
            <option value="">Todas</option>
            {(datos?.secciones ?? []).map((s) => (
              <option key={s.id} value={s.id}>
                {s.descripcion}
              </option>
            ))}
          </select>
        </label>
        {grupos.length > 1 && (
          <label className="chip-filtro">
            Saltar a
            <select
              aria-label="Ir a sección"
              value=""
              onChange={(e) => {
                const g = grupos[Number(e.target.value)]
                if (g) irASeccion(g.seccion?.id ?? null)
              }}
            >
              <option value="">Elegir sección…</option>
              {grupos.map((g, i) => (
                <option key={`${g.seccion?.id ?? 'sin'}-${i}`} value={i}>
                  {etiquetas[i]}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="chip-filtro">
          Buscar línea
          <input
            type="search"
            value={textoBusqueda}
            maxLength={100}
            onChange={(e) => setTextoBusqueda(e.target.value)}
          />
        </label>
        <label className="casilla chip-casilla">
          <input
            type="checkbox"
            checked={soloTotales}
            onChange={(e) => setSoloTotales(e.target.checked)}
          />
          Solo totales y subtotales
        </label>
        <label className="casilla chip-casilla">
          <input
            type="checkbox"
            checked={ocultarVacias}
            onChange={(e) => setOcultarVacias(e.target.checked)}
          />
          Ocultar líneas sin cifras
        </label>
      </form>
      {errorExportar && <MensajeError texto={errorExportar} />}

      {cargas.cargando && <Cargando />}
      {cargas.error && <MensajeError texto={cargas.error} />}
      {!cargas.cargando && periodos.length === 0 && (
        <p className="suave">Aún no hay meses cargados: sube un archivo en la pestaña Cargas.</p>
      )}
      {variance.cargando && periodo !== '' && <Cargando texto="Calculando el reporte…" />}
      {variance.error &&
        (SIN_MAPEO.test(variance.error) ? (
          <div className="mensaje mensaje-aviso" role="alert">
            <strong>Todavía no hay un reporte armado para este hotel.</strong> Falta un mapeo de
            cuentas aprobado por Contraloría. Pídele a TI que cargue los datos (para la revisión de
            agosto 2026: <code>python -m fpa.demo_agosto</code>) o a un analista que importe el
            Excel del Variance para que el contralor lo apruebe. Si ya lo hicieron, recarga la
            página.
          </div>
        ) : (
          <MensajeError texto={variance.error} />
        ))}

      {datos && (
        <>
          {resumen && resumen.conVariacion > 0 && (
            <section className="kpis" aria-label="Resumen del mes">
              <TarjetaKpi
                titulo="Líneas con variación desfavorable"
                valor={
                  <>
                    {resumen.desfavorables} <span className="kpi-de">de {resumen.conVariacion}</span>
                  </>
                }
                detalle={`${resumen.favorables} favorables · en el mes ${periodo}`}
                tono={resumen.desfavorables > 0 ? 'desfavorable' : 'neutro'}
                extra={
                  <BarraApilada
                    tramos={[
                      { etiqueta: 'favorables', cantidad: resumen.favorables, tono: 'favorable' },
                      { etiqueta: 'desfavorables', cantidad: resumen.desfavorables, tono: 'desfavorable' },
                      { etiqueta: 'sin variación', cantidad: resumen.sinVariacion, tono: 'neutro' },
                    ]}
                  />
                }
              />
              <TarjetaKpi
                titulo="Mayor desviación desfavorable"
                valor={resumen.mayorDesfavorable ? formatoContable(resumen.mayorDesfavorable.variacion) : '—'}
                detalle={resumen.mayorDesfavorable?.descripcion ?? 'Ninguna línea desfavorable'}
                tono={resumen.mayorDesfavorable ? 'desfavorable' : 'neutro'}
              />
              <TarjetaKpi
                titulo="Mayor desviación favorable"
                valor={resumen.mayorFavorable ? formatoContable(resumen.mayorFavorable.variacion) : '—'}
                detalle={resumen.mayorFavorable?.descripcion ?? 'Ninguna línea favorable'}
                tono={resumen.mayorFavorable ? 'favorable' : 'neutro'}
              />
            </section>
          )}
          {(sinBudgetEnElMes(datos.lineas) || datos.advertencias.length > 0) && (
            <details className="avisos" open>
              <summary>
                Avisos ({datos.advertencias.length + (sinBudgetEnElMes(datos.lineas) ? 1 : 0)})
              </summary>
          {sinBudgetEnElMes(datos.lineas) && (
            <p className="mensaje mensaje-aviso" role="status">
              <strong>No hay Budget para {periodo}.</strong> Por eso Presupuesto, Variación y % var.
              salen en «—» (el Actual sí se calcula).{' '}
              {alIrABudget ? (
                <button type="button" className="boton boton-secundario" onClick={alIrABudget}>
                  Capturar el Budget de {periodo}
                </button>
              ) : (
                'Pide a Contraloría que lo capture o lo importe.'
              )}
            </p>
          )}
          {datos.advertencias.length > 0 && (
            <ul className="mensaje mensaje-aviso advertencias" role="status" aria-label="Advertencias">
              {datos.advertencias.map((a) => (
                <li key={a}>{a}</li>
              ))}
            </ul>
          )}
            </details>
          )}
          {datos.lineas.length === 0 ? (
            <p className="suave">Ninguna línea coincide con los filtros.</p>
          ) : (
            <>
              <div className="barra-herramientas" role="toolbar" aria-label="Herramientas de la tabla">
                <button type="button" className="boton-herramienta" onClick={() => setPlegadas(new Set())}>
                  <Icono nombre="expandir" tamano={16} /> Expandir todo
                </button>
                <button
                  type="button"
                  className="boton-herramienta"
                  onClick={() => setPlegadas(new Set(grupos.map((g) => g.seccion?.id ?? null)))}
                >
                  <Icono nombre="plegar" tamano={16} /> Plegar todo
                </button>
                <button
                  type="button"
                  className="boton-herramienta"
                  aria-pressed={compacta}
                  onClick={() => setCompacta((v) => !v)}
                >
                  <Icono nombre="densidad" tamano={16} /> Densidad: {compacta ? 'compacta' : 'cómoda'}
                </button>
                <button type="button" className="boton-herramienta" onClick={() => window.print()}>
                  <Icono nombre="imprimir" tamano={16} /> Imprimir
                </button>
              </div>
              <div className="herramientas-tabla">
              <div className="barra-lectura">
                <p className="suave cuenta-lineas" role="status">
                  {busqueda !== '' && (
                    <>
                      <strong>
                        {encontradas} {encontradas === 1 ? 'línea encontrada' : 'líneas encontradas'}
                      </strong>{' '}
                      para «{busqueda}»
                      {grupos.length > 0 && ` en ${grupos.length} ${grupos.length === 1 ? 'sección' : 'secciones'}`}.{' '}
                    </>
                  )}
                  {ocultas > 0 && (
                    <>
                      Hay {ocultas} {ocultas === 1 ? 'línea oculta' : 'líneas ocultas'} por no tener
                      cifras.{' '}
                      <button type="button" className="enlace" onClick={() => setOcultarVacias(false)}>
                        Mostrarlas
                      </button>
                    </>
                  )}
                </p>
              </div>
              <LeyendaVariance />
              </div>
              {grupos.length === 0 ? (
                <p className="suave">Todas las líneas están sin cifras: desmarca «Ocultar líneas sin cifras».</p>
              ) : (
                <TablaVariance
                  grupos={grupos}
                  periodo={periodo}
                  puedeDesglosar={puede(rol, 'drilldown:leer')}
                  plegadas={plegadas}
                  alAlternar={alternar}
                  busqueda={busqueda}
                  lineaDestacada={lineaOrigen}
                  periodosYtd={datos.periodos_ytd}
                  anoFiscal={datos.ano_fiscal}
                  lineaSeleccionada={lineaPanel}
                  alSeleccionar={(id) => setLineaPanel((actual) => (actual === id ? null : id))}
                  compacta={compacta}
                />
              )}
            </>
          )}
          {lineaPanel !== null && datos.lineas.some((l) => l.linea_id === lineaPanel) && (
            <PanelLinea
              linea={datos.lineas.find((l) => l.linea_id === lineaPanel)!}
              periodo={periodo}
              periodosYtd={datos.periodos_ytd}
              anoFiscal={datos.ano_fiscal}
              puedeDesglosar={puede(rol, 'drilldown:leer')}
              alCerrar={() => setLineaPanel(null)}
            />
          )}
          <details className="notas-reporte" open>
            <summary>Notas del reporte</summary>
            <p className="suave nota-pie">
              Variación favorable = positiva. Ingresos y utilidades: real − presupuesto; gastos:
              presupuesto − real. Los importes se muestran a centavos; el cálculo es exacto.
            </p>
          </details>
        </>
      )}
    </section>
  )
}

/**
 * Pantalla de Variance y su recorrido de desglose. Cada ruta monta SOLO su pantalla: ir al detalle
 * de una cuenta no vuelve a pedir el reporte completo.
 */
export function PanelVariance({ hotelId, rol, alIrABudget }: Props) {
  const { ruta } = useRuta()
  const filtros = useFiltrosVariance()
  // Línea del reporte desde la que se bajó al detalle: al volver se resalta en la tabla
  const [lineaOrigen, setLineaOrigen] = useState<number | null>(null)
  const lineaDeLaRuta =
    ruta.tipo === 'desglose'
      ? ruta.lineaId
      : ruta.tipo === 'cuenta' || ruta.tipo === 'asiento'
        ? (ruta.lineaId ?? null)
        : null
  if (lineaDeLaRuta !== null && lineaDeLaRuta !== lineaOrigen) setLineaOrigen(lineaDeLaRuta)
  switch (ruta.tipo) {
    case 'variance':
      return (
        <ReporteVariance
          hotelId={hotelId}
          rol={rol}
          alIrABudget={alIrABudget}
          filtros={filtros}
          lineaOrigen={lineaOrigen}
        />
      )
    case 'desglose':
      return (
        <Desglose
          hotelId={hotelId}
          periodo={ruta.periodo}
          lineaId={ruta.lineaId}
          bloque={ruta.bloque}
        />
      )
    case 'cuenta':
      return (
        <Movimientos
          hotelId={hotelId}
          periodo={ruta.periodo}
          codigo={ruta.codigo}
          bloque={ruta.bloque}
          lineaId={ruta.lineaId}
        />
      )
    case 'asiento':
      return (
        <AsientoVista
          hotelId={hotelId}
          periodo={ruta.periodo}
          asiento={ruta.asiento}
          cuenta={ruta.cuenta}
          lineaId={ruta.lineaId}
          bloque={ruta.bloque}
        />
      )
    default:
      return (
        <section className="mensaje mensaje-aviso" role="alert" aria-label="Ruta no válida">
          La dirección no es válida. <a href="#/variance">Volver al Variance</a>
        </section>
      )
  }
}
