// Rutas de la aplicación por hash (#/variance/...), sin librería de ruteo. Funciones puras: se
// prueban sin navegador. Toda parte de la ruta se valida con una lista blanca de caracteres antes de
// usarse (viene de la barra de direcciones: es entrada del usuario).

import type { Permiso } from '../permisos'

export type Bloque = 'mes' | 'ytd'

export type Ruta =
  | { tipo: 'sin-ruta' }
  | { tipo: 'invalida' }
  | { tipo: 'variance'; periodo: string | null }
  | { tipo: 'desglose'; periodo: string; lineaId: number; bloque: Bloque }
  | { tipo: 'cuenta'; periodo: string; codigo: string; bloque: Bloque }
  | { tipo: 'asiento'; periodo: string; asiento: string }

const PERIODO = /^20\d{2}-(0[1-9]|1[0-2])$/
const CODIGO = /^[0-9A-Za-z][0-9A-Za-z.-]{0,39}$/
const ENTERO = /^[1-9]\d{0,9}$/

function bloqueDe(consulta: URLSearchParams): Bloque | null {
  const b = consulta.get('bloque') ?? 'mes'
  return b === 'mes' || b === 'ytd' ? b : null
}

/** "#/variance/2026-08/linea/12?bloque=ytd" -> Ruta. Cualquier cosa rara es `invalida`. */
export function parsearRuta(hash: string): Ruta {
  if (hash === '' || hash === '#' || hash === '#/') return { tipo: 'sin-ruta' }
  if (!hash.startsWith('#/')) return { tipo: 'invalida' }
  const [camino, consultaTexto = ''] = hash.slice(2).split('?', 2)
  const partes = camino.split('/')
  const consulta = new URLSearchParams(consultaTexto)
  if (partes[0] !== 'variance') return { tipo: 'invalida' }
  if (partes.length === 1) return { tipo: 'variance', periodo: null }
  const periodo = partes[1]
  if (!PERIODO.test(periodo)) return { tipo: 'invalida' }
  if (partes.length === 2) return { tipo: 'variance', periodo }
  const bloque = bloqueDe(consulta)
  if (partes.length !== 4 || bloque === null) return { tipo: 'invalida' }
  const [, , tipo, valor] = partes
  let decodificado: string
  try {
    decodificado = decodeURIComponent(valor)
  } catch {
    return { tipo: 'invalida' } // secuencia % mal formada
  }
  if (tipo === 'linea' && ENTERO.test(decodificado)) {
    return { tipo: 'desglose', periodo, lineaId: Number(decodificado), bloque }
  }
  if (tipo === 'cuenta' && CODIGO.test(decodificado)) {
    return { tipo: 'cuenta', periodo, codigo: decodificado, bloque }
  }
  if (tipo === 'asiento' && CODIGO.test(decodificado)) {
    return { tipo: 'asiento', periodo, asiento: decodificado }
  }
  return { tipo: 'invalida' }
}

export function construirRuta(ruta: Ruta): string {
  switch (ruta.tipo) {
    case 'sin-ruta':
    case 'invalida':
      return '#/'
    case 'variance':
      return ruta.periodo ? `#/variance/${ruta.periodo}` : '#/variance'
    case 'desglose':
      return `#/variance/${ruta.periodo}/linea/${ruta.lineaId}?bloque=${ruta.bloque}`
    case 'cuenta':
      return `#/variance/${ruta.periodo}/cuenta/${encodeURIComponent(ruta.codigo)}?bloque=${ruta.bloque}`
    case 'asiento':
      return `#/variance/${ruta.periodo}/asiento/${encodeURIComponent(ruta.asiento)}?bloque=mes`
  }
}

/** Permiso que el rol necesita para ver la pantalla de esa ruta (null = ninguno en especial). */
export function permisoDeRuta(ruta: Ruta): Permiso | null {
  switch (ruta.tipo) {
    case 'variance':
      return 'variance:leer'
    case 'desglose':
    case 'cuenta':
    case 'asiento':
      return 'drilldown:leer'
    default:
      return null
  }
}
