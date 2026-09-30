"""Crea catálogos CON020 (.xls) SINTÉTICOS con el mismo formato del reporte real de Novohit."""

import io

import xlwt

ENCABEZADO = [
    "TIPO", "Aux", "Activ", "GRUPO E.F", "DEPTO EdoFro", "DPTO. TI", "Cta.Terceros", "Cuentas SAT",
]  # fmt: skip
VACIA = ["", "", "", "", "", "", "", ""]


def titulo(texto: str, con_encabezado: bool = False) -> list[str]:
    """Fila de título de la jerarquía; en el reporte real comparte fila con los encabezados."""
    return [texto, "", "", *(ENCABEZADO if con_encabezado else VACIA)]


def cuenta(
    base: str,
    sub: str = "",
    descripcion: str = "",
    tipo: str = "Deudor",
    aux: str = "",
    activa: str = "S",
    grupo: str = "",
    depto: str = "",
    ti: str = "",
    terceros: str = "",
    sat: str = "",
) -> list[str]:
    return [base, sub, descripcion, tipo, aux, activa, grupo, depto, ti, terceros, sat]


def encabezado_de_pagina() -> list[list[str]]:
    vacia = [""] * 11
    return [
        ["Torres Mazatlan S.A. de C.V.", *[""] * 10],
        ["Catálogo Contable", *[""] * 9, "30/09/2026"],
        [*[""] * 10, "15:04"],
        [*[""] * 10, "1"],
        vacia[:1],
    ][:4]


def catalogo_basico() -> list[list[str]]:
    """Ingresos de bar y sueldos de Gerencia y Recepción, con páginas repetidas como el real."""
    filas = encabezado_de_pagina()
    filas += [
        titulo("4  INGRESOS"),
        titulo("40  INGRESOS"),
        titulo("4001  INGRESOS CENTROS DE CONSUMO", con_encabezado=True),
        cuenta("4001002", "", "INGRESOS DE BAR", "Acreedor", "S", "S", sat="401.01 Ventas"),
        cuenta(
            "4001002",
            "001",
            "INGRESOS DE BAR BEBIDAS",
            "Acreedor",
            "",
            "S",
            "INCOME",
            "BAR",
            "CENTRO INGRESO",
            "",
            "401.01 Ventas",
        ),
    ]
    filas += encabezado_de_pagina()  # salto de página: se repite todo
    filas += [
        titulo("4  INGRESOS"),
        titulo("40  INGRESOS"),
        titulo("6  GASTOS"),
        titulo("60  GASTOS DE OPERACION"),
        titulo("6009  GERENCIA Y RECEPCION", con_encabezado=True),
        cuenta("6009001", "", "SUELDOS", "Deudor", "S", "S"),
        cuenta(
            "6009001",
            "001",
            "SUELDOS",
            "Deudor",
            "",
            "S",
            "PAYROLL EXPENS",
            "MGT & CHECK IN",
            "OPERACIONES OPERAT",
            "",
            "601.01 Sueldos",
        ),
        cuenta("6009002", "", "SERVICIO A DUE¥OS", "Deudor", "", "N"),  # inactiva; Ñ mal exportada
    ]
    return filas


def a_xls(filas: list[list[str]]) -> bytes:
    libro = xlwt.Workbook(encoding="utf-8")
    hoja = libro.add_sheet("CON020_XLS")
    for r, fila in enumerate(filas):
        for c, valor in enumerate(fila):
            hoja.write(r, c, valor)
    buf = io.BytesIO()
    libro.save(buf)
    return buf.getvalue()
