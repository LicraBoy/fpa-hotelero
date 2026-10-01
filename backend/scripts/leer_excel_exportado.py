"""Lee el Excel exportado del Variance y lo imprime como JSON (lo usa la prueba de navegador).

Uso:  python scripts/leer_excel_exportado.py <archivo.xlsx>
Salida: [{"descripcion": "...", "cifras": ["1000.00", null, ...]}] con las 12 cifras de cada fila
de datos, a centavos (o a 6 decimales los porcentajes), y `null` donde la celda está en blanco.
"""

import json
import sys
from decimal import ROUND_HALF_UP, Decimal

from openpyxl import load_workbook


def main(ruta: str) -> None:
    hoja = load_workbook(ruta)["Variance"]
    salida = []
    for fila in hoja.iter_rows(min_row=6, values_only=True):
        if fila[1] is None:
            continue
        cifras = []
        for i in (2, 3, 4, 5, 7, 8, 9, 10, 12, 13, 14, 15):
            valor = fila[i]
            if valor is None:
                cifras.append(None)
                continue
            paso = Decimal("0.000001") if i in (5, 10, 15) else Decimal("0.01")
            cifras.append(str(Decimal(str(valor)).quantize(paso, rounding=ROUND_HALF_UP)))
        salida.append({"descripcion": fila[1], "cifras": cifras})
    sys.stdout.write(json.dumps(salida, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1])
