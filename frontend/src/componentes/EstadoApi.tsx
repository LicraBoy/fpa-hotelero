import { useEffect, useState } from 'react'
import { Insignia } from './Insignia'

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

  if (estado === 'ok') return <Insignia tono="ok">API conectada</Insignia>
  if (estado === 'error') return <Insignia tono="error">API sin respuesta · reintentando…</Insignia>
  return <Insignia tono="neutro">Conectando…</Insignia>
}
