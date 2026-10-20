// Único punto donde viven las credenciales de la sesión.
//
// Reglas de seguridad (docs/adr/0004-seguridad-del-frontend.md):
//  - Nada de credenciales en localStorage ni sessionStorage: solo en memoria de la página.
//  - La sesión real va en una cookie HttpOnly + Secure + SameSite=Strict que el navegador envía solo
//    (el JavaScript nunca la toca; ADR 0005). Aquí no hay tokens.
//  - En desarrollo se puede elegir un usuario con la cabecera `X-Usuario-Dev`, que el backend
//    acepta únicamente con FPA_ENTORNO=desarrollo.

let usuarioDev: string | null = null
let sesionReal = false
let alExpirar: (() => void) | null = null

/** Con sesión real (cookie) un 401 significa que la sesión caducó: la pantalla vuelve al inicio. */
export function usarSesionReal(activa: boolean, cuandoExpire?: () => void): void {
  sesionReal = activa
  alExpirar = activa ? (cuandoExpire ?? null) : null
}

export function avisarNoAutorizado(): void {
  if (sesionReal && alExpirar) alExpirar()
}

export function fijarUsuarioDev(email: string | null): void {
  usuarioDev = email
}

/** Cabeceras de identidad para cada petición. */
export function credencialesActuales(): Record<string, string> {
  return usuarioDev ? { 'X-Usuario-Dev': usuarioDev } : {}
}
