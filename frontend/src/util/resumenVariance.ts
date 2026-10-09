import type { LineaVariance } from '../api/tipos'
import { aCentavos } from './dinero.ts'

export interface ExtremoVariance {
  descripcion: string
  /** La Variación del mes tal como la entrega la API (texto decimal). */
  variacion: string
}

export interface ResumenVariance {
  /** Líneas de detalle con una Variación calculada en el mes. */
  conVariacion: number
  desfavorables: number
  favorables: number
  /** Con Variación calculada pero exactamente en cero. */
  sinVariacion: number
  mayorDesfavorable: ExtremoVariance | null
  mayorFavorable: ExtremoVariance | null
}

/**
 * Resume el mes con lo que la API ya calculó: cuenta y ordena las Variaciones de las líneas de
 * detalle. NO suma importes entre líneas (cada una tiene su propio sentido de signo) y no inventa
 * ninguna cifra: solo se muestran valores que ya están en la tabla.
 */
export function resumirVariance(lineas: LineaVariance[]): ResumenVariance {
  const resumen: ResumenVariance = {
    conVariacion: 0,
    desfavorables: 0,
    favorables: 0,
    sinVariacion: 0,
    mayorDesfavorable: null,
    mayorFavorable: null,
  }
  let peor = 0n
  let mejor = 0n
  for (const linea of lineas) {
    if (linea.tipo !== 'detalle' || linea.mes.var === null) continue
    let centavos: bigint
    try {
      centavos = aCentavos(linea.mes.var)
    } catch {
      continue // una cifra que no se puede leer no cuenta; nunca se adivina
    }
    resumen.conVariacion += 1
    if (centavos < 0n) {
      resumen.desfavorables += 1
      if (centavos < peor) {
        peor = centavos
        resumen.mayorDesfavorable = { descripcion: linea.descripcion, variacion: linea.mes.var }
      }
    } else if (centavos > 0n) {
      resumen.favorables += 1
      if (centavos > mejor) {
        mejor = centavos
        resumen.mayorFavorable = { descripcion: linea.descripcion, variacion: linea.mes.var }
      }
    } else {
      resumen.sinVariacion += 1
    }
  }
  return resumen
}
