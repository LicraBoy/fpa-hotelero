"""Motor de Variance: arma el reporte completo a partir de sus piezas ya calculadas.

Función **pura**: recibe el Actual del mes y del acumulado (YTD), el Budget (mes, YTD y anual),
las reglas de suma y la convención de signo de cada línea, y devuelve, para cada línea, los tres
bloques del reporte (mes, YTD, anual) con Actual, Budget, Variance y Variance %.

- Totales y subtotales salen de sus reglas, **también en el Budget**.
- El bloque anual compara el Actual acumulado contra el Budget del año completo.
- Un Budget que no existe (`None`) deja Variance y % en `None`: no se inventa un cero.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from fpa.calculo.totales import completar_con_totales
from fpa.calculo.variance import Convencion, variance, variance_pct

CERO = Decimal("0")


@dataclass(frozen=True)
class Cifras:
    actual: Decimal
    budget: Decimal | None
    var: Decimal | None
    pct: Decimal | None


@dataclass(frozen=True)
class LineaVariance:
    linea_id: int
    convencion: Convencion
    mes: Cifras
    ytd: Cifras
    anual: Cifras


def _budget_completo(
    base: Mapping[int, Decimal] | None, reglas: Mapping[int, Sequence[tuple[int, int]]]
) -> dict[int, Decimal] | None:
    """Budget de todas las líneas (totales por regla); `None` si no hay Budget de este bloque."""
    if base is None:
        return None
    return completar_con_totales(reglas, base)


def armar_variance(
    lineas: Sequence[int],
    reglas: Mapping[int, Sequence[tuple[int, int]]],
    convenciones: Mapping[int, Convencion],
    actual_mes: Mapping[int, Decimal],
    actual_ytd: Mapping[int, Decimal],
    budget_mes: Mapping[int, Decimal] | None,
    budget_ytd: Mapping[int, Decimal] | None,
    budget_anual: Mapping[int, Decimal] | None,
) -> dict[int, LineaVariance]:
    """`lineas`: ids de las líneas del reporte (sin secciones), en orden."""
    a_mes = completar_con_totales(reglas, actual_mes)
    a_ytd = completar_con_totales(reglas, actual_ytd)
    b_mes = _budget_completo(budget_mes, reglas)
    b_ytd = _budget_completo(budget_ytd, reglas)
    b_anual = _budget_completo(budget_anual, reglas)

    def cifras(
        actual: Mapping[int, Decimal],
        budget: Mapping[int, Decimal] | None,
        linea: int,
        convencion: Convencion,
    ) -> Cifras:
        real = actual.get(linea, CERO)
        previsto = budget.get(linea) if budget is not None else None
        var = variance(real, previsto, convencion)
        return Cifras(real, previsto, var, variance_pct(var, previsto))

    salida: dict[int, LineaVariance] = {}
    for linea in lineas:
        conv = convenciones[linea]
        salida[linea] = LineaVariance(
            linea_id=linea,
            convencion=conv,
            mes=cifras(a_mes, b_mes, linea, conv),
            ytd=cifras(a_ytd, b_ytd, linea, conv),
            anual=cifras(a_ytd, b_anual, linea, conv),
        )
    return salida
