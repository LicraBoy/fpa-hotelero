// Etiquetas legibles de periodos «AAAA-MM» para los encabezados del reporte (fechas, no dinero).

const MESES = [
  'enero',
  'febrero',
  'marzo',
  'abril',
  'mayo',
  'junio',
  'julio',
  'agosto',
  'septiembre',
  'octubre',
  'noviembre',
  'diciembre',
]

const PATRON = /^(\d{4})-(0[1-9]|1[0-2])$/

/** "2026-08" -> "agosto 2026". Un texto que no es un periodo se devuelve tal cual. */
export function etiquetaMesLargo(periodo: string): string {
  const m = PATRON.exec(periodo)
  return m ? `${MESES[Number(m[2]) - 1]} ${m[1]}` : periodo
}

/** "2026-07" -> "jul" (abreviatura de tres letras). */
export function etiquetaMesCorto(periodo: string): string {
  const m = PATRON.exec(periodo)
  return m ? MESES[Number(m[2]) - 1].slice(0, 3) : periodo
}

/** ["2026-07","2026-08"] -> "jul – ago"; con un solo mes, ese mes. */
export function etiquetaRangoMeses(periodos: readonly string[]): string {
  if (periodos.length === 0) return ''
  const primero = etiquetaMesCorto(periodos[0])
  const ultimo = etiquetaMesCorto(periodos[periodos.length - 1])
  return primero === ultimo ? primero : `${primero} – ${ultimo}`
}
