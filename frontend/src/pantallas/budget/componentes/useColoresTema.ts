import { useEffect, useState } from 'react'

export interface ColoresTema {
  suave: string
  primario: string
  texto: string
  /** Paleta vibrante y diferenciada para series categóricas (donut, barras agrupadas, leyendas).
   * Diseñada para máximo contraste visual y coherencia con la referencia de Budget Studio. */
  paletaSerie: string[]
  /** Paleta extendida para gráficos con muchas categorías. */
  paletaExtendida: string[]
}

const RESPALDO: ColoresTema = {
  suave: '#64748b',
  primario: '#2563eb',
  texto: '#1e293b',
  paletaSerie: ['#2563eb', '#10b981', '#f97316', '#8b5cf6', '#0284c7', '#64748b'],
  paletaExtendida: ['#2563eb', '#10b981', '#f97316', '#8b5cf6', '#0284c7', '#ec4899', '#eab308', '#64748b'],
}

function leer(): ColoresTema {
  if (typeof document === 'undefined') return RESPALDO
  const estilo = getComputedStyle(document.documentElement)
  const token = (nombre: string, respaldo: string) => estilo.getPropertyValue(nombre).trim() || respaldo
  const esOscuro = document.documentElement.getAttribute('data-tema') === 'oscuro'
  return {
    suave: token('--suave', RESPALDO.suave),
    primario: token('--primario', RESPALDO.primario),
    texto: esOscuro ? '#e2e8f0' : '#1e293b',
    paletaSerie: RESPALDO.paletaSerie,
    paletaExtendida: RESPALDO.paletaExtendida,
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
