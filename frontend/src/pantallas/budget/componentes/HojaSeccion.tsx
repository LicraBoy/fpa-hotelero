import { useEffect, useRef, useState, type ReactNode } from 'react'
import { ErrorApi, enviarJson, importarOtherIncomeExcel, obtenerTipado } from '../../../api/cliente'
import type { components } from '../../../api/schema'
import type { LineaEdicionBudget } from '../../../api/tipos'
import { useDatos } from '../../../api/useDatos'
import { Icono, type NombreIcono } from '../../../componentes/Iconos'
import { Cargando, MensajeError } from '../../../componentes/Insignia'
import { aMicros, formatoMicros } from '../calculo'
import { rangoDePeriodos } from '../editorCuenta'
import {
  acumulada,
  cambioContraBase,
  etiquetaMes,
  formatoPorcentaje,
  fraccionAPorcentaje,
  porcentajeAFraccion,
  seriesComparativo,
  sumaAnual,
  totalConInflacion,
  variacionAnual,
} from '../hojaSeccion'
import { GraficoComparativo } from './GraficoComparativo'
import { AyudaTooltip, TarjetaIndicador } from './HojaUi'
import { microsDe, sumaDe } from '../consumo'
import { HojaConsumo } from './HojaConsumo'
import { TablaInflacion, type EstadoInflacion } from './TablaInflacion'
import { TablaInflacionPorMes } from './TablaInflacionPorMes'
import { EditorPartida } from './EditorPartida'
import { TablaInternaLinea } from './TablaInternaLinea'
import { extendidoDe, partidaDesdeApi, seccionAdmitePartidas, type PartidaEditable } from '../partidas'

type Hoja = components['schemas']['HojaSalida']
type HojaCuenta = components['schemas']['HojaCuentaSalida']
type LineaMensual = components['schemas']['LineaMensualSalida']
type Vista = 'cuentas' | 'comparacion'
type FiltroCuentas = 'todas' | 'con' | 'sin'

const NO_DISPONIBLE = 'No disponible'
const dinero = (micros: bigint | null) => (micros === null ? NO_DISPONIBLE : `$ ${formatoMicros(micros)}`)
const micros = (t: string | null) => (t === null ? null : aMicros(t))
const signo = (m: bigint) => (m > 0n ? '+' : '')
const conSigno = (m: bigint) => `${signo(m)}${formatoMicros(m)}`
const tieneImporte = (meses: (string | null)[]) => meses.some((m) => m !== null && aMicros(m) !== 0n)
const textoMonto = (m: bigint | null) => (m === null ? NO_DISPONIBLE : formatoMicros(m))

interface Props {
  hotelId: number
  cicloId: number
  seccionId: number
  /** Ejercicio fiscal real («2026/27»), para el pill del encabezado y el editor de cuenta. */
  anoFiscal: string
  /** Cuenta que se abre al entrar (si se llegó desde una cuenta y no desde la sección). */
  cuentaInicial?: number | null
  periodos: string[]
  /** Las líneas de la sección (para abrir el editor mensual de una cuenta). */
  cuentas: LineaEdicionBudget[]
  puedeEditar: boolean
  alVolver: () => void
  alGuardarCuenta: (lineaId: number, valores: LineaMensual[]) => void
  alCambiarCiclo: () => void
  /** `cuenta`: la hoja de UNA cuenta por partidas (filas = partidas); por omisión, la hoja de la sección. */
  modo?: 'seccion' | 'cuenta'
  /** La cuenta cuya hoja se ve (solo en modo `cuenta`). */
  lineaId?: number
  /** Nombre de la sección a la que se regresa desde la hoja de una cuenta. */
  nombrePadre?: string
  /** Cuentas de la sección que ya se capturan por partidas. */
  usaPartidas?: ReadonlySet<number>
  /** La cuenta volvió al Editor mensual (se quitaron sus partidas). */
  alQuitarPartidasListo?: () => void
}

/**
 * La Hoja de sección (Other Income, Mgmt & Check In) tal como la trae el Excel de Contraloría, en página completa:
 * vista «Cuentas» (indicadores, cuentas por mes y el bloque de inflación) y vista «Comparación anual»
 * (gráfico y tabla). Clic en una cuenta abre el Editor mensual, que reemplaza a la hoja mientras está
 * abierto.
 */
