// Espejo de la matriz del backend (backend/fpa/identidad/permisos.py) SOLO para decidir qué
// mostrar. La autorización real la hace siempre el servidor.

export type Permiso =
  | 'carga:crear'
  | 'carga:leer'
  | 'catalogo:leer'
  | 'catalogo:importar'
  | 'saldos:leer'
  | 'auditoria:leer'
  | 'reporte:leer'
  | 'mapeo:leer'
  | 'mapeo:editar'
  | 'mapeo:aprobar'
  | 'budget:leer'
  | 'budget:importar'
  | 'budget:capturar'
  | 'budget:objetivo'
  | 'budget:revisar'
  | 'budget:aprobar'
  | 'budget:bloquear'
  | 'variance:leer'
  | 'drilldown:leer'
  | 'usuarios:administrar'
  | 'comentario:leer'
  | 'comentario:crear'
  | 'comentario:resolver'
  | 'cierre:leer'
  | 'cierre:revisar'
  | 'cierre:aprobar'
  | 'cierre:bloquear'

const POR_ROL: Record<string, Permiso[]> = {
  contralor: [
    'carga:crear',
    'carga:leer',
    'catalogo:leer',
    'catalogo:importar',
    'saldos:leer',
    'auditoria:leer',
    'reporte:leer',
    'mapeo:leer',
    'mapeo:editar',
    'mapeo:aprobar',
    'budget:leer',
    'budget:importar',
    'budget:capturar',
    'budget:objetivo',
    'budget:revisar',
    'budget:aprobar',
    'budget:bloquear',
    'variance:leer',
    'drilldown:leer',
    'usuarios:administrar',
    'comentario:leer',
    'comentario:crear',
    'comentario:resolver',
    'cierre:leer',
    'cierre:revisar',
    'cierre:aprobar',
    'cierre:bloquear',
  ],
  analista: [
    'carga:crear',
    'carga:leer',
    'catalogo:leer',
    'catalogo:importar',
    'saldos:leer',
    'reporte:leer',
    'mapeo:leer',
    'mapeo:editar',
    'budget:leer',
    'budget:importar',
    'budget:revisar',
    'variance:leer',
    'drilldown:leer',
    'comentario:leer',
    'comentario:crear',
    'comentario:resolver',
    'cierre:leer',
    'cierre:revisar',
  ],
  responsable_area: [
    'catalogo:leer',
    'reporte:leer',
    'budget:capturar',
    'variance:leer',
    'drilldown:leer',
    'comentario:leer',
    'comentario:crear',
  ],
  direccion: [
    'carga:leer',
    'catalogo:leer',
    'saldos:leer',
    'reporte:leer',
    'mapeo:leer',
    'budget:leer',
    'budget:objetivo',
    'variance:leer',
    'comentario:leer',
    'cierre:leer',
  ],
  auditoria: [
    'carga:leer',
    'catalogo:leer',
    'saldos:leer',
    'auditoria:leer',
    'reporte:leer',
    'mapeo:leer',
    'budget:leer',
    'variance:leer',
    'drilldown:leer',
    'comentario:leer',
    'cierre:leer',
  ],
}

export const NOMBRE_ROL: Record<string, string> = {
  contralor: 'Contralor',
  analista: 'Analista de Contraloría',
  responsable_area: 'Responsable de departamento',
  direccion: 'Dirección',
  auditoria: 'Auditoría / consulta',
}

/** Roles que solo ven las secciones del reporte que se les asignaron (espejo del backend). */
export function tieneAccesoLimitado(rol: string | undefined): boolean {
  return rol === 'responsable_area'
}

export function puede(rol: string | undefined, permiso: Permiso): boolean {
  return !!rol && (POR_ROL[rol] ?? []).includes(permiso)
}

// Usuarios de la semilla de desarrollo (backend/fpa/semilla.py). No son personas reales.
export const USUARIOS_DESARROLLO = [
  { email: 'contralor@torres.local', nombre: 'Contralor' },
  { email: 'analista@torres.local', nombre: 'Analista' },
  { email: 'responsable@torres.local', nombre: 'Responsable de área' },
  { email: 'direccion@torres.local', nombre: 'Dirección' },
  { email: 'auditoria@torres.local', nombre: 'Auditoría' },
]
