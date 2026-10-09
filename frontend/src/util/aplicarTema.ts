import { resolverTema, type PreferenciaTema } from './tema'

/** Pone `data-tema` en <html>: los colores de cada tema viven en index.css. */
export function aplicarTema(preferencia: PreferenciaTema): void {
  const oscuro = window.matchMedia('(prefers-color-scheme: dark)').matches
  document.documentElement.dataset.tema = resolverTema(preferencia, oscuro)
}
