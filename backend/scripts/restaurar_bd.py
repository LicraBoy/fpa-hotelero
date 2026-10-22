"""Restaura un respaldo cifrado (ADR 0010, Fase 6.4) — para el ensayo de restauración y para una
recuperación real.

SQLite: escribe el volcado descifrado directamente como el archivo de base de datos destino.
PostgreSQL: usa `pg_restore` (debe estar en el PATH) contra `FPA_DATABASE_URL`.

Uso (desde backend/):
    .venv\\Scripts\\python scripts/restaurar_bd.py backups\\respaldo_20261022_120000.enc \\
        --destino fpa_restaurada.db
    .venv\\Scripts\\python scripts/restaurar_bd.py backups\\respaldo_20261022_120000.enc --postgres
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess  # nosec B404 - pg_restore con argumentos fijos, sin entrada del usuario ni shell
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fpa.config import settings
from scripts.respaldar_bd import RespaldoError, descifrar


def _restaurar_postgres(datos: bytes, database_url: str) -> None:
    if shutil.which("pg_restore") is None:
        raise RespaldoError("pg_restore no está en el PATH; instala el cliente de PostgreSQL")
    partes = urlparse(database_url.replace("postgresql+psycopg://", "postgresql://"))
    entorno = dict(os.environ)
    if partes.password:
        entorno["PGPASSWORD"] = partes.password
    comando = [
        "pg_restore",
        "--clean",
        "--if-exists",
        f"--host={partes.hostname}",
        f"--port={partes.port or 5432}",
        f"--username={partes.username}",
        f"--dbname={partes.path.lstrip('/')}",
    ]
    resultado = subprocess.run(  # noqa: S603 - argumentos fijos, sin shell=True
        comando, input=datos, env=entorno, capture_output=True, timeout=600
    )
    if resultado.returncode != 0:
        raise RespaldoError(f"pg_restore falló: {resultado.stderr.decode(errors='replace')}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("respaldo", type=Path, help="archivo .enc a restaurar")
    ap.add_argument("--destino", type=Path, help="ruta del archivo SQLite de destino")
    ap.add_argument(
        "--postgres", action="store_true", help="restaurar contra FPA_DATABASE_URL (PostgreSQL)"
    )
    args = ap.parse_args()

    if not args.respaldo.exists():
        print(f"ERROR: no existe {args.respaldo}", file=sys.stderr)
        return 1

    try:
        datos = descifrar(args.respaldo)
        if args.postgres:
            _restaurar_postgres(datos, settings.database_url)
            print("Restaurado contra PostgreSQL.")
        else:
            destino = args.destino or Path("fpa_restaurada.db")
            destino.write_bytes(datos)
            print(f"Restaurado en: {destino}")
    except RespaldoError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
