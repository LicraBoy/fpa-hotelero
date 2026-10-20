// Llamadas de inicio y cierre de sesión (ADR 0005). La cookie de sesión es HttpOnly: este código
// nunca la ve; el navegador la envía solo en cada petición al mismo origen.
import { ErrorApi } from './cliente'
import type { components } from './schema'

export type UsuarioSesion = components['schemas']['UsuarioSesion']
export type EstadoAuth = components['schemas']['EstadoAuth']
export type MfaIniciada = components['schemas']['MfaIniciada']

async function enviar<T>(ruta: string, cuerpo?: object): Promise<T | null> {
  const r = await fetch(`/api/v1/auth${ruta}`, {
    method: ruta === '/estado' ? 'GET' : 'POST',
    headers: cuerpo ? { 'Content-Type': 'application/json' } : undefined,
    body: cuerpo ? JSON.stringify(cuerpo) : undefined,
  })
  let json: unknown = null
  try {
    json = await r.json()
  } catch {
    json = null
  }
  if (!r.ok) {
    const detalle =
      json && typeof json === 'object' && 'detail' in json && typeof json.detail === 'string'
        ? json.detail
        : `Error ${r.status}`
    throw new ErrorApi(r.status, detalle, false)
  }
  return json as T | null
}

export const estadoAuth = () => enviar<EstadoAuth>('/estado') as Promise<EstadoAuth>
export const iniciarSesion = (email: string, password: string, codigo?: string) =>
  enviar<UsuarioSesion>('/login', { email, password, codigo: codigo || null }) as Promise<UsuarioSesion>
export const cerrarSesion = () => enviar('/logout', {})
export const cambiarPassword = (actual: string, nueva: string) =>
  enviar('/cambiar-password', { actual, nueva })
export const iniciarMfa = () => enviar<MfaIniciada>('/mfa/iniciar', {}) as Promise<MfaIniciada>
export const confirmarMfa = (codigo: string) => enviar('/mfa/confirmar', { codigo })
export const desactivarMfa = (password: string) => enviar('/mfa/desactivar', { password })
