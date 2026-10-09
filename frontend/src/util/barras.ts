import { aCentavos } from './dinero.ts'

function centavos(texto: string | null | undefined): bigint | null {
  if (texto === null || texto === undefined) return null
  try {
    return aCentavos(texto)
  } catch {
    return null // una cifra que no se puede leer no dibuja barra: nunca se adivina
  }
}

/** Mayor valor absoluto (en centavos) de varios importes; 0 si ninguno se puede leer. */
export function maximoAbsoluto(textos: (string | null | undefined)[]): bigint {
  let max = 0n
  for (const t of textos) {
    const c = centavos(t)
    if (c === null) continue
    const abs = c < 0n ? -c : c
    if (abs > max) max = abs
  }
  return max
}

/**
 * Largo de una barra (0 a 100, con un decimal) de `valor` respecto de `maximo`. Solo es geometría de
 * dibujo: se calcula con enteros (BigInt), sin pasar el dinero por number. Sin dato o sin máximo: 0.
 */
export function porcentajeBarra(valor: string | null | undefined, maximo: bigint): number {
  const c = centavos(valor)
  if (c === null || maximo <= 0n) return 0
  const abs = c < 0n ? -c : c
  const decimas = (abs * 1000n) / maximo
  return Number(decimas > 1000n ? 1000n : decimas) / 10
}
