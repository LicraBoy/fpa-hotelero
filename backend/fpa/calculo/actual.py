"""Motor de Actual: lo realmente ocurrido en cada línea del reporte.

`Actual(línea) = Σ signo × neto(cuenta)` sobre las cuentas que el mapeo vincula a la línea, con
`neto = Débito − Crédito` de la cuenta en el periodo. El signo del vínculo (+1 Deudor, −1 Acreedor)
deja positivos tanto los ingresos como los gastos, igual que el reporte de Contraloría.

Función **pura y determinística**: sin base de datos, sin float, sin efectos. El orden de entrada no
cambia el resultado.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal

CERO = Decimal("0")

# (línea, código de cuenta, signo)
Vinculo = tuple[int, str, int]


def calcular_actual(
    vinculos: Iterable[Vinculo], netos: Mapping[str, Decimal]
) -> dict[int, Decimal]:
    """Actual de cada línea que tenga vínculos (0 si sus cuentas no tuvieron movimiento).

    Una cuenta con movimiento que ningún vínculo toma no aparece en ningún lado: de eso se ocupa
    la validación del mapeo, no el cálculo.
    """
    actual: dict[int, Decimal] = {}
    for linea, cuenta, signo in vinculos:
        if signo not in (1, -1):
            raise ValueError(f"Signo inválido {signo!r} en la línea {linea}, cuenta {cuenta}")
        actual[linea] = actual.get(linea, CERO) + signo * netos.get(cuenta, CERO)
    return actual
