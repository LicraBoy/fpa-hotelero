import { useEffect, useMemo, useState } from 'react'
import {
  ErrorApi,
  enviarJson,
  guardarActualesCapturados,
  guardarVersionBudget,
  importarBudgetExcel,
  obtenerTipado,
} from '../../api/cliente'
import type { components } from '../../api/schema'
import { useDatos } from '../../api/useDatos'
import type { LineaEdicionBudget, RespuestaBudget, VistaEdicionBudget } from '../../api/tipos'
import { Icono } from '../../componentes/Iconos'
import { Cargando, EstadoVacio, MensajeError } from '../../componentes/Insignia'
import { puede } from '../../permisos'
import { BudgetHeader } from './componentes/BudgetHeader'
import { BudgetResumen } from './componentes/BudgetResumen'
import type { PestanaBudget } from './componentes/BudgetTabs'
import { BudgetVersionesTab } from './componentes/BudgetVersionesTab'
import { DetalleCapturaLinea } from './componentes/DetalleCapturaLinea'
import { HojaSeccion } from './componentes/HojaSeccion'
import { CicloPresupuesto } from './CicloPresupuesto'
import {
  agruparPorSeccionId,
  aMicros,
  anosFiscalesConocidos,
  cambiosActualPendientes,
  cambiosPendientes,
  claveActual,
  claveCelda,
  completarConTotales,
  formatoMicros,
  sumaImportes,
  sumarMicros,
  textoDeMicros,
} from './calculo'
import { seccionTieneTablaInterna } from './detalleCuenta'

type AnoFiscal = components['schemas']['AnoFiscalSalida']
type Ciclo = components['schemas']['CicloSalida']
type LineaCaptura = components['schemas']['LineaCapturaSalida']
type Perfil = components['schemas']['PerfilSalida']
type LineaMensual = components['schemas']['LineaMensualSalida']
type VersionBudget = components['schemas']['VersionPlanSalida']

interface Props {
  hotelId: number
  rol: string | undefined
  pestana: PestanaBudget
  onCambiarPestana: (p: PestanaBudget) => void
}

const MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
const TODAS = 'todas'

const plural = (n: number, uno: string, varios: string) => `${n} ${n === 1 ? uno : varios}`

const etiquetaMes = (periodo: string) => `${MESES[Number(periodo.slice(5, 7)) - 1]} ${periodo.slice(2, 4)}`

type Mensaje = { tono: 'ok' | 'aviso' | 'error'; texto: string }

/**
 * Pantalla de Budget: la grilla mes a mes con el Actual al lado como referencia (como siempre), con
 * el ciclo de Presupuesto (estado, objetivo, captura por departamento) fusionado encima — no hay una
 * pantalla "Presupuesto" separada. Según el permiso y si hay un ciclo abierto, "Guardar" crea una
 * versión de Budget nueva de una vez, o alimenta el ciclo de captura (línea por línea).
 */
export function PanelBudget({ hotelId, rol, pestana, onCambiarPestana }: Props) {
  // El año fiscal por omisión sale del último mes cargado; el Budget vigente puede ser de otro.
  // Un responsable de departamento no tiene por qué poder leer Cargas: sin ese permiso no se
  // consulta (no es un dato que necesite para capturar su presupuesto).
  const puedeVerCargas = puede(rol, 'carga:leer')
  const cargas = useDatos(
    () =>
      puedeVerCargas
        ? obtenerTipado('/api/v1/hoteles/{hotel_id}/cargas', { path: { hotel_id: hotelId } })
        : Promise.resolve([]),
    [hotelId, puedeVerCargas],
  )
  const versiones = useDatos(
    () => obtenerTipado('/api/v1/hoteles/{hotel_id}/budget/versiones', { path: { hotel_id: hotelId } }),
    [hotelId],
  )
  const [elegido, setElegido] = useState<string | null>(null)
  const anos = useMemo(
    () => anosFiscalesConocidos(cargas.datos ?? [], versiones.datos ?? []),
    [versiones.datos, cargas.datos],
  )
  const anoFiscal = elegido && anos.includes(elegido) ? elegido : (anos[0] ?? null)

  // Al recargar la lista de versiones (tras guardar) no se desmonta el editor: perdería su mensaje
  if ((cargas.cargando && !cargas.datos) || (versiones.cargando && !versiones.datos)) return <Cargando />
  if (cargas.error || versiones.error) return <MensajeError texto={cargas.error ?? versiones.error ?? ''} />
  if (anoFiscal === null) {
    return (
      <section className="tarjeta">
        <h2>Budget</h2>
        <p className="mensaje mensaje-aviso">
          Todavía no hay cargas ni Budget en este hotel: sube primero un CON130 en la pestaña Cargas.
        </p>
      </section>
    )
  }
  return (
    <EditorBudget
      key={`${hotelId}-${anoFiscal}`}
      hotelId={hotelId}
      anoFiscal={anoFiscal}
      anos={anos}
      rol={rol}
      versiones={versiones.datos ?? []}
      alElegirAno={setElegido}
      alCambiarVersiones={versiones.recargar}
      pestana={pestana}
      onCambiarPestana={onCambiarPestana}
    />
  )
}

interface PropsEditor {
  hotelId: number
  anoFiscal: string
  anos: string[]
  rol: string | undefined
  versiones: VersionBudget[]
  alElegirAno: (ano: string) => void
  alCambiarVersiones: () => void
  pestana: PestanaBudget
  onCambiarPestana: (p: PestanaBudget) => void
}

