"""Mapeo línea del reporte ↔ cuentas locales, tal como está en las fórmulas de la hoja `Ago`.

Cada línea de detalle trae en la columna S (Actual del mes) y en la T (Budget) una fórmula como
`=-'4002001.002'!L128-'6023001.002'!L10`: el **nombre de la hoja es el código de cuenta** y el signo
que la antecede es el signo con el que la cuenta entra a la línea. Se prefiere esto a las columnas
X a AJ porque Excel guarda `4002001.010` como número (`4002001.01`) y pierde el cero final.

Si una cuenta aparece en S y en T con signos distintos, manda S (el Actual) y se avisa. Una cuenta
que solo está en T también se toma, con aviso.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import load_workbook

from fpa.ingesta.variance_estructura import (
    HOJA,
    ResultadoEstructura,
    TipoLinea,
    leer_variance_estructura_filas,
)

COLUMNA_S = 18
COLUMNA_T = 19
_TERMINO = re.compile(r"([+-]*)\s*'([^']+)'!\$?[A-Z]{1,3}\$?\d+")
_CODIGO = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.\-]*$")


@dataclass
class VinculoLeido:
    orden: int  # línea de detalle
    fila_origen: int
    cuenta_codigo: str
    signo: int  # +1 o -1
    # `excel` = de una fórmula (código exacto); `excel_ago` = valor pegado en la hoja del reporte
    # (Excel pudo quitarle el cero final al código: se resuelve contra el catálogo al importar)
    origen: str = "excel"


@dataclass
class ResultadoMapeo:
    vinculos: list[VinculoLeido] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)

    @property
    def es_valido(self) -> bool:
        return not self.errores

    @property
    def lineas_vinculadas(self) -> int:
        return len({v.orden for v in self.vinculos})


def analizar_terminos(formula: object) -> tuple[list[tuple[str, int]], str] | None:
    """`=-'4001'!L1+'6001'!L2` -> ([("4001", -1), ("6001", +1)], "").

    Devuelve None si no es una fórmula; el texto devuelto es lo que sobró sin reconocer.
    """
    if not (isinstance(formula, str) and formula.startswith("=")):
        return None
    cuerpo = formula[1:]
    terminos = [
        (m.group(2).strip(), -1 if m.group(1).count("-") % 2 else 1)
        for m in _TERMINO.finditer(cuerpo)
    ]
    resto = _TERMINO.sub("", cuerpo).strip()
    return terminos, resto


def leer_variance_mapeo(ruta: str | Path, hoja: str = HOJA) -> ResultadoMapeo:
    with Path(ruta).open("rb") as archivo:
        wb = load_workbook(archivo, read_only=True, data_only=False)
        try:
            if hoja not in wb.sheetnames:
                raise ValueError(f'El libro no tiene la hoja "{hoja}"')
            filas = [tuple(r) for r in wb[hoja].iter_rows(max_col=COLUMNA_T + 1, values_only=True)]
        finally:
            wb.close()
    return leer_variance_mapeo_filas(filas, leer_variance_estructura_filas(filas))


def _celda(fila: Sequence[object], columna: int) -> object:
    return fila[columna] if len(fila) > columna else None


def leer_variance_mapeo_filas(
    filas: Sequence[Sequence[object]], estructura: ResultadoEstructura
) -> ResultadoMapeo:
    res = ResultadoMapeo()
    if not estructura.es_valido:
        res.errores.append("La estructura del reporte no es válida; no se puede leer el mapeo")
        return res
    solo_budget = 0
    signo_distinto = 0
    ilegibles: list[str] = []
    for linea in estructura.lineas:
        if linea.tipo is not TipoLinea.DETALLE or linea.fila_origen > len(filas):
            continue
        fila = filas[linea.fila_origen - 1]
        por_cuenta: dict[str, int] = {}
        for columna, nombre in ((COLUMNA_S, "S"), (COLUMNA_T, "T")):
            analisis = analizar_terminos(_celda(fila, columna))
            if analisis is None:
                continue
            terminos, resto = analisis
            if resto and terminos:
                ilegibles.append(f"{linea.fila_origen}{nombre}")
            for codigo, signo in terminos:
                if not _CODIGO.match(codigo):
                    res.avisos.append(
                        f"Fila {linea.fila_origen}: código de cuenta inválido {codigo!r}; se ignora"
                    )
                    continue
                if codigo not in por_cuenta:
                    if nombre == "T" and any(c for c in por_cuenta):
                        solo_budget += 1
                    por_cuenta[codigo] = signo
                elif por_cuenta[codigo] != signo and nombre == "S":
                    signo_distinto += 1  # dentro de la misma columna: manda la primera aparición
        for codigo, signo in por_cuenta.items():
            res.vinculos.append(
                VinculoLeido(
                    orden=linea.orden,
                    fila_origen=linea.fila_origen,
                    cuenta_codigo=codigo,
                    signo=signo,
                )
            )
    if not res.vinculos:
        res.errores.append("La hoja no trae fórmulas con cuentas (columnas S y T)")
    if solo_budget:
        res.avisos.append(f"{solo_budget} cuentas solo aparecen en la columna T (Budget)")
    if signo_distinto:
        res.avisos.append(f"{signo_distinto} cuentas repetidas en una línea con signos distintos")
    if ilegibles:
        res.avisos.append(
            f"{len(ilegibles)} fórmulas con términos no reconocidos: {', '.join(ilegibles[:5])}"
        )
    return res
