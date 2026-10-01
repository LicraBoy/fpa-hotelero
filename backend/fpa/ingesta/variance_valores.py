"""Valores (no fórmulas) de las columnas D a Q de la hoja `Ago` del Variance.

Sirve para dos cosas: cargar el **Budget** pegado en el Excel (columnas E, J y O) y comparar el
motor de Variance contra el reporte de Contraloría (prueba dorada). Los números se leen como
`Decimal(str(valor))`, sin pasar por `float`, y **sin redondear**: el Budget del Excel trae
decimales de más (`20639.6489456203`) y recortarlo cambiaría los totales.

Bloques de la hoja: mes (D Actual, E Budget, F Var, G %), YTD (I, J, K, L) y anual
(N Actual YTD, O Budget anual, P, Q). H y M son columnas de comentarios.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fpa.ingesta.variance_estructura import HOJA, leer_filas_hoja

# índice (desde 0) de cada columna en la hoja
_COLUMNAS = {
    "mes_actual": 3,
    "mes_budget": 4,
    "mes_var": 5,
    "mes_pct": 6,
    "ytd_actual": 8,
    "ytd_budget": 9,
    "ytd_var": 10,
    "ytd_pct": 11,
    "anual_actual": 13,
    "anual_budget": 14,
    "anual_var": 15,
    "anual_pct": 16,
}


@dataclass(frozen=True)
class ValoresFila:
    fila_origen: int
    mes_actual: Decimal | None = None
    mes_budget: Decimal | None = None
    mes_var: Decimal | None = None
    mes_pct: Decimal | None = None
    ytd_actual: Decimal | None = None
    ytd_budget: Decimal | None = None
    ytd_var: Decimal | None = None
    ytd_pct: Decimal | None = None
    anual_actual: Decimal | None = None
    anual_budget: Decimal | None = None
    anual_var: Decimal | None = None
    anual_pct: Decimal | None = None

    @property
    def tiene_budget(self) -> bool:
        return any(v is not None for v in (self.mes_budget, self.ytd_budget, self.anual_budget))


def a_decimal(valor: object) -> Decimal | None:
    """Número de Excel -> Decimal exacto (sin float). Texto, vacío o error -> None."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        try:
            return Decimal(str(valor))
        except InvalidOperation:
            return None
    return None


def leer_valores_filas(filas: Sequence[Sequence[object]]) -> dict[int, ValoresFila]:
    """`{fila_origen: ValoresFila}` solo para filas con algún número en D a Q."""
    salida: dict[int, ValoresFila] = {}
    for n, fila in enumerate(filas, start=1):
        valores = {
            campo: a_decimal(fila[i]) if i < len(fila) else None for campo, i in _COLUMNAS.items()
        }
        if any(v is not None for v in valores.values()):
            salida[n] = ValoresFila(fila_origen=n, **valores)
    return salida


def leer_variance_valores(ruta: str | Path, hoja: str = HOJA) -> dict[int, ValoresFila]:
    """Lee la hoja con los **valores calculados** que guardó Excel (no las fórmulas)."""
    return leer_valores_filas(leer_filas_hoja(ruta, hoja, max_col=17, solo_valores=True))
