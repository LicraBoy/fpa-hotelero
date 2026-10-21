// Catálogo único de pantallas de la aplicación. La barra lateral, la barra «Ubicación» y las rutas
// por hash leen de aquí. Solo aparece lo que EXISTE (docs/VISION_DEL_PRODUCTO.md): cuando haya un
// módulo nuevo se agrega una entrada y nada más; nunca se listan módulos futuros.

import type { NombreIcono } from '../componentes/nombreIcono.ts'
import { puede, tieneAccesoLimitado, type Permiso } from '../permisos.ts'

export type IdPantalla =
  | 'variance'
  | 'budget'
  | 'departamentos'
  | 'cargas'
  | 'catalogo'
  | 'saldos'
  | 'auditoria'
  | 'usuarios'
  | 'cuenta'

export type GrupoNavegacion = 'Finanzas' | 'Datos' | 'Administración'

export interface Pantalla {
  id: IdPantalla
  nombre: string
  /** `null`: no aparece en la barra lateral (se abre desde otro lugar, p. ej. el menú de usuario). */
  grupo: GrupoNavegacion | null
  icono: NombreIcono
  /** Basta con tener alguno de estos permisos. `[]` = cualquiera con sesión. */
  permisos: Permiso[]
  /** Solo existe con inicio de sesión real (no con el selector de desarrollo). */
  soloConSesion?: boolean
  /** No la ve quien solo tiene asignadas algunas secciones del reporte (cruza secciones). */
  soloAccesoCompleto?: boolean
}

export const PANTALLAS: readonly Pantalla[] = [
  { id: 'variance', nombre: 'Variance', grupo: 'Finanzas', icono: 'informe', permisos: ['variance:leer'] },
  { id: 'budget', nombre: 'Budget', grupo: 'Finanzas', icono: 'presupuesto', permisos: ['budget:importar'] },
  {
    id: 'departamentos',
    nombre: 'Por departamento',
    grupo: 'Finanzas',
    icono: 'catalogo',
    permisos: ['variance:leer'],
    soloAccesoCompleto: true,
  },
  { id: 'cargas', nombre: 'Cargas', grupo: 'Datos', icono: 'subir', permisos: ['carga:leer', 'carga:crear'] },
  { id: 'catalogo', nombre: 'Catálogo', grupo: 'Datos', icono: 'catalogo', permisos: ['catalogo:leer'] },
  { id: 'saldos', nombre: 'Saldos', grupo: 'Datos', icono: 'saldos', permisos: ['saldos:leer'] },
  { id: 'auditoria', nombre: 'Auditoría', grupo: 'Administración', icono: 'auditoria', permisos: ['auditoria:leer'] },
  { id: 'usuarios', nombre: 'Usuarios', grupo: 'Administración', icono: 'usuario', permisos: ['usuarios:administrar'] },
  { id: 'cuenta', nombre: 'Mi cuenta', grupo: null, icono: 'usuario', permisos: [], soloConSesion: true },
]

export const GRUPOS: readonly GrupoNavegacion[] = ['Finanzas', 'Datos', 'Administración']

const IDS = new Set<string>(PANTALLAS.map((p) => p.id))

export function esIdPantalla(valor: string): valor is IdPantalla {
  return IDS.has(valor)
}

export function pantallaDe(id: IdPantalla): Pantalla {
  return PANTALLAS.find((p) => p.id === id)!
}

/** ¿Puede este rol abrir la pantalla? (El servidor autoriza igual y siempre.) */
export function puedeAbrir(p: Pantalla, rol: string | undefined, conSesion: boolean): boolean {
  if (p.soloConSesion && !conSesion) return false
  if (p.soloAccesoCompleto && tieneAccesoLimitado(rol)) return false
  return p.permisos.length === 0 ? rol !== undefined : p.permisos.some((x) => puede(rol, x))
}

export function rutaDe(id: IdPantalla): string {
  return `#/${id}`
}