export function HojaSeccion(p: Props) {
  const esCuenta = p.modo === 'cuenta'
  const hoja = useDatos<Hoja | HojaCuenta>(
    () =>
      esCuenta
        ? obtenerTipado('/api/v1/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}/lineas/{linea_id}/hoja', {
            path: { hotel_id: p.hotelId, ciclo_id: p.cicloId, linea_id: p.lineaId ?? 0 },
          })
        : obtenerTipado('/api/v1/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}/hojas/{seccion_id}', {
            path: { hotel_id: p.hotelId, ciclo_id: p.cicloId, seccion_id: p.seccionId },
          }),
    [p.hotelId, p.cicloId, p.seccionId, esCuenta, p.lineaId],
  )
  const [cuentaAbierta, setCuentaAbierta] = useState<number | null>(p.cuentaInicial ?? null)
  // Importar del Excel cambia todas las cuentas: la tabla de la cuenta abierta se vuelve a leer
  const [versionCuentas, setVersionCuentas] = useState(0)
  // El mensaje y los avisos viven aquí: guardar o importar recarga la hoja y remonta el cuerpo
  const [mensaje, setMensaje] = useState<string | null>(null)
  const [avisos, setAvisos] = useState<string[]>([])
  const [vista, setVista] = useState<Vista>('cuentas')
  const lineaAbierta = p.cuentas.find((l) => l.linea_id === cuentaAbierta) ?? null
  // Cuentas que cambian de modo en esta sesión (el ciclo tarda en recargar su lista de líneas)
  const [forzadas, setForzadas] = useState<ReadonlyMap<number, boolean>>(new Map())
  const usaPartidas = (id: number) => forzadas.get(id) ?? p.usaPartidas?.has(id) ?? false
  const datosCuenta = esCuenta ? (hoja.datos as HojaCuenta | null) : null

  async function detallar(lineaId: number) {
    try {
      await enviarJson('POST', `/api/v1/hoteles/${p.hotelId}/presupuesto/ciclos/${p.cicloId}/lineas/${lineaId}/partidas/activar`)
      setForzadas((m) => new Map(m).set(lineaId, true))
      p.alCambiarCiclo()
    } catch (e) {
      setMensaje(e instanceof ErrorApi ? e.detalle : 'No se pudo pasar la cuenta a partidas')
    }
  }

  async function quitarPartidas() {
    const soloConsumo = datosCuenta?.consumo != null && (datosCuenta?.partidas.length ?? 0) === 0
    const que = soloConsumo ? 'su consumo' : 'sus partidas'
    if (!window.confirm(`¿Volver esta cuenta al Editor mensual? Se borra ${que} y el Budget actual queda como importes fijos.`)) return
    try {
      await enviarJson(
        'DELETE',
        `/api/v1/hoteles/${p.hotelId}/presupuesto/ciclos/${p.cicloId}/lineas/${p.lineaId}/${soloConsumo ? 'consumo' : 'partidas'}`,
      )
      p.alCambiarCiclo()
      p.alQuitarPartidasListo?.()
    } catch (e) {
      setMensaje(e instanceof ErrorApi ? e.detalle : 'No se pudieron quitar las partidas')
    }
  }

  // Hoja de UNA cuenta (modo cuenta): con una partida abierta se ve solo su editor
  const partidas = (datosCuenta?.partidas ?? []).map((x) => partidaDesdeApi(x))
  const indicePartida = cuentaAbierta === -1 ? -1 : partidas.findIndex((x) => x.id === cuentaAbierta)
  const partidaAbierta = esCuenta && cuentaAbierta !== null && (cuentaAbierta === -1 || indicePartida >= 0)
  const hojaDeCuenta = lineaAbierta !== null && usaPartidas(lineaAbierta.linea_id)

  return (
    <section className="captura-area hoja-seccion" aria-label={esCuenta ? 'Hoja de la cuenta' : 'Hoja de la sección'}>
      {hoja.cargando && !hoja.datos && <Cargando texto="Cargando la hoja…" />}
      {hoja.error && <MensajeError texto={hoja.error} />}
      {hoja.datos && !partidaAbierta && !(!esCuenta && lineaAbierta && p.cuentas.length > 0) && (
        <Cuerpo
          // Cada recarga (guardar, importar) vuelve a armar el borrador de inflación desde la API
          key={`${hoja.datos.inflacion.join('|')}-${hoja.datos.totales.join('|')}`}
          p={p}
          hoja={hoja.datos}
          recargar={hoja.recargar}
          setCuentaAbierta={setCuentaAbierta}
          vista={vista}
          setVista={setVista}
          mensaje={mensaje}
          setMensaje={setMensaje}
          avisos={avisos}
          setAvisos={setAvisos}
          alImportar={() => setVersionCuentas((v) => v + 1)}
          alQuitarPartidas={() => void quitarPartidas()}
          partidas={partidas}
        />
      )}
      {partidaAbierta && datosCuenta && (
        <EditorPartida
          key={`${cuentaAbierta}-${versionCuentas}`}
          hotelId={p.hotelId}
          cicloId={p.cicloId}
          lineaId={datosCuenta.linea_id}
          cuenta={datosCuenta.seccion}
          partidas={partidas}
          indice={indicePartida}
          inflacion={Object.fromEntries(datosCuenta.periodos.map((per, i) => [per, datosCuenta.inflacion[i] ?? '0']))}
          periodos={datosCuenta.periodos}
          puedeEditar={p.puedeEditar}
          alElegir={(i) => setCuentaAbierta(partidas[i].id)}
          alVolver={() => setCuentaAbierta(null)}
          alGuardado={(texto, h) => {
            setMensaje(texto)
            setCuentaAbierta(null)
            if (h) p.alGuardarCuenta(h.linea_id, h.periodos.map((per, i) => ({ periodo: per, importe: h.total_con_inflacion[i] })))
            p.alCambiarCiclo()
            hoja.recargar()
          }}
        />
      )}
      {!esCuenta && lineaAbierta && hoja.datos && hojaDeCuenta && (
        <HojaSeccion
          {...p}
          key={`cuenta-${lineaAbierta.linea_id}-${versionCuentas}`}
          modo="cuenta"
          lineaId={lineaAbierta.linea_id}
          cuentaInicial={null}
          nombrePadre={hoja.datos.seccion}
          alVolver={() => {
            setCuentaAbierta(null)
            hoja.recargar()
          }}
          alCambiarCiclo={() => {
            p.alCambiarCiclo()
            setForzadas((m) => new Map(m).set(lineaAbierta.linea_id, usaPartidas(lineaAbierta.linea_id)))
          }}
          alQuitarPartidasListo={() => {
            setForzadas((m) => new Map(m).set(lineaAbierta.linea_id, false))
            setVersionCuentas((v) => v + 1)
          }}
        />
      )}
      {!esCuenta && lineaAbierta && hoja.datos && !hojaDeCuenta && (
        // Con una cuenta abierta se ve solo su editor; la hoja vuelve al regresar
        <TablaInternaLinea
          key={`${lineaAbierta.linea_id}-${versionCuentas}`}
          hotelId={p.hotelId}
          cicloId={p.cicloId}
          linea={lineaAbierta}
          seccion={hoja.datos.seccion}
          anoFiscal={p.anoFiscal}
          periodos={p.periodos}
          hermanas={p.cuentas}
          puedeEditar={p.puedeEditar}
          alElegirLinea={setCuentaAbierta}
          alVolver={() => {
            setCuentaAbierta(null)
            hoja.recargar()
          }}
          alGuardar={(id, valores) => p.alGuardarCuenta(id, valores)}
          alDetallar={seccionAdmitePartidas(hoja.datos.seccion) && p.puedeEditar ? detallar : undefined}
        />
      )}
    </section>
  )
}

