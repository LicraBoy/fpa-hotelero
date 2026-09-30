import type { Fuente, RespuestaCarga, RespuestaImportacion } from './tipos'

/** Error de la API con el código HTTP y un mensaje listo para mostrar. */
export class ErrorApi extends Error {
  readonly estado: number
  readonly detalle: string

  constructor(estado: number, detalle: string) {
    super(detalle)
    this.estado = estado
    this.detalle = detalle
  }
}

// Identidad de DESARROLLO: el backend acepta esta cabecera solo con FPA_ENTORNO=desarrollo.
// Se reemplazará por el inicio de sesión corporativo (OIDC) cuando TI lo defina.
let usuarioDev: string | null = null

export function fijarUsuarioDev(email: string | null): void {
  usuarioDev = email
}

function cabeceras(): Headers {
  const h = new Headers()
  if (usuarioDev) h.set('X-Usuario-Dev', usuarioDev)
  return h
}

function mensajeDeError(cuerpo: unknown, estado: number): string {
  if (cuerpo && typeof cuerpo === 'object' && 'detail' in cuerpo) {
    const detalle = (cuerpo as { detail: unknown }).detail
    if (typeof detalle === 'string') return detalle
    if (Array.isArray(detalle)) return 'Los datos enviados no son válidos'
  }
  if (estado === 401) return 'No hay una sesión válida'
  if (estado === 403) return 'No tienes permiso para esta acción'
  if (estado === 404) return 'No se encontró lo solicitado (o no tienes acceso)'
  if (estado >= 500) return 'La API no está disponible en este momento'
  return `Error ${estado}`
}

async function leerJson(r: Response): Promise<unknown> {
  try {
    return await r.json()
  } catch {
    return null
  }
}

export async function obtener<T>(ruta: string, parametros?: Record<string, string>): Promise<T> {
  const consulta = parametros ? `?${new URLSearchParams(parametros).toString()}` : ''
  const r = await fetch(`/api/v1${ruta}${consulta}`, { headers: cabeceras() })
  const cuerpo = await leerJson(r)
  if (!r.ok) throw new ErrorApi(r.status, mensajeDeError(cuerpo, r.status))
  return cuerpo as T
}

export interface DatosCarga {
  archivo: File
  fuente: Fuente
  confirmarReemplazo: boolean
  periodos: string
}

/**
 * Sube un archivo. Las respuestas de negocio (creada, duplicada, requiere confirmación,
 * rechazada) traen un cuerpo con `resolucion` y se devuelven tal cual; el resto son errores.
 */
export async function subirCarga(
  hotelId: number,
  datos: DatosCarga,
): Promise<{ estado: number; cuerpo: RespuestaCarga }> {
  const formulario = new FormData()
  formulario.append('archivo', datos.archivo)
  formulario.append('fuente', datos.fuente)
  formulario.append('confirmar_reemplazo', String(datos.confirmarReemplazo))
  if (datos.periodos.trim()) formulario.append('periodos', datos.periodos.trim())
  const r = await fetch(`/api/v1/hoteles/${hotelId}/cargas`, {
    method: 'POST',
    body: formulario,
    headers: cabeceras(),
  })
  const cuerpo = await leerJson(r)
  if (cuerpo && typeof cuerpo === 'object' && 'resolucion' in cuerpo) {
    return { estado: r.status, cuerpo: cuerpo as RespuestaCarga }
  }
  throw new ErrorApi(r.status, mensajeDeError(cuerpo, r.status))
}

/** Importa el catálogo contable oficial (.xls del reporte CON020 de Novohit). */
export async function importarCatalogo(
  hotelId: number,
  archivo: File,
): Promise<{ estado: number; cuerpo: RespuestaImportacion }> {
  const formulario = new FormData()
  formulario.append('archivo', archivo)
  const r = await fetch(`/api/v1/hoteles/${hotelId}/catalogo/importar`, {
    method: 'POST',
    body: formulario,
    headers: cabeceras(),
  })
  const cuerpo = await leerJson(r)
  if (cuerpo && typeof cuerpo === 'object' && 'resolucion' in cuerpo) {
    return { estado: r.status, cuerpo: cuerpo as RespuestaImportacion }
  }
  throw new ErrorApi(r.status, mensajeDeError(cuerpo, r.status))
}
