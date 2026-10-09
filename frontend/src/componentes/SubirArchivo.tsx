import { useState, type FormEvent } from 'react'
import { ErrorApi, subirCarga } from '../api/cliente'
import type { Fuente, RespuestaCarga } from '../api/tipos'
import { formatoDinero } from '../util/dinero'
import { EncabezadoPagina } from './EncabezadoPagina'
import { Insignia, MensajeError } from './Insignia'
import { ReporteCalidadVista } from './ReporteCalidadVista'

// Desde la 4.10 la única fuente que se sube por pantalla es el CON130 de Novohit: el sistema deduce
// de él la cuenta, la fecha y el mes de cada movimiento (lo que antes hacían las fórmulas del Excel).
// La fuente `variance_base_datos` sigue existiendo en la API (demostración y pruebas), no aquí.
const FUENTE: Fuente = 'con130'
const NOMBRE_FUENTE = 'CON130 · Mayor Analítico (Novohit)'
const AYUDA_FUENTE =
  'Reporte exportado de Novohit, tal cual, en .xls, .xlsx o .csv. El sistema toma de él la cuenta, ' +
  'la fecha y el mes de cada movimiento; no hace falta agregarle fórmulas ni columnas.'

interface Props {
  hotelId: number
  alCambiar: () => void
}

type Resultado =
  | { tipo: 'ninguno' }
  | { tipo: 'respuesta'; estado: number; cuerpo: RespuestaCarga }
  | { tipo: 'error'; mensaje: string }

export function SubirArchivo({ hotelId, alCambiar }: Props) {
  const [archivo, setArchivo] = useState<File | null>(null)
  const [periodos, setPeriodos] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [resultado, setResultado] = useState<Resultado>({ tipo: 'ninguno' })

  async function enviar(confirmarReemplazo: boolean) {
    if (!archivo) return
    setEnviando(true)
    try {
      const { estado, cuerpo } = await subirCarga(hotelId, {
        archivo,
        fuente: FUENTE,
        confirmarReemplazo,
        periodos,
      })
      setResultado({ tipo: 'respuesta', estado, cuerpo })
      if (cuerpo.resolucion === 'creada' || cuerpo.resolucion === 'reemplazada') alCambiar()
    } catch (e) {
      setResultado({
        tipo: 'error',
        mensaje: e instanceof ErrorApi ? e.detalle : 'No se pudo enviar el archivo',
      })
    } finally {
      setEnviando(false)
    }
  }

  function alEnviar(ev: FormEvent) {
    ev.preventDefault()
    void enviar(false)
  }

  return (
    <section className="tarjeta" aria-labelledby="titulo-subir">
      <EncabezadoPagina
        id="titulo-subir"
        titulo="Subir archivo"
        subtitulo="Cuatro pasos: fuente, archivo, validación y resultado."
      />
      <form onSubmit={alEnviar} className="formulario formulario-pasos" aria-busy={enviando}>
        <ol className="pasos">
          <li className="paso">
            <span className="paso-num" aria-hidden="true">
              1
            </span>
            <div className="paso-cuerpo">
              <h3>Fuente</h3>
              <p>
                <strong>{NOMBRE_FUENTE}</strong>
              </p>
              <p className="suave">{AYUDA_FUENTE}</p>
              <p className="formatos">
                <span className="suave">Formatos permitidos</span>
                <Insignia tono="info">.xls</Insignia>
                <Insignia tono="info">.xlsx</Insignia>
                <Insignia tono="info">.csv</Insignia>
              </p>
            </div>
          </li>
          <li className="paso">
            <span className="paso-num" aria-hidden="true">
              2
            </span>
            <div className="paso-cuerpo">
              <h3>Archivo</h3>
              <label>
                Archivo (.xls, .xlsx o .csv)
                <input
                  type="file"
                  accept=".xls,.xlsx,.csv"
                  onChange={(e) => {
                    setArchivo(e.target.files?.[0] ?? null)
                    setResultado({ tipo: 'ninguno' })
                  }}
                />
                {archivo && (
                  <span className="archivo-elegido">
                    {archivo.name} · {Math.max(1, Math.round(archivo.size / 1024)).toLocaleString('es-MX')} KB
                  </span>
                )}
              </label>
            </div>
          </li>
          <li className="paso">
            <span className="paso-num" aria-hidden="true">
              3
            </span>
            <div className="paso-cuerpo">
              <h3>Validar y subir</h3>
              <label>
                Meses que declara el archivo (opcional)
                <input
                  type="text"
                  placeholder="2026-07,2026-08"
                  value={periodos}
                  onChange={(e) => setPeriodos(e.target.value)}
                />
                <span className="suave">
                  Si lo llenas, cualquier movimiento fuera de esos meses rechaza la carga.
                </span>
              </label>
              <div>
                <button type="submit" className="boton" disabled={!archivo || enviando}>
                  {enviando ? 'Enviando…' : 'Subir y validar'}
                </button>
              </div>
            </div>
          </li>
        </ol>
      </form>
      <ResultadoVista
        resultado={resultado}
        enviando={enviando}
        alConfirmar={() => void enviar(true)}
      />
    </section>
  )
}

