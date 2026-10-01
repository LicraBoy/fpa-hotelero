import { useEffect, useMemo, useState } from 'react'
import { ErrorApi, descargarVarianceExcel, obtenerTipado } from '../../api/cliente'
import { useDatos } from '../../api/useDatos'
import { Cargando, Insignia, MensajeError } from '../../componentes/Insignia'
import { puede } from '../../permisos'
import { useRuta } from '../../ruta/useRuta'
import { agruparPorSeccion } from './agrupar'
import { AsientoVista } from './AsientoVista'
import { Desglose } from './Desglose'
import { Movimientos } from './Movimientos'
import { TablaVariance } from './TablaVariance'

interface Props {
  hotelId: number
  rol: string | undefined
}

const ESPERA_BUSQUEDA_MS = 300
// Texto con el que la API avisa que no hay mapeo aprobado (servicios/actual.py, version_de_mapeo)
const SIN_MAPEO = /No hay un mapeo aprobado/

/** Pantalla de Variance: el reporte del mes, el acumulado del año fiscal y el Budget anual. */
function ReporteVariance({ hotelId, rol }: Props) {
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

  const [seccionId, setSeccionId] = useState<number | null>(null)
  const [soloTotales, setSoloTotales] = useState(false)
  const [textoBusqueda, setTextoBusqueda] = useState('')
  const [busqueda, setBusqueda] = useState('')
  const [plegadas, setPlegadas] = useState<ReadonlySet<number | null>>(new Set())
  const [exportando, setExportando] = useState(false)
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

  const grupos = useMemo(
    () => (variance.datos ? agruparPorSeccion(variance.datos.lineas, variance.datos.secciones) : []),
    [variance.datos],
  )

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
  return (
    <section className="tarjeta" aria-labelledby="titulo-variance">
      <h2 id="titulo-variance">Variance</h2>
      <form className="filtros" role="search" onSubmit={(e) => e.preventDefault()}>
        <label>
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
        <label>
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
        <label>
          Buscar línea
          <input
            type="search"
            value={textoBusqueda}
            maxLength={100}
            onChange={(e) => setTextoBusqueda(e.target.value)}
          />
        </label>
        <label className="casilla">
          <input
            type="checkbox"
            checked={soloTotales}
            onChange={(e) => setSoloTotales(e.target.checked)}
          />
          Solo totales y subtotales
        </label>
        <button
          type="button"
          className="boton-exportar"
          disabled={exportando || periodo === ''}
          onClick={() => void exportar()}
        >
          {exportando ? 'Exportando…' : 'Exportar a Excel'}
        </button>
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
          <p className="suave resumen-variance">
            Año fiscal <strong>{datos.ano_fiscal}</strong> · acumulado de{' '}
            {datos.periodos_ytd.join(', ')} · mapeo v{datos.version_mapeo_id}
            {datos.version_plan_id !== null ? ` · Budget v${datos.version_plan_id}` : ''}{' '}
            {datos.periodos_sin_datos.length > 0 && (
              <Insignia tono="aviso">Acumulado incompleto</Insignia>
            )}
          </p>
          {datos.advertencias.length > 0 && (
            <ul className="mensaje mensaje-aviso advertencias" role="status" aria-label="Advertencias">
              {datos.advertencias.map((a) => (
                <li key={a}>{a}</li>
              ))}
            </ul>
          )}
          {datos.lineas.length === 0 ? (
            <p className="suave">Ninguna línea coincide con los filtros.</p>
          ) : (
            <TablaVariance
              grupos={grupos}
              periodo={periodo}
              puedeDesglosar={puede(rol, 'drilldown:leer')}
              plegadas={plegadas}
              alAlternar={alternar}
            />
          )}
          <p className="suave nota-pie">
            Variación favorable = positiva. Ingresos y utilidades: real − presupuesto; gastos:
            presupuesto − real. Los importes se muestran a centavos; el cálculo es exacto.
          </p>
        </>
      )}
    </section>
  )
}

/**
 * Pantalla de Variance y su recorrido de desglose. Cada ruta monta SOLO su pantalla: ir al detalle
 * de una cuenta no vuelve a pedir el reporte completo.
 */
export function PanelVariance({ hotelId, rol }: Props) {
  const { ruta } = useRuta()
  switch (ruta.tipo) {
    case 'variance':
      return <ReporteVariance hotelId={hotelId} rol={rol} />
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
        />
      )
    case 'asiento':
      return <AsientoVista hotelId={hotelId} periodo={ruta.periodo} asiento={ruta.asiento} />
    default:
      return (
        <section className="mensaje mensaje-aviso" role="alert" aria-label="Ruta no válida">
          La dirección no es válida. <a href="#/variance">Volver al Variance</a>
        </section>
      )
  }
}
