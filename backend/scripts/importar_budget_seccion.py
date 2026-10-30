"""Importa una sección del Excel del Budget a la base de desarrollo.

Es lo mismo que hace «Importar del Excel» en la pantalla de Captura, pero sin subir el archivo.

Uso (desde backend/):
    .venv\\Scripts\\python scripts/importar_budget_seccion.py RUTA.xlsx CLAVE "Nombre"
        [--ciclo 1] [--aplicar]

- `CLAVE`: nombre normalizado de la sección (minúsculas sin signos), con ordinal si el nombre se
  repite en el reporte: `othertaxesfeesandinsurance`, `itsystems`, `store`, `store#2`.
- `Nombre`: el título de la sección en el Excel (p. ej. "Other Taxes, Fees & Insurance").
- Sin `--aplicar` es un **ensayo**: importa, imprime el resultado y deshace todo.
- Con `--aplicar` primero respalda la base (`<base>.respaldo_antes_<fecha>.db`) y luego
  confirma. Las cuentas que el Contralor ya pasó a partidas o consumo no se pisan.

Solo corre con `FPA_ENTORNO=desarrollo`.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.engine import make_url

from fpa.config import settings
from fpa.db import SessionLocal
from fpa.ingesta.budget_seccion import leer_seccion
from fpa.modelos.identidad import Usuario
from fpa.semilla import sembrar_torres
from fpa.servicios.presupuesto_detalle import importar_seccion

CONTRALOR = "contralor@torres.local"


def _respaldar() -> Path | None:
    """Copia consistente de la base SQLite antes de escribir; `None` si no es SQLite."""
    url = make_url(settings.database_url)
    if not url.drivername.startswith("sqlite") or not url.database:
        print("La base no es SQLite: haz tu respaldo con scripts/respaldar_bd.py antes de aplicar.")
        return None
    origen = Path(url.database)
    destino = origen.with_name(f"{origen.stem}.respaldo_antes_{datetime.now():%Y%m%d_%H%M%S}.db")
    with sqlite3.connect(origen) as a, sqlite3.connect(destino) as b:
        a.backup(b)
    return destino


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("excel", type=Path)
    p.add_argument("clave")
    p.add_argument("nombre")
    p.add_argument("--ciclo", type=int, default=1)
    p.add_argument("--aplicar", action="store_true", help="confirma los cambios (si no, ensayo)")
    a = p.parse_args()

    if settings.entorno != "desarrollo":
        raise SystemExit("Este script solo corre con FPA_ENTORNO=desarrollo.")
    if not a.excel.is_file():
        raise SystemExit(f"No existe el archivo: {a.excel}")

    leido = leer_seccion(a.excel, a.clave, a.nombre)
    if a.aplicar:
        copia = _respaldar()
        if copia is not None:
            print(f"Respaldo: {copia}")

    with SessionLocal() as db:
        hotel = sembrar_torres(db)
        contralor = db.scalar(select(Usuario).where(Usuario.email == CONTRALOR))
        if contralor is None:
            raise SystemExit("Falta el usuario de desarrollo: corre `python -m fpa.semilla`")
        res = importar_seccion(
            db,
            organizacion_id=hotel.organizacion_id,
            hotel_id=hotel.id,
            usuario_id=contralor.id,
            ciclo_id=a.ciclo,
            leido=leido,
            visibles=None,
            seccion=a.clave,
        )
        print(f"Cuentas importadas: {res.importadas}")
        for aviso in res.avisos:
            print(f"  aviso: {aviso}")
        if a.aplicar:
            db.commit()
            print("Aplicado.")
        else:
            db.rollback()
            print("Ensayo: no se guardó nada (usa --aplicar para confirmar).")


if __name__ == "__main__":
    main()
