"""Acumulado del año fiscal (YTD): suma de los meses desde su inicio hasta el corte.

Función **pura**. Un mes sin datos (nadie cargó ese periodo) **no se oculta**: se devuelve en
`sin_datos` para que el reporte avise que el acumulado está incompleto. Cuenta como cero.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal

from fpa.calculo.ano_fiscal import MES_INICIO_POR_DEFECTO, periodos_ytd

CERO = Decimal("0")


@dataclass(frozen=True)
class AcumuladoYtd:
    por_linea: dict[int, Decimal]
    periodos: list[str]
    sin_datos: list[str] = field(default_factory=list)

    @property
    def completo(self) -> bool:
        return not self.sin_datos


def acumular_ytd(
    actual_por_periodo: Mapping[str, Mapping[int, Decimal]],
    periodo: str,
    mes_inicio: int = MES_INICIO_POR_DEFECTO,
) -> AcumuladoYtd:
    """Suma, línea por línea, el Actual de cada mes del año fiscal hasta `periodo`.

    `actual_por_periodo` solo trae los meses que **tienen datos**; los demás van a `sin_datos`.
    """
    periodos = periodos_ytd(periodo, mes_inicio)
    total: dict[int, Decimal] = {}
    sin_datos: list[str] = []
    for p in periodos:
        mes = actual_por_periodo.get(p)
        if mes is None:
            sin_datos.append(p)
            continue
        for linea, valor in mes.items():
            total[linea] = total.get(linea, CERO) + valor
    return AcumuladoYtd(por_linea=total, periodos=periodos, sin_datos=sin_datos)
