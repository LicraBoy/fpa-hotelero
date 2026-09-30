"""Lector del reporte CON020 "Catálogo Contable" de Novohit (archivo .xls).

Estructura real (Torres, 30/09/2026): una hoja con páginas que **repiten** el encabezado de la
empresa, el título del reporte, la fecha y los títulos de la jerarquía. Filas útiles:

- Título de la jerarquía, en la primera columna: `1  ACTIVO`, `10  ACTIVO CIRCULANTE`,
  `1000  B A N C O S` (códigos de 1, 2 o 4 dígitos; algún nombre viene con letras espaciadas).
- Cuenta: la primera columna trae 7 dígitos (`1000001`), la segunda la subcuenta de 3 (`001`, vacía
  en la cuenta base), luego descripción, TIPO (Deudor/Acreedor), Aux, Activ, GRUPO E.F,
  DEPTO EdoFro, DPTO. TI, Cta.Terceros y Cuentas SAT.

El código de una subcuenta se escribe `1000001.001`, igual que en el CON130.
Las columnas se ubican por el nombre del encabezado, no por posición.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import xlrd

from fpa.ingesta.catalogo_contrato import CuentaCatalogo, ResultadoCatalogo, TituloCatalogo
from fpa.ingesta.utilidades import corregir_codificacion

_RE_CUENTA_BASE = re.compile(r"^\d{7}$")
_RE_TITULO = re.compile(r"^(\d{1,4})\s+(\S.*)$")
_RE_FECHA = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_RE_LETRAS_ESPACIADAS = re.compile(r"^(?:\S ){2,}\S$")
_TIPOS = {"Deudor", "Acreedor"}

# Nombre normalizado del encabezado -> campo
_ENCABEZADOS = {
    "tipo": "tipo",
    "aux": "aux",
    "activ": "activ",
    "grupoef": "grupo_ef",
    "deptoedofro": "depto_ef",
    "dptoti": "depto_ti",
    "ctaterceros": "cuenta_terceros",
    "cuentassat": "cuenta_sat",
}


def _normalizar(texto: str) -> str:
    sin_acentos = unicodedata.normalize("NFKD", texto.lower())
    return re.sub(r"[^a-z0-9]", "", sin_acentos)


def limpiar_nombre(texto: str) -> str:
    """`B A N C O S` -> `BANCOS`; los nombres normales no cambian."""
    palabras = re.split(r" {2,}", texto.strip())
    limpias = [p.replace(" ", "") if _RE_LETRAS_ESPACIADAS.match(p) else p for p in palabras]
    return " ".join(limpias)


def _texto(valor: object) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return corregir_codificacion(str(valor)).strip()


def _opcional(valor: object) -> str | None:
    texto = _texto(valor)
    return texto or None


def leer_con020(ruta: str | Path) -> ResultadoCatalogo:
    contenido = Path(ruta).read_bytes()
    try:
        libro = xlrd.open_workbook(file_contents=contenido)
    except Exception as e:  # xlrd lanza errores de varios tipos ante archivos dañados
        raise ValueError(
            f"No se pudo leer el archivo como un libro de Excel .xls ({type(e).__name__})"
        ) from None
    hoja = libro.sheet_by_index(0)
    filas = [[hoja.cell_value(r, c) for c in range(hoja.ncols)] for r in range(hoja.nrows)]
    return leer_con020_filas(filas)


def _ubicar_columnas(filas: Sequence[Sequence[object]]) -> dict[str, int]:
    for fila in filas[:40]:
        columnas: dict[str, int] = {}
        for j, celda in enumerate(fila):
            campo = _ENCABEZADOS.get(_normalizar(_texto(celda)))
            if campo and campo not in columnas:
                columnas[campo] = j
        if {"tipo", "activ"} <= columnas.keys():
            return columnas
    raise ValueError(
        "No se encontró el encabezado de columnas (TIPO, Aux, Activ…): "
        "no parece un CON020 de Novohit"
    )


def leer_con020_filas(filas: Sequence[Sequence[object]]) -> ResultadoCatalogo:
    res = ResultadoCatalogo()
    columnas = _ubicar_columnas(filas)

    def celda(fila: Sequence[object], campo: str) -> object:
        j = columnas.get(campo)
        return fila[j] if j is not None and j < len(fila) else None

    for fila in filas[:6]:
        for valor in fila:
            texto = _texto(valor)
            if res.empresa is None and texto and not texto.lower().startswith("cat"):
                res.empresa = texto
            if res.fecha_emision is None and _RE_FECHA.match(texto):
                res.fecha_emision = texto

    vistas: dict[str, CuentaCatalogo] = {}
    titulos: dict[str, str] = {}

    for n, fila in enumerate(filas, start=1):
        primera = _texto(fila[0] if fila else None)
        if not primera:
            continue

        if _RE_CUENTA_BASE.match(primera):
            sub = _texto(fila[1] if len(fila) > 1 else None)
            if sub and sub.isdigit():
                sub = sub.zfill(3)
            codigo = f"{primera}.{sub}" if sub else primera
            descripcion = _texto(fila[2] if len(fila) > 2 else None)
            tipo = _texto(celda(fila, "tipo"))
            if tipo not in _TIPOS:
                res.errores.append(f"Fila {n}: la cuenta {codigo} trae un TIPO inválido ({tipo!r})")
                continue
            cuenta = CuentaCatalogo(
                codigo=codigo,
                descripcion=descripcion,
                tipo=tipo,
                auxiliar=_texto(celda(fila, "aux")).upper() == "S",
                activa=_texto(celda(fila, "activ")).upper() == "S",
                grupo_ef=_opcional(celda(fila, "grupo_ef")),
                depto_ef=_opcional(celda(fila, "depto_ef")),
                depto_ti=_opcional(celda(fila, "depto_ti")),
                cuenta_terceros=_opcional(celda(fila, "cuenta_terceros")),
                cuenta_sat=_opcional(celda(fila, "cuenta_sat")),
                fila=n,
            )
            previa = vistas.get(codigo)
            if previa is not None:
                if replace(previa, fila=0) != replace(cuenta, fila=0):
                    res.errores.append(
                        f"Fila {n}: la cuenta {codigo} aparece repetida con datos distintos"
                    )
                continue
            vistas[codigo] = cuenta
            res.cuentas.append(cuenta)
            if not cuenta.activa:
                res.avisos.append(f"La cuenta {codigo} ({descripcion}) está inactiva")
            continue

        titulo = _RE_TITULO.match(primera)
        if titulo:
            codigo_t, nombre = titulo.group(1), limpiar_nombre(titulo.group(2))
            previo = titulos.get(codigo_t)
            if previo is None:
                titulos[codigo_t] = nombre
                res.titulos.append(TituloCatalogo(codigo=codigo_t, descripcion=nombre, fila=n))
            elif previo != nombre:
                res.errores.append(
                    f"Fila {n}: el título {codigo_t} tiene dos nombres ({previo!r} y {nombre!r})"
                )
            continue

        res.filas_ignoradas += 1  # encabezados y pies de página repetidos

    if not res.cuentas and not res.errores:
        res.errores.append("El archivo no trae cuentas")
    return res
