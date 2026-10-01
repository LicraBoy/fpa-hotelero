// Formato de cifras del reporte. Los importes y porcentajes llegan de la API como TEXTO decimal
// ("-1234.5678"); se formatean con aritmética de enteros (BigInt), nunca con number, para no
// perder ni inventar centavos.

const PATRON = /^(-?)(\d+)(?:\.(\d+))?$/

interface Magnitud {
  negativo: boolean
  // valor absoluto en unidades de 10^-escala
  unidades: bigint
}

function leer(texto: string, escala: number): Magnitud | null {
  const m = PATRON.exec(texto.trim())
  if (!m) return null
  const decimales = m[3] ?? ''
  const base = BigInt(m[2] + decimales.slice(0, escala).padEnd(escala, '0'))
  // Redondeo half-up sobre el valor absoluto con el primer decimal que sobra
  const sobra = decimales.length > escala ? Number(decimales[escala]) : 0
  return { negativo: m[1] === '-', unidades: sobra >= 5 ? base + 1n : base }
}

function conMiles(entero: string): string {
  return entero.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}

function partir(unidades: bigint, escala: number): string {
  const texto = unidades.toString().padStart(escala + 1, '0')
  const enteros = conMiles(texto.slice(0, texto.length - escala))
  return escala === 0 ? enteros : `${enteros}.${texto.slice(texto.length - escala)}`
}

/** "-1234.5" -> "(1,234.50)"; null -> "—". Cero se muestra "0.00". */
export function formatoContable(texto: string | null | undefined): string {
  if (texto === null || texto === undefined) return '—'
  const v = leer(texto, 2)
  if (!v) return '—'
  const cuerpo = partir(v.unidades, 2)
  return v.negativo && v.unidades !== 0n ? `(${cuerpo})` : cuerpo
}

/** Razón decimal -> porcentaje con un decimal: "0.25" -> "25.0%"; "-0.5" -> "(50.0%)". */
export function formatoPorcentaje(razon: string | null | undefined): string {
  if (razon === null || razon === undefined) return '—'
  // razón con 6 decimales -> décimas de punto porcentual: razón × 1000
  const v = leer(razon, 6)
  if (!v) return '—'
  const decimas = (v.unidades + 500n) / 1000n
  const cuerpo = `${partir(decimas, 1)}%`
  return v.negativo && decimas !== 0n ? `(${cuerpo})` : cuerpo
}

/** ¿La variación es desfavorable? (el reporte es favorable-positivo: negativo = desfavorable). */
export function esDesfavorable(variacion: string | null | undefined): boolean {
  if (variacion === null || variacion === undefined) return false
  const v = leer(variacion, 2)
  return v !== null && v.negativo && v.unidades !== 0n
}
