"""Variance y Variance %: cuánto se desvió lo real del plan, con la convención del reporte.

**Convención de signo** (configurable, `[POR VALIDAR]` con Contraloría): el reporte muestra el
Variance como *favorable positivo*:
- ingresos y utilidades: `Actual − Budget`  (`REAL_MENOS_PRESUPUESTO`)
- gastos y costos:       `Budget − Actual`  (`PRESUPUESTO_MENOS_REAL`)

Se deduce de la propia estructura, sin tabla aparte, y se puede corregir línea por línea:
- línea de detalle: por el signo mayoritario de sus cuentas **de resultados** (clases 4, 5 y 6;
  −1 = Acreedor = ingreso). Una cuenta de pasivo (clase 2) con signo −1, como el IVA por pagar,
  no hace ingreso a la línea: `IVA Taxes` es un gasto;
- detalle o línea sin cuentas: por la mayoría de su sección (sin información: gasto);
- total o subtotal: por la de su **primer componente positivo** (así `Profit = Ingresos − Gastos`
  sigue a los ingresos y `Total Gastos` a los gastos).

**Variance %** = `Var / |Budget|`. Con Budget 0 no hay división: vale `+1` si el Variance es
positivo, `−1` si es negativo y `0` si es cero (lo mismo que hace el reporte). Sin Budget
(`None`) no hay Variance ni %: se devuelve `None`, nunca un cero inventado.

Todo es **puro y determinístico** (`Decimal`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

CERO = Decimal("0")
UNO = Decimal("1")


class Convencion(StrEnum):
    REAL_MENOS_PRESUPUESTO = "real_menos_presupuesto"  # ingresos y utilidades
    PRESUPUESTO_MENOS_REAL = "presupuesto_menos_real"  # gastos y costos


def variance(actual: Decimal, budget: Decimal | None, convencion: Convencion) -> Decimal | None:
    """Variance favorable-positivo; `None` si no hay Budget."""
    if budget is None:
        return None
    if convencion is Convencion.REAL_MENOS_PRESUPUESTO:
        return actual - budget
    return budget - actual


def variance_pct(var: Decimal | None, budget: Decimal | None) -> Decimal | None:
    """`Var / |Budget|`; con Budget 0, `+1`, `-1` o `0` según el signo del Variance."""
    if var is None or budget is None:
        return None
    if budget == CERO:
        return UNO if var > CERO else -UNO if var < CERO else CERO
    return var / abs(budget)


@dataclass(frozen=True)
class LineaParaConvencion:
    id: int
    tipo: str  # seccion | detalle | subtotal | total | informativa
    seccion_id: int | None


def _mayoria(signos: Sequence[int]) -> Convencion | None:
    """Ingreso si hay más cuentas Acreedoras (−1) que Deudoras (+1); None si no hay cuentas."""
    if not signos:
        return None
    acreedoras = sum(1 for s in signos if s < 0)
    if acreedoras * 2 > len(signos):
        return Convencion.REAL_MENOS_PRESUPUESTO
    return Convencion.PRESUPUESTO_MENOS_REAL


def deducir_convenciones(
    lineas: Sequence[LineaParaConvencion],
    cuentas_por_linea: Mapping[int, Sequence[tuple[str, int]]],
    reglas: Mapping[int, Sequence[tuple[int, int]]],
    excepciones: Mapping[int, Convencion] | None = None,
) -> dict[int, Convencion]:
    """Convención de cada línea (menos las secciones). `excepciones` manda sobre lo deducido.

    `cuentas_por_linea`: línea -> [(código de cuenta, signo)]. `lineas` debe venir en el orden del
    reporte: de él depende cuál es el "primer componente".
    """
    excepciones = excepciones or {}
    orden = {x.id: i for i, x in enumerate(lineas)}
    por_id = {x.id: x for x in lineas}

    # 1) detalle con cuentas, por sus signos
    propia: dict[int, Convencion] = {}
    for linea in lineas:
        signos = [s for cuenta, s in cuentas_por_linea.get(linea.id, ()) if cuenta[:1] in "456"]
        if linea.tipo == "detalle" and (c := _mayoria(signos)):
            propia[linea.id] = c

    # 2) mayoría de cada sección entre las líneas con cuentas
    por_seccion: dict[int, list[int]] = {}
    for linea_id, conv in propia.items():
        seccion = por_id[linea_id].seccion_id
        if seccion is not None:
            por_seccion.setdefault(seccion, []).append(
                -1 if conv is Convencion.REAL_MENOS_PRESUPUESTO else 1
            )
    de_seccion = {s: _mayoria(signos) for s, signos in por_seccion.items()}

    resultado: dict[int, Convencion] = {}
    en_curso: set[int] = set()

    def convencion(linea_id: int) -> Convencion:
        if linea_id in excepciones:
            return excepciones[linea_id]
        if linea_id in resultado:
            return resultado[linea_id]
        if linea_id in propia:
            return propia[linea_id]
        if linea_id in reglas and linea_id not in en_curso:
            componentes = sorted(
                (c for c, _ in reglas[linea_id] if c in orden), key=lambda c: orden[c]
            )
            positivos = [c for c, signo in reglas[linea_id] if signo > 0 and c in orden]
            primero = min(positivos or componentes, key=lambda c: orden[c], default=None)
            if primero is not None:
                en_curso.add(linea_id)
                resultado[linea_id] = convencion(primero)
                en_curso.discard(linea_id)
                return resultado[linea_id]
        seccion = por_id[linea_id].seccion_id
        resultado[linea_id] = (
            de_seccion.get(seccion) if seccion is not None else None
        ) or Convencion.PRESUPUESTO_MENOS_REAL
        return resultado[linea_id]

    return {x.id: convencion(x.id) for x in lineas if x.tipo != "seccion"}
