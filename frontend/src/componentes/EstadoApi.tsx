import { useEffect, useState } from 'react'

const REINTENTO_MS = 2000

type Estado = 'conectando' | 'ok' | 'error'

/** Indicador de salud de la API; reintenta si aún está arrancando. */
export function EstadoApi() {
  const [estado, setEstado] = useState<Estado>('conectando')

  useEffect(() => {
    const controlador = new AbortController()
    let temporizador: ReturnType<typeof setTimeout> | undefined
    const consultar = () => {
      fetch('/api/health', { signal: controlador.signal })
        .then((r) => {
          if (!r.ok) throw new Error(`HTTP ${r.status}`)
          setEstado('ok')
        })
        .catch((e: Error) => {
          if (e.name === 'AbortError') return
          setEstado('error')
          temporizador = setTimeout(consultar, REINTENTO_MS)
        })
    }
    consultar()
    return () => {
      controlador.abort()
      if (temporizador) clearTimeout(temporizador)
    }
  }, [])

  const texto =
    estado === 'ok' ? 'API conectada' : estado === 'error' ? 'API sin respuesta · reintentando…' : 'Conectando…'
  return (
    <span className={`estado-api estado-api-${estado}`} title={texto}>
      <span className="estado-api-punto" aria-hidden="true" />
      <span className="solo-lectores">{texto}</span>
    </span>
  )
}
