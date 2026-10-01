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

/** Suma exacta, como texto FORMATEADO para mostrar (con miles). Para comparar usa `sumarCentavos`. */
export function sumar(textos: string[]): string {
  return deCentavos(textos.reduce((acc, t) => acc + aCentavos(t), 0n))
}

/** Centavos -> texto plano, SIN separadores de miles ("-123450" -> "-1234.50"), para seguir operando. */
export function aTextoPlano(centavos: bigint): string {
  const negativo = centavos < 0n
  const digitos = (negativo ? -centavos : centavos).toString().padStart(3, '0')
  return `${negativo ? '-' : ''}${digitos.slice(0, -2)}.${digitos.slice(-2)}`
}

/** Suma exacta en centavos. A diferencia de `sumar`, devuelve el entero para poder comparar. */
export function sumarCentavos(textos: string[]): bigint {
  return textos.reduce((acc, t) => acc + aCentavos(t), 0n)
}

/**
 * Cambia el signo de un importe exacto, sin separadores de miles (para seguir operando con él):
 * "5.00" -> "-5.00"; "-1234.50" -> "1234.50".
 */
export function negar(texto: string): string {
  return aTextoPlano(-aCentavos(texto))
}
