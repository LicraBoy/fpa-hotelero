"""Totales y subtotales del reporte a partir de sus reglas de suma.

Función **pura y determinística** (Decimal): dados los valores de las líneas base (detalle y
cualquier línea sin regla), calcula cada total y subtotal siguiendo sus reglas, en el orden que
exijan las dependencias. Una regla que depende de sí misma (directa o indirectamente) es un error.
Sirve igual para Actual (mes y YTD) y para Budget (mes, YTD y anual).

**Líneas aditivas:** una línea de detalle que suma cuentas **y** referencias a otras líneas (en
Mazatlán, `IVA Taxes = '2007001'!L5 + '2-1-70-20'!L5 − J756 − J807 − J363`) vale «lo que suman sus
cuentas + lo que suman sus componentes». Se indican en `aditivas`; en el resto, la regla reemplaza
al valor base.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from decimal import Decimal

CERO = Decimal("0")

# Coeficiente de un componente: ±1 (suma o resta) o un factor como ±0.16 (16 % de otra línea)
Coeficiente = int | Decimal
Reglas = Mapping[int, Sequence[tuple[int, Coeficiente]]]


class CicloEnReglas(ValueError):
    """Los totales se referencian en círculo y no se pueden calcular."""


def evaluar_totales(
    reglas: Reglas,
    valores: Mapping[int, Decimal],
    aditivas: Collection[int] = frozenset(),
) -> dict[int, Decimal]:
    """`reglas`: línea total -> [(línea componente, signo)]. `valores`: línea -> importe.

    Devuelve el importe de cada línea con regla. Un componente sin valor ni regla cuenta 0. En las
    líneas `aditivas`, el valor propio (sus cuentas) se suma al de sus componentes.
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
        propio = valores.get(linea, CERO) if linea in aditivas else CERO
        total = propio + sum((signo * valor(c) for c, signo in reglas[linea]), CERO)
        en_curso.discard(linea)
        resultado[linea] = total
        return total

    for linea in reglas:
        valor(linea)
    return resultado


def completar_con_totales(
    reglas: Reglas,
    base: Mapping[int, Decimal],
    aditivas: Collection[int] = frozenset(),
) -> dict[int, Decimal]:
    """Valor de **todas** las líneas: las base tal cual y las que tienen regla, calculadas.

    Si una línea tiene regla, manda la regla aunque venga también en `base`.
    """
    return {**base, **evaluar_totales(reglas, base, aditivas)}
