import { useMemo, useState } from 'react'
import {
  ErrorApi,
  guardarActualesCapturados,
  guardarVersionBudget,
  importarBudgetExcel,
  obtenerTipado,
} from '../../api/cliente'
import { useDatos } from '../../api/useDatos'
import type { LineaEdicionBudget, RespuestaBudget, VistaEdicionBudget } from '../../api/tipos'
import { Cargando, Insignia, MensajeError } from '../../componentes/Insignia'
import {
  agruparPorSeccionId,
  ajustarPorcentaje,
  aMicros,
  cambiosActualPendientes,
  cambiosPendientes,
  claveActual,
  claveCelda,
  completarConTotales,
  etiquetaAnoFiscal,
  formatoMicros,
  textoDeMicros,
} from './calculo'

interface Props {
  hotelId: number
}

const MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
const TODAS = 'todas'

const plural = (n: number, uno: string, varios: string) => `${n} ${n === 1 ? uno : varios}`

const etiquetaMes = (periodo: string) => `${MESES[Number(periodo.slice(5, 7)) - 1]} ${periodo.slice(2, 4)}`

type Mensaje = { tono: 'ok' | 'aviso' | 'error'; texto: string }

/** Pantalla de Budget: editar el Budget mes a mes con el Actual al lado como referencia. */
export function PanelBudget({ hotelId }: Props) {
  // El año fiscal por omisión sale del último mes cargado; el Budget vigente puede ser de otro.
  const cargas = useDatos(
    () => obtenerTipado('/api/v1/hoteles/{hotel_id}/cargas', { path: { hotel_id: hotelId } }),
    [hotelId],
  )
  const versiones = useDatos(
    () => obtenerTipado('/api/v1/hoteles/{hotel_id}/budget/versiones', { path: { hotel_id: hotelId } }),
    [hotelId],
  )
  const [elegido, setElegido] = useState<string | null>(null)
  const anos = useMemo(() => {
    const salida = new Set<string>()
    for (const v of versiones.datos ?? []) salida.add(v.ano_fiscal)
    for (const c of cargas.datos ?? []) if (c.estado === 'vigente') salida.add(etiquetaAnoFiscal(c.periodo))
    return [...salida].sort().reverse()
  }, [versiones.datos, cargas.datos])
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
      alElegirAno={setElegido}
      alCambiarVersiones={versiones.recargar}
    />
  )
}

interface PropsEditor {
  hotelId: number
  anoFiscal: string
  anos: string[]
  alElegirAno: (ano: string) => void
  alCambiarVersiones: () => void
}

function EditorBudget({ hotelId, anoFiscal, anos, alElegirAno, alCambiarVersiones }: PropsEditor) {
  const vista = useDatos(
    () =>
      obtenerTipado('/api/v1/hoteles/{hotel_id}/budget/edicion', {
        path: { hotel_id: hotelId },
        query: { ano_fiscal: anoFiscal },
      }),
    [hotelId, anoFiscal],
  )
  const [ediciones, setEdiciones] = useState<ReadonlyMap<string, string>>(new Map())
  const [seccion, setSeccion] = useState<string>('')
  const [texto, setTexto] = useState('')
  const [soloEditables, setSoloEditables] = useState(false)
  const [porcentaje, setPorcentaje] = useState('')
  const [soloVacios, setSoloVacios] = useState(true)
  const [confirmando, setConfirmando] = useState(false)
  const [guardando, setGuardando] = useState(false)
  const [mensaje, setMensaje] = useState<Mensaje | null>(null)

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
  return (
    <VistaEditor
      datos={vista.datos}
      hotelId={hotelId}
      anoFiscal={anoFiscal}
      anos={anos}
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
    />
  )
}

interface PropsVista {
  datos: VistaEdicionBudget
  hotelId: number
  anoFiscal: string
  anos: string[]
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
}

