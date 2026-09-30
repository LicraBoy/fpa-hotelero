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


if __name__ == "__main__":
    main(Path(sys.argv[1]))
