"""Lectores del Excel de Variance de **Mazatlán** (ver `formato_variance.py`).

La estructura sale de `Ago` (el lector común sirve tal cual). Las **reglas de suma** y el **mapeo
con su signo** salen de las fórmulas de la hoja `Jul-Ago`, columna J (agosto):

    =-SUMIFS('4002011'!L:L,'4002011'!B:B,"Agosto",'4002011'!G:G,"Total")     ingreso: signo −
    =SUMIFS('6009013.001'!L:L,…) + SUMIFS('6009013.002'!L:L,…)               gasto: signo +
    =SUM(J36:J75)    =J76+J77    ='6009081'!L5

El nombre de la hoja citada es el **código exacto de la cuenta** (Excel pierde el cero final en las
celdas: `4002001.010` aparece como `4002001.01` en `Ago!I:O`), y el signo es el de la fórmula.
**Nunca se evalúa** el texto del Excel: solo se reconocen estos términos.

Los valores de referencia (Actual, Budget, Var y %) y el **Budget de cada mes** salen de `Jul-Ago`
(julio en D a H y agosto en I a M) y de `Ago` (agosto en D a H).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook

from fpa.ingesta.formato_variance import HOJA_DOS_MESES, HOJA_REPORTE, PERFIL_MZT
from fpa.ingesta.utilidades import a_texto
from fpa.ingesta.variance_estructura import (
    ResultadoEstructura,
    TipoLinea,
    leer_variance_estructura_filas,
)
from fpa.ingesta.variance_mapeo import ResultadoMapeo, VinculoLeido
from fpa.ingesta.variance_reglas import ResultadoReglas, leer_variance_reglas_filas
from fpa.ingesta.variance_valores import a_decimal

COLUMNAS_REPORTE = 17  # hasta la Q (la de control)
COLUMNAS_DOS_MESES = 13  # hasta la M (agosto: Actual, Budget, Var, %)
# Cuentas de cada línea en `Ago`: columnas I a O (índices 8 a 14)
CUENTAS_DESDE, CUENTAS_HASTA = 8, 15
# Bloques de `Jul-Ago`: (Actual, Budget, Var, %) por mes
BLOQUES = {0: (3, 5, 6, 7), 1: (8, 10, 11, 12)}
COLUMNA_FORMULA_MES = {0: 4, 1: 9}  # E (julio) y J (agosto)

_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}  # fmt: skip
_MESES_EN = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}  # fmt: skip
_RE_ANIO = re.compile(r"month of\s+([a-z]+)[\s-]+(\d{4})", re.IGNORECASE)
_TERMINO = re.compile(
    r"([+-]*)\s*(?:SUMIFS\(\s*'([^']+)'!\$?[A-Z]{1,3}:\$?[A-Z]{1,3}"
    r"|'([^']+)'!\$?[A-Z]{1,3}\$?\d+)",
    re.IGNORECASE,
)
_CODIGO = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.\-]*$")
_MES_CRITERIO = re.compile(
    r'"(Julio|Agosto|Septiembre|Octubre|Noviembre|Diciembre|Enero|Febrero|Marzo|Abril|Mayo|Junio)"',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ValoresMes:
    """Las cuatro cifras de una línea para un mes, tal como las pegó Contraloría."""

    fila_origen: int
    actual: Decimal | None = None
    budget: Decimal | None = None
    var: Decimal | None = None
    pct: Decimal | None = None


@dataclass
class HojasMzt:
    reporte: Sequence[Sequence[object]]  # `Ago`, con fórmulas
    dos_meses: Sequence[Sequence[object]]  # `Jul-Ago`, con fórmulas
    dos_meses_valores: Sequence[Sequence[object]]  # `Jul-Ago`, con valores


def leer_hojas_mzt(ruta: str | Path) -> HojasMzt:
    """Lee las hojas `Ago` y `Jul-Ago` (la segunda con fórmulas y con valores)."""
    with Path(ruta).open("rb") as archivo:
        con_formulas = load_workbook(archivo, read_only=True, data_only=False)
        try:
            for nombre in (HOJA_REPORTE, HOJA_DOS_MESES):
                if nombre not in con_formulas.sheetnames:
                    raise ValueError(f'El libro no tiene la hoja "{nombre}"')
            reporte = [
                tuple(r)
                for r in con_formulas[HOJA_REPORTE].iter_rows(
                    max_col=COLUMNAS_REPORTE, values_only=True
                )
            ]
            dos = [
                tuple(r)
                for r in con_formulas[HOJA_DOS_MESES].iter_rows(
                    max_col=COLUMNAS_DOS_MESES, values_only=True
                )
            ]
        finally:
            con_formulas.close()
    with Path(ruta).open("rb") as archivo:
        con_valores = load_workbook(archivo, read_only=True, data_only=True)
        try:
            valores = [
                tuple(r)
                for r in con_valores[HOJA_DOS_MESES].iter_rows(
                    max_col=COLUMNAS_DOS_MESES, values_only=True
                )
            ]
        finally:
            con_valores.close()
    return HojasMzt(reporte=reporte, dos_meses=dos, dos_meses_valores=valores)


def periodos_de_la_hoja(dos_meses: Sequence[Sequence[object]]) -> list[str]:
    """`['2026-07', '2026-08']` a partir de `Month of July-2026` y los rótulos JULIO / AGOSTO."""
    anio = None
    for fila in dos_meses[:8]:
        for celda in fila:
            m = _RE_ANIO.search(str(celda)) if celda is not None else None
            if m and m.group(1).lower() in _MESES_EN:
                anio = int(m.group(2))
    if anio is None:
        raise ValueError('No se encontró "Month of <mes>-<año>" en la hoja Jul-Ago')
    meses: list[int] = []
    for fila in dos_meses[:8]:
        rotulos = [_MESES.get(str(c).strip().lower()) for c in fila if c is not None]
        encontrados = [m for m in rotulos if m is not None]
        if len(encontrados) >= 2:
            meses = encontrados[:2]
            break
    if len(meses) != 2:
        raise ValueError(
            "No se encontraron los rótulos de los dos meses (JULIO, AGOSTO) en Jul-Ago"
        )
    primero, segundo = meses
    return [
        f"{anio:04d}-{primero:02d}",
        f"{anio + (1 if segundo < primero else 0):04d}-{segundo:02d}",
    ]


def _texto_de_linea(fila: Sequence[object]) -> str:
    """Descripción de la línea (columna C o, en los títulos, B), sin espacios ni mayúsculas."""
    texto = (a_texto(fila[2]) if len(fila) > 2 else None) or (
        a_texto(fila[1]) if len(fila) > 1 else None
    )
    return "".join((texto or "").split()).lower()


def leer_estructura_mzt(hojas: HojasMzt) -> ResultadoEstructura:
    """Estructura de `Ago`; verifica que `Jul-Ago` tenga exactamente las mismas líneas."""
    estructura = leer_variance_estructura_filas(hojas.reporte)
    for linea in estructura.lineas:
        if linea.tipo is TipoLinea.SECCION or linea.fila_origen > len(hojas.dos_meses):
            continue
        aqui = _texto_de_linea(hojas.reporte[linea.fila_origen - 1])
        alla = _texto_de_linea(hojas.dos_meses[linea.fila_origen - 1])
        if aqui != alla:
            estructura.errores.append(
                f"La fila {linea.fila_origen} no es la misma línea en Ago y en Jul-Ago "
                f"({linea.descripcion!r}): las hojas no están alineadas"
            )
            break
    return estructura


def leer_reglas_mzt(hojas: HojasMzt, estructura: ResultadoEstructura) -> ResultadoReglas:
    """Reglas de suma de las fórmulas de agosto (`Jul-Ago!J`)."""
    return leer_variance_reglas_filas(
        hojas.dos_meses,
        estructura,
        columna=PERFIL_MZT.col_formula_mes,
        letra=PERFIL_MZT.letra_formula_mes,
    )


def analizar_terminos_cuenta(formula: object) -> tuple[list[tuple[str, int]], bool] | None:
    """Cuentas de una fórmula de agosto: `[(código, signo)]` y si cita otro mes.

    `=-SUMIFS('4002011'!L:L,…)+SUMIFS('X'!L:L,…)` -> [("4002011", -1), ("X", +1)].
    `None` si no es una fórmula.
    """
    if not (isinstance(formula, str) and formula.startswith("=")):
        return None
    cuerpo = formula[1:]
    terminos = [
        ((m.group(2) or m.group(3)).strip(), -1 if m.group(1).count("-") % 2 else 1)
        for m in _TERMINO.finditer(cuerpo)
    ]
    return terminos, False


def leer_mapeo_mzt(hojas: HojasMzt, estructura: ResultadoEstructura) -> ResultadoMapeo:
    """Cuentas y signo de cada línea de detalle, de las fórmulas de agosto (`Jul-Ago!J`)."""
    res = ResultadoMapeo()
    if not estructura.es_valido:
        res.errores.append("La estructura del reporte no es válida; no se puede leer el mapeo")
        return res
    col = PERFIL_MZT.col_formula_mes
    otro_mes: list[int] = []
    solo_en_ago: list[str] = []
    solo_en_formula: list[str] = []
    for linea in estructura.lineas:
        if linea.tipo is not TipoLinea.DETALLE or linea.fila_origen > len(hojas.dos_meses):
            continue
        fila = hojas.dos_meses[linea.fila_origen - 1]
        valor = fila[col] if len(fila) > col else None
        analisis = analizar_terminos_cuenta(valor)
        por_cuenta: dict[str, int] = {}
        if analisis is not None:
            if _MES_CRITERIO.search(str(valor)) and any(
                m.group(1).lower() != "agosto" for m in _MES_CRITERIO.finditer(str(valor))
            ):
                otro_mes.append(linea.fila_origen)
            for codigo, signo in analisis[0]:
                if not _CODIGO.match(codigo):
                    res.avisos.append(
                        f"Fila {linea.fila_origen}: código de cuenta inválido {codigo!r}; se ignora"
                    )
                    continue
                por_cuenta.setdefault(codigo, signo)
        for codigo, signo in por_cuenta.items():
            res.vinculos.append(
                VinculoLeido(
                    orden=linea.orden,
                    fila_origen=linea.fila_origen,
                    cuenta_codigo=codigo,
                    signo=signo,
                )
            )
        # Cuentas pegadas en `Ago!I:O`. Las que la fórmula no suma (líneas sin movimiento este mes o
        # cuentas agregadas después) también son del mapeo: entran con el signo que da la clase de
        # la cuenta (las que empiezan con 4 restan) y se marcan para resolver su código contra el
        # catálogo, porque Excel pudo quitarles el cero final.
        pegadas = {
            c
            for c in (
                _texto_de_cuenta(v)
                for v in hojas.reporte[linea.fila_origen - 1][CUENTAS_DESDE:CUENTAS_HASTA]
            )
            if c and _CODIGO.match(c)
        }
        formuladas = {normalizar_codigo(c) for c in por_cuenta}
        pegadas_normales = {normalizar_codigo(c) for c in pegadas}
        faltan = sorted(c for c in pegadas if normalizar_codigo(c) not in formuladas)
        sobran = sorted(c for c in por_cuenta if normalizar_codigo(c) not in pegadas_normales)
        for codigo in faltan:
            res.vinculos.append(
                VinculoLeido(
                    orden=linea.orden,
                    fila_origen=linea.fila_origen,
                    cuenta_codigo=codigo,
                    signo=-1 if codigo.startswith("4") else 1,
                    origen="excel_ago",
                )
            )
        if faltan and valor is not None:
            solo_en_ago.append(f"{linea.fila_origen}: {', '.join(faltan)}")
        if sobran and pegadas:
            solo_en_formula.append(f"{linea.fila_origen}: {', '.join(sobran)}")
    if not res.vinculos:
        res.errores.append("La hoja Jul-Ago no trae fórmulas con cuentas (columna J)")
    if otro_mes:
        res.avisos.append(
            f"{len(otro_mes)} fórmulas de agosto citan otro mes: filas "
            f"{', '.join(map(str, otro_mes[:5]))}"
        )
    if solo_en_ago:
        res.avisos.append(
            f"{len(solo_en_ago)} líneas con cuentas en Ago!I:O que su fórmula no suma: "
            f"{'; '.join(solo_en_ago[:4])}"
        )
    if solo_en_formula:
        res.avisos.append(
            f"{len(solo_en_formula)} líneas cuya fórmula suma cuentas que Ago!I:O no lista: "
            f"{'; '.join(solo_en_formula[:4])}"
        )
    return res


def _texto_de_cuenta(valor: object) -> str:
    """Código tal como lo pegó Excel: `4002011` llega como entero y `4002001.01` como flotante."""
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def normalizar_codigo(codigo: object) -> str:
    """`4002001.01` (Excel pierde el cero final) y `4002001.010` se comparan como iguales."""
    texto = str(codigo).strip()
    if re.fullmatch(r"\d+\.\d+", texto):
        entero, decimales = texto.split(".")
        return f"{entero}.{decimales.rstrip('0')}"
    return texto


@dataclass
class ValoresMensualesMzt:
    por_periodo: dict[str, dict[int, ValoresMes]] = field(default_factory=dict)

    @property
    def periodos(self) -> list[str]:
        return sorted(self.por_periodo)


def leer_valores_mensuales_mzt(hojas: HojasMzt) -> ValoresMensualesMzt:
    """Actual, Budget, Var y % de cada línea en cada uno de los dos meses de `Jul-Ago`."""
    periodos = periodos_de_la_hoja(hojas.dos_meses_valores)
    salida = ValoresMensualesMzt()
    for indice, periodo in enumerate(periodos):
        c_act, c_bud, c_var, c_pct = BLOQUES[indice]
        por_fila: dict[int, ValoresMes] = {}
        for n, fila in enumerate(hojas.dos_meses_valores, start=1):
            if len(fila) <= c_pct:
                continue
            valores = [a_decimal(fila[c]) for c in (c_act, c_bud, c_var, c_pct)]
            if any(v is not None for v in valores):
                por_fila[n] = ValoresMes(n, *valores)
        salida.por_periodo[periodo] = por_fila
    return salida
