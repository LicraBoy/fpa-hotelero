import { useCallback, useEffect, useState } from 'react'
import { ErrorApi } from './cliente'

export interface EstadoDatos<T> {
  datos: T | null
  error: string | null
  cargando: boolean
  recargar: () => void
}

/** Carga datos de la API cuando cambian las dependencias; expone `recargar`. */
export function useDatos<T>(cargar: () => Promise<T>, dependencias: unknown[]): EstadoDatos<T> {
  const [datos, setDatos] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [cargando, setCargando] = useState(true)
  const [version, setVersion] = useState(0)

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const funcion = useCallback(cargar, dependencias)

  useEffect(() => {
    let vigente = true
    setCargando(true)
    funcion()
      .then((d) => {
        if (!vigente) return
        setDatos(d)
        setError(null)
      })
      .catch((e: unknown) => {
        if (!vigente) return
        setDatos(null)
        setError(e instanceof ErrorApi ? e.detalle : 'No se pudo cargar la información')
      })
      .finally(() => {
        if (vigente) setCargando(false)
      })
    return () => {
      vigente = false
    }
  }, [funcion, version])

  return { datos, error, cargando, recargar: () => setVersion((v) => v + 1) }
}