function EditorBudget({
  hotelId,
  anoFiscal,
  anos,
  rol,
  versiones,
  alElegirAno,
  alCambiarVersiones,
  pestana,
  onCambiarPestana: setPestana,
}: PropsEditor) {
  const vista = useDatos(
    () =>
      obtenerTipado('/api/v1/hoteles/{hotel_id}/budget/edicion', {
        path: { hotel_id: hotelId },
        query: { ano_fiscal: anoFiscal },
      }),
    [hotelId, anoFiscal],
  )

  // Ciclo de Presupuesto para este año fiscal: se resuelve solo (nunca se le pide a Contraloría
  // llenar un formulario de calendario). Sin permiso de administrar el calendario, si todavía no
  // existe, el Budget se ve igual que siempre, sin la barra de ciclo.
  const puedeAdministrarCiclo = puede(rol, 'budget:aprobar')
  const anosPresupuesto = useDatos(
    () => obtenerTipado('/api/v1/hoteles/{hotel_id}/presupuesto/anos-fiscales', { path: { hotel_id: hotelId } }),
    [hotelId],
  )
  const existente = (anosPresupuesto.datos ?? []).find((a) => a.etiqueta === anoFiscal) ?? null
  const [anoCreado, setAnoCreado] = useState<AnoFiscal | null>(null)
  const [creandoAno, setCreandoAno] = useState(false)

  useEffect(() => {
    if (existente || anoCreado || creandoAno || !puedeAdministrarCiclo) return
    let vigente = true
    setCreandoAno(true)
    void (async () => {
      try {
        const ano = await enviarJson<AnoFiscal>(
          'POST',
          `/api/v1/hoteles/${hotelId}/presupuesto/anos-fiscales`,
          { etiqueta: anoFiscal, mes_inicio: 7, mes_fin: 6 },
        )
        if (ano) {
          await enviarJson('POST', `/api/v1/hoteles/${hotelId}/presupuesto/anos-fiscales/${ano.id}/periodos/generar`)
          if (vigente) {
            setAnoCreado(ano)
            anosPresupuesto.recargar()
          }
        }
      } catch {
        // Sin año fiscal de Presupuesto el Budget sigue funcionando: solo no habrá ciclo.
      } finally {
        if (vigente) setCreandoAno(false)
      }
    })()
    return () => {
      vigente = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [existente, anoCreado, creandoAno, puedeAdministrarCiclo, hotelId, anoFiscal])

  const anoFiscalPresupuestoId = existente?.id ?? anoCreado?.id ?? null

  const [versionCiclo, setVersionCiclo] = useState(0)
  const recargarCiclo = () => setVersionCiclo((v) => v + 1)

  const ciclos = useDatos(
    () =>
      anoFiscalPresupuestoId === null
        ? Promise.resolve([])
        : obtenerTipado('/api/v1/hoteles/{hotel_id}/presupuesto/ciclos', {
            path: { hotel_id: hotelId },
            query: { ano_fiscal_id: anoFiscalPresupuestoId },
          }),
    [hotelId, anoFiscalPresupuestoId, versionCiclo],
  )
  const cicloAbierto = (ciclos.datos ?? []).find((c) => c.estado !== 'bloqueado') ?? null
  const cicloId = cicloAbierto?.id ?? null

  const cicloDetalle = useDatos(
    () =>
      cicloId === null
        ? Promise.resolve(null)
        : obtenerTipado('/api/v1/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}', {
            path: { hotel_id: hotelId, ciclo_id: cicloId },
          }),
    [hotelId, cicloId, versionCiclo],
  )
  const lineasCiclo = useDatos(
    () =>
      cicloId === null
        ? Promise.resolve([])
        : obtenerTipado('/api/v1/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}/lineas', {
            path: { hotel_id: hotelId, ciclo_id: cicloId },
          }),
    [hotelId, cicloId, versionCiclo],
  )
  const perfiles = useDatos(
    () =>
      cicloId === null
        ? Promise.resolve([])
        : obtenerTipado('/api/v1/hoteles/{hotel_id}/presupuesto/perfiles', { path: { hotel_id: hotelId } }),
    [hotelId, cicloId],
  )
  // Mismo `versionCiclo` que el resto del ciclo: Resumen y Captura nunca muestran datos de
  // versiones distintas entre sí.
  const resumenCiclo = useDatos(
    () =>
      cicloId === null
        ? Promise.resolve(null)
        : obtenerTipado('/api/v1/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}/resumen', {
            path: { hotel_id: hotelId, ciclo_id: cicloId },
          }),
    [hotelId, cicloId, versionCiclo],
  )
  const resumenMensualCiclo = useDatos(
    () =>
      cicloId === null
        ? Promise.resolve(null)
        : obtenerTipado('/api/v1/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}/resumen-mensual', {
            path: { hotel_id: hotelId, ciclo_id: cicloId },
          }),
    [hotelId, cicloId, versionCiclo],
  )

  const [abriendoCiclo, setAbriendoCiclo] = useState(false)
  const [errorCiclo, setErrorCiclo] = useState<string | null>(null)

  async function abrirCiclo() {
    if (anoFiscalPresupuestoId === null) return
    setAbriendoCiclo(true)
    setErrorCiclo(null)
    try {
      await enviarJson<Ciclo>('POST', `/api/v1/hoteles/${hotelId}/presupuesto/ciclos`, {
        ano_fiscal_id: anoFiscalPresupuestoId,
      })
      ciclos.recargar()
    } catch (e) {
      setErrorCiclo(e instanceof ErrorApi ? e.detalle : 'No se pudo abrir el ciclo')
    } finally {
      setAbriendoCiclo(false)
    }
  }

  const [ediciones, setEdiciones] = useState<ReadonlyMap<string, string>>(new Map())
  const [seccion, setSeccion] = useState<string>('')
  const [texto, setTexto] = useState('')
  const [soloEditables, setSoloEditables] = useState(false)
  // La hoja de sección (y, dentro de ella, la comparación anual o el editor mensual) está abierta: el encabezado
  // de Captura y el flujo del ciclo solo se ven en la pantalla principal de Captura.
  const [enPantallaInterna, setEnPantallaInterna] = useState(false)
  const [estadoCaptura, setEstadoCaptura] = useState<'todos' | 'pendiente' | 'capturada'>('todos')
  const [confirmando, setConfirmando] = useState(false)
  const [guardando, setGuardando] = useState(false)
  const [mensaje, setMensaje] = useState<Mensaje | null>(null)
  // La línea elegida sobrevive a recargar (guardar vuelve a montar la vista)
  const [lineaSeleccionada, setLineaSeleccionada] = useState<number | null>(null)
  // «Panel de línea» arranca cerrado y se conserva al guardar (la pantalla se vuelve a armar)
  const [panelOculto, setPanelOculto] = useState(true)
  const descripcionPorLinea = useMemo(
    () => new Map((vista.datos?.lineas ?? []).map((l) => [l.linea_id, l.descripcion])),
    [vista.datos],
  )

  if (vista.cargando) return <Cargando />
  if (vista.error || !vista.datos) {
    return (
      <section className="tarjeta">
        <h2>Budget {anoFiscal}</h2>
        <MensajeError texto={vista.error ?? 'No se pudo cargar el Budget'} />
        <p className="suave">
          Para editar el Budget hace falta la estructura del reporte y un mapeo aprobado.
        </p>
      </section>
    )
  }
  // Desde Resumen, "Ver en Captura"/clic en una barra lleva a la sección correspondiente (si se
  // reconoce por nombre): el filtro de sección en Captura ya vive aquí, no se duplica.
  function irACaptura(nombreSeccion?: string) {
    setPestana('captura')
    if (!nombreSeccion) return
    const encontrada = vista.datos?.secciones.find((s) => s.descripcion === nombreSeccion)
    if (encontrada) setSeccion(String(encontrada.id))
  }

  const periodos = vista.datos.periodos
  const rangoFiscal =
    periodos && periodos.length >= 12
      ? `${etiquetaMes(periodos[0])} – ${etiquetaMes(periodos[periodos.length - 1])}`
      : undefined

  const ocultarMarco = pestana === 'captura' && enPantallaInterna
  return (
    <>
      {!ocultarMarco && (
      <BudgetHeader
        anoFiscal={anoFiscal}
        rangoFiscal={rangoFiscal}
        version={vista.datos.version}
        puedeAdministrarCiclo={puedeAdministrarCiclo}
        cicloAbierto={cicloAbierto !== null || anoFiscalPresupuestoId === null}
        abriendoCiclo={abriendoCiclo}
        errorCiclo={errorCiclo}
        onAbrirCiclo={() => void abrirCiclo()}
        estadoCiclo={cicloDetalle.datos?.estado ?? null}
        cobertura={
          resumenCiclo.datos
            ? { capturadas: resumenCiclo.datos.lineas_capturadas, total: resumenCiclo.datos.total_lineas }
            : null
        }
      />
      )}
      {/* El flujo del ciclo (etapas, enviar a revisión, actividad) va en una barra pequeña en Resumen
          y en Captura, y no en Versiones, para no saturar la pantalla. */}
      {cicloId !== null && pestana !== 'versiones' && !ocultarMarco && (
        <CicloPresupuesto
          hotelId={hotelId}
          cicloId={cicloId}
          onVerVersiones={() => setPestana('versiones')}
          alCambiar={() => {
            recargarCiclo()
            alCambiarVersiones()
            vista.recargar()
          }}
        />
      )}
      {/* La navegación Resumen/Captura/Versiones vive en el sidebar global (App.tsx), como
         sub-navegación del bloque "Budget Studio" — ya no se repite aquí. Los paneles siguen
         señalando sus botones por id (role="tab" en el sidebar) para la relación aria-labelledby. */}

      <div role="tabpanel" id="budget-panel-resumen" aria-labelledby="budget-tab-resumen" hidden={pestana !== 'resumen'}>
        <BudgetResumen
          ciclo={cicloDetalle.datos ?? null}
          resumen={resumenCiclo.datos ?? null}
          resumenMensual={resumenMensualCiclo.datos ?? null}
          lineasCiclo={lineasCiclo.datos ?? []}
          cargando={resumenCiclo.cargando}
          error={resumenCiclo.error}
          onIrACaptura={irACaptura}
          onNavegarTab={setPestana}
        />
      </div>

      <div role="tabpanel" id="budget-panel-captura" aria-labelledby="budget-tab-captura" hidden={pestana !== 'captura'}>
        <VistaEditor
        datos={vista.datos}
        hotelId={hotelId}
        anoFiscal={anoFiscal}
        anos={anos}
        rol={rol}
        cicloId={cicloId}
        estadoCiclo={cicloDetalle.datos?.estado ?? null}
        lineasCiclo={lineasCiclo.datos ?? []}
        perfiles={perfiles.datos ?? []}
        alElegirAno={alElegirAno}
        ediciones={ediciones}
        setEdiciones={setEdiciones}
        seccion={seccion}
        setSeccion={setSeccion}
        texto={texto}
        setTexto={setTexto}
        soloEditables={soloEditables}
        setSoloEditables={setSoloEditables}
        estadoCaptura={estadoCaptura}
        setEstadoCaptura={setEstadoCaptura}
        confirmando={confirmando}
        setConfirmando={setConfirmando}
        guardando={guardando}
        setGuardando={setGuardando}
        mensaje={mensaje}
        setMensaje={setMensaje}
        lineaSeleccionada={lineaSeleccionada}
        setLineaSeleccionada={setLineaSeleccionada}
        panelOculto={panelOculto}
        setPanelOculto={setPanelOculto}
        recargar={() => {
          setEdiciones(new Map())
          setConfirmando(false)
          vista.recargar()
          alCambiarVersiones()
        }}
        recargarCiclo={recargarCiclo}
        alCambiarPantallaInterna={setEnPantallaInterna}
        />
      </div>

      <div role="tabpanel" id="budget-panel-versiones" aria-labelledby="budget-tab-versiones" hidden={pestana !== 'versiones'}>
        <BudgetVersionesTab
          hotelId={hotelId}
          versiones={versiones}
          descripcionPorLinea={descripcionPorLinea}
          cargando={false}
        />
      </div>
    </>
  )
}

interface PropsVista {
  datos: VistaEdicionBudget
  hotelId: number
  anoFiscal: string
  anos: string[]
  rol: string | undefined
  cicloId: number | null
  estadoCiclo: string | null
  lineasCiclo: LineaCaptura[]
  perfiles: Perfil[]
  alElegirAno: (ano: string) => void
  ediciones: ReadonlyMap<string, string>
  setEdiciones: (e: ReadonlyMap<string, string>) => void
  seccion: string
  setSeccion: (s: string) => void
  texto: string
  setTexto: (t: string) => void
  soloEditables: boolean
  setSoloEditables: (b: boolean) => void
  estadoCaptura: 'todos' | 'pendiente' | 'capturada'
  setEstadoCaptura: (e: 'todos' | 'pendiente' | 'capturada') => void
  confirmando: boolean
  setConfirmando: (b: boolean) => void
  guardando: boolean
  setGuardando: (b: boolean) => void
  mensaje: Mensaje | null
  setMensaje: (m: Mensaje | null) => void
  lineaSeleccionada: number | null
  setLineaSeleccionada: (id: number | null) => void
  panelOculto: boolean
  setPanelOculto: (oculto: boolean) => void
  recargar: () => void
  recargarCiclo: () => void
  /** Avisa si una pantalla interna (hoja de sección) está abierta, para ocultar el marco de Captura. */
  alCambiarPantallaInterna: (abierta: boolean) => void
}

function VistaEditor(p: PropsVista) {
  const { datos, ediciones } = p
  const periodos = datos.periodos
  const secciones = datos.secciones

  const puedeImportar = puede(p.rol, 'budget:importar')
  const puedeCapturar = puede(p.rol, 'budget:capturar')
  const puedeObjetivo = puede(p.rol, 'budget:objetivo')
  const cicloBorrador = p.cicloId !== null && p.estadoCiclo === 'borrador'
  const lineasPermitidas = useMemo(() => new Set(p.lineasCiclo.map((l) => l.linea_id)), [p.lineasCiclo])
  const objetivoPorLinea = useMemo(() => new Map(p.lineasCiclo.map((l) => [l.linea_id, l])), [p.lineasCiclo])
  // Cuándo "Guardar" alimenta el ciclo de captura en vez de crear una versión de Budget de una vez.
  const usaCaptura = cicloBorrador && puedeCapturar

  // Budget vigente por celda (lo que dice la versión guardada), para saber qué cambió
  const actuales = useMemo(() => {
    const m = new Map<string, bigint | null>()
    for (const l of datos.lineas) {
      for (const c of l.meses) {
        m.set(claveCelda(l.linea_id, c.periodo), c.budget === null ? null : aMicros(c.budget))
      }
    }
    return m
  }, [datos])

  // Budget en pantalla = el vigente con lo editado encima; los totales se recalculan de sus reglas
  const budgetEnPantalla = useMemo(() => {
    const salida = new Map<string, bigint | null>()
    for (const periodo of periodos) {
      const base = new Map<number, bigint>()
      for (const l of datos.lineas) {
        if (!l.editable && datos.reglas.some((r) => r.linea_id === l.linea_id)) continue
        const editado = ediciones.get(claveCelda(l.linea_id, periodo))
        const valor =
          editado !== undefined && editado.trim() !== ''
            ? aMicros(editado)
            : (actuales.get(claveCelda(l.linea_id, periodo)) ?? null)
        if (valor !== null) base.set(l.linea_id, valor)
      }
      for (const [linea, valor] of completarConTotales(datos.reglas, base)) {
        salida.set(claveCelda(linea, periodo), valor)
      }
    }
    return salida
  }, [datos, ediciones, actuales, periodos])

  // ¿Puede este usuario escribir el Budget de esta línea? Con captura por ciclo, solo las líneas que
  // el ciclo le deja ver (su sección); con acceso completo (budget:importar), todas como siempre.
  function puedeEditarBudget(linea: LineaEdicionBudget): boolean {
    if (!linea.editable) return false
    if (puedeImportar) return true
    return usaCaptura && lineasPermitidas.has(linea.linea_id)
  }

  const { cambios, invalidas: invalidasBudget } = useMemo(
    () => cambiosPendientes(ediciones, actuales),
    [ediciones, actuales],
  )

  // Actual capturado a mano que ya hay (lo que dice la base), para saber qué cambió
  const capturadosVigentes = useMemo(() => {
    const m = new Map<string, bigint | null>()
    for (const l of datos.lineas) {
      if (!l.actual_editable) continue
      for (const c of l.meses) {
        m.set(claveCelda(l.linea_id, c.periodo), c.actual === null ? null : aMicros(c.actual))
      }
    }
    return m
  }, [datos])
  const { cambios: cambiosActual, invalidas: invalidasActual } = useMemo(
    () => cambiosActualPendientes(ediciones, capturadosVigentes),
    [ediciones, capturadosVigentes],
  )
  const invalidas = [...invalidasBudget, ...invalidasActual]
  const totalCambios = cambios.length + cambiosActual.length

  const visibles = useMemo(() => {
    const buscado = p.texto.trim().toLowerCase()
    return datos.lineas.filter((l) => {
      if (p.seccion !== '' && p.seccion !== TODAS && String(l.seccion_id) !== p.seccion) return false
      if (p.soloEditables && !l.editable) return false
      if (p.estadoCaptura !== 'todos' && (objetivoPorLinea.get(l.linea_id)?.estado ?? 'pendiente') !== p.estadoCaptura) {
        return false
      }
      if (buscado === '') return true
      return (
        l.descripcion.toLowerCase().includes(buscado) ||
        (l.codigo_corporativo ?? '').toLowerCase().includes(buscado)
      )
    })
  }, [datos.lineas, p.seccion, p.texto, p.soloEditables, p.estadoCaptura, objetivoPorLinea])

  // Con una sola celda editable a la vez (el resto es texto), ver todas las secciones ya no pesa.
  const seccionActiva = p.seccion === '' ? TODAS : p.seccion
  const lineasMostradas = useMemo(
    () =>
      visibles.filter((l) => seccionActiva === TODAS || String(l.seccion_id) === seccionActiva),
    [visibles, seccionActiva],
  )
  const nombreSeccion = new Map(secciones.map((s) => [s.id, s.descripcion]))

  const [modo, setModo] = useState<'tabla' | 'arbol'>('tabla')
  const { lineaSeleccionada, setLineaSeleccionada, panelOculto, setPanelOculto } = p
  // Sección cuya hoja completa está abierta (página completa, como el Excel de Contraloría)
  // La cuenta con la que se abrió la hoja (si se entró por una cuenta, no por la sección)
  const [cuentaInicial, setCuentaInicial] = useState<number | null>(null)
  const [seccionHoja, setSeccionHoja] = useState<number | null>(null)
  const [celdaActiva, setCeldaActiva] = useState<{ linea: number; periodo: string } | null>(null)
  const [seccionesColapsadas, setSeccionesColapsadas] = useState<ReadonlySet<string>>(new Set())
  // El panel de detalle siempre muestra una línea: la elegida o, si no hay, la primera de detalle.
  const primeraDetalle = lineasMostradas.find((l) => l.tipo === 'detalle') ?? null
  const lineaDetalle = panelOculto
    ? null
    : (lineasMostradas.find((l) => l.linea_id === lineaSeleccionada) ?? primeraDetalle)
  function seleccionar(id: number) {
    setLineaSeleccionada(id)
    setPanelOculto(false)
  }
  function alternarSeccion(clave: string) {
    const siguiente = new Set(seccionesColapsadas)
    if (siguiente.has(clave)) siguiente.delete(clave)
    else siguiente.add(clave)
    setSeccionesColapsadas(siguiente)
  }
  // Líneas por las que se puede moverse con el teclado (editables y visibles)
  const navegables = lineasMostradas.filter(
    (l) => !seccionesColapsadas.has(String(l.seccion_id)) && puedeEditarBudget(l),
  )
  function moverCelda(linea: number, periodo: string, dLinea: number, dMes: number) {
    const i = navegables.findIndex((l) => l.linea_id === linea)
    const m = periodos.indexOf(periodo)
    if (i < 0 || m < 0) return
    const ni = Math.min(Math.max(i + dLinea, 0), navegables.length - 1)
    const nm = Math.min(Math.max(m + dMes, 0), periodos.length - 1)
    setCeldaActiva({ linea: navegables[ni].linea_id, periodo: periodos[nm] })
    setLineaSeleccionada(navegables[ni].linea_id)
  }

  function editar(linea: number, periodo: string, valor: string) {
    const siguiente = new Map(ediciones)
    siguiente.set(claveCelda(linea, periodo), valor)
    p.setEdiciones(siguiente)
    p.setMensaje(null)
    p.setConfirmando(false)
  }

  function rellenarMeses(linea: number, valores: LineaMensual[]) {
    const siguiente = new Map(ediciones)
    for (const v of valores) siguiente.set(claveCelda(linea, v.periodo), v.importe)
    p.setEdiciones(siguiente)
    p.setMensaje(null)
    p.setConfirmando(false)
    p.recargarCiclo()
  }

  function editarActual(linea: number, periodo: string, valor: string) {
    const siguiente = new Map(ediciones)
    siguiente.set(claveActual(linea, periodo), valor)
    p.setEdiciones(siguiente)
    p.setMensaje(null)
    p.setConfirmando(false)
  }

  async function guardarEnCiclo() {
    if (p.cicloId === null) return { capturadas: 0, mensualizadas: 0 }
    const lineasAfectadas = [...new Set(cambios.map((c) => c.linea_id))]
    let capturadas = 0
    let mensualizadas = 0
    for (const lineaId of lineasAfectadas) {
      const linea = datos.lineas.find((l) => l.linea_id === lineaId)
      if (!linea) continue
      const importes: Record<string, string> = {}
      let completo = true
      for (const c of linea.meses) {
        const valor = budgetEnPantalla.get(claveCelda(lineaId, c.periodo)) ?? null
        if (valor === null) {
          completo = false
          continue
        }
        importes[c.periodo] = textoDeMicros(valor)
      }
      const anual = sumaImportes(importes)
      if (anual === null) continue
      await enviarJson('PUT', `/api/v1/hoteles/${p.hotelId}/presupuesto/ciclos/${p.cicloId}/lineas/${lineaId}`, {
        propuesta_anual: anual,
        nota: null,
      })
      capturadas += 1
      if (completo && Object.keys(importes).length === periodos.length) {
        try {
          await enviarJson(
            'POST',
            `/api/v1/hoteles/${p.hotelId}/presupuesto/ciclos/${p.cicloId}/lineas/${lineaId}/importes-mensuales`,
            { importes },
          )
          mensualizadas += 1
        } catch {
          // El reparto mensual no cuadró: la propuesta anual ya quedó capturada, se puede
          // prorratear después (con un perfil, o editando los meses otra vez).
        }
      }
    }
    return { capturadas, mensualizadas }
  }

  async function guardar() {
    p.setGuardando(true)
    try {
      const partes: string[] = []
      if (cambiosActual.length > 0) {
        const n = await guardarActualesCapturados(p.hotelId, cambiosActual)
        partes.push(`${plural(n, 'Actual capturado', 'Actuales capturados')}`)
      }
      if (usaCaptura) {
        if (cambios.length > 0) {
          const { capturadas, mensualizadas } = await guardarEnCiclo()
          partes.push(
            `${plural(capturadas, 'línea capturada', 'líneas capturadas')} en el ciclo de presupuesto` +
              (mensualizadas > 0 ? ` (${mensualizadas} con su reparto mensual)` : ''),
          )
          p.recargarCiclo()
        }
      } else if (cambios.length > 0) {
        const r = await guardarVersionBudget(p.hotelId, {
          ano_fiscal: p.anoFiscal,
          base_version_id: datos.version?.id ?? null,
          cambios,
        })
        partes.push(
          `Budget guardado como versión ${r.version?.numero ?? ''} (la anterior queda en el historial)`,
        )
      }
      p.recargar()
      p.setMensaje({ tono: 'ok', texto: `Guardado: ${partes.join('; ')}.` })
    } catch (e) {
      p.setConfirmando(false)
      p.setMensaje({
        tono: 'error',
        texto:
          e instanceof ErrorApi
            ? e.estado === 409
              ? `${e.detalle}. Descarta tus cambios y recarga.`
              : e.detalle
            : 'No se pudo guardar el Budget',
      })
    } finally {
      p.setGuardando(false)
    }
  }

  const lineasConCambio = new Set([
    ...cambios.map((c) => c.linea_id),
    ...cambiosActual.map((c) => c.linea_id),
  ]).size
  const grupos = agruparPorSeccionId(lineasMostradas)
  // Las cuentas con tabla interna (hoy, las de Other Income) y solo con un ciclo abierto: ahí vive el detalle
  const tieneTabla = (l: LineaEdicionBudget) =>
    p.cicloId !== null &&
    l.tipo === 'detalle' &&
    l.seccion_id !== null &&
    seccionTieneTablaInterna(nombreSeccion.get(l.seccion_id))
  const tieneHoja = (seccionId: number | null) =>
    p.cicloId !== null &&
    seccionId !== null &&
    seccionTieneTablaInterna(nombreSeccion.get(seccionId)) &&
    datos.lineas.some((l) => l.seccion_id === seccionId && lineasPermitidas.has(l.linea_id))
  // Entrar por una cuenta lleva a la hoja de su sección, con esa cuenta ya abierta
  function abrirHojaDeCuenta(lineaId: number) {
    const linea = datos.lineas.find((l) => l.linea_id === lineaId)
    if (!linea || linea.seccion_id === null) return
    setCuentaInicial(lineaId)
    setSeccionHoja(linea.seccion_id)
  }
  const hojaAbierta = seccionHoja !== null && p.cicloId !== null && tieneHoja(seccionHoja)
  const { alCambiarPantallaInterna } = p
  useEffect(() => {
    alCambiarPantallaInterna(hojaAbierta)
    return () => alCambiarPantallaInterna(false)
  }, [hojaAbierta, alCambiarPantallaInterna])
  if (seccionHoja !== null && p.cicloId !== null && hojaAbierta) {
    return (
      <HojaSeccion
        key={seccionHoja}
        hotelId={p.hotelId}
        cicloId={p.cicloId}
        seccionId={seccionHoja}
        anoFiscal={p.anoFiscal}
        cuentaInicial={cuentaInicial}
        periodos={periodos}
        cuentas={datos.lineas.filter((l) => l.seccion_id === seccionHoja && tieneTabla(l))}
        puedeEditar={usaCaptura}
        alVolver={() => {
          setSeccionHoja(null)
          setCuentaInicial(null)
        }}
        alGuardarCuenta={(id, valores) => rellenarMeses(id, valores)}
        alCambiarCiclo={p.recargarCiclo}
        usaPartidas={new Set(p.lineasCiclo.filter((l) => l.usa_partidas || l.usa_consumo).map((l) => l.linea_id))}
      />
    )
  }
  return (
    <section className="captura-area" aria-labelledby="titulo-budget">
      {datos.advertencias.map((a) => (
        <p key={a} className="mensaje mensaje-aviso" role="status">
          {a}
        </p>
      ))}

      <div className="captura-trabajo captura-trabajo-sin-panel">
        <section className="tarjeta-tabla" aria-label="Líneas del presupuesto">
          <form className="barra-captura" role="search" onSubmit={(e) => e.preventDefault()}>
            <label className="campo-buscar">
              <span className="solo-lectores">Buscar línea o código</span>
              <Icono nombre="buscar" tamano={16} />
              <input
                type="search"
                aria-label="Buscar línea o código"
                placeholder="Buscar línea o código…"
                value={p.texto}
                onChange={(e) => p.setTexto(e.target.value)}
              />
            </label>
            <label className="campo-filtro">
              <span>Sección</span>
              <select aria-label="Sección" value={seccionActiva} onChange={(e) => p.setSeccion(e.target.value)}>
                <option value={TODAS}>Todas</option>
                {secciones.map((s) => (
                  <option key={s.id} value={String(s.id)}>
                    {s.descripcion}
                  </option>
                ))}
              </select>
            </label>
            <label className="campo-filtro">
              <span>Estado</span>
              <select
                aria-label="Estado de captura"
                value={p.estadoCaptura}
                onChange={(e) => p.setEstadoCaptura(e.target.value as 'todos' | 'pendiente' | 'capturada')}
              >
                <option value="todos">Todos</option>
                <option value="pendiente">Pendientes</option>
                <option value="capturada">Capturadas</option>
              </select>
            </label>
            <label className="interruptor toolbar-interruptor">
              <input
                type="checkbox"
                checked={p.soloEditables}
                onChange={(e) => p.setSoloEditables(e.target.checked)}
              />
              <span className="interruptor-pista" aria-hidden="true" />
              Solo editables
            </label>

            <div className="barra-captura-acciones">
              <div className="control-segmentado" role="group" aria-label="Vista de Captura">
                <button
                  type="button"
                  className={modo === 'tabla' ? 'activo' : ''}
                  aria-pressed={modo === 'tabla'}
                  onClick={() => {
                    setModo('tabla')
                    setSeccionesColapsadas(new Set())
                  }}
                >
                  Tabla
                </button>
                <button
                  type="button"
                  className={modo === 'arbol' ? 'activo' : ''}
                  aria-pressed={modo === 'arbol'}
                  onClick={() => {
                    setModo('arbol')
                    setSeccionesColapsadas(new Set(grupos.map((g) => String(g.seccionId))))
                  }}
                >
                  Árbol
                </button>
              </div>
              <details className="menu-flotante">
                <summary className="boton boton-secundario boton-chico">
                  <span>Herramientas</span>
                  <Icono nombre="chevron" tamano={12} />
                </summary>
                <div className="menu-flotante-panel menu-herramientas">
                  <button type="button" className="boton boton-secundario" onClick={() => setSeccionesColapsadas(new Set())}>
                    Expandir todas las secciones
                  </button>
                  <button
                    type="button"
                    className="boton boton-secundario"
                    onClick={() => setSeccionesColapsadas(new Set(grupos.map((g) => String(g.seccionId))))}
                  >
                    Contraer todas las secciones
                  </button>
                  <button
                    type="button"
                    className="boton boton-secundario"
                    onClick={() => {
                      p.setTexto('')
                      p.setSeccion(TODAS)
                      p.setEstadoCaptura('todos')
                      p.setSoloEditables(false)
                    }}
                  >
                    Limpiar filtros
                  </button>
                </div>
              </details>
              {puedeImportar && (
                <details className="menu-flotante menu-importar">
                  <summary className="boton boton-secundario boton-chico">
                    <Icono nombre="subir" tamano={14} />
                    <span>Importar Excel</span>
                  </summary>
                  <div className="menu-flotante-panel">
                    <ImportarExcel hotelId={p.hotelId} alImportar={p.recargar} hayCambios={totalCambios > 0} />
                  </div>
                </details>
              )}
            </div>
          </form>

          {p.mensaje && (
            <p
              className={`mensaje mensaje-${p.mensaje.tono === 'ok' ? 'ok' : p.mensaje.tono === 'error' ? 'error' : 'aviso'}`}
              role={p.mensaje.tono === 'error' ? 'alert' : 'status'}
            >
              {p.mensaje.texto}
            </p>
          )}

          {lineasMostradas.length === 0 && visibles.length === 0 && datos.lineas.length === 0 && (
            <EstadoVacio>No hay líneas que mostrar.</EstadoVacio>
          )}

          <div className="tabla-variance-contenedor" role="region" aria-label="Captura de Budget" tabIndex={0}>
            <table className={`tabla-variance tabla-budget tabla-budget-unificada${modo === 'arbol' ? ' modo-arbol' : ''}`}>
              <caption className="solo-lectores">
                Budget por mes. Haz clic en una celda de una línea de detalle para editarla; los totales se
                calculan solos y el Actual se ve al pasar el cursor. Selecciona una línea para ver su detalle.
              </caption>
              <thead>
                <tr>
                  <th scope="col" className="col-linea">
                    Línea / Código
                  </th>
                  <th scope="col" className="col-anual">
                    Anual
                  </th>
                  {periodos.map((per) => (
                    <th key={per} scope="col" className="col-mes">
                      {etiquetaMes(per)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {grupos.map((g) => {
                  const claveSeccion = String(g.seccionId)
                  return (
                    <GrupoFilas
                      key={`${g.seccionId}-${g.lineas[0].linea_id}`}
                      seccionId={g.seccionId}
                      titulo={g.seccionId === null ? null : (nombreSeccion.get(g.seccionId) ?? null)}
                      lineas={g.lineas}
                      periodos={periodos}
                      ediciones={ediciones}
                      budget={budgetEnPantalla}
                      objetivoPorLinea={objetivoPorLinea}
                      alEditar={editar}
                      puedeEditarBudget={puedeEditarBudget}
                      colapsada={seccionesColapsadas.has(claveSeccion)}
                      onAlternar={() => alternarSeccion(claveSeccion)}
                      seleccionada={lineaDetalle?.linea_id ?? null}
                      onSeleccionar={seleccionar}
                      celdaActiva={celdaActiva}
                      onActivar={(linea, periodo) => {
                        // Editar una celda no abre el panel; solo recuerda la línea por si lo abres
                        setCeldaActiva({ linea, periodo })
                        setLineaSeleccionada(linea)
                      }}
                      onDesactivar={(linea, periodo) =>
                        setCeldaActiva((a) => (a && a.linea === linea && a.periodo === periodo ? null : a))
                      }
                      onMover={moverCelda}
                      tieneTabla={tieneTabla}
                      tieneHoja={tieneHoja}
                      onAbrirHoja={(id) => {
                        setCuentaInicial(null)
                        setSeccionHoja(id)
                      }}
                      onAbrirTabla={(id) => {
                        setLineaSeleccionada(id)
                        abrirHojaDeCuenta(id)
                      }}
                    />
                  )
                })}
                {lineasMostradas.length === 0 && datos.lineas.length > 0 && (
                  <tr>
                    <td colSpan={periodos.length + 2}>Ninguna línea coincide con el filtro.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {lineaDetalle && (
          <DetalleCapturaLinea
            linea={lineaDetalle}
            periodos={periodos}
            ediciones={ediciones}
            budget={budgetEnPantalla}
            alEditarActual={editarActual}
            puedeEditarBudget={puedeEditarBudget(lineaDetalle)}
            puedeEditarActual={lineaDetalle.actual_editable && puedeImportar}
            captura={objetivoPorLinea.get(lineaDetalle.linea_id)}
            puedeObjetivo={puedeObjetivo && cicloBorrador && lineasPermitidas.has(lineaDetalle.linea_id)}
            hotelId={p.hotelId}
            cicloId={p.cicloId}
            perfiles={p.perfiles}
            puedeRellenarConPerfil={usaCaptura && lineasPermitidas.has(lineaDetalle.linea_id)}
            alRellenarMeses={rellenarMeses}
            alCambiarCiclo={p.recargarCiclo}
            alAbrirTabla={tieneTabla(lineaDetalle) ? () => abrirHojaDeCuenta(lineaDetalle.linea_id) : null}
            onCerrar={() => setPanelOculto(true)}
          />
        )}
      </div>

      {p.confirmando && (
        <div className="mensaje mensaje-aviso" role="status">
          <p>
            <strong>
              Vas a guardar {plural(totalCambios, 'cambio', 'cambios')} en{' '}
              {plural(lineasConCambio, 'línea', 'líneas')}.
            </strong>{' '}
            {usaCaptura && cambios.length > 0 && (
              <>Se manda tu propuesta al ciclo de presupuesto, línea por línea. </>
            )}
            {!usaCaptura && cambios.length > 0 && (
              <>
                Se crea la versión {(datos.version?.numero ?? 0) + 1} del Budget {p.anoFiscal}; la
                anterior queda en el historial.{' '}
              </>
            )}
            {cambiosActual.length > 0 && (
              <>Los Actuales capturados se guardan con tu nombre y quedan en la bitácora. </>
            )}
            {!usaCaptura && 'El Variance los usará de inmediato.'}
          </p>
          <button type="button" className="boton" disabled={p.guardando} onClick={() => void guardar()}>
            {p.guardando ? 'Guardando…' : 'Confirmar y guardar'}
          </button>{' '}
          <button type="button" className="boton boton-secundario" onClick={() => p.setConfirmando(false)}>
            Cancelar
          </button>
        </div>
      )}

      {(totalCambios > 0 || invalidas.length > 0) && (
        <div className="barra-cambios" role="status">
          <span className="barra-cambios-info" aria-hidden="true">
            i
          </span>
          <div className="barra-cambios-texto">
            <strong>
              {plural(totalCambios, 'cambio', 'cambios')} en {plural(lineasConCambio, 'línea', 'líneas')}
            </strong>
            <span className="suave">{plural(invalidas.length, 'celda inválida', 'celdas inválidas')}</span>
          </div>
          <ul className="barra-cambios-leyenda" aria-label="Leyenda de estados de celda">
            <li>
              <span className="punto punto-editado" aria-hidden="true" />
              Editado
            </li>
            <li>
              <span className="punto punto-invalido" aria-hidden="true" />
              Inválido
            </li>
            <li>
              <span className="punto punto-calculado" aria-hidden="true" />
              Calculado
            </li>
            <li>
              <Icono nombre="alerta" tamano={11} />
              Solo lectura
            </li>
          </ul>
          <div className="barra-cambios-acciones">
            <button
              type="button"
              className="boton boton-secundario"
              disabled={ediciones.size === 0 || p.guardando}
              onClick={() => {
                p.setEdiciones(new Map())
                p.setConfirmando(false)
                p.setMensaje(null)
              }}
            >
              Descartar cambios
            </button>
            <button
              type="button"
              className="boton"
              disabled={totalCambios === 0 || invalidas.length > 0 || p.guardando}
              onClick={() => p.setConfirmando(true)}
              title={usaCaptura ? 'Guarda la propuesta en el ciclo de presupuesto' : 'Crea una versión nueva del Budget'}
            >
              <Icono nombre="check" tamano={15} />
              Guardar cambios
            </button>
          </div>
        </div>
      )}
    </section>
  )
}

interface PropsGrupo {
  seccionId: number | null
  titulo: string | null
  lineas: LineaEdicionBudget[]
  periodos: string[]
  ediciones: ReadonlyMap<string, string>
  budget: ReadonlyMap<string, bigint | null>
  objetivoPorLinea: ReadonlyMap<number, LineaCaptura>
  alEditar: (linea: number, periodo: string, valor: string) => void
  puedeEditarBudget: (linea: LineaEdicionBudget) => boolean
  colapsada: boolean
  onAlternar: () => void
  seleccionada: number | null
  onSeleccionar: (linea: number) => void
  celdaActiva: { linea: number; periodo: string } | null
  onActivar: (linea: number, periodo: string) => void
  onDesactivar: (linea: number, periodo: string) => void
  onMover: (linea: number, periodo: string, dLinea: number, dMes: number) => void
  tieneTabla: (linea: LineaEdicionBudget) => boolean
  tieneHoja: (seccionId: number | null) => boolean
  onAbrirHoja: (seccionId: number) => void
  onAbrirTabla: (linea: number) => void
}

/** Importe con prefijo $ (columna Anual y totales de sección). */
const dinero = (micros: bigint | null) => (micros === null ? '—' : `$ ${formatoMicros(micros)}`)

/** Fila(s) de una sección: encabezado colapsable con totales (anual y por mes) y, si no está
 * colapsada, una fila por línea. Los totales se calculan solo sobre líneas de detalle (los
 * subtotales y totales del reporte ya agregan a esas mismas líneas: sumarlos duplicaría). */
function GrupoFilas({
  titulo,
  lineas,
  periodos,
  budget,
  objetivoPorLinea,
  colapsada,
  onAlternar,
  tieneHoja,
  onAbrirHoja,
  seccionId,
  ...resto
}: PropsGrupo) {
  const detalle = lineas.filter((l) => l.tipo === 'detalle')
  const totalMes = (periodo: string) =>
    sumarMicros(detalle.map((l) => budget.get(claveCelda(l.linea_id, periodo)) ?? null))
  const totalSeccion = sumarMicros(periodos.map((per) => totalMes(per)))
  const capturadas = lineas.filter((l) => objetivoPorLinea.get(l.linea_id)?.estado === 'capturada').length

  return (
    <>
      {titulo !== null && (
        <tr className="fila-seccion">
          <th scope="rowgroup" className="col-linea fila-seccion-celda">
            <button
              type="button"
              className="fila-seccion-boton"
              onClick={onAlternar}
              aria-expanded={!colapsada}
              title={`${capturadas}/${lineas.length} líneas capturadas`}
            >
              <Icono nombre="chevron" tamano={13} />
              <span>{titulo}</span>
            </button>
            {seccionId !== null && tieneHoja(seccionId) && (
              <button
                type="button"
                className="fila-seccion-hoja"
                onClick={() => onAbrirHoja(seccionId)}
                aria-label={`Abrir la hoja de ${titulo}`}
                title="Abrir la hoja completa de esta sección, como en el Excel"
              >
                <Icono nombre="informe" tamano={13} />
              </button>
            )}
          </th>
          <td className="num col-anual fila-seccion-anual">{dinero(totalSeccion)}</td>
          {periodos.map((per) => (
            <td key={per} className="num fila-seccion-mes">
              {formatoMicros(totalMes(per))}
            </td>
          ))}
        </tr>
      )}
      {!colapsada &&
        lineas.map((l) => (
          <FilaBudget
            key={l.linea_id}
            linea={l}
            periodos={periodos}
            budget={budget}
            {...resto}
          />
        ))}
    </>
  )
}

function FilaBudget({
  linea,
  ediciones,
  budget,
  alEditar,
  puedeEditarBudget,
  seleccionada,
  onSeleccionar,
  celdaActiva,
  onActivar,
  onDesactivar,
  onMover,
  tieneTabla,
  onAbrirTabla,
}: Omit<PropsGrupo, 'titulo' | 'lineas' | 'seccionId' | 'objetivoPorLinea' | 'colapsada' | 'onAlternar' | 'tieneHoja' | 'onAbrirHoja'> & {
  linea: LineaEdicionBudget
}) {
  const informativa = linea.tipo === 'informativa'
  const calculados = linea.meses.map((c) => budget.get(claveCelda(linea.linea_id, c.periodo)) ?? null)
  const editableBudget = puedeEditarBudget(linea)
  const anual = sumarMicros(calculados)
  const activa = seleccionada === linea.linea_id

  return (
    <tr className={`fila-${linea.tipo}${activa ? ' fila-activa' : ''}`}>
      <th scope="row" className="col-linea">
        <button
          type="button"
          className="fila-linea-boton"
          // El nombre abre las tablas de la cuenta (hoja); sin tablas, el detalle de la línea
          onClick={() => (tieneTabla(linea) ? onAbrirTabla(linea.linea_id) : onSeleccionar(linea.linea_id))}
          aria-current={activa ? 'true' : undefined}
          title={
            tieneTabla(linea)
              ? 'Abrir las tablas de esta cuenta'
              : 'Ver detalle, objetivo, nota y perfil de esta línea'
          }
        >
          <span className="linea-icono" aria-hidden="true">
            <Icono nombre={linea.editable ? 'presupuesto' : 'informe'} tamano={14} />
          </span>
          <span className="linea-textos">
            <span className="descripcion">{linea.descripcion}</span>
            {linea.codigo_corporativo && <span className="codigo">{linea.codigo_corporativo}</span>}
          </span>
        </button>
        <button
          type="button"
          className="fila-tabla-interna"
          onClick={() => onSeleccionar(linea.linea_id)}
          aria-label={`Ver el panel de línea de ${linea.descripcion}`}
          title="Ver detalle, objetivo, nota y perfil de esta línea"
        >
          <Icono nombre="info" tamano={14} />
        </button>
      </th>
      {/* un tipo de cambio no se suma: su "año" queda en blanco */}
      <td className="num col-anual celda-anual">{informativa ? '—' : dinero(anual)}</td>
      {linea.meses.map((c, i) => {
        const clave = claveCelda(linea.linea_id, c.periodo)
        const calculado = calculados[i]
        const editado = ediciones.get(clave)
        const hayEdicion = editado !== undefined
        const invalido = hayEdicion && editado.trim() !== '' && aMicros(editado) === null
        const microsEditado = hayEdicion && editado.trim() !== '' ? aMicros(editado) : null
        const mostrado = invalido ? editado : formatoMicros(hayEdicion && microsEditado !== null ? microsEditado : calculado)
        const actualMicros = c.actual === null ? null : aMicros(c.actual)
        const origen =
          c.actual_origen === 'manual'
            ? 'capturado a mano'
            : c.actual_origen === 'excel'
              ? 'del Excel de Contraloría'
              : 'sin capturar'
        const activaCelda = celdaActiva?.linea === linea.linea_id && celdaActiva.periodo === c.periodo
        const nombre = `Budget de ${linea.descripcion}, ${etiquetaMes(c.periodo)}`
        const clases = [
          'celda-mes',
          hayEdicion ? 'celda-editada' : '',
          invalido ? 'celda-invalida' : '',
          !editableBudget ? (linea.editable ? 'celda-solo-lectura' : 'celda-calculada') : '',
        ]
          .filter(Boolean)
          .join(' ')
        return (
          <td key={c.periodo} className={clases} title={`Actual: ${formatoMicros(actualMicros)} (${origen})`}>
            {editableBudget && activaCelda ? (
              <input
                type="text"
                inputMode="decimal"
                className="entrada-celda"
                aria-label={nombre}
                aria-invalid={invalido || undefined}
                // eslint-disable-next-line jsx-a11y/no-autofocus
                autoFocus
                value={editado ?? (calculado === null ? '' : textoDeMicros(calculado))}
                onChange={(e) => alEditar(linea.linea_id, c.periodo, e.target.value)}
                onBlur={() => onDesactivar(linea.linea_id, c.periodo)}
                onKeyDown={(e) => {
                  if (e.key === 'Escape') {
                    e.preventDefault()
                    onDesactivar(linea.linea_id, c.periodo)
                  } else if (e.key === 'Enter' || e.key === 'ArrowDown') {
                    e.preventDefault()
                    onMover(linea.linea_id, c.periodo, 1, 0)
                  } else if (e.key === 'ArrowUp') {
                    e.preventDefault()
                    onMover(linea.linea_id, c.periodo, -1, 0)
                  } else if (e.key === 'Tab') {
                    e.preventDefault()
                    onMover(linea.linea_id, c.periodo, 0, e.shiftKey ? -1 : 1)
                  }
                }}
              />
            ) : editableBudget ? (
              <button type="button" className="celda-valor" aria-label={nombre} onClick={() => onActivar(linea.linea_id, c.periodo)}>
                {mostrado}
              </button>
            ) : (
              <span className="celda-valor">{mostrado}</span>
            )}
          </td>
        )
      })}
    </tr>
  )
}

function ImportarExcel({
  hotelId,
  alImportar,
  hayCambios,
}: {
  hotelId: number
  alImportar: () => void
  hayCambios: boolean
}) {
  const [archivo, setArchivo] = useState<File | null>(null)
  const [enviando, setEnviando] = useState(false)
  const [respuesta, setRespuesta] = useState<RespuestaBudget | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function enviar(confirmar: boolean) {
    if (!archivo) return
    setEnviando(true)
    setError(null)
    try {
      const r = await importarBudgetExcel(hotelId, archivo, confirmar)
      setRespuesta(r)
      if (r.resolucion === 'creada' || r.resolucion === 'reemplazada') alImportar()
    } catch (e) {
      setRespuesta(null)
      setError(e instanceof ErrorApi ? e.detalle : 'No se pudo importar el archivo')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <details className="importar-budget">
      <summary>Importar el Budget desde el Excel de Contraloría (punto de partida)</summary>
      <p className="suave">
        Sube el Excel del Variance con el Budget de cada mes; después puedes corregirlo aquí. Si ya hay
        un Budget vigente, se pide confirmación y la versión anterior se conserva.
        {hayCambios && ' Tienes cambios sin guardar: se perderían al importar.'}
      </p>
      <label>
        Excel del Variance (.xlsx)
        <input
          type="file"
          accept=".xlsx"
          onChange={(e) => {
            setArchivo(e.target.files?.[0] ?? null)
            setRespuesta(null)
            setError(null)
          }}
        />
      </label>{' '}
      <button type="button" className="boton" disabled={!archivo || enviando} onClick={() => void enviar(false)}>
        {enviando ? 'Importando…' : 'Importar Budget'}
      </button>
      {error && <MensajeError texto={error} />}
      {respuesta && (
        <div
          className={`mensaje mensaje-${respuesta.resolucion === 'rechazada' ? 'error' : 'aviso'}`}
          role={respuesta.resolucion === 'rechazada' ? 'alert' : 'status'}
        >
          {respuesta.resolucion === 'requiere_confirmacion' && (
            <>
              <p>{respuesta.motivos.join(' ')}</p>
              <button type="button" className="boton" disabled={enviando} onClick={() => void enviar(true)}>
                Confirmar reemplazo
              </button>
            </>
          )}
          {respuesta.resolucion === 'rechazada' && <p>{respuesta.motivos.join(' ')}</p>}
          {respuesta.resolucion === 'duplicada' && <p>Ese archivo ya estaba importado: no cambió nada.</p>}
          {(respuesta.resolucion === 'creada' || respuesta.resolucion === 'reemplazada') && (
            <p>
              Budget importado como versión {respuesta.version?.numero} (formato{' '}
              {respuesta.formato === 'mzt' ? 'Mazatlán' : 'Vallarta'}).
            </p>
          )}
          {respuesta.avisos.map((a) => (
            <p key={a} className="suave">
              {a}
            </p>
          ))}
        </div>
      )}
    </details>
  )
}
