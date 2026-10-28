"""Lector de una sección del Budget de Mazatlán que NO tiene hoja propia (p. ej. *Mgmt & Check In*).

A diferencia de *Other Income* (hoja `Other Income` con fórmulas base × factor), estas secciones viven
dentro de la hoja `Budget 26-27 MZT`: un título con las letras separadas (`M g m t   &   C h e c k
I n`), una fila por cuenta (código en la columna B, descripción en la C, JUL … JUN en D..O) y un
renglón `Total …` al final. La fórmula nunca se evalúa: se leen los valores que Excel dejó guardados.

- Una cuenta con `#REF!` (p. ej. la nómina, cuyos salarios se borraron del libro) o con celdas vacías
  **no se importa**: se avisa y queda para captura.
- Los importes del Budget se importan como monto fijo (son el resultado ya calculado, con inflación).
- El bloque inferior de la hoja (Est-Act y Budget del año previo) sale del renglón `Total …` de las
  hojas `EstAct 25-26 MZT` y `MZT Budget 25-26`, que tienen la misma distribución de filas.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook

from fpa.ingesta.budget_partidas import datos_de_hoja, leer_hoja_partidas
from fpa.ingesta.budget_other_income import (
    HOJA_BUDGET,
    CeldaLeida,
    FilaOtherIncome,
    OtherIncomeLeido,
    _dec,
    normalizar,
)

HOJA_EST_ACT_PREVIO = "EstAct 25-26 MZT"
HOJA_BUDGET_PREVIO = "MZT Budget 25-26"
COL_CODIGO = 1  # B
COL_DESCRIPCION = 2  # C
COL_PRIMER_MES = 3  # D
# Departamento (prefijo de las hojas `0111-60055 Other Fringe`) de las secciones con partidas
DEPARTAMENTO_POR_SECCION = {"mgmtcheckin": "0111"}
MESES = 12
_COLS_MAX = COL_PRIMER_MES + MESES

Fila = Sequence[object]


def _limpiar(texto: object) -> str:
    """`A l l o c a t e d   E x p e n s e s` -> `Allocated Expenses` (el Excel separa las letras)."""
    t = str(texto or "").strip()
    if re.match(r"^(\S ){5,}", t):
        return t.replace("   ", "|").replace(" ", "").replace("|", " ")
    return t


def _celdas_de(fila: Fila) -> list[object]:
    return list(fila) + [None] * (_COLS_MAX - len(fila))


def _meses_de(fila: Fila) -> list[Decimal | None]:
    celdas = _celdas_de(fila)
    return [_dec(celdas[COL_PRIMER_MES + i]) for i in range(MESES)]


def _limites_seccion(filas: Sequence[Fila], seccion: str) -> tuple[int, int] | None:
    """(índice de la primera cuenta, índice del renglón `Total …`) o `None` si no hay la sección."""
    inicio = next(
        (i for i, f in enumerate(filas) if normalizar(_celdas_de(f)[COL_CODIGO]) == seccion), None
    )
    if inicio is None:
        return None
    total = f"total{seccion}"
    for i in range(inicio + 1, len(filas)):
        if normalizar(_celdas_de(filas[i])[COL_DESCRIPCION]) == total:
            return inicio + 1, i
    return None


def _total_de_seccion(filas: Sequence[Fila], seccion: str) -> list[Decimal] | None:
    """Los 12 importes del renglón `Total …` de la sección; `None` si falta o trae `#REF!`."""
    limites = _limites_seccion(filas, seccion)
    if limites is None:
        return None
    meses = _meses_de(filas[limites[1]])
    return None if any(m is None for m in meses) else [m for m in meses if m is not None]


def _meses_por_cuenta(filas: Sequence[Fila], seccion: str) -> dict[str, list[Decimal | None]]:
    """Por cuenta (nombre normalizado), sus 12 importes de la hoja del año previo (`None` si no son número)."""
    limites = _limites_seccion(filas, seccion)
    if limites is None:
        return {}
    salida: dict[str, list[Decimal | None]] = {}
    for n in range(limites[0], limites[1]):
        concepto = _limpiar(_celdas_de(filas[n])[COL_DESCRIPCION])
        if concepto and not normalizar(concepto).startswith("total"):
            salida.setdefault(normalizar(concepto), _meses_de(filas[n]))
    return salida


def leer_seccion_filas(
    budget: Sequence[Fila],
    est_act_previo: Sequence[Fila] | None,
    budget_previo: Sequence[Fila] | None,
    seccion: str,
    nombre: str,
) -> OtherIncomeLeido:
    """Lee la sección (`seccion` = nombre normalizado, p. ej. `mgmtcheckin`) de las hojas ya cargadas."""
    res = OtherIncomeLeido()
    limites = _limites_seccion(budget, seccion)
    if limites is None:
        raise ValueError(f"La hoja {HOJA_BUDGET} no trae la sección «{nombre}»")
    desde, hasta = limites
    con_ref: list[str] = []
    for n in range(desde, hasta):
        celdas = _celdas_de(budget[n])
        concepto = _limpiar(celdas[COL_DESCRIPCION])
        if not concepto or normalizar(concepto).startswith("total"):
            continue
        meses = _meses_de(budget[n])
        if any(m is None for m in meses):
            con_ref.append(concepto)
            continue
        res.filas.append(
            FilaOtherIncome(
                n + 1,
                concepto,
                [CeldaLeida("fijo", m, monto_fijo=m) for m in meses if m is not None],
            )
        )
    res.sin_importes = list(con_ref)
    if con_ref:
        res.avisos.append(
            f"{len(con_ref)} cuentas traen #REF! o celdas vacías y quedan para captura: "
            + ", ".join(f"«{c}»" for c in con_ref)
        )
    if not res.filas:
        res.avisos.append(f"La sección «{nombre}» no trae cuentas con importes")
    por_cuenta: dict[str, list[list[Decimal | None]]] = {}
    for origen, hoja_previa in ((0, est_act_previo), (1, budget_previo)):
        if hoja_previa is not None:
            for concepto, meses in _meses_por_cuenta(hoja_previa, seccion).items():
                por_cuenta.setdefault(concepto, [[None] * MESES, [None] * MESES])[origen] = meses
    res.referencias = {k: (v[0], v[1]) for k, v in por_cuenta.items()}
    if est_act_previo is not None:
        res.est_act = _total_de_seccion(est_act_previo, seccion)
        if res.est_act is None:
            res.avisos.append(f"No se pudo leer el Est-Act del año previo de «{nombre}»")
    if budget_previo is not None:
        res.budget_previo = _total_de_seccion(budget_previo, seccion)
        if res.budget_previo is None:
            res.avisos.append(f"No se pudo leer el Budget del año previo de «{nombre}»")
    return res


def leer_seccion(ruta: str | Path, seccion: str, nombre: str) -> OtherIncomeLeido:
    """Lee una sección de un libro `.xlsx` (sin evaluar fórmulas)."""

    def hoja(wb, titulo: str) -> list[tuple[object, ...]] | None:  # type: ignore[no-untyped-def]
        if titulo not in wb.sheetnames:
            return None
        return [tuple(r) for r in wb[titulo].iter_rows(max_col=_COLS_MAX, values_only=True)]

    with Path(ruta).open("rb") as archivo:
        wb = load_workbook(archivo, read_only=True, data_only=True)
        try:
            budget = hoja(wb, HOJA_BUDGET)
            if budget is None:
                raise ValueError(f'El libro no tiene la hoja "{HOJA_BUDGET}"')
            leido = leer_seccion_filas(
                budget, hoja(wb, HOJA_EST_ACT_PREVIO), hoja(wb, HOJA_BUDGET_PREVIO), seccion, nombre
            )
            departamento = DEPARTAMENTO_POR_SECCION.get(seccion)
            for titulo in wb.sheetnames if departamento else []:
                datos = datos_de_hoja(titulo)
                if datos is None or datos[0] != departamento:
                    continue
                filas = [
                    tuple(r) for r in wb[titulo].iter_rows(max_row=60, max_col=26, values_only=True)
                ]
                try:
                    leida = leer_hoja_partidas(titulo, filas)
                except ValueError as e:
                    leido.avisos.append(str(e))
                    continue
                leido.partidas.append(leida)
            return leido
        finally:
            wb.close()


__all__ = ["leer_seccion", "leer_seccion_filas"]
