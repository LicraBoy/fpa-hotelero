import { useEffect, useState } from 'react'

type Estado =
  | { tipo: 'cargando' }
  | { tipo: 'ok'; app: string; version: string }
  | { tipo: 'error'; mensaje: string }

const REINTENTO_MS = 2000

export default function App() {
  const [estado, setEstado] = useState<Estado>({ tipo: 'cargando' })

  useEffect(() => {
    const controlador = new AbortController()
    let temporizador: ReturnType<typeof setTimeout> | undefined

    // Si la API aún está arrancando, reintenta en vez de quedarse en error.
    const consultar = () => {
      fetch('/api/health', { signal: controlador.signal })
        .then((r) => {
          if (!r.ok) throw new Error(`HTTP ${r.status}`)
          return r.json()
        })
        .then((d) => setEstado({ tipo: 'ok', app: d.app, version: d.version }))
        .catch((e: Error) => {
          if (e.name === 'AbortError') return
          setEstado({ tipo: 'error', mensaje: e.message })
          temporizador = setTimeout(consultar, REINTENTO_MS)
        })
    }
    consultar()

    return () => {
      controlador.abort()
      if (temporizador) clearTimeout(temporizador)
    }
  }, [])

  return (
    <main className="pagina">
      <h1>Plataforma FP&amp;A Hotelera</h1>
      <p className="sub">Torres Mazatlán</p>
      <section className="tarjeta" aria-live="polite">
        {estado.tipo === 'cargando' && <p>Conectando con la API…</p>}
        {estado.tipo === 'ok' && (
          <p className="ok">
            API conectada: {estado.app} v{estado.version}
          </p>
        )}
        {estado.tipo === 'error' && (
          <p className="error">
            No se pudo conectar con la API ({estado.mensaje}). Reintentando… Si persiste, revisa la
            ventana del backend.
          </p>
        )}
      </section>
    </main>
  )
}
