// Único punto donde viven las credenciales de la sesión.
//
// Reglas de seguridad (docs/adr/0004-seguridad-del-frontend.md):
//  - Nada de credenciales en localStorage ni sessionStorage: solo en memoria de la página.
//  - Hoy no hay tokens: en desarrollo la identidad es una cabecera (`X-Usuario-Dev`) que el backend
//    acepta únicamente con FPA_ENTORNO=desarrollo.
//  - Con el inicio de sesión corporativo (OIDC) la sesión irá en una cookie HttpOnly + Secure +
//    SameSite=Strict que el navegador envía solo (el JavaScript nunca la toca) y este módulo dejará
//    de devolver cabeceras.

let usuarioDev: string | null = null

export function fijarUsuarioDev(email: string | null): void {
  usuarioDev = email
}

/** Cabeceras de identidad para cada petición. */
export function credencialesActuales(): Record<string, string> {
  return usuarioDev ? { 'X-Usuario-Dev': usuarioDev } : {}
}
