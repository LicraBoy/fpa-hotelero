// Tema de la interfaz (claro / oscuro). Funciones puras: se prueban sin navegador.

export type PreferenciaTema = 'auto' | 'claro' | 'oscuro'
export type TemaAplicado = 'claro' | 'oscuro'

export function esPreferenciaTema(valor: unknown): valor is PreferenciaTema {
  return valor === 'auto' || valor === 'claro' || valor === 'oscuro'
}

/** El tema que se pinta: la preferencia explícita o, en `auto`, el del sistema operativo. */
export function resolverTema(preferencia: PreferenciaTema, sistemaOscuro: boolean): TemaAplicado {
  if (preferencia === 'claro' || preferencia === 'oscuro') return preferencia
  return sistemaOscuro ? 'oscuro' : 'claro'
}

/** Lo que pasa al pulsar el interruptor: se fija el tema contrario al que se está viendo. */
export function temaContrario(actual: TemaAplicado): TemaAplicado {
  return actual === 'oscuro' ? 'claro' : 'oscuro'
}
