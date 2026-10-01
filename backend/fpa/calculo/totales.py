"""Totales y subtotales del reporte a partir de sus reglas de suma.

Función **pura y determinística** (Decimal): dados los valores de las líneas base (detalle y
cualquier línea sin regla), calcula cada total y subtotal siguiendo sus reglas, en el orden que
exijan las dependencias. Una regla que depende de sí misma (directa o indirectamente) es un error.
Sirve igual para Actual (mes y YTD) y para Budget (mes, YTD y anual).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal

CERO = Decimal("0")


class CicloEnReglas(ValueError):
    """Los totales se referencian en círculo y no se pueden calcular."""


def evaluar_totales(
    reglas: Mapping[int, Sequence[tuple[int, int]]],
    valores: Mapping[int, Decimal],
) -> dict[int, Decimal]:
    """`reglas`: línea total -> [(línea componente, signo)]. `valores`: línea -> importe.

    Devuelve el importe de cada línea con regla. Un componente sin valor ni regla cuenta 0.
    """
    resultado: dict[int, Decimal] = {}
    en_curso: set[int] = set()

    def valor(linea: int) -> Decimal:
        if linea in resultado:
            return resultado[linea]
        if linea not in reglas:
            return valores.get(linea, CERO)
        if linea in en_curso:
            raise CicloEnReglas(f"La línea {linea} depende de sí misma")
        en_curso.add(linea)
        total = sum((signo * valor(c) for c, signo in reglas[linea]), CERO)
        en_curso.discard(linea)
        resultado[linea] = total
        return total

    for linea in reglas:
        valor(linea)
    return resultado


def completar_con_totales(
    reglas: Mapping[int, Sequence[tuple[int, int]]],
    base: Mapping[int, Decimal],
) -> dict[int, Decimal]:
    """Valor de **todas** las líneas: las base tal cual y las que tienen regla, calculadas.

    Si una línea tiene regla, manda la regla aunque venga también en `base`.
    """
    return {**base, **evaluar_totales(reglas, base)}
