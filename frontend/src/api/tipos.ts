// Tipos que reflejan las respuestas de la API (backend/fpa/api/v1). Los importes llegan como
// texto ("57835193.08") para no perder centavos; nunca se convierten a number.

export type Fuente = 'con130' | 'variance_base_datos'

export interface Hotel {
  id: number
  codigo: string
  nombre: string
  rol: string
}

export interface Carga {
  id: number
  periodo: string
  fuente: string
  estado: 'vigente' | 'reemplazada'
  nombre_archivo: string
  sha256: string
  n_movimientos: number
  total_debito: string
  total_credito: string
  fecha_min: string
  fecha_max: string
  creado_en: string
  usuario_id: number | null
  reemplazada_por_id: number | null
}

export type Severidad = 'ok' | 'aviso' | 'error'

export interface ControlCalidad {
  codigo: string
  severidad: Severidad
  resumen: string
  ejemplos: string[]
}

export interface ReporteCalidad {
  fuente: string | null
  aprobado: boolean
  controles: ControlCalidad[]
}

export interface CargaDetalle extends Carga {
  controles: ReporteCalidad | null
}

export interface Conflicto {
  periodo: string
  carga_vigente_id: number
  archivo_vigente: string
  n_vigente: number
  debito_vigente: string
  credito_vigente: string
  n_nuevo: number
  debito_nuevo: string
  credito_nuevo: string
}

export type Resolucion =
  | 'creada'
  | 'duplicada'
  | 'requiere_confirmacion'
  | 'reemplazada'
  | 'rechazada'

export interface RespuestaCarga {
  resolucion: Resolucion
  cargas: Carga[]
  reemplazadas: Carga[]
  conflictos: Conflicto[]
  sin_cambio: string[]
  motivos: string[]
  reporte: ReporteCalidad | null
}

export interface NodoCatalogo {
  codigo: string
  descripcion: string | null
  clase: string
  nivel: number | null
  con_movimientos: boolean
  es_titulo: boolean
  sin_jerarquia: boolean
  tipo: 'Deudor' | 'Acreedor' | null
  grupo_ef: string | null
  depto_ef: string | null
  cuenta_sat: string | null
  activa: boolean
  en_catalogo_oficial: boolean
  hijos: NodoCatalogo[]
}

export interface RespuestaImportacion {
  resolucion: 'importado' | 'sin_cambio' | 'rechazado'
  total_cuentas: number
  total_titulos: number
  creadas: number
  actualizadas: number
  sin_cambio: number
  titulos_con_nombre_nuevo: number
  fuera_del_catalogo: string[]
  inactivas_con_movimientos: string[]
  ya_no_vienen: string[]
  avisos: string[]
  motivos: string[]
}

export interface Saldo {
  cuenta_codigo: string
  suma_debito: string
  suma_credito: string
  neto: string
  n_movimientos: number
}

export interface EventoAuditoria {
  id: number
  accion: string
  entidad: string
  entidad_id: number | null
  usuario_id: number | null
  detalle: Record<string, unknown> | null
  creado_en: string
}