function Cuerpo({
  p,
  hoja,
  recargar,
  setCuentaAbierta,
  vista,
  setVista,
  mensaje,
  setMensaje,
  avisos,
  setAvisos,
  alImportar,
  alQuitarPartidas,
  partidas,
}: {
  p: Props
  hoja: Hoja
  recargar: () => void
  setCuentaAbierta: (id: number | null) => void
  vista: Vista
  setVista: (v: Vista) => void
  mensaje: string | null
  setMensaje: (m: string | null) => void
  avisos: string[]
  setAvisos: (a: string[]) => void
  alImportar: () => void
  alQuitarPartidas: () => void
  partidas: readonly PartidaEditable[]
}) {
  const esCuenta = p.modo === 'cuenta'
  // Cuenta de consumo (Diesel, Gas, Electricity, Water): trae su consumo mensual; sin partidas es solo consumo
  const consumo = esCuenta ? ((hoja as HojaCuenta).consumo ?? null) : null
  const soloConsumo = consumo !== null && partidas.length === 0
  const [inflacion, setInflacion] = useState<string[]>(() => hoja.inflacion.map(fraccionAPorcentaje))
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [enfocarInflacion, setEnfocarInflacion] = useState(false)
  const entradaArchivo = useRef<HTMLInputElement>(null)

  const periodos = hoja.periodos
  const totales = hoja.totales.map((t) => aMicros(t) ?? 0n)
  const inflPantalla = inflacion.map((t) => {
    const f = t.trim() === '' ? '0' : porcentajeAFraccion(t)
    return f === null ? null : aMicros(f)
  })
  const invalida = inflPantalla.some((v) => v === null)
  const sucio = inflacion.some((t, i) => t !== fraccionAPorcentaje(hoja.inflacion[i]))
  const acum = acumulada(inflPantalla)
  // Con partidas Y consumo (Water & Sewer) el Budget suma las partidas con inflación y el consumo sin ella
  const consumoMixto = consumo !== null && partidas.length > 0 ? consumo.budget.map((m) => microsDe(m.total) ?? 0n) : null
  const conInflacion = totalConInflacion(totales, inflPantalla).map((v, i) => v + (consumoMixto?.[i] ?? 0n))
  const estAct = hoja.est_act.map(micros)
  const previo = hoja.budget_previo.map(micros)
  const variacion = hoja.variacion.map(micros)
  const totalAnual = sumaAnual(totales)
  const anualVar = variacionAnual(estAct, previo)
  const conDatos = hoja.cuentas.filter((c) => tieneImporte(c.meses)).length

  async function guardarInflacion() {
    const cuerpo: Record<string, string> = {}
    for (let i = 0; i < periodos.length; i++) {
      const f = inflacion[i].trim() === '' ? '0' : porcentajeAFraccion(inflacion[i])
      if (f === null) {
        setError(`La inflación de ${etiquetaMes(periodos[i])} no es un porcentaje válido`)
        return
      }
      cuerpo[periodos[i]] = f
    }
    setGuardando(true)
    setError(null)
    try {
      if (esCuenta) {
        // La inflación de una cuenta por partidas SÍ entra al Budget: se recalcula y se avisa a la hoja
        const h = await enviarJson<HojaCuenta>(
          'PUT',
          `/api/v1/hoteles/${p.hotelId}/presupuesto/ciclos/${p.cicloId}/lineas/${p.lineaId}/hoja/inflacion`,
          { inflacion: cuerpo },
        )
        setMensaje('Inflación guardada. El Budget de la cuenta se recalculó.')
        if (h) p.alGuardarCuenta(h.linea_id, h.periodos.map((per, i) => ({ periodo: per, importe: h.total_con_inflacion[i] })))
        p.alCambiarCiclo()
      } else {
        await enviarJson(
          'PUT',
          `/api/v1/hoteles/${p.hotelId}/presupuesto/ciclos/${p.cicloId}/hojas/${p.seccionId}/inflacion`,
          { inflacion: cuerpo },
        )
        setMensaje('Inflación guardada. Es informativa: el Budget de las cuentas no cambia.')
      }
      recargar()
    } catch (e) {
      setError(e instanceof ErrorApi ? e.detalle : 'No se pudo guardar la inflación')
    } finally {
      setGuardando(false)
    }
  }

  async function importar(archivo: File) {
    setGuardando(true)
    setError(null)
    setAvisos([])
    try {
      const r = await importarOtherIncomeExcel(p.hotelId, p.cicloId, archivo, p.seccionId, esCuenta ? p.lineaId : undefined)
      setAvisos(r.avisos)
      setMensaje(
        esCuenta
          ? r.importadas > 0
            ? `Se importaron las partidas de ${hoja.seccion} desde el Excel.`
            : `No se importó nada: ${hoja.seccion} no tiene partidas en el Excel.`
          : `Se importaron ${r.importadas} cuentas desde el Excel.`,
      )
      p.alCambiarCiclo()
      alImportar()
      recargar()
    } catch (e) {
      setError(e instanceof ErrorApi ? e.detalle : 'No se pudo leer el Excel')
    } finally {
      setGuardando(false)
      if (entradaArchivo.current) entradaArchivo.current.value = ''
    }
  }

  const estado: EstadoInflacion = {
    periodos,
    inflacion,
    setInflacion,
    inflPantalla,
    inflacionGuardada: hoja.inflacion,
    acumulada: acum,
    conInflacion,
    estAct,
    previo,
    variacion,
    variacionPct: hoja.variacion_pct,
    totalConInflacion: sumaAnual(conInflacion),
    totalEstAct: sumaAnual(estAct),
    totalPrevio: sumaAnual(previo),
    anualVar,
    invalida,
    sucio,
    guardando,
    puedeEditar: p.puedeEditar,
    guardar: () => void guardarInflacion(),
    descartar: () => setInflacion(hoja.inflacion.map(fraccionAPorcentaje)),
    entraAlBudget: esCuenta,
  }

  const rango = rangoDePeriodos(periodos)
  const pill = (
    <span className="hoja-pill" title="Ejercicio fiscal de la hoja">
      <Icono nombre="calendario" tamano={14} />
      <strong>{p.anoFiscal}</strong>
      {rango && <span className="hoja-pill-rango">{rango}</span>}
    </span>
  )
  const mensajes = (
    <>
      {error && <MensajeError texto={error} />}
      {mensaje && (
        <p className="mensaje mensaje-ok" role="status">
          {mensaje}
        </p>
      )}
      {avisos.length > 0 && (
        <ul className="mensaje mensaje-aviso tabla-interna-avisos" role="status">
          {avisos.map((a) => (
            <li key={a}>{a}</li>
          ))}
        </ul>
      )}
    </>
  )
  const irAComparacion = (enfocar: boolean) => {
    setEnfocarInflacion(enfocar)
    setVista('comparacion')
  }

  if (vista === 'comparacion') {
    return (
      <>
        <Encabezado
          icono="tabla"
          titulo="Comparación anual e inflación"
          etiqueta="Comparación anual"
          ruta={null}
          compacto
          volverTexto={esCuenta ? 'Hoja de cuenta' : 'Hoja de sección'}
          volverEtiqueta={esCuenta ? 'Volver a la Hoja de cuenta' : 'Volver a la Hoja de sección'}
          alVolver={() => setVista('cuentas')}
          descripcion={
            esCuenta ? (
              <>
                Compara el Budget de la cuenta con el año previo y muestra la inflación mensual. La inflación{' '}
                <strong>sí entra al Budget</strong>: Budget del mes = distribución × (1 + inflación).
              </>
            ) : (
              <>
                Aquí puedes ver la comparación con el año previo, la inflación mensual y su impacto en los totales de la
                hoja. La inflación es <strong>informativa</strong> y no modifica el Budget de las cuentas.
              </>
            )
          }
          derecha={
            <>
              {pill}
            </>
          }
        />
        {mensajes}
        <HojaComparacion
          hoja={hoja}
          // En una cuenta por partidas, el Budget ES el total con inflación (en la sección es la suma de sus cuentas)
          totales={esCuenta ? conInflacion : totales}
          totalAnual={esCuenta ? sumaAnual(conInflacion) : totalAnual}
          e={estado}
          enfocarInflacion={enfocarInflacion}
        />
      </>
    )
  }

  return (
    <>
      <Encabezado
        icono={esCuenta ? 'tabla' : 'baseDatos'}
        titulo={hoja.seccion}
        etiqueta={esCuenta ? 'Hoja de cuenta' : 'Hoja de sección'}
        ruta={esCuenta ? null : <strong aria-current="page">{hoja.seccion}</strong>}
        compacto={esCuenta}
        volverTexto={esCuenta ? p.nombrePadre : undefined}
        volverEtiqueta={esCuenta ? 'Volver a la Hoja de sección' : 'Volver a Captura'}
        alVolver={p.alVolver}
        descripcion={
          esCuenta ? (
            <>
              {soloConsumo ? (
                <>
                  La cuenta <strong>{hoja.seccion}</strong> se captura por consumo: cada mes son unidades ({consumo?.unidad}) × costo
                  unitario. Aquí ves los cuatro bloques de su hoja del Excel; el Budget es el consumo de {p.anoFiscal} y
                  no lleva inflación (el costo unitario ya es la tarifa del año).
                </>
              ) : consumo !== null ? (
                <>
                  La cuenta <strong>{hoja.seccion}</strong> suma su consumo ({consumo.unidad} × costo unitario, sin inflación)
                  y sus partidas (cantidad × costo, con inflación). Haz clic en una partida para editarla.
                </>
              ) : (
                <>
                  La cuenta <strong>{hoja.seccion}</strong> se captura por partidas (cantidad × costo, repartidas por mes). Haz clic
                  en una partida para editarla. El Budget de cada mes es la distribución × (1 + inflación): la inflación{' '}
                  <strong>sí entra al Budget</strong>.
                </>
              )}
            </>
          ) : (
            <>
              Es la hoja de <strong>{hoja.seccion}</strong> del Excel de Contraloría: cada cuenta con su Budget mes a
              mes, el total y, abajo, cómo se compara ese total con el año previo. Haz clic en una cuenta para ver y
              editar cómo se calcula (base × factor o partidas). La inflación es <strong>informativa</strong>: no
              modifica el Budget de las cuentas.
            </>
          )
        }
        derecha={
          <>
            {pill}
            {p.puedeEditar && (
              <>
                <input
                  ref={entradaArchivo}
                  type="file"
                  accept=".xlsx"
                  className="solo-lectores"
                  aria-label={
                    esCuenta ? `Excel del Budget con las partidas de ${hoja.seccion}` : `Excel del Budget con la hoja ${hoja.seccion}`
                  }
                  onChange={(e) => {
                    const archivo = e.target.files?.[0]
                    if (archivo) void importar(archivo)
                  }}
                />
                <button
                  type="button"
                  className="boton boton-secundario boton-chico"
                  disabled={guardando}
                  onClick={() => {
                    if (
                      esCuenta &&
                      (hoja.cuentas.length > 0 || consumo !== null) &&
                      !window.confirm(
                        consumo !== null
                          ? `Se reemplazará el consumo actual de ${hoja.seccion}${hoja.cuentas.length > 0 ? ' y sus partidas' : ''} con el de la hoja del Excel. ¿Continuar?`
                          : `Se reemplazarán las ${hoja.cuentas.length} partidas actuales de ${hoja.seccion} con las de la hoja del Excel. ¿Continuar?`,
                      )
                    ) {
                      return
                    }
                    entradaArchivo.current?.click()
                  }}
                  title={
                    esCuenta
                      ? `Trae las partidas de ${hoja.seccion} (cantidad, unidad, costo y meses) desde su hoja de detalle del Excel`
                      : `Llena las cuentas y los comparativos de ${hoja.seccion} desde el Excel del Budget`
                  }
                >
                  <Icono nombre="subir" tamano={14} /> {esCuenta ? (consumo !== null ? 'Importar consumo del Excel' : 'Importar partidas del Excel') : 'Importar del Excel'}
                </button>
              </>
            )}
            {esCuenta && p.puedeEditar && (
              <button
                type="button"
                className="boton boton-secundario boton-chico"
                onClick={alQuitarPartidas}
                title="Vuelve la cuenta al Editor mensual; el Budget actual queda como importes fijos"
              >
                {soloConsumo ? 'Quitar consumo' : 'Quitar partidas'}
              </button>
            )}
          </>
        }
      />

      <div className="hoja-indicadores" role="group" aria-label="Resumen de la hoja">
        <TarjetaIndicador tono="azul" icono="baseDatos" etiqueta={esCuenta ? 'Budget anual (con inflación)' : 'Budget anual de la hoja'}>
          {dinero(esCuenta ? estado.totalConInflacion : totalAnual)}
        </TarjetaIndicador>
        <TarjetaIndicador tono="verde" icono="flechaArriba" etiqueta="Est-Act año previo">
          {dinero(estado.totalEstAct)}
        </TarjetaIndicador>
        <TarjetaIndicador tono="morado" icono="calendario" etiqueta="Budget año previo">
          {dinero(estado.totalPrevio)}
        </TarjetaIndicador>
        <TarjetaIndicador tono="naranja" icono="tendenciaArriba" etiqueta="Variación (Est-Act − Budget previo)">
          {anualVar ? (
            <>
              {conSigno(anualVar.diferencia)}
              {anualVar.fraccion !== null && <span className="hi-pct"> ({formatoPorcentaje(anualVar.fraccion)})</span>}
            </>
          ) : (
            NO_DISPONIBLE
          )}
        </TarjetaIndicador>
        <TarjetaIndicador
          tono="celeste"
          icono="cuentas"
          etiqueta={soloConsumo ? `Consumo anual (${consumo?.unidad})` : esCuenta ? 'Partidas' : 'Cuentas con importe'}
        >
          {soloConsumo && consumo
            ? formatoMicros(sumaDe(consumo.budget.map((m) => microsDe(m.unidades))) ?? 0n)
            : esCuenta
              ? hoja.cuentas.length
              : `${conDatos} de ${hoja.cuentas.length}`}
        </TarjetaIndicador>
      </div>

      {mensajes}

      {consumo !== null && (
        <HojaConsumo
          // Cada guardado (o importación) vuelve a armar el borrador desde lo que dice la API
          key={consumo.budget.map((m) => `${m.unidades}-${m.costo_unitario}-${m.total}`).join('|')}
          hotelId={p.hotelId}
          cicloId={p.cicloId}
          lineaId={p.lineaId ?? 0}
          consumo={consumo}
          periodos={periodos}
          puedeEditar={p.puedeEditar}
          alGuardado={(texto, h) => {
            setMensaje(texto)
            if (h) p.alGuardarCuenta(h.linea_id, h.periodos.map((per, i) => ({ periodo: per, importe: h.total_con_inflacion[i] })))
            p.alCambiarCiclo()
            recargar()
          }}
        />
      )}

      {!soloConsumo && (
        <HojaCuentas
          hoja={hoja}
          totales={totales}
          totalAnual={totalAnual}
          alAbrirCuenta={setCuentaAbierta}
          alComparacion={() => irAComparacion(false)}
          esCuenta={esCuenta}
          alAgregar={esCuenta && p.puedeEditar ? () => setCuentaAbierta(-1) : undefined}
          partidas={esCuenta ? partidas : undefined}
        />
      )}

      {!soloConsumo && (
      <section className="hoja-tarjeta hoja-inflacion-tarjeta" aria-labelledby="hoja-inflacion-titulo">
        <div className="hoja-inflacion-cabecera">
          <div>
            <h3 id="hoja-inflacion-titulo" className="hoja-subtitulo">
              Comparación con el año previo e inflación
              <AyudaTooltip
                etiqueta="Qué es este bloque"
                texto={
                  <>
                    Este bloque es el que Contraloría usa para juzgar si el total es razonable: lo compara contra lo real
                    y lo presupuestado el año anterior. La inflación es informativa (igual que en el Excel): muestra
                    cuánto subiría el total, pero no cambia el Budget de las cuentas.
                  </>
                }
              />
            </h3>
            {!esCuenta && (
              <div className="hoja-subtabs" role="tablist" aria-label="Contenido del bloque">
                <button type="button" role="tab" aria-selected="true" className="hoja-subtab hoja-subtab-activa">
                  Inflación y comparativos
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected="false"
                  disabled
                  aria-describedby="hoja-subtab-nodisp"
                  className="hoja-subtab"
                >
                  Presupuesto por cuenta
                </button>
                <span id="hoja-subtab-nodisp" className="hoja-nodisp">
                  {NO_DISPONIBLE}: la hoja no trae Est-Act ni Budget previo por cuenta.
                </span>
              </div>
            )}
          </div>
          <button type="button" className="boton boton-secundario boton-chico" onClick={() => irAComparacion(true)}>
            <Icono nombre="lapiz" tamano={14} /> Editar inflación
          </button>
        </div>
        <TablaInflacion e={estado} />
      </section>
      )}
    </>
  )
}

