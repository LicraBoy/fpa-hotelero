import { useCallback, useSyncExternalStore } from 'react'
import { construirRuta, parsearRuta, type Ruta } from './ruta'

function suscribir(avisar: () => void): () => void {
  window.addEventListener('hashchange', avisar)
  return () => window.removeEventListener('hashchange', avisar)
}

const hashActual = () => window.location.hash

/** La ruta actual (de la barra de direcciones) y una función para navegar. */
export function useRuta(): { ruta: Ruta; navegar: (destino: Ruta) => void } {
  const hash = useSyncExternalStore(suscribir, hashActual)
  const navegar = useCallback((destino: Ruta) => {
    window.location.hash = construirRuta(destino)
  }, [])
  return { ruta: parsearRuta(hash), navegar }
}
