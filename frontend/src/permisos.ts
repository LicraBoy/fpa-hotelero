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
  | 'variance:leer'

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
    'variance:leer',
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
    'variance:leer',
  ],
  responsable_area: ['catalogo:leer', 'reporte:leer'],
  direccion: [
    'carga:leer',
    'catalogo:leer',
    'saldos:leer',
    'reporte:leer',
    'mapeo:leer',
    'budget:leer',
    'variance:leer',
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
  ],
}

export const NOMBRE_ROL: Record<string, string> = {
  contralor: 'Contralor',
  analista: 'Analista de Contraloría',
  responsable_area: 'Responsable de departamento',
  direccion: 'Dirección',
  auditoria: 'Auditoría / consulta',
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
