// Importes exactos: se manejan como texto y se suman en centavos enteros (BigInt). Nunca number.

const PATRON = /^(-?)(\d+)(?:\.(\d{1,2}))?$/

export function aCentavos(texto: string): bigint {
  const m = PATRON.exec(texto.trim())
  if (!m) throw new Error(`Importe inválido: ${texto}`)
  const centavos = BigInt(m[2] + (m[3] ?? '').padEnd(2, '0'))
  return m[1] ? -centavos : centavos
}

export function deCentavos(centavos: bigint): string {
  const negativo = centavos < 0n
  const absoluto = negativo ? -centavos : centavos
  const texto = absoluto.toString().padStart(3, '0')
  const enteros = texto.slice(0, -2).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return `${negativo ? '-' : ''}${enteros}.${texto.slice(-2)}`
}

/** "57835193.08" -> "57,835,193.08" */
export function formatoDinero(texto: string): string {
  return deCentavos(aCentavos(texto))
}

export function sumar(textos: string[]): string {
  return deCentavos(textos.reduce((acc, t) => acc + aCentavos(t), 0n))
}