function ResultadoVista({
  resultado,
  enviando,
  alConfirmar,
}: {
  resultado: Resultado
  enviando: boolean
  alConfirmar: () => void
}) {
  if (resultado.tipo === 'ninguno') return null
  if (resultado.tipo === 'error') return <MensajeError texto={resultado.mensaje} />
  const { cuerpo } = resultado

  if (cuerpo.resolucion === 'requiere_confirmacion') {
    return (
      <div className="mensaje mensaje-aviso" role="status">
        <p>
          <strong>Ya hay datos cargados para estos meses con otro archivo.</strong> Si confirmas, la
          carga anterior queda en el historial como reemplazada y se usan los datos nuevos.
        </p>
        <table className="tabla">
          <thead>
            <tr>
              <th>Mes</th>
              <th>Archivo vigente</th>
              <th className="num">Movimientos hoy</th>
              <th className="num">Movimientos nuevos</th>
              <th className="num">Débito hoy</th>
              <th className="num">Débito nuevo</th>
              <th className="num">Crédito hoy</th>
              <th className="num">Crédito nuevo</th>
            </tr>
          </thead>
          <tbody>
            {cuerpo.conflictos.map((c) => (
              <tr key={c.periodo}>
                <td>{c.periodo}</td>
                <td>{c.archivo_vigente}</td>
                <td className="num">{c.n_vigente}</td>
                <td className="num">{c.n_nuevo}</td>
                <td className="num">{formatoDinero(c.debito_vigente)}</td>
                <td className="num">{formatoDinero(c.debito_nuevo)}</td>
                <td className="num">{formatoDinero(c.credito_vigente)}</td>
                <td className="num">{formatoDinero(c.credito_nuevo)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <button type="button" className="boton boton-peligro" onClick={alConfirmar} disabled={enviando}>
          Confirmar reemplazo
        </button>
      </div>
    )
  }

  if (cuerpo.resolucion === 'rechazada') {
    return (
      <div className="mensaje mensaje-error" role="alert">
        <p>
          <strong>El archivo se rechazó.</strong> No se guardó nada.
        </p>
        <ul>
          {cuerpo.motivos.map((m) => (
            <li key={m}>{m}</li>
          ))}
        </ul>
        {cuerpo.reporte && <ReporteCalidadVista reporte={cuerpo.reporte} />}
      </div>
    )
  }

  if (cuerpo.resolucion === 'duplicada') {
    return (
      <p className="mensaje mensaje-info" role="status">
        Este archivo ya estaba cargado ({cuerpo.sin_cambio.join(', ')}). No se cambió nada.
      </p>
    )
  }

  return (
    <div className="mensaje mensaje-ok" role="status">
      <p>
        <strong>{cuerpo.resolucion === 'reemplazada' ? 'Carga reemplazada' : 'Carga creada'}.</strong>{' '}
        {cuerpo.sin_cambio.length > 0 && `Sin cambio: ${cuerpo.sin_cambio.join(', ')}.`}
      </p>
      <ul>
        {cuerpo.cargas.map((c) => (
          <li key={c.id}>
            <Insignia tono="ok">{c.periodo}</Insignia> {c.n_movimientos} movimientos · Débito{' '}
            {formatoDinero(c.total_debito)} · Crédito {formatoDinero(c.total_credito)}
          </li>
        ))}
      </ul>
      {cuerpo.reporte && <ReporteCalidadVista reporte={cuerpo.reporte} />}
    </div>
  )
}