function Encabezado({
  icono,
  titulo,
  etiqueta,
  ruta,
  volverEtiqueta,
  alVolver,
  descripcion,
  derecha,
  compacto,
  volverTexto,
}: {
  compacto?: boolean
  /** Si se da, el botón de regreso lleva este texto (además del icono) en vez de ser solo la flecha. */
  volverTexto?: string
  icono: NombreIcono
  titulo: string
  etiqueta: string
  ruta: ReactNode
  volverEtiqueta: string
  alVolver: () => void
  descripcion: ReactNode
  derecha: ReactNode
}) {
  return (
    <header className={compacto ? 'hoja-cabecera hoja-cabecera-compacta' : 'hoja-cabecera'}>
      <div className="hoja-cabecera-izq">
        <nav aria-label="Ruta de la hoja" className="hoja-migas">
          {volverTexto ? (
            <button type="button" className="hoja-volver" onClick={alVolver} aria-label={volverEtiqueta}>
              <Icono nombre="volver" tamano={14} />
              {volverTexto}
            </button>
          ) : (
            <button type="button" className="ec-flecha" onClick={alVolver} aria-label={volverEtiqueta} title={volverEtiqueta}>
              <Icono nombre="volver" tamano={16} />
            </button>
          )}
          {ruta}
          <span className="etiqueta-pantalla">{etiqueta}</span>
        </nav>
        <div className="hoja-identidad">
          <span className="hoja-icono-seccion" aria-hidden="true">
            <Icono nombre={icono} tamano={compacto ? 20 : 26} />
          </span>
          <div className="hoja-titulos">
            <h2>{titulo}</h2>
            <p className="hoja-explicacion">{descripcion}</p>
          </div>
        </div>
      </div>
      <div className="hoja-cabecera-der">{derecha}</div>
    </header>
  )
}

