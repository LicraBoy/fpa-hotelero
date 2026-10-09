import { useEffect, useState } from 'react'
import { guardarTema, leerTema } from '../util/preferencias'
import { resolverTema, temaContrario, type PreferenciaTema } from '../util/tema'
import { Icono } from './Iconos'

const CONSULTA_OSCURO = '(prefers-color-scheme: dark)'

/** Interruptor claro/oscuro. Por omisión sigue al sistema; al pulsarlo se fija la elección. */
export function ConmutadorTema() {
  const [preferencia, setPreferencia] = useState<PreferenciaTema>(leerTema)
  const [sistemaOscuro, setSistemaOscuro] = useState(() => window.matchMedia(CONSULTA_OSCURO).matches)

  useEffect(() => {
    const consulta = window.matchMedia(CONSULTA_OSCURO)
    const alCambiar = (e: MediaQueryListEvent) => setSistemaOscuro(e.matches)
    consulta.addEventListener('change', alCambiar)
    return () => consulta.removeEventListener('change', alCambiar)
  }, [])

  useEffect(() => {
    document.documentElement.dataset.tema = resolverTema(preferencia, sistemaOscuro)
  }, [preferencia, sistemaOscuro])

  const visible = resolverTema(preferencia, sistemaOscuro)
  const siguiente = temaContrario(visible)
  return (
    <button
      type="button"
      className="boton-icono"
      aria-label={`Cambiar a tema ${siguiente}`}
      title={`Cambiar a tema ${siguiente}`}
      onClick={() => {
        setPreferencia(siguiente)
        guardarTema(siguiente)
      }}
    >
      <Icono nombre={visible === 'oscuro' ? 'sol' : 'luna'} />
    </button>
  )
}
