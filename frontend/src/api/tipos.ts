// Tipos de la API: salen del OpenAPI generado (`npm run api:tipos` -> schema.d.ts), nunca se
// escriben a mano. Los importes llegan como texto ("57835193.08") para no perder centavos; nunca
// se convierten a number.
import type { components } from './schema'

type Esquemas = components['schemas']

export type Fuente = Esquemas['Fuente']
export type Hotel = Esquemas['HotelSalida']
export type Carga = Esquemas['CargaSalida']
export type CargaDetalle = Esquemas['CargaDetalle']
export type ReporteCalidad = Esquemas['ReporteCalidadSalida']
export type ControlCalidad = Esquemas['ControlCalidadSalida']
export type Severidad = ControlCalidad['severidad']
export type Conflicto = Esquemas['ConflictoSalida']
export type RespuestaCarga = Esquemas['RespuestaCarga']
export type Resolucion = RespuestaCarga['resolucion']
export type NodoCatalogo = Esquemas['NodoSalida']
export type RespuestaImportacion = Esquemas['RespuestaImportacion']
export type Saldo = Esquemas['SaldoSalida']
export type EventoAuditoria = Esquemas['EventoSalida']

export type Variance = Esquemas['VarianceSalida']
export type LineaVariance = Esquemas['LineaVarianceSalida']
export type CifrasVariance = Esquemas['CifrasSalida']
export type SeccionVariance = Esquemas['SeccionSalida']
export type DesgloseLinea = Esquemas['DesgloseSalida']
export type PaginaMovimientos = Esquemas['PaginaSalida']
export type MovimientoDetalle = Esquemas['MovimientoSalida']
export type Asiento = Esquemas['AsientoSalida']
