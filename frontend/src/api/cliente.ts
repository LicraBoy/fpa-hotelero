import { credencialesActuales } from './sesion'
import type { paths } from './schema'
import type { Fuente, RespuestaCarga, RespuestaImportacion } from './tipos'

export { fijarUsuarioDev } from './sesion'

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

function cabeceras(): Headers {
  const h = new Headers()
  for (const [nombre, valor] of Object.entries(credencialesActuales())) h.set(nombre, valor)
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

type Rutas = paths
type RutaGet = {
  [R in keyof Rutas]: Rutas[R] extends { get: { responses: { 200: unknown } } } ? R : never
}[keyof Rutas]
type ParametrosGet<R extends RutaGet> = Rutas[R] extends { get: { parameters: infer P } } ? P : never
type ParteDe<P, K extends string> = P extends { [clave in K]?: infer V } ? NonNullable<V> : never
type RespuestaGet<R extends RutaGet> = Rutas[R] extends {
  get: { responses: { 200: { content: { 'application/json': infer T } } } }
}
  ? T
  : never

/** Opciones de una consulta: los parámetros de ruta y de query que el OpenAPI declara. */
export type OpcionesGet<R extends RutaGet> = (ParteDe<ParametrosGet<R>, 'path'> extends never
  ? { path?: undefined }
  : { path: ParteDe<ParametrosGet<R>, 'path'> }) &
  (ParteDe<ParametrosGet<R>, 'query'> extends never
    ? { query?: undefined }
    : { query?: ParteDe<ParametrosGet<R>, 'query'> })

function armarUrl(ruta: string, path?: object, query?: object): string {
  let url = ruta
  for (const [clave, valor] of Object.entries(path ?? {})) {
    url = url.replace(`{${clave}}`, encodeURIComponent(String(valor)))
  }
  const consulta = new URLSearchParams()
  for (const [clave, valor] of Object.entries(query ?? {})) {
    if (valor === undefined || valor === null) continue
    for (const v of Array.isArray(valor) ? valor : [valor]) consulta.append(clave, String(v))
  }
  const texto = consulta.toString()
  return texto ? `${url}?${texto}` : url
}

/**
 * GET con tipos del OpenAPI: la ruta, sus parámetros y la forma de la respuesta se comprueban al
 * compilar. Un cambio en la API que rompa a un llamador falla en `npm run build`.
 */
export async function obtenerTipado<R extends RutaGet>(
  ruta: R,
  opciones: OpcionesGet<R>,
): Promise<RespuestaGet<R>> {
  const r = await fetch(armarUrl(ruta, opciones.path, opciones.query), { headers: cabeceras() })
  const cuerpo = await leerJson(r)
  if (!r.ok) throw new ErrorApi(r.status, mensajeDeError(cuerpo, r.status))
  return cuerpo as RespuestaGet<R>
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