function HojaCuentas({
  hoja,
  totales,
  totalAnual,
  alAbrirCuenta,
  alComparacion,
  esCuenta,
  alAgregar,
  partidas,
}: {
  hoja: Hoja
  totales: bigint[]
  totalAnual: bigint | null
  alAbrirCuenta: (id: number) => void
  alComparacion: () => void
  /** Las filas son las partidas de una cuenta (no las cuentas de una sección). */
  esCuenta?: boolean
  alAgregar?: () => void
  /** Cant., unidad, costo y método de cada partida (modo cuenta), como la tabla del Excel. */
  partidas?: readonly PartidaEditable[]
}) {
  const partidasPorId = new Map((partidas ?? []).map((x) => [x.id, x]))
  // Costo extendido total (= Total Expense del Excel): null si alguna partida no se puede calcular
  let extendidoTotal: bigint | null = 0n
  for (const x of partidas ?? []) {
    const e = extendidoDe(x.cantidad, x.costo)
    extendidoTotal = extendidoTotal === null || e === null ? null : extendidoTotal + e
  }
  const [busqueda, setBusqueda] = useState('')
  const [filtro, setFiltro] = useState<FiltroCuentas>('todas')
  const [ampliado, setAmpliado] = useState(false)
  const periodos = hoja.periodos
  const hayFiltro = busqueda.trim() !== '' || filtro !== 'todas'

  useEffect(() => {
    if (!ampliado) return
    const tecla = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setAmpliado(false)
    }
    document.addEventListener('keydown', tecla)
    return () => document.removeEventListener('keydown', tecla)
  }, [ampliado])

  const visibles = hoja.cuentas.filter((c) => {
    const q = busqueda.trim().toLowerCase()
    if (q && !`${c.descripcion} ${c.codigo ?? ''}`.toLowerCase().includes(q)) return false
    if (filtro === 'con') return tieneImporte(c.meses)
    if (filtro === 'sin') return !tieneImporte(c.meses)
    return true
  })

  return (
    <section className={ampliado ? 'hoja-tarjeta hoja-cuentas-tarjeta hoja-ampliada' : 'hoja-tarjeta hoja-cuentas-tarjeta'}>
      <div className="hoja-barra">
        <div className="hoja-tabs" role="tablist" aria-label="Vista de la hoja">
          <button type="button" role="tab" aria-selected="true" className="hoja-tab hoja-tab-activa">
            {esCuenta ? 'Partidas' : 'Cuentas'}
          </button>
          <button type="button" role="tab" aria-selected="false" className="hoja-tab" onClick={alComparacion}>
            Comparación anual
          </button>
        </div>
        <div className="hoja-filtros">
          <label className="hoja-buscador">
            <Icono nombre="buscar" tamano={15} />
            <input
              type="search"
              aria-label={esCuenta ? 'Buscar partida' : 'Buscar cuenta'}
              placeholder={esCuenta ? 'Buscar partida…' : 'Buscar cuenta…'}
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
            />
          </label>
          <select aria-label="Filtrar cuentas" value={filtro} onChange={(e) => setFiltro(e.target.value as FiltroCuentas)}>
            <option value="todas">Todas las cuentas</option>
            <option value="con">Con importe</option>
            <option value="sin">Sin importe</option>
          </select>
          <button
            type="button"
            className={hayFiltro ? 'boton-icono hoja-embudo hoja-embudo-activo' : 'boton-icono hoja-embudo'}
            aria-label="Limpiar la búsqueda y el filtro"
            title="Limpiar la búsqueda y el filtro"
            onClick={() => {
              setBusqueda('')
              setFiltro('todas')
            }}
          >
            <Icono nombre="embudo" tamano={16} />
          </button>
        </div>
        {alAgregar && (
          <button type="button" className="boton boton-chico" onClick={alAgregar}>
            + Agregar partida
          </button>
        )}
        <button
          type="button"
          className="boton-icono"
          aria-label={ampliado ? 'Cerrar la vista ampliada' : 'Ampliar la tabla de cuentas'}
          title={ampliado ? 'Cerrar (Esc)' : 'Ampliar'}
          onClick={() => setAmpliado((a) => !a)}
        >
          <Icono nombre={ampliado ? 'cerrar' : 'ampliar'} tamano={16} />
        </button>
      </div>

      <div
        className={
          esCuenta
            ? 'tabla-variance-contenedor hoja-cuentas-contenedor hoja-cuentas-partidas'
            : 'tabla-variance-contenedor hoja-cuentas-contenedor'
        }
        role="region"
        aria-label="Hoja de cuentas por mes"
        tabIndex={0}
      >
        <table className={esCuenta ? 'tabla-variance hoja-tabla hoja-tabla-partidas' : 'tabla-variance hoja-tabla'}>
          <caption className="solo-lectores">
            Budget por cuenta y por mes de {hoja.seccion}, con el total de toda la hoja al pie.
          </caption>
          <thead>
            <tr>
              <th scope="col" className="col-linea">
                {esCuenta ? 'Partida' : 'Cuenta'}
              </th>
              {esCuenta && (
                <>
                  <th scope="col" className="num col-dato-partida">
                    Cant.
                  </th>
                  <th scope="col" className="col-dato-partida">
                    Unidad
                  </th>
                  <th scope="col" className="num col-dato-partida">
                    Costo
                  </th>
                  <th scope="col" className="num col-dato-partida">
                    Costo extendido
                  </th>
                </>
              )}
              <th scope="col" className="num col-anual">
                Total anual
              </th>
              {periodos.map((per) => (
                <th key={per} scope="col" className="num col-mes">
                  {etiquetaMes(per)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibles.map((c) => {
              const meses = c.meses.map(micros)
              const partida = esCuenta ? partidasPorId.get(c.linea_id) : undefined
              return (
                <tr key={c.linea_id}>
                  <th scope="row" className="col-linea">
                    <button
                      type="button"
                      className="fila-linea-boton"
                      aria-label={esCuenta ? `Abrir la partida ${c.descripcion}` : `Abrir el editor mensual de ${c.descripcion}`}
                      onClick={() => alAbrirCuenta(c.linea_id)}
                    >
                      <Icono nombre="chevron" tamano={14} />
                      <span className="linea-textos">
                        <span className="descripcion">{c.descripcion}</span>
                        {!esCuenta && c.codigo && <span className="codigo">{c.codigo}</span>}
                      </span>
                    </button>
                  </th>
                  {esCuenta && (
                    <>
                      <td className="num col-dato-partida">{partida?.cantidad ?? ''}</td>
                      <td className="col-dato-partida">{partida?.unidad ?? ''}</td>
                      <td className="num col-dato-partida">{partida ? textoMonto(aMicros(partida.costo)) : ''}</td>
                      <td className="num col-dato-partida">
                        {partida ? textoMonto(extendidoDe(partida.cantidad, partida.costo)) : ''}
                      </td>
                    </>
                  )}
                  <td className="num col-anual celda-anual">{formatoMicros(sumaAnual(meses))}</td>
                  {meses.map((m, i) => (
                    <td key={periodos[i]} className="num">
                      {formatoMicros(m)}
                    </td>
                  ))}
                </tr>
              )
            })}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row" className="col-linea">
                <span className="descripcion">Total Distribution</span>
                <span className="hoja-ayuda">
                  {esCuenta ? 'Suma de todas las partidas de la cuenta.' : 'Suma de todas las cuentas de la hoja.'}
                </span>
              </th>
              {esCuenta && (
                <>
                  <td colSpan={3} className="col-dato-partida" />
                  <td className="num col-dato-partida">{textoMonto(extendidoTotal)}</td>
                </>
              )}
              <td className="num col-anual celda-anual">{formatoMicros(totalAnual)}</td>
              {totales.map((v, i) => (
                <td key={periodos[i]} className="num">
                  {formatoMicros(v)}
                </td>
              ))}
            </tr>
          </tfoot>
        </table>
      </div>
      {visibles.length === 0 && (
        <p className="hoja-vacio">
          {esCuenta && hoja.cuentas.length === 0
            ? 'Esta cuenta aún no tiene partidas. Agrega la primera con «+ Agregar partida».'
            : 'Ninguna cuenta coincide con la búsqueda o el filtro.'}
        </p>
      )}
      {hayFiltro && (
        <p className="hoja-nota-filtro" role="status">
          Mostrando {visibles.length} de {hoja.cuentas.length} cuentas. El total del pie y los indicadores son de toda
          la hoja, no del filtro.
        </p>
      )}
    </section>
  )
}

function HojaComparacion({
  hoja,
  totales,
  totalAnual,
  e,
  enfocarInflacion,
}: {
  hoja: Hoja
  totales: bigint[]
  totalAnual: bigint | null
  e: EstadoInflacion
  enfocarInflacion: boolean
}) {
  const periodos = hoja.periodos
  const series = seriesComparativo(totales, e.estAct, e.previo)
  const [ampliado, setAmpliado] = useState(false)
  // Mes activo compartido: el cursor o el teclado en el gráfico resaltan su columna en la tabla y viceversa
  const [mesActivo, setMesActivo] = useState<number | null>(null)
  useEffect(() => {
    if (!ampliado) return
    const tecla = (ev: KeyboardEvent) => {
      if (ev.key === 'Escape') setAmpliado(false)
    }
    document.addEventListener('keydown', tecla)
    return () => document.removeEventListener('keydown', tecla)
  }, [ampliado])

  const acumFinal = e.acumulada.length > 0 ? e.acumulada[e.acumulada.length - 1] : null
  const cambioInfl =
    totalAnual !== null && e.totalConInflacion !== null ? cambioContraBase(totalAnual, e.totalConInflacion) : null
  const rangoMeses = periodos.length > 0 ? `${etiquetaMes(periodos[0])} – ${etiquetaMes(periodos[periodos.length - 1])}` : ''
  const tonoVar = e.anualVar === null || e.anualVar.diferencia === 0n ? 'neutro' : e.anualVar.diferencia > 0n ? 'positivo' : 'negativo'

  return (
    <div className="hoja-comparacion">
      <div className="hoja-franja" role="group" aria-label="Resumen de la comparación">
        <TarjetaIndicador compacto tono="neutro" icono="tendenciaArriba" etiqueta="Inflación acumulada" nota={rangoMeses}>
          {acumFinal === null ? NO_DISPONIBLE : formatoPorcentaje(acumFinal)}
        </TarjetaIndicador>
        <TarjetaIndicador
          compacto
          tono="azul"
          icono="baseDatos"
          etiqueta="Total con inflación"
          nota={cambioInfl !== null ? `${cambioInfl > 0n ? '+' : ''}${formatoPorcentaje(cambioInfl)} frente al Budget anual` : undefined}
        >
          {dinero(e.totalConInflacion)}
        </TarjetaIndicador>
        <TarjetaIndicador
          compacto
          tono={tonoVar}
          icono={e.anualVar && e.anualVar.diferencia < 0n ? 'tendenciaAbajo' : 'tendenciaArriba'}
          etiqueta="Variación vs año previo"
          nota={
            e.anualVar && e.anualVar.fraccion !== null
              ? `${e.anualVar.fraccion > 0n ? '+' : ''}${formatoPorcentaje(e.anualVar.fraccion)} frente al Budget previo`
              : undefined
          }
        >
          {e.anualVar ? (
            <>
              <span aria-hidden="true">{e.anualVar.diferencia > 0n ? '▲' : e.anualVar.diferencia < 0n ? '▼' : '■'}</span>{' '}
              {conSigno(e.anualVar.diferencia)}
            </>
          ) : (
            NO_DISPONIBLE
          )}
        </TarjetaIndicador>
        <TarjetaIndicador compacto tono="neutro" icono="flechaArriba" etiqueta="Est-Act año previo">
          {dinero(e.totalEstAct)}
        </TarjetaIndicador>
        <TarjetaIndicador compacto tono="neutro" icono="calendario" etiqueta="Budget año previo">
          {dinero(e.totalPrevio)}
        </TarjetaIndicador>
      </div>

      <section
        className={ampliado ? 'hoja-tarjeta hoja-grafico-tarjeta hoja-ampliada' : 'hoja-tarjeta hoja-grafico-tarjeta'}
        aria-label="Comparativo anual"
      >
        <GraficoComparativo
          series={series}
          periodos={periodos}
          variacion={e.variacion}
          variacionPct={e.variacionPct}
          activo={mesActivo}
          alActivar={setMesActivo}
          alto={ampliado ? 420 : 208}
          acciones={
            <button
              type="button"
              className="boton-icono"
              aria-label={ampliado ? 'Cerrar el gráfico ampliado' : 'Ampliar el gráfico'}
              title={ampliado ? 'Cerrar (Esc)' : 'Ampliar'}
              onClick={() => setAmpliado((a) => !a)}
            >
              <Icono nombre={ampliado ? 'cerrar' : 'ampliar'} tamano={16} />
            </button>
          }
        />
        {series.length < 3 && series.length > 0 && (
          <p className="hoja-nota-filtro">Solo se dibujan las series con los doce meses; las demás no están disponibles.</p>
        )}
      </section>

      <section className="hoja-tarjeta hoja-inflacion-tarjeta">
        <h3 className="hoja-subtitulo">Inflación y comparativos</h3>
        <TablaInflacionPorMes e={e} enfocarPrimero={enfocarInflacion} mesActivo={mesActivo} alActivarMes={setMesActivo} />
      </section>
    </div>
  )
}
