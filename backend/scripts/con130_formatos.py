"""CON130 SINTÉTICO en .xls y .csv para las pruebas de navegador (nunca datos reales de Torres)."""

import csv
import io

import xlwt

Movimiento = tuple[str, str, str, float | None, float | None]
ENCABEZADO = ["# ASIENTO", "Fecha", "Tp.Asiento", "Oper.", "Tp.Doc.", "Número", "Fecha", "Concepto"]


def _filas(movimientos: list[Movimiento]) -> list[list[object]]:
    """Las filas del reporte; el lector ubica sus columnas por el encabezado `# ASIENTO`."""
    filas: list[list[object]] = [
        ["Torres Sintética S.A. de C.V."],
        ["Mayor Analítico (movimientos por cuentas) "],
        ["Periodo Agosto 2026 a Agosto 2026"],
        [*ENCABEZADO, "Débito", "Crédito", "Saldo"],
    ]
    por_cuenta: dict[str, list[tuple[str, str, float | None, float | None]]] = {}
    for cuenta, fecha, concepto, debito, credito in movimientos:
        por_cuenta.setdefault(cuenta, []).append((fecha, concepto, debito, credito))
    for cuenta, items in sorted(por_cuenta.items()):
        filas.append([cuenta, None, None, None, None, None, None, "Saldo anterior", 0, 0])
        for n, (fecha, concepto, debito, credito) in enumerate(items, start=1):
            filas.append(
                [
                    f"8.1.{n}",
                    fecha,
                    "POLIZA",
                    "REGISTRO",
                    "POLIZA",
                    f"P{n}",
                    fecha,
                    concepto,
                    debito,
                    credito,
                ]
            )
        suma_d = sum(i[2] or 0 for i in items)
        suma_c = sum(i[3] or 0 for i in items)
        filas.append([None] * 7 + [f"Total  {cuenta}", suma_d, suma_c])
    return filas


def con130_xls(movimientos: list[Movimiento]) -> bytes:
    libro = xlwt.Workbook()
    hoja = libro.add_sheet("CON130")
    for i, fila in enumerate(_filas(movimientos)):
        for j, valor in enumerate(fila):
            if valor is not None:
                hoja.write(i, j, valor)
    buf = io.BytesIO()
    libro.save(buf)
    return buf.getvalue()


def con130_csv(movimientos: list[Movimiento]) -> bytes:
    buf = io.StringIO(newline="")
    escritor = csv.writer(buf, delimiter=";")  # como lo guarda Excel en español
    for fila in _filas(movimientos):
        escritor.writerow(["" if v is None else v for v in fila])
    return buf.getvalue().encode("cp1252")