function VistaEditor(p: PropsVista) {
  const { datos, ediciones } = p
  const periodos = datos.periodos
  const secciones = datos.secciones

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

  function editar(linea: number, periodo: string, valor: string) {
    const siguiente = new Map(ediciones)
    siguiente.set(claveCelda(linea, periodo), valor)
    p.setEdiciones(siguiente)
    p.setMensaje(null)
    p.setConfirmando(false)
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
      if (!l.editable || l.tipo === 'informativa') continue
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

  async function guardar() {
    p.setGuardando(true)
    try {
      const partes: string[] = []
      if (cambiosActual.length > 0) {
        const n = await guardarActualesCapturados(p.hotelId, cambiosActual)
        partes.push(`${plural(n, 'Actual capturado', 'Actuales capturados')}`)
      }
      if (cambios.length > 0) {
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
    <section className="tarjeta" aria-labelledby="titulo-budget">
      <h2 id="titulo-budget">Budget {p.anoFiscal}</h2>
      <p className="suave">
        Escribe el Budget de cada mes; el <strong>Actual</strong> aparece al lado como referencia. Los
        totales se calculan solos. Guardar crea una <strong>versión nueva</strong>: la anterior se
        conserva. Las líneas sin cuentas (como el <strong>Exchange Rate</strong>) también dejan
        escribir su Actual de cada mes.{' '}
        {datos.version ? (
          <Insignia tono="info">Versión {datos.version.numero} · {datos.version.nombre_archivo}</Insignia>
        ) : (
          <Insignia tono="aviso">Todavía no hay Budget para este año</Insignia>
        )}
      </p>
      {datos.advertencias.map((a) => (
        <p key={a} className="mensaje mensaje-aviso" role="status">
          {a}
        </p>
      ))}

      <ImportarExcel hotelId={p.hotelId} alImportar={p.recargar} hayCambios={totalCambios > 0} />

      <div className="filtros">
        <label>
          Año fiscal
          <select value={p.anoFiscal} onChange={(e) => p.alElegirAno(e.target.value)}>
            {p.anos.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </label>
        <label>
          Sección
          <select value={seccionActiva} onChange={(e) => p.setSeccion(e.target.value)}>
            <option value={TODAS}>Todas (más lento)</option>
            {secciones.map((s) => (
              <option key={s.id} value={String(s.id)}>
                {s.descripcion}
              </option>
            ))}
          </select>
        </label>
        <label>
          Buscar línea
          <input type="search" value={p.texto} onChange={(e) => p.setTexto(e.target.value)} />
        </label>
        <label className="casilla">
          <input
            type="checkbox"
            checked={p.soloEditables}
            onChange={(e) => p.setSoloEditables(e.target.checked)}
          />
          Solo líneas editables
        </label>
      </div>

      <div className="filtros" role="group" aria-label="Copiar el Actual">
        <label>
          Ajuste sobre el Actual (%)
          <input
            type="text"
            inputMode="decimal"
            placeholder="0"
            value={p.porcentaje}
            onChange={(e) => p.setPorcentaje(e.target.value)}
          />
        </label>
        <label className="casilla">
          <input
            type="checkbox"
            checked={p.soloVacios}
            onChange={(e) => p.setSoloVacios(e.target.checked)}
          />
          Solo meses sin Budget
        </label>
        <button type="button" className="boton boton-secundario" onClick={copiarActual}>
          Copiar el Actual a las líneas que se ven
        </button>
      </div>

      {p.mensaje && (
        <p
          className={`mensaje mensaje-${p.mensaje.tono === 'ok' ? 'ok' : p.mensaje.tono === 'error' ? 'error' : 'aviso'}`}
          role={p.mensaje.tono === 'error' ? 'alert' : 'status'}
        >
          {p.mensaje.texto}
        </p>
      )}

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
              />
            ))}
            {lineasMostradas.length === 0 && (
              <tr>
                <td colSpan={periodos.length * 2 + 3}>Ninguna línea coincide con el filtro.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="acciones-budget">
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
          Guardar como versión nueva
        </button>
      </div>

      {p.confirmando && (
        <div className="mensaje mensaje-aviso" role="status">
          <p>
            <strong>
              Vas a guardar {plural(totalCambios, 'cambio', 'cambios')} en{' '}
              {plural(lineasConCambio, 'línea', 'líneas')}.
            </strong>{' '}
            {cambios.length > 0 && (
              <>
                Se crea la versión {(datos.version?.numero ?? 0) + 1} del Budget {p.anoFiscal}; la
                anterior queda en el historial.{' '}
              </>
            )}
            {cambiosActual.length > 0 && (
              <>Los Actuales capturados se guardan con tu nombre y quedan en la bitácora. </>
            )}
            El Variance los usará de inmediato.
          </p>
          <button type="button" className="boton" disabled={p.guardando} onClick={() => void guardar()}>
            {p.guardando ? 'Guardando…' : 'Confirmar y guardar'}
          </button>{' '}
          <button type="button" className="boton boton-secundario" onClick={() => p.setConfirmando(false)}>
            Cancelar
          </button>
        </div>
      )}
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
}

function GrupoFilas({
  titulo,
  lineas,
  periodos,
  ediciones,
  budget,
  alEditar,
  alEditarActual,
}: PropsGrupo) {
  return (
    <>
      {titulo !== null && (
        <tr className="fila-seccion">
          <th scope="rowgroup" colSpan={periodos.length * 2 + 3} className="col-linea">
            {titulo}
          </th>
        </tr>
      )}
      {lineas.map((l) => (
        <FilaBudget
          key={l.linea_id}
          linea={l}
          ediciones={ediciones}
          budget={budget}
          alEditar={alEditar}
          alEditarActual={alEditarActual}
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
  alEditarActual,
}: Omit<PropsGrupo, 'titulo' | 'lineas' | 'periodos'> & { linea: LineaEdicionBudget }) {
  const informativa = linea.tipo === 'informativa'
  const calculados = linea.meses.map((c) => budget.get(claveCelda(linea.linea_id, c.periodo)) ?? null)
  const actuales = linea.meses.map((c) => (c.actual === null ? null : aMicros(c.actual)))
  const sumar = (valores: (bigint | null)[]) => {
    const con = valores.filter((v): v is bigint => v !== null)
    return con.length === 0 ? null : con.reduce((a, v) => a + v, 0n)
  }
  return (
    <tr className={`fila-${linea.tipo}`}>
      <th scope="row" className="col-linea">
        <span className="descripcion">{linea.descripcion}</span>
        {linea.codigo_corporativo && <span className="codigo suave"> {linea.codigo_corporativo}</span>}
      </th>
      {linea.meses.flatMap((c, i) => {
        const clave = claveCelda(linea.linea_id, c.periodo)
        const calculado = calculados[i]
        const editado = ediciones.get(clave)
        const invalido = editado !== undefined && editado.trim() !== '' && aMicros(editado) === null
        const inicio = i === 0 ? '' : ' inicio-mes'
        const celdaBudget = linea.editable ? (
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
        const celdaActual = linea.actual_editable ? (
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
      <td className="num inicio-mes">{informativa ? '—' : formatoMicros(sumar(calculados))}</td>
      <td className="num suave">{informativa ? '—' : formatoMicros(sumar(actuales))}</td>
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
