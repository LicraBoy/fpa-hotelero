import { useState, type FormEvent } from 'react'
import { ErrorApi, importarCatalogo } from '../api/cliente'
import type { RespuestaImportacion } from '../api/tipos'
import { MensajeError } from './Insignia'

type Resultado =
  | { tipo: 'ninguno' }
  | { tipo: 'respuesta'; cuerpo: RespuestaImportacion }
  | { tipo: 'error'; mensaje: string }

function Lista({ titulo, codigos }: { titulo: string; codigos: string[] }) {
  if (codigos.length === 0) return null
  return (
    <details>
      <summary>
        {titulo} ({codigos.length})
      </summary>
      <p className="suave">{codigos.join(', ')}</p>
    </details>
  )
}

export function ImportarCatalogo({ hotelId, alCambiar }: { hotelId: number; alCambiar: () => void }) {
  const [archivo, setArchivo] = useState<File | null>(null)
  const [enviando, setEnviando] = useState(false)
  const [resultado, setResultado] = useState<Resultado>({ tipo: 'ninguno' })

  async function enviar(ev: FormEvent) {
    ev.preventDefault()
    if (!archivo) return
    setEnviando(true)
    try {
      const { cuerpo } = await importarCatalogo(hotelId, archivo)
      setResultado({ tipo: 'respuesta', cuerpo })
      if (cuerpo.resolucion === 'importado') alCambiar()
    } catch (e) {
      setResultado({
        tipo: 'error',
        mensaje: e instanceof ErrorApi ? e.detalle : 'No se pudo enviar el archivo',
      })
    } finally {
      setEnviando(false)
    }
  }

  return (
    <section className="tarjeta" aria-labelledby="titulo-importar-catalogo">
      <h2 id="titulo-importar-catalogo">Importar catálogo oficial</h2>
      <p className="suave">
        Reporte “Catálogo Contable” (CON020) de Novohit, en formato .xls. Trae los nombres de la
        jerarquía, si la cuenta es Deudor o Acreedor, el departamento y el código SAT.
      </p>
      <form onSubmit={(ev) => void enviar(ev)} className="formulario">
        <label>
          Catálogo (.xls)
          <input
            type="file"
            accept=".xls"
            onChange={(e) => {
              setArchivo(e.target.files?.[0] ?? null)
              setResultado({ tipo: 'ninguno' })
            }}
          />
        </label>
        <div>
          <button type="submit" className="boton" disabled={!archivo || enviando}>
            {enviando ? 'Importando…' : 'Importar catálogo'}
          </button>
        </div>
      </form>

      {resultado.tipo === 'error' && <MensajeError texto={resultado.mensaje} />}
      {resultado.tipo === 'respuesta' && resultado.cuerpo.resolucion === 'rechazado' && (
        <div className="mensaje mensaje-error" role="alert">
          <p>
            <strong>El catálogo se rechazó.</strong> No se guardó nada.
          </p>
          <ul>
            {resultado.cuerpo.motivos.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </div>
      )}
      {resultado.tipo === 'respuesta' && resultado.cuerpo.resolucion === 'sin_cambio' && (
        <p className="mensaje mensaje-info" role="status">
          Este catálogo ya estaba importado. No se cambió nada.
        </p>
      )}
      {resultado.tipo === 'respuesta' && resultado.cuerpo.resolucion === 'importado' && (
        <div className="mensaje mensaje-ok" role="status">
          <p>
            <strong>Catálogo importado.</strong> {resultado.cuerpo.total_cuentas} cuentas y{' '}
            {resultado.cuerpo.total_titulos} títulos: {resultado.cuerpo.creadas} nuevos,{' '}
            {resultado.cuerpo.actualizadas} actualizados, {resultado.cuerpo.sin_cambio} sin cambio.
          </p>
          <Lista
            titulo="Cuentas con movimientos que no están en el catálogo oficial"
            codigos={resultado.cuerpo.fuera_del_catalogo}
          />
          <Lista
            titulo="Cuentas inactivas que tienen movimientos"
            codigos={resultado.cuerpo.inactivas_con_movimientos}
          />
          <Lista titulo="Avisos" codigos={resultado.cuerpo.avisos} />
        </div>
      )}
    </section>
  )
}
