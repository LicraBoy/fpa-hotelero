import { useEffect, useState } from 'react'

export interface ColoresTema {
  suave: string
  primario: string
  /** Hasta 6 tonos de marca ya existentes (--primario/--acento/--ok/--aviso/--error/--suave), para
   * series categóricas (p. ej. un pastel por sección) — nunca la paleta por defecto de Plotly. */
  paletaSerie: string[]
}

const RESPALDO: ColoresTema = {
  suave: '#64748b',
  primario: '#2563eb',
  paletaSerie: ['#2563eb', '#0f766e', '#16a34a', '#d97706', '#dc2626', '#64748b'],
}

function leer(): ColoresTema {
  if (typeof document === 'undefined') return RESPALDO
  const estilo = getComputedStyle(document.documentElement)
  const token = (nombre: string, respaldo: string) => estilo.getPropertyValue(nombre).trim() || respaldo
  return {
    suave: token('--suave', RESPALDO.suave),
    primario: token('--primario', RESPALDO.primario),
    paletaSerie: [
      token('--primario', RESPALDO.paletaSerie[0]),
      token('--acento', RESPALDO.paletaSerie[1]),
      token('--ok', RESPALDO.paletaSerie[2]),
      token('--aviso', RESPALDO.paletaSerie[3]),
      token('--error', RESPALDO.paletaSerie[4]),
      token('--suave', RESPALDO.paletaSerie[5]),
    ],
  }
}

/**
 * Los mismos dos colores de la app, nunca la paleta categórica de Plotly (la haría ver una
 * plantilla genérica). Plotly dibuja en SVG con el color que se le da tal cual (no resuelve
 * `var(--token)`): se lee el valor ya calculado del token y se sigue el cambio de tema.
 */
export function useColoresTema(): ColoresTema {
  const [colores, setColores] = useState(leer)
  useEffect(() => {
    const obs = new MutationObserver(() => setColores(leer()))
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-tema'] })
    return () => obs.disconnect()
  }, [])
  return colores
}
