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
DEPARTAMENTO_POR_SECCION = {
    "mgmtcheckin": "0111",
    "accounting": "0115",
    "maidlinen": "0114",
    "apartmentinterior": "0118",
    "commonarea": "0106",
    "utilities": "0000",
    "owneractivities": "0101",
    "othertaxesfeesandinsurance": "0000",
    "ownerservices": "0108",
    "purchasing": "0122",
    "telephones": "0000",
    "travelagency": "0120",
    "store": "0128",
    "cafeteria": "5036",
    "bar": "0103",
    "moneyexchange": "0109",
    "restaurant": "0124",
    "legal": "0130",
    "itsystems": "1136|0000",  # varios departamentos separados por «|»
}
# Commercial Services: cada negocio trae un bloque de ventas y otro de gastos con el MISMO título. La clave de la
# sección lleva el ordinal del bloque (`store`, `store#2`) y cada bloque termina donde empieza el siguiente título.
BLOQUES_COMERCIALES = {
    "telephones", "travelagency", "store", "cafeteria", "bar", "moneyexchange", "restaurant",
}  # fmt: skip
# Renglones que el Excel calcula (no son cuentas): se ignoran en las secciones comerciales
_CALCULADOS = ("total", "gross", "net", "telephoneprofit")
# Secciones cuyo renglón de cierre no lleva el nombre completo (`Total Other Taxes`)
TOTAL_ALTERNO = {
    "othertaxesfeesandinsurance": "totalothertaxes",
    "vdsallocationcollections": "totalvdsallocationc",  # el Excel corta el texto del total
}
# Filas que se leen de cada hoja de detalle: las de Kit Items llegan a 186 (con 60 se truncaban)
_MAX_FILAS_HOJA = 300
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


def separar_clave(seccion: str) -> tuple[str, int]:
    """`store#2` -> (`store`, 2); `store` -> (`store`, 1)."""
    base, _, n = seccion.partition("#")
    return base, int(n) if n.isdigit() else 1


def _es_titulo(fila: Fila) -> bool:
    """Un renglón de título de bloque: texto en B, nada en C y no es un código de cuenta."""
    celdas = _celdas_de(fila)
    texto = str(celdas[COL_CODIGO] or "").strip()
    return bool(texto) and not str(celdas[COL_DESCRIPCION] or "").strip() and not texto[0].isdigit()


def _es_calculado(concepto: str, base: str) -> bool:
    n = normalizar(concepto)
    if base in BLOQUES_COMERCIALES:
        return n.startswith(_CALCULADOS)
    return n.startswith("total")


def _limites_seccion(filas: Sequence[Fila], seccion: str) -> tuple[int, int] | None:
    """(índice de la primera cuenta, índice del renglón de cierre) o `None` si no hay la sección. En las
    secciones comerciales el cierre es el título del bloque siguiente; en las demás, el renglón `Total …`."""
    base, ordinal = separar_clave(seccion)
    titulos = [i for i, f in enumerate(filas) if normalizar(_celdas_de(f)[COL_CODIGO]) == base]
    if len(titulos) < ordinal:
        return None
    inicio = titulos[ordinal - 1]
    if base in BLOQUES_COMERCIALES:
        siguiente = next((i for i in range(inicio + 1, len(filas)) if _es_titulo(filas[i])), None)
        return (inicio + 1, siguiente) if siguiente is not None else None
    seccion = base
    totales = {f"total{seccion}", TOTAL_ALTERNO.get(seccion, "")}
    for i in range(inicio + 1, len(filas)):
        if normalizar(_celdas_de(filas[i])[COL_DESCRIPCION]) in totales:
            return inicio + 1, i
    return None


def _total_de_seccion(filas: Sequence[Fila], seccion: str) -> list[Decimal] | None:
    """Los 12 importes del renglón `Total …` de la sección; `None` si falta o trae `#REF!`."""
    limites = _limites_seccion(filas, seccion)
    if limites is None:
        return None
    base, _ = separar_clave(seccion)
    if base in BLOQUES_COMERCIALES:
        # no hay renglón de total: es la suma de las cuentas del bloque (las que traen sus 12 importes)
        cuentas = [
            _meses_de(filas[n])
            for n in range(limites[0], limites[1])
            if _limpiar(_celdas_de(filas[n])[COL_DESCRIPCION])
            and not _es_calculado(_limpiar(_celdas_de(filas[n])[COL_DESCRIPCION]), base)
        ]
        validas = [c for c in cuentas if all(m is not None for m in c)]
        if not validas:
            return None
        return [sum((c[i] or Decimal(0) for c in validas), Decimal(0)) for i in range(MESES)]
    meses = _meses_de(filas[limites[1]])
    if any(m is None for m in meses):
        # el renglón de total trae #REF! (p. ej. Legal): se usa la suma de las cuentas que sí traen sus 12 importes
        cuentas = [
            _meses_de(filas[n])
            for n in range(limites[0], limites[1])
            if _limpiar(_celdas_de(filas[n])[COL_DESCRIPCION])
            and not _es_calculado(_limpiar(_celdas_de(filas[n])[COL_DESCRIPCION]), base)
        ]
        validas = [c for c in cuentas if all(m is not None for m in c)]
        if not validas:
            return None
        return [sum((c[i] or Decimal(0) for c in validas), Decimal(0)) for i in range(MESES)]
    return [m for m in meses if m is not None]


def _meses_por_cuenta(filas: Sequence[Fila], seccion: str) -> dict[str, list[Decimal | None]]:
    """Por cuenta (nombre normalizado), sus 12 importes de la hoja del año previo (`None` si no son número)."""
    limites = _limites_seccion(filas, seccion)
    if limites is None:
        return {}
    salida: dict[str, list[Decimal | None]] = {}
    base, _ = separar_clave(seccion)
    for n in range(limites[0], limites[1]):
        concepto = _limpiar(_celdas_de(filas[n])[COL_DESCRIPCION])
        if concepto and not _es_calculado(concepto, base):
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
        if not concepto or _es_calculado(concepto, separar_clave(seccion)[0]):
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
            departamentos = set((DEPARTAMENTO_POR_SECCION.get(separar_clave(seccion)[0]) or '').split('|')) - {''}
            for titulo in wb.sheetnames if departamentos else []:
                datos = datos_de_hoja(titulo)
                if datos is None or datos[0] not in departamentos:
                    continue
                filas = [
                    tuple(r) for r in wb[titulo].iter_rows(max_row=_MAX_FILAS_HOJA, max_col=32, values_only=True)
                ]
                try:
                    leida = leer_hoja_partidas(titulo, filas)
                except ValueError as e:
                    leido.avisos.append(f"{e}; esa hoja no se lee")
                    continue
                leido.partidas.append(leida)
            return leido
        finally:
            wb.close()


__all__ = ["leer_seccion", "leer_seccion_filas"]
