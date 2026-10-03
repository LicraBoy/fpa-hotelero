"""Motor de Variance: arma el reporte completo a partir de sus piezas ya calculadas.

Función **pura**: recibe el Actual del mes y del acumulado (YTD), el Budget (mes, YTD y anual),
las reglas de suma y la convención de signo de cada línea, y devuelve, para cada línea, los tres
bloques del reporte (mes, YTD, anual) con Actual, Budget, Variance y Variance %.

- Totales y subtotales salen de sus reglas, **también en el Budget**.
- El bloque anual compara el Actual acumulado contra el Budget del año completo.
- Un Budget que no existe (`None`) deja Variance y % en `None`: no se inventa un cero.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from fpa.calculo.totales import Reglas, completar_con_totales
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
    base: Mapping[int, Decimal] | None,
    reglas: Reglas,
    detalle_con_regla: Collection[int],
) -> dict[int, Decimal] | None:
    """Budget de todas las líneas (totales por regla); `None` si no hay Budget de este bloque.

    Una línea de detalle con regla (cuentas + otras líneas, o «16 % de otra») trae su Budget como un
    número, igual que cualquier línea de detalle: su regla solo aplica al Actual.
    """
    if base is None:
        return None
    return completar_con_totales(
        {linea: r for linea, r in reglas.items() if linea not in detalle_con_regla}, base
    )


def _aplicar_compuestas(
    salida: dict[int, LineaVariance],
    bloque: str,
    compuestas: Mapping[int, Sequence[tuple[int, int]]],
) -> None:
    """Variación = suma (con signo) de las Variaciones de otras líneas, como en el Excel.

    El Actual y el Presupuesto de la línea no cambian; el % se recalcula con su nueva Variación. Los
    componentes que a su vez son compuestos se resuelven primero; un ciclo no se calcula.
    """
    hechas: dict[int, Decimal | None] = {}
    en_curso: set[int] = set()

    def variacion(linea: int) -> Decimal | None:
        if linea in hechas:
            return hechas[linea]
        actual: Cifras = getattr(salida[linea], bloque)
        if linea not in compuestas or linea in en_curso:
            return actual.var
        en_curso.add(linea)
        total: Decimal | None = CERO
        for componente, signo in compuestas[linea]:
            if componente not in salida:
                continue
            parte = variacion(componente)
            if parte is None or total is None:
                total = None
            else:
                total += signo * parte
        en_curso.discard(linea)
        hechas[linea] = total
        return total

    for linea in compuestas:
        if linea not in salida:
            continue
        var = variacion(linea)
        viejo: Cifras = getattr(salida[linea], bloque)
        nuevo = Cifras(viejo.actual, viejo.budget, var, variance_pct(var, viejo.budget))
        actual_linea = salida[linea]
        salida[linea] = LineaVariance(
            linea_id=actual_linea.linea_id,
            convencion=actual_linea.convencion,
            mes=nuevo if bloque == "mes" else actual_linea.mes,
            ytd=nuevo if bloque == "ytd" else actual_linea.ytd,
            anual=nuevo if bloque == "anual" else actual_linea.anual,
        )


def armar_variance(
    lineas: Sequence[int],
    reglas: Reglas,
    convenciones: Mapping[int, Convencion],
    actual_mes: Mapping[int, Decimal],
    actual_ytd: Mapping[int, Decimal],
    budget_mes: Mapping[int, Decimal] | None,
    budget_ytd: Mapping[int, Decimal] | None,
    budget_anual: Mapping[int, Decimal] | None,
    aditivas: Collection[int] = frozenset(),
    detalle_con_regla: Collection[int] = frozenset(),
    convenciones_bloque: Mapping[str, Mapping[int, Convencion]] | None = None,
    variaciones_compuestas: Mapping[str, Mapping[int, Sequence[tuple[int, int]]]] | None = None,
) -> dict[int, LineaVariance]:
    """`lineas`: ids de las líneas del reporte (sin secciones), en orden.

    `aditivas`: líneas cuyo Actual es «cuentas + componentes». `detalle_con_regla`: líneas de
    detalle con regla (su regla no se aplica al Budget). `convenciones_bloque`: el sentido de la
    Variación escrito en el Excel por línea y bloque (`mes`, `ytd`, `anual`); sin dato, vale
    `convenciones`. `variaciones_compuestas`: líneas cuya Variación el Excel calcula como la
    **suma de las Variaciones de otras líneas** (`=G613-G614`), por bloque.
    """
    a_mes = completar_con_totales(reglas, actual_mes, aditivas)
    a_ytd = completar_con_totales(reglas, actual_ytd, aditivas)
    b_mes = _budget_completo(budget_mes, reglas, detalle_con_regla)
    b_ytd = _budget_completo(budget_ytd, reglas, detalle_con_regla)
    b_anual = _budget_completo(budget_anual, reglas, detalle_con_regla)

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

    por_bloque = convenciones_bloque or {}

    def sentido(bloque: str, linea: int) -> Convencion:
        return por_bloque.get(bloque, {}).get(linea) or convenciones[linea]

    salida: dict[int, LineaVariance] = {}
    for linea in lineas:
        salida[linea] = LineaVariance(
            linea_id=linea,
            convencion=sentido("mes", linea),
            mes=cifras(a_mes, b_mes, linea, sentido("mes", linea)),
            ytd=cifras(a_ytd, b_ytd, linea, sentido("ytd", linea)),
            anual=cifras(a_ytd, b_anual, linea, sentido("anual", linea)),
        )
    if variaciones_compuestas:
        for bloque, por_linea in variaciones_compuestas.items():
            _aplicar_compuestas(salida, bloque, por_linea)
    return salida
