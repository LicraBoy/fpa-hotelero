"""Lector de la estructura del reporte Variance (hoja `Ago` del Excel de Contraloría).

La hoja mezcla secciones, líneas de detalle, subtotales y totales. No hay columna de "tipo": se
deduce de qué columna trae el texto y cómo está escrito (los títulos de sección y de total vienen
con las letras separadas, `T o t a l   O t h e r`). Se lee por posición de columna porque la hoja no
tiene encabezados fiables:

- A: clave concatenada (código + descripción); no se usa.
- B: código corporativo (`029-0101-45010-000`, **se repite** entre líneas) o título de sección.
- C: descripción de la línea, o texto del subtotal/total.
- D: Actual del mes (solo se usa para distinguir una fila informativa de un título).
- S: fórmula de control; con importe y fórmula es subtotal/total, sin fórmula es informativa.

Solo se importa la **estructura** (qué líneas hay y en qué orden); las cifras y el mapeo a cuentas
llegan en las sub-fases siguientes.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from openpyxl import load_workbook

from fpa.ingesta.utilidades import a_texto

HOJA = "Ago"

_RE_CODIGO_CORPORATIVO = re.compile(r"^\d+(?:-\d+)+$")
# "T o t a l   O t h e r": cada letra separada por un espacio
# Fórmula que solo suma o resta otras filas de la columna S (`=S438`, `=SUM(S1:S5)`, `=S6-S7`)
_REF_S = r"(?:SUM\(\s*S\d+\s*:\s*S\d+\s*\)|S\d+)"
_RE_FORMULA_DE_SUMA = re.compile(
    rf"^=\s*[+-]?\s*{_REF_S}(?:\s*[+-]\s*{_REF_S})*\s*$", re.IGNORECASE
)
_RE_ESPACIADO = re.compile(r"^(?:\S +){2,}\S")


class TipoLinea(StrEnum):
    SECCION = "seccion"
    DETALLE = "detalle"
    SUBTOTAL = "subtotal"
    TOTAL = "total"
    INFORMATIVA = "informativa"  # tipo de cambio, líneas de resumen sin código, notas con importe


@dataclass
class LineaLeida:
    orden: int
    fila_origen: int
    tipo: TipoLinea
    descripcion: str
    codigo_corporativo: str | None = None
    # `orden` de la sección a la que pertenece (None si aparece antes de la primera sección)
    seccion_orden: int | None = None

    @property
    def nivel(self) -> int:
        return 0 if self.tipo is TipoLinea.SECCION else 1

    @property
    def clave(self) -> str:
        """Clave **provisional**: la clave natural está por confirmar con Contraloría."""
        return f"{self.orden:04d}:{_slug(self.descripcion)}"


@dataclass
class ResultadoEstructura:
    lineas: list[LineaLeida] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)

    @property
    def es_valido(self) -> bool:
        return not self.errores

    def contar(self, tipo: TipoLinea) -> int:
        return sum(1 for linea in self.lineas if linea.tipo is tipo)


def _slug(texto: str) -> str:
    sin_acentos = unicodedata.normalize("NFKD", texto)
    return re.sub(r"[^a-z0-9]+", "-", sin_acentos.lower()).strip("-")[:80]


def _es_espaciado(texto: str | None) -> bool:
    return texto is not None and _RE_ESPACIADO.match(texto) is not None


def normalizar_texto_espaciado(texto: str) -> str:
    """`T o t a l   O t h e r` -> `Total Other`. Un texto normal se devuelve igual."""
    if not _es_espaciado(texto):
        return " ".join(texto.split())
    palabras = re.split(r"\s{2,}", texto.strip())
    return " ".join(p.replace(" ", "") for p in palabras if p.strip())


def _es_total(descripcion: str) -> bool:
    minuscula = descripcion.lower()
    return minuscula.startswith(("total", "grand total"))


def _ubicar_inicio(filas: Sequence[Sequence[object]]) -> int:
    """Índice de la primera fila de datos: dos filas después de la que dice `Account #`."""
    for i, fila in enumerate(filas[:30]):
        if len(fila) > 1 and isinstance(fila[1], str) and fila[1].strip().lower() == "account #":
            return i + 2
    raise ValueError('No se encontró el encabezado "Account #" de la hoja del Variance')


def leer_filas_hoja(
    ruta: str | Path, hoja: str = HOJA, max_col: int = 20, solo_valores: bool = False
) -> list[tuple[object, ...]]:
    """Filas de la hoja hasta `max_col`: con **fórmulas** o, si `solo_valores`, con sus valores."""
    with Path(ruta).open("rb") as archivo:
        wb = load_workbook(archivo, read_only=True, data_only=solo_valores)
        try:
            if hoja not in wb.sheetnames:
                raise ValueError(f'El libro no tiene la hoja "{hoja}"')
            return [tuple(r) for r in wb[hoja].iter_rows(max_col=max_col, values_only=True)]
        finally:
            wb.close()


def leer_variance_estructura(ruta: str | Path, hoja: str = HOJA) -> ResultadoEstructura:
    with Path(ruta).open("rb") as archivo:
        wb = load_workbook(archivo, read_only=True, data_only=False)
        try:
            if hoja not in wb.sheetnames:
                raise ValueError(f'El libro no tiene la hoja "{hoja}"')
            filas = [tuple(r) for r in wb[hoja].iter_rows(max_col=19, values_only=True)]
        finally:
            wb.close()
    return leer_variance_estructura_filas(filas)


def leer_variance_estructura_filas(filas: Sequence[Sequence[object]]) -> ResultadoEstructura:
    res = ResultadoEstructura()
    try:
        inicio = _ubicar_inicio(filas)
    except ValueError as e:
        res.errores.append(str(e))
        return res

    seccion_actual: int | None = None
    sin_etiqueta: list[int] = []
    for n, fila in enumerate(filas[inicio:], start=inicio + 1):
        celdas = [*fila, *([None] * 19)][:19]
        b, c = a_texto(celdas[1]), a_texto(celdas[2])
        d = celdas[3]
        if isinstance(d, str) and not d.strip():
            d = None  # un espacio en blanco no es una cifra (Mazatlán rotula así sus secciones)
        formula = celdas[18] if isinstance(celdas[18], str) else ""
        con_formula = formula.startswith("=")
        es_suma = _RE_FORMULA_DE_SUMA.match(formula) is not None
        if b is None and c is None:
            if d is not None:
                sin_etiqueta.append(n)  # cifras sin nombre (p. ej. un porcentaje suelto)
            continue

        tipo: TipoLinea
        codigo: str | None = None
        if b is not None and _RE_CODIGO_CORPORATIVO.match(b):
            tipo, codigo = TipoLinea.DETALLE, b
            texto = c or b
        elif b is not None and _es_espaciado(b):
            texto = normalizar_texto_espaciado(b)
            if d is None:
                tipo = TipoLinea.SECCION
            elif con_formula:  # subtotal con el título en la columna B (p. ej. PUERTO VALLARTA)
                tipo = TipoLinea.TOTAL if _es_total(texto) else TipoLinea.SUBTOTAL
            else:
                tipo = TipoLinea.INFORMATIVA
        else:
            texto = normalizar_texto_espaciado(c or b or "")
            if _es_espaciado(c):
                tipo = TipoLinea.TOTAL if _es_total(texto) else TipoLinea.SUBTOTAL
            elif _es_total(texto):
                tipo = TipoLinea.TOTAL
            elif es_suma and d is not None:  # vínculo a otra línea (p. ej. `=S438`)
                tipo = TipoLinea.SUBTOTAL
            else:
                tipo = TipoLinea.INFORMATIVA

        orden = len(res.lineas) + 1
        if tipo is TipoLinea.SECCION:
            seccion_actual = orden
        res.lineas.append(
            LineaLeida(
                orden=orden,
                fila_origen=n,
                tipo=tipo,
                descripcion=texto,
                codigo_corporativo=codigo,
                seccion_orden=None if tipo is TipoLinea.SECCION else seccion_actual,
            )
        )

    if res.contar(TipoLinea.DETALLE) == 0:
        res.errores.append("La hoja no trae líneas de detalle (código corporativo en la columna B)")
    if sin_etiqueta:
        muestra = ", ".join(str(n) for n in sin_etiqueta[:5])
        res.avisos.append(
            f"{len(sin_etiqueta)} filas con cifras y sin nombre se ignoran: {muestra}"
        )
    repetidos = Counter(
        (linea.seccion_orden, linea.descripcion)
        for linea in res.lineas
        if linea.tipo is TipoLinea.DETALLE
    )
    duplicadas = sum(1 for veces in repetidos.values() if veces > 1)
    if duplicadas:
        res.avisos.append(
            f"{duplicadas} descripciones de detalle se repiten dentro de la misma sección"
        )
    return res
