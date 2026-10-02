"""Libro SINTÉTICO con el formato de Mazatlán (hojas `Ago` y `Jul-Ago`) para las pruebas.

Mismas reglas que el real, con cifras pequeñas y fáciles de verificar. Nunca contiene datos reales.

  Ingresos:  Rental Income  (4002011)               julio 100.00 · agosto 120.00 · Budget 90 / 110
             Laundry        (4002001.010)           agosto 0 (sin fórmula; el código viene pegado)
             Total Income = suma
  Gastos:    Salaries       (6009001.001 + .002)    julio 40.00 · agosto 50.00 · Budget 45 / 48
             Total Expenses = suma
  Tipo de cambio (informativa): Actual 17.1337 / 17.2175 · Budget 18
"""

from pathlib import Path
from typing import Any

from openpyxl import Workbook

ANIO = 2026


def _hoja_ago(wb: Workbook) -> None:
    ws = wb.active
    assert ws is not None
    ws.title = "Ago"
    ws["B1"] = "FY 25/26 Budget Performance"
    ws["B4"] = "Month of August-2026"
    ws["B6"], ws["C6"], ws["D6"], ws["I6"] = "Account #", "Account Description", "AGOSTO", "CUENTA"
    ws["D7"], ws["F7"], ws["G7"], ws["H7"] = "Actual", "Budget", "Var", "%"
    ws["C9"], ws["D9"], ws["F9"], ws["G9"], ws["H9"] = (
        "Exchange Rate:",
        17.1337,
        18,
        0.8663,
        0.048128,
    )
    ws["B10"], ws["D10"] = "I n c o m e", " "  # una sección rotulada con un espacio en blanco
    filas: list[tuple[int, Any, Any, Any, Any, Any, Any, Any]] = [
        (11, "028-0000-43080-000", "Rental Income", 120, 110, 10, 0.0909, "4002011"),
        (12, "028-0101-45010-000", "Laundry", 0, 0, 0, 0, "4002001.01"),
        (14, "028-0111-60010-000", "Salaries", 50, 48, -2, -0.0417, "6009001.001"),
    ]
    for fila, codigo, desc, actual, budget, var, pct, cuenta in filas:
        ws.cell(row=fila, column=2, value=codigo)
        ws.cell(row=fila, column=3, value=desc)
        ws.cell(row=fila, column=4, value=actual)
        ws.cell(row=fila, column=6, value=budget)
        ws.cell(row=fila, column=7, value=var)
        ws.cell(row=fila, column=8, value=pct)
        ws.cell(row=fila, column=9, value=cuenta)
    ws["J14"] = "6009001.002"  # la segunda cuenta de Salaries
    ws["K12"] = "4002011"  # Laundry lista una cuenta que la fórmula de Rental Income ya suma
    ws["C13"], ws["D13"], ws["F13"] = "T o t a l   I n c o m e", 120, 110
    ws["B13"] = None
    ws["B15"], ws["D15"] = "E x p e n s e s", " "
    ws["C16"], ws["D16"], ws["F16"] = "T o t a l   E x p e n s e s", 50, 48
    ws["C17"], ws["D17"], ws["F17"] = "N e t   P r o f i t", 70, 62
    ws["Q11"] = "=+D11-E11"  # la columna de control es la única con fórmulas en Ago


def _hoja_jul_ago(wb: Workbook) -> None:
    ws = wb.create_sheet("Jul-Ago")
    ws["B4"] = "Month of July-2026"
    ws["B6"], ws["C6"], ws["D6"], ws["I6"] = "Account #", "Account Description", "JULIO", "AGOSTO"
    ws["D7"], ws["F7"], ws["G7"], ws["H7"] = "Actual", "Budget", "Var", "%"
    ws["I7"], ws["K7"], ws["L7"], ws["M7"] = "Actual", "Budget", "Var", "%"
    ws["C9"], ws["D9"], ws["F9"], ws["G9"], ws["H9"] = (
        "Exchange Rate:",
        17.2175,
        18,
        0.7825,
        0.04347,
    )
    ws["I9"], ws["K9"], ws["L9"], ws["M9"] = 17.1337, 18, 0.8663, 0.048128
    ws["B10"], ws["D10"] = "I n c o m e", " "
    # cada fila: código, descripción, julio (actual, budget), agosto (actual, budget) y fórmulas
    ws["B11"], ws["C11"] = "028-0000-43080-000", "Rental Income"
    ws["D11"], ws["F11"], ws["I11"], ws["K11"] = 100, 90, 120, 110
    ws["E11"] = "=-SUMIFS('4002011'!L:L,'4002011'!B:B,\"Julio\",'4002011'!G:G,\"Total\")"
    ws["J11"] = "=-SUMIFS('4002011'!L:L,'4002011'!B:B,\"Agosto\",'4002011'!G:G,\"Total\")"
    ws["B12"], ws["C12"] = "028-0101-45010-000", "Laundry"
    ws["D12"], ws["F12"], ws["I12"], ws["K12"] = 0, 0, 0, 0  # sin fórmula: no tuvo movimiento
    ws["C13"], ws["D13"], ws["F13"], ws["I13"], ws["K13"] = (
        "T o t a l   I n c o m e",
        100,
        90,
        120,
        110,
    )
    ws["E13"], ws["J13"] = "=SUM(E11:E12)", "=SUM(J11:J12)"
    ws["B14"], ws["C14"] = "028-0111-60010-000", "Salaries"
    ws["D14"], ws["F14"], ws["I14"], ws["K14"] = 40, 45, 50, 48
    ws["E14"] = (
        "=SUMIFS('6009001.001'!L:L,'6009001.001'!B:B,\"Julio\",'6009001.001'!G:G,\"Total\")"
        " + SUMIFS('6009001.002'!L:L,'6009001.002'!B:B,\"Julio\",'6009001.002'!G:G,\"Total\")"
    )
    ws["J14"] = (
        "=SUMIFS('6009001.001'!L:L,'6009001.001'!B:B,\"Agosto\",'6009001.001'!G:G,\"Total\")"
        " + SUMIFS('6009001.002'!L:L,'6009001.002'!B:B,\"Agosto\",'6009001.002'!G:G,\"Total\")"
    )
    ws["B15"], ws["D15"] = "E x p e n s e s", " "
    ws["C16"], ws["D16"], ws["F16"], ws["I16"], ws["K16"] = (
        "T o t a l   E x p e n s e s",
        40,
        45,
        50,
        48,
    )
    ws["E16"], ws["J16"] = "=SUM(E14:E14)", "=SUM(J14:J14)"
    ws["C17"], ws["D17"], ws["F17"], ws["I17"], ws["K17"] = "N e t   P r o f i t", 60, 45, 70, 62
    ws["E17"], ws["J17"] = "=E13-E16", "=J13-J16"


def crear_libro_mzt(ruta: Path) -> Path:
    wb = Workbook()
    _hoja_ago(wb)
    _hoja_jul_ago(wb)
    wb.save(ruta)
    return ruta
