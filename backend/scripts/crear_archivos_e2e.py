"""Crea los Excel SINTÉTICOS que usan las pruebas de navegador (nunca datos reales de Torres).

Uso:  python scripts/crear_archivos_e2e.py <carpeta_destino>
"""

import io
import sys
import zipfile
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from xls_sintetico import a_xls, catalogo_basico

ENCABEZADO_VARIANCE = [
    None, "Mes", "Fecha", "No Cuenta", "Nombre de la Cuenta", "Asiento - Salida",
    "Concepto - Nombre Articulo", "Cantidad", "Costo", "Débito", "Crédito",
]  # fmt: skip


def variance(filas: list[tuple]) -> bytes:  # type: ignore[type-arg]
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Base de Datos"
    ws.append([])
    ws.append(ENCABEZADO_VARIANCE)
    for f in filas:
        ws.append(list(f))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def fila(
    mes: str, dia: datetime, cuenta: str, nombre: str, debito: float | None, credito: float | None
):  # type: ignore[no-untyped-def]
    return (None, mes, dia, cuenta, nombre, "8.3.1", "MOVIMIENTO", None, None, debito, credito)


def reporte_variance() -> bytes:
    """Variance sintético COMPLETO (hojas `Ago` y `Base de Datos`) con cifras fáciles de verificar.

    Agosto: Room Revenue 1,000.00 (Budget 900), Food Revenue 500.50 (600), Salaries 400.00 (380),
    Supplies 150.25 (140). Julio: Room Revenue 700.00 y Salaries 380.00. Los conceptos incluyen
    HTML a propósito: la pantalla debe mostrarlo como texto, nunca interpretarlo.
    """
    wb = Workbook()
    ago = wb.active
    assert ago is not None
    ago.title = "Ago"

    def poner(n: int, b=None, c=None, d=None, e=None, j=None, o=None, s=None):  # type: ignore[no-untyped-def]
        for col, valor in ((2, b), (3, c), (4, d), (5, e), (10, j), (15, o), (19, s)):
            if valor is not None:
                ago.cell(row=n, column=col, value=valor)

    poner(2, "Account #", "Account Description", "AUGUST")
    poner(3, None, None, "Actual")
    poner(4, "R e v e n u e")
    poner(5, "029-0000-1-000", "Room Revenue", 1000.0, 900.0, 1700.0, 10800.0, "=-'4001002.001'!L5")
    poner(6, "029-0000-2-000", "Food Revenue", 500.5, 600.0, 1200.0, 7200.0, "=-'4001005.001'!L5")
    poner(7, None, "T o t a l   R e v e n u e", 1500.5, 1500.0, 2900.0, 18000.0, "=SUM(S5:S6)")
    poner(9, "E x p e n s e s")
    poner(10, "029-0111-60010-000", "Salaries", 400.0, 380.0, 760.0, 4560.0, "='6009001.001'!L9")
    poner(11, "029-0000-3-000", "Supplies", 150.25, 140.0, 280.0, 1680.0, "='6005024'!L3")
    poner(12, None, "T o t a l   E x p e n s e s", 550.25, 520.0, 1040.0, 6240.0, "=SUM(S10:S11)")
    poner(14, None, "N e t   P r o f i t", 950.25, 980.0, 1860.0, 11760.0, "=S7-S12")

    bd = wb.create_sheet("Base de Datos")
    bd.append([])
    bd.append(ENCABEZADO_VARIANCE)
    mov = [
        (
            "Julio",
            datetime(2026, 7, 10),
            "4001002.001",
            "ROOM",
            "7.1.1",
            "Hospedaje julio",
            None,
            700.0,
        ),
        (
            "Julio",
            datetime(2026, 7, 11),
            "6009001.001",
            "SUELDOS",
            "7.1.2",
            "Nómina julio",
            380.0,
            None,
        ),
        (
            "Agosto",
            datetime(2026, 8, 2),
            "4001002.001",
            "ROOM",
            "8.1.1",
            "Hospedaje <b>agosto</b> & más",
            None,
            600.0,
        ),
        (
            "Agosto",
            datetime(2026, 8, 3),
            "4001002.001",
            "ROOM",
            "8.1.2",
            "Hospedaje agosto 2",
            None,
            400.0,
        ),
        ("Agosto", datetime(2026, 8, 4), "4001005.001", "FOOD", "8.1.3", "Alimentos", None, 500.5),
        (
            "Agosto",
            datetime(2026, 8, 5),
            "6009001.001",
            "SUELDOS",
            "8.1.4",
            "Quincena 1",
            150.0,
            None,
        ),
        (
            "Agosto",
            datetime(2026, 8, 6),
            "6009001.001",
            "SUELDOS",
            "8.1.5",
            "Quincena 2",
            150.0,
            None,
        ),
        ("Agosto", datetime(2026, 8, 7), "6009001.001", "SUELDOS", "8.1.6", "Bono", 100.0, None),
        (
            "Agosto",
            datetime(2026, 8, 8),
            "6005024",
            "INSUMOS",
            "8.1.7",
            "Compra de insumos",
            150.25,
            None,
        ),
    ]
    for mes, dia, cuenta, nombre, asiento, concepto, debito, credito in mov:
        bd.append([None, mes, dia, cuenta, nombre, asiento, concepto, None, None, debito, credito])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def golden_real(destino: Path) -> None:
    """Con el Excel real de agosto, guarda cifras de referencia para el e2e (NO se versiona).

    Elige líneas con descripción única en el reporte y que no estén entre las excepciones
    documentadas de la prueba dorada, y guarda sus 12 cifras tal como las pegó Contraloría.
    """
    import os
    import re

    from fpa.ingesta.variance_estructura import TipoLinea, leer_variance_estructura
    from fpa.ingesta.variance_valores import leer_variance_valores

    carpeta = Path(
        os.environ.get(
            "FPA_DATOS_REALES",
            Path.home() / "Desktop" / "PLATAFORMA FP&A E INTELIGENCIA HOTELERA",
        )
    )
    excel = carpeta / "02. VT August 2026 Variance (Envio) (1).xlsx"
    salida = destino / "golden_real.json"
    if not excel.exists():
        salida.unlink(missing_ok=True)
        return
    from test_variance_dorada import EXCEPCIONES

    estructura = leer_variance_estructura(excel)
    valores = leer_variance_valores(excel)
    descripciones = [x.descripcion for x in estructura.lineas if x.tipo is not TipoLinea.SECCION]
    elegidas = []
    for linea in estructura.lineas:
        v = valores.get(linea.fila_origen)
        if (
            v is None
            or linea.tipo is TipoLinea.SECCION
            or linea.fila_origen in EXCEPCIONES
            or descripciones.count(linea.descripcion) != 1
            or not re.search(r"[A-Za-z]{4}", linea.descripcion)
            or v.mes_budget is None
            or v.mes_actual is None
        ):
            continue
        elegidas.append((linea, v))
    paso = max(1, len(elegidas) // 14)
    muestra = elegidas[::paso][:14]
    campos = [
        "mes_actual", "mes_budget", "mes_var", "mes_pct",
        "ytd_actual", "ytd_budget", "ytd_var", "ytd_pct",
        "anual_actual", "anual_budget", "anual_var", "anual_pct",
    ]  # fmt: skip
    import json

    salida.write_text(
        json.dumps(
            [
                {
                    "fila": linea.fila_origen,
                    "descripcion": linea.descripcion,
                    "tipo": linea.tipo.value,
                    "cifras": [
                        None if getattr(v, c) is None else str(getattr(v, c)) for c in campos
                    ],
                }
                for linea, v in muestra
            ],
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )


def main(destino: Path) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    agosto = [
        fila("Agosto", datetime(2026, 8, 5), "4001002.001", "INGRESOS DE BAR", None, 100.50),
        fila("Agosto", datetime(2026, 8, 6), "6009001.001", "SUELDOS", 40.25, None),
    ]
    corregido = [
        fila("Agosto", datetime(2026, 8, 5), "4001002.001", "INGRESOS DE BAR", None, 120.00),
        fila("Agosto", datetime(2026, 8, 6), "6009001.001", "SUELDOS", 40.25, None),
    ]
    (destino / "variance_reporte.xlsx").write_bytes(reporte_variance())
    (destino / "variance_agosto.xlsx").write_bytes(variance(agosto))
    (destino / "variance_agosto_corregido.xlsx").write_bytes(variance(corregido))
    # Catálogo contable (CON020) sintético en .xls, y un falso .xls de texto
    (destino / "catalogo.xls").write_bytes(a_xls(catalogo_basico()))
    (destino / "falso.xls").write_bytes(b"esto no es un libro de Excel")
    # Falso .xlsx: texto plano con extensión de Excel
    (destino / "falso.xlsx").write_bytes(b"esto no es un libro de Excel")
    # Zip que no es un libro de Excel
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("hola.txt", "hola")
    (destino / "zip_no_excel.xlsx").write_bytes(buf.getvalue())
    golden_real(destino)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
