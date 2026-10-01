import { useEffect, useMemo, useState } from 'react'
import { obtenerTipado } from '../../api/cliente'
import { useDatos } from '../../api/useDatos'
import { Cargando, Insignia, MensajeError } from '../../componentes/Insignia'
import { puede } from '../../permisos'
import { useRuta } from '../../ruta/useRuta'
import { agruparPorSeccion } from './agrupar'
import { TablaVariance } from './TablaVariance'

interface Props {
  hotelId: number
  rol: string | undefined
}

const ESPERA_BUSQUEDA_MS = 300

/** Pantalla de Variance: el reporte del mes, el acumulado del año fiscal y el Budget anual. */
export function PanelVariance({ hotelId, rol }: Props) {
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
  // El mes activo se deriva: el de la ruta si existe, si no el más reciente cargado.
  const periodo =
    rutaPeriodo && periodos.includes(rutaPeriodo) ? rutaPeriodo : (periodos[0] ?? '')

  const [seccionId, setSeccionId] = useState<number | null>(null)
  const [soloTotales, setSoloTotales] = useState(false)
  const [textoBusqueda, setTextoBusqueda] = useState('')
  const [busqueda, setBusqueda] = useState('')
  const [plegadas, setPlegadas] = useState<ReadonlySet<number | null>>(new Set())

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

  function alternar(id: number | null) {
    setPlegadas((anteriores) => {
      const nuevas = new Set(anteriores)
      if (nuevas.has(id)) nuevas.delete(id)
      else nuevas.add(id)
      return nuevas
    })
  }

  if (ruta.tipo !== 'variance') {
    // El desglose (cuentas, movimientos y asientos) llega en la sub-fase 4.5.
    return (
      <section className="tarjeta" aria-label="Desglose">
        <p className="suave">
          Esta pantalla (<span>{ruta.tipo}</span>) se construye en la sub-fase 4.5.
        </p>
        <a href="#/variance">Volver al Variance</a>
      </section>
    )
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
      </form>

      {cargas.cargando && <Cargando />}
      {cargas.error && <MensajeError texto={cargas.error} />}
      {!cargas.cargando && periodos.length === 0 && (
        <p className="suave">Aún no hay meses cargados: sube un archivo en la pestaña Cargas.</p>
      )}
      {variance.cargando && periodo !== '' && <Cargando texto="Calculando el reporte…" />}
      {variance.error && <MensajeError texto={variance.error} />}

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
