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
import { ArbolLineas } from './componentes/ArbolLineas'
import { BudgetHeader } from './componentes/BudgetHeader'
import { BudgetResumen } from './componentes/BudgetResumen'
import { BudgetTabs, type PestanaBudget } from './componentes/BudgetTabs'
import { BudgetVersionesTab } from './componentes/BudgetVersionesTab'
import { DetalleCapturaLinea } from './componentes/DetalleCapturaLinea'
import { SelectorPerfilDistribucion } from './componentes/SelectorPerfilDistribucion'
import { CicloPresupuesto } from './CicloPresupuesto'
import {
  agruparPorSeccionId,
  ajustarPorcentaje,
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

type AnoFiscal = components['schemas']['AnoFiscalSalida']
type Ciclo = components['schemas']['CicloSalida']
type LineaCaptura = components['schemas']['LineaCapturaSalida']
type Perfil = components['schemas']['PerfilSalida']
type LineaMensual = components['schemas']['LineaMensualSalida']
type VersionBudget = components['schemas']['VersionPlanSalida']

interface Props {
  hotelId: number
  rol: string | undefined
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
export function PanelBudget({ hotelId, rol }: Props) {
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
}

function EditorBudget({ hotelId, anoFiscal, anos, rol, versiones, alElegirAno, alCambiarVersiones }: PropsEditor) {
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

  const [pestana, setPestana] = useState<PestanaBudget>('resumen')

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
  const [porcentaje, setPorcentaje] = useState('')
  const [soloVacios, setSoloVacios] = useState(true)
  const [confirmando, setConfirmando] = useState(false)
  const [guardando, setGuardando] = useState(false)
  const [mensaje, setMensaje] = useState<Mensaje | null>(null)
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

  return (
    <>
      <BudgetHeader
        anoFiscal={anoFiscal}
        rangoFiscal={rangoFiscal}
        version={vista.datos.version}
        puedeAdministrarCiclo={puedeAdministrarCiclo}
        cicloAbierto={cicloAbierto !== null || anoFiscalPresupuestoId === null}
        abriendoCiclo={abriendoCiclo}
        errorCiclo={errorCiclo}
        onAbrirCiclo={() => void abrirCiclo()}
        onVerVersiones={() => setPestana('versiones')}
      />
      {cicloId !== null && (
        <CicloPresupuesto
          hotelId={hotelId}
          cicloId={cicloId}
          alCambiar={() => {
            recargarCiclo()
            alCambiarVersiones()
            vista.recargar()
          }}
        />
      )}
      <BudgetTabs activa={pestana} onCambiar={setPestana} />

      <div role="tabpanel" id="budget-panel-resumen" aria-labelledby="budget-tab-resumen" hidden={pestana !== 'resumen'}>
        <BudgetResumen
          ciclo={cicloDetalle.datos ?? null}
          resumen={resumenCiclo.datos ?? null}
          resumenMensual={resumenMensualCiclo.datos ?? null}
          lineasCiclo={lineasCiclo.datos ?? []}
          perfiles={perfiles.datos ?? []}
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
        porcentaje={porcentaje}
        setPorcentaje={setPorcentaje}
        soloVacios={soloVacios}
        setSoloVacios={setSoloVacios}
        confirmando={confirmando}
        setConfirmando={setConfirmando}
        guardando={guardando}
        setGuardando={setGuardando}
        mensaje={mensaje}
        setMensaje={setMensaje}
        recargar={() => {
          setEdiciones(new Map())
          setConfirmando(false)
          vista.recargar()
          alCambiarVersiones()
        }}
        recargarCiclo={recargarCiclo}
        />
      </div>

      <div role="tabpanel" id="budget-panel-versiones" aria-labelledby="budget-tab-versiones" hidden={pestana !== 'versiones'}>
        <BudgetVersionesTab hotelId={hotelId} versiones={versiones} descripcionPorLinea={descripcionPorLinea} />
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
  porcentaje: string
  setPorcentaje: (t: string) => void
  soloVacios: boolean
  setSoloVacios: (b: boolean) => void
  confirmando: boolean
  setConfirmando: (b: boolean) => void
  guardando: boolean
  setGuardando: (b: boolean) => void
  mensaje: Mensaje | null
  setMensaje: (m: Mensaje | null) => void
  recargar: () => void
  recargarCiclo: () => void
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
      return buscado === '' || l.descripcion.toLowerCase().includes(buscado)
    })
  }, [datos.lineas, p.seccion, p.texto, p.soloEditables])

  // Por omisión se muestra una sección a la vez: el reporte tiene cientos de líneas por 12 meses
  const seccionActiva = p.seccion === '' ? String(secciones[0]?.id ?? TODAS) : p.seccion
  const lineasMostradas = useMemo(
    () =>
      visibles.filter((l) => seccionActiva === TODAS || String(l.seccion_id) === seccionActiva),
    [visibles, seccionActiva],
  )
  const nombreSeccion = new Map(secciones.map((s) => [s.id, s.descripcion]))

  const [vistaCaptura, setVistaCaptura] = useState<'tabla' | 'arbol'>('tabla')
  const [lineaSeleccionada, setLineaSeleccionada] = useState<number | null>(null)
  const lineaDetalle = datos.lineas.find((l) => l.linea_id === lineaSeleccionada) ?? null

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

  function copiarActual() {
    const ajuste = p.porcentaje.trim()
    if (ajuste !== '' && ajustarPorcentaje(1_000_000n, ajuste) === null) {
      p.setMensaje({ tono: 'error', texto: 'El porcentaje de ajuste no es un número válido' })
      return
    }
    const siguiente = new Map(ediciones)
    let copiadas = 0
    for (const l of lineasMostradas) {
      // el tipo de cambio (informativa) tiene su propio Budget: no se copia de su Actual
      if (!puedeEditarBudget(l) || l.tipo === 'informativa') continue
      for (const c of l.meses) {
        if (c.actual === null) continue
        const clave = claveCelda(l.linea_id, c.periodo)
        const tieneBudget = (actuales.get(clave) ?? null) !== null || ediciones.has(clave)
        if (p.soloVacios && tieneBudget) continue
        const base = aMicros(c.actual)
        const nuevo = base === null ? null : ajustarPorcentaje(base, ajuste)
        if (nuevo === null) continue
        siguiente.set(clave, textoDeMicros(nuevo))
        copiadas += 1
      }
    }
    p.setEdiciones(siguiente)
    p.setConfirmando(false)
    p.setMensaje({
      tono: copiadas > 0 ? 'ok' : 'aviso',
      texto:
        copiadas > 0
          ? `Se copió el Actual en ${plural(copiadas, 'celda', 'celdas')} (sin guardar todavía).`
          : 'No había celdas a las que copiar el Actual (sin movimientos, o ya tenían Budget).',
    })
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

  return (
    <section aria-labelledby="titulo-budget">
      <details className="notas-reporte" open={!datos.version}>
        <summary>Cómo funciona</summary>
        <p className="suave nota-pie">
          Escribe el Budget de cada mes; el <strong>Actual</strong> aparece al lado como referencia.
          Los totales se calculan solos.{' '}
          {usaCaptura ? (
            <>
              Hay un <strong>ciclo de presupuesto abierto</strong>: Guardar manda tu propuesta a ese
              ciclo (por línea); el Budget oficial se crea cuando el ciclo se aprueba.
            </>
          ) : (
            <>
              Guardar crea una <strong>versión nueva</strong>: la anterior se conserva.
            </>
          )}{' '}
          Las líneas sin cuentas (como el <strong>Exchange Rate</strong>) también dejan escribir su
          Actual de cada mes.
        </p>
      </details>
      {datos.advertencias.map((a) => (
        <p key={a} className="mensaje mensaje-aviso" role="status">
          {a}
        </p>
      ))}

      {puedeImportar && <ImportarExcel hotelId={p.hotelId} alImportar={p.recargar} hayCambios={totalCambios > 0} />}

      <form className="barra-filtros" role="search" onSubmit={(e) => e.preventDefault()}>
        <div className="filtro-campo">
          <span className="filtro-etiqueta">Año fiscal</span>
          <select aria-label="Año fiscal" value={p.anoFiscal} onChange={(e) => p.alElegirAno(e.target.value)}>
            {p.anos.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </div>
        <div className="filtro-campo">
          <span className="filtro-etiqueta">Sección</span>
          <select aria-label="Sección" value={seccionActiva} onChange={(e) => p.setSeccion(e.target.value)}>
            <option value={TODAS}>Todas (más lento)</option>
            {secciones.map((s) => (
              <option key={s.id} value={String(s.id)}>
                {s.descripcion}
              </option>
            ))}
          </select>
        </div>
        <label className="filtro-campo filtro-busqueda">
          <span className="filtro-etiqueta">Buscar línea</span>
          <span className="campo-busqueda">
            <Icono nombre="buscar" tamano={16} />
            <input
              type="search"
              aria-label="Buscar línea"
              value={p.texto}
              onChange={(e) => p.setTexto(e.target.value)}
            />
          </span>
        </label>
        <div className="filtro-interruptores">
          <label className="interruptor">
            <input
              type="checkbox"
              checked={p.soloEditables}
              onChange={(e) => p.setSoloEditables(e.target.checked)}
            />
            <span className="interruptor-pista" aria-hidden="true" />
            Solo líneas editables
          </label>
        </div>
      </form>

      <div className="selector-bloque" role="group" aria-label="Vista de Captura">
        <button
          type="button"
          className={vistaCaptura === 'tabla' ? 'chip chip-activo' : 'chip'}
          aria-pressed={vistaCaptura === 'tabla'}
          onClick={() => setVistaCaptura('tabla')}
        >
          Tabla
        </button>
        <button
          type="button"
          className={vistaCaptura === 'arbol' ? 'chip chip-activo' : 'chip'}
          aria-pressed={vistaCaptura === 'arbol'}
          onClick={() => setVistaCaptura('arbol')}
        >
          Árbol
        </button>
      </div>

      {puedeImportar && (
        <div className="barra-filtros herramienta-copiar" role="group" aria-label="Copiar el Actual">
          <div className="filtro-campo">
            <span className="filtro-etiqueta">Ajuste sobre el Actual (%)</span>
            <input
              type="text"
              inputMode="decimal"
              aria-label="Ajuste sobre el Actual (%)"
              placeholder="0"
              value={p.porcentaje}
              onChange={(e) => p.setPorcentaje(e.target.value)}
            />
          </div>
          <div className="filtro-interruptores">
            <label className="interruptor">
              <input
                type="checkbox"
                checked={p.soloVacios}
                onChange={(e) => p.setSoloVacios(e.target.checked)}
              />
              <span className="interruptor-pista" aria-hidden="true" />
              Solo meses sin Budget
            </label>
          </div>
          <button type="button" className="boton boton-secundario" onClick={copiarActual}>
            Copiar el Actual a las líneas que se ven
          </button>
        </div>
      )}

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
      {vistaCaptura === 'tabla' ? (
      <div className="tabla-variance-contenedor" role="region" aria-label="Tabla de Budget" tabIndex={0}>
        <table className="tabla-variance tabla-budget">
          <caption className="solo-lectores">
            Budget por mes con el Actual de referencia. Las celdas de Budget de las líneas de detalle
            se pueden editar; los totales se calculan solos.
          </caption>
          <thead>
            <tr>
              <th scope="col" rowSpan={2} className="col-linea">
                Línea
              </th>
              {periodos.map((per) => (
                <th key={per} scope="colgroup" colSpan={2} className="grupo-bloque">
                  {etiquetaMes(per)}
                </th>
              ))}
              <th scope="colgroup" colSpan={2} className="grupo-bloque">
                Año
              </th>
              {puedeObjetivo || objetivoPorLinea.size > 0 ? (
                <th scope="col" rowSpan={2}>
                  Objetivo
                </th>
              ) : null}
            </tr>
            <tr>
              {[...periodos, 'año'].flatMap((per) => [
                <th key={`${per}-b`} scope="col" className={per === periodos[0] ? '' : 'inicio-mes'}>
                  Budget
                </th>,
                <th key={`${per}-a`} scope="col">
                  Actual
                </th>,
              ])}
            </tr>
          </thead>
          <tbody>
            {grupos.map((g) => (
              <GrupoFilas
                key={`${g.seccionId}-${g.lineas[0].linea_id}`}
                titulo={g.seccionId === null ? null : (nombreSeccion.get(g.seccionId) ?? null)}
                lineas={g.lineas}
                periodos={periodos}
                ediciones={ediciones}
                budget={budgetEnPantalla}
                alEditar={editar}
                alEditarActual={editarActual}
                puedeEditarBudget={puedeEditarBudget}
                puedeEditarActual={(l) => l.actual_editable && puedeImportar}
                mostrarObjetivo={puedeObjetivo || objetivoPorLinea.size > 0}
                objetivoPorLinea={objetivoPorLinea}
                puedeObjetivo={puedeObjetivo && cicloBorrador}
                hotelId={p.hotelId}
                cicloId={p.cicloId}
                perfiles={p.perfiles}
                puedeRellenarConPerfil={usaCaptura}
                lineasPermitidas={lineasPermitidas}
                alRellenarMeses={rellenarMeses}
                alCambiarCiclo={p.recargarCiclo}
              />
            ))}
            {lineasMostradas.length === 0 && datos.lineas.length > 0 && (
              <tr>
                <td colSpan={periodos.length * 2 + 3}>Ninguna línea coincide con el filtro.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      ) : (
      <div className="captura-split">
        <ArbolLineas
          grupos={grupos}
          nombreSeccion={nombreSeccion}
          periodos={periodos}
          budget={budgetEnPantalla}
          objetivoPorLinea={objetivoPorLinea}
          seleccionada={lineaSeleccionada}
          onSeleccionar={setLineaSeleccionada}
        />
        {lineaDetalle ? (
          <DetalleCapturaLinea
            linea={lineaDetalle}
            periodos={periodos}
            ediciones={ediciones}
            budget={budgetEnPantalla}
            alEditar={editar}
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
          />
        ) : (
          <EstadoVacio>Elige una línea del árbol para capturarla.</EstadoVacio>
        )}
      </div>
      )}

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
      <div className="acciones-budget acciones-fijas">
        <span className="suave" role="status">
          {totalCambios === 0
            ? 'Sin cambios.'
            : `${plural(totalCambios, 'cambio', 'cambios')} en ${plural(lineasConCambio, 'línea', 'líneas')} sin guardar.`}
          {invalidas.length > 0 && ` ${plural(invalidas.length, 'celda', 'celdas')} con un importe no válido.`}
        </span>
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
        >
          {usaCaptura ? 'Guardar en el ciclo de presupuesto' : 'Guardar como versión nueva'}
        </button>
      </div>

    </section>
  )
}

interface PropsGrupo {
  titulo: string | null
  lineas: LineaEdicionBudget[]
  periodos: string[]
  ediciones: ReadonlyMap<string, string>
  budget: ReadonlyMap<string, bigint | null>
  alEditar: (linea: number, periodo: string, valor: string) => void
  alEditarActual: (linea: number, periodo: string, valor: string) => void
  puedeEditarBudget: (linea: LineaEdicionBudget) => boolean
  puedeEditarActual: (linea: LineaEdicionBudget) => boolean
  mostrarObjetivo: boolean
  objetivoPorLinea: ReadonlyMap<number, LineaCaptura>
  puedeObjetivo: boolean
  hotelId: number
  cicloId: number | null
  perfiles: Perfil[]
  puedeRellenarConPerfil: boolean
  lineasPermitidas: ReadonlySet<number>
  alRellenarMeses: (linea: number, valores: LineaMensual[]) => void
  alCambiarCiclo: () => void
}

function GrupoFilas({ titulo, lineas, periodos, ...resto }: PropsGrupo) {
  return (
    <>
      {titulo !== null && (
        <tr className="fila-seccion">
          <th scope="rowgroup" colSpan={periodos.length * 2 + (resto.mostrarObjetivo ? 4 : 3)} className="col-linea">
            {titulo}
          </th>
        </tr>
      )}
      {lineas.map((l) => (
        <FilaBudget key={l.linea_id} linea={l} {...resto} />
      ))}
    </>
  )
}

function FilaBudget({
  linea,
  ediciones,
  budget,
  alEditar,
  alEditarActual,
  puedeEditarBudget,
  puedeEditarActual,
  mostrarObjetivo,
  objetivoPorLinea,
  puedeObjetivo,
  hotelId,
  cicloId,
  perfiles,
  puedeRellenarConPerfil,
  lineasPermitidas,
  alRellenarMeses,
  alCambiarCiclo,
}: Omit<PropsGrupo, 'titulo' | 'lineas' | 'periodos'> & { linea: LineaEdicionBudget }) {
  const informativa = linea.tipo === 'informativa'
  const calculados = linea.meses.map((c) => budget.get(claveCelda(linea.linea_id, c.periodo)) ?? null)
  const actuales = linea.meses.map((c) => (c.actual === null ? null : aMicros(c.actual)))
  const editableBudget = puedeEditarBudget(linea)
  const editableActual = puedeEditarActual(linea)
  const anualActual = sumarMicros(calculados)
  const puedeRellenar =
    puedeRellenarConPerfil &&
    linea.tipo === 'detalle' &&
    cicloId !== null &&
    lineasPermitidas.has(linea.linea_id) &&
    perfiles.length > 0 &&
    anualActual !== null
  const captura = objetivoPorLinea.get(linea.linea_id)

  return (
    <tr className={`fila-${linea.tipo}`}>
      <th scope="row" className="col-linea">
        <span className="descripcion">{linea.descripcion}</span>
        {linea.codigo_corporativo && <span className="codigo suave"> {linea.codigo_corporativo}</span>}
        {puedeRellenar && cicloId !== null && anualActual !== null && (
          <SelectorPerfilDistribucion
            hotelId={hotelId}
            cicloId={cicloId}
            linea={linea.linea_id}
            anual={textoDeMicros(anualActual)}
            perfiles={perfiles}
            periodos={linea.meses.map((c) => c.periodo)}
            alAplicar={(valores) => alRellenarMeses(linea.linea_id, valores)}
          />
        )}
      </th>
      {linea.meses.flatMap((c, i) => {
        const clave = claveCelda(linea.linea_id, c.periodo)
        const calculado = calculados[i]
        const editado = ediciones.get(clave)
        const invalido = editado !== undefined && editado.trim() !== '' && aMicros(editado) === null
        const inicio = i === 0 ? '' : ' inicio-mes'
        const celdaBudget = editableBudget ? (
          <td key={`${c.periodo}-b`} className={`num${inicio}${editado !== undefined ? ' editada' : ''}`}>
            <input
              type="text"
              inputMode="decimal"
              className={invalido ? 'entrada-budget entrada-invalida' : 'entrada-budget'}
              aria-label={`Budget de ${linea.descripcion}, ${etiquetaMes(c.periodo)}`}
              aria-invalid={invalido || undefined}
              placeholder="—"
              value={editado ?? (calculado === null ? '' : textoDeMicros(calculado))}
              onChange={(e) => alEditar(linea.linea_id, c.periodo, e.target.value)}
            />
          </td>
        ) : (
          <td key={`${c.periodo}-b`} className={`num${inicio}`}>
            {formatoMicros(calculado)}
          </td>
        )
        const claveA = claveActual(linea.linea_id, c.periodo)
        const editadoA = ediciones.get(claveA)
        const invalidoA = editadoA !== undefined && editadoA.trim() !== '' && aMicros(editadoA) === null
        const celdaActual = editableActual ? (
          <td
            key={`${c.periodo}-a`}
            className={`num${editadoA !== undefined ? ' editada' : ''}`}
            title={
              c.actual_origen === 'manual'
                ? 'Capturado a mano'
                : c.actual_origen === 'excel'
                  ? 'Viene del Excel de Contraloría'
                  : 'Sin capturar'
            }
          >
            <input
              type="text"
              inputMode="decimal"
              className={invalidoA ? 'entrada-budget entrada-invalida' : 'entrada-budget'}
              aria-label={`Actual de ${linea.descripcion}, ${etiquetaMes(c.periodo)}`}
              aria-invalid={invalidoA || undefined}
              placeholder="—"
              value={editadoA ?? (actuales[i] === null ? '' : textoDeMicros(actuales[i]))}
              onChange={(e) => alEditarActual(linea.linea_id, c.periodo, e.target.value)}
            />
          </td>
        ) : (
          <td key={`${c.periodo}-a`} className="num suave">
            {formatoMicros(actuales[i])}
          </td>
        )
        return [celdaBudget, celdaActual]
      })}
      {/* un tipo de cambio no se suma: su "año" queda en blanco */}
      <td className="num inicio-mes">{informativa ? '—' : formatoMicros(sumarMicros(calculados))}</td>
      <td className="num suave">{informativa ? '—' : formatoMicros(sumarMicros(actuales))}</td>
      {mostrarObjetivo && (
        <td>
          {cicloId !== null && captura ? (
            <ObjetivoCelda
              hotelId={hotelId}
              cicloId={cicloId}
              linea={linea.linea_id}
              descripcion={linea.descripcion}
              objetivoInicial={captura.objetivo}
              puedeEditar={puedeObjetivo && lineasPermitidas.has(linea.linea_id)}
              alGuardar={alCambiarCiclo}
            />
          ) : (
            <span className="suave">—</span>
          )}
        </td>
      )}
    </tr>
  )
}

export function ObjetivoCelda({
  hotelId,
  cicloId,
  linea,
  descripcion,
  objetivoInicial,
  puedeEditar,
  alGuardar,
}: {
  hotelId: number
  cicloId: number
  linea: number
  descripcion: string
  objetivoInicial: string | null
  puedeEditar: boolean
  alGuardar: () => void
}) {
  const [valor, setValor] = useState(objetivoInicial ?? '')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const cambio = valor !== (objetivoInicial ?? '')

  if (!puedeEditar) return <span>{objetivoInicial ?? '—'}</span>

  async function guardar() {
    setGuardando(true)
    setError(null)
    try {
      await enviarJson(
        'PUT',
        `/api/v1/hoteles/${hotelId}/presupuesto/ciclos/${cicloId}/lineas/${linea}/objetivo`,
        { objetivo: valor.trim() === '' ? null : valor },
      )
      alGuardar()
    } catch (e) {
      setError(e instanceof ErrorApi ? e.detalle : 'No se pudo guardar el objetivo')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="campo-con-boton">
      <input
        type="text"
        inputMode="decimal"
        aria-label={`Objetivo de ${descripcion}`}
        value={valor}
        onChange={(e) => setValor(e.target.value)}
      />
      <button
        type="button"
        className="boton boton-secundario"
        disabled={!cambio || guardando}
        onClick={() => void guardar()}
      >
        Guardar
      </button>
      {error && <MensajeError texto={error} />}
    </div>
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
