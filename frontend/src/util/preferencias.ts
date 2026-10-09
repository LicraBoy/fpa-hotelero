// Preferencias de la interfaz que no son secretos. Único archivo autorizado a usar el almacenamiento
// del navegador (scripts/verificar_seguridad.mjs). **Nunca** guardar aquí credenciales ni tokens: la
// sesión vive en memoria (api/sesion.ts) y, con OIDC, en una cookie HttpOnly.
//
// Se usa sessionStorage (se borra al cerrar la pestaña), no localStorage.

import { esPreferenciaTema, type PreferenciaTema } from './tema'

const CLAVE_USUARIO_DEV = 'fpa_usuario_dev'
const CLAVE_TEMA = 'fpa_tema'
const CLAVE_LATERAL = 'fpa_lateral_plegado'

function almacenamiento(): Storage | null {
  try {
    return window.sessionStorage
  } catch {
    return null // modo privado o almacenamiento bloqueado
  }
}

/** Correo del usuario de desarrollo elegido en el selector (solo existe con FPA_ENTORNO=desarrollo). */
export function leerUsuarioDev(): string | null {
  return almacenamiento()?.getItem(CLAVE_USUARIO_DEV) ?? null
}

export function guardarUsuarioDev(email: string): void {
  try {
    almacenamiento()?.setItem(CLAVE_USUARIO_DEV, email)
  } catch {
    // sin almacenamiento: solo vale para esta sesión de la página
  }
}

/** Preferencia de tema (claro / oscuro / auto). No es un secreto; vale mientras dure la pestaña. */
export function leerTema(): PreferenciaTema {
  const guardado = almacenamiento()?.getItem(CLAVE_TEMA)
  return esPreferenciaTema(guardado) ? guardado : 'auto'
}

export function guardarTema(preferencia: PreferenciaTema): void {
  try {
    almacenamiento()?.setItem(CLAVE_TEMA, preferencia)
  } catch {
    // sin almacenamiento: el tema elegido solo vale hasta recargar
  }
}

/** ¿La barra lateral está plegada (solo iconos)? Preferencia de la interfaz, no un secreto. */
export function leerLateralPlegado(): boolean {
  return almacenamiento()?.getItem(CLAVE_LATERAL) === '1'
}

export function guardarLateralPlegado(plegado: boolean): void {
  try {
    almacenamiento()?.setItem(CLAVE_LATERAL, plegado ? '1' : '0')
  } catch {
    // sin almacenamiento: vale solo hasta recargar
  }
}
