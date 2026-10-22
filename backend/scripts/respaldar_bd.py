"""Respaldo cifrado de la base de datos (ADR 0010, Fase 6.4).

SQLite: usa la API de respaldo de `sqlite3` (consistente aunque la base esté en uso) y cifra el
resultado con la clave de `FPA_RESPALDO_CLAVE` (Fernet — AES128 + HMAC, de `cryptography`).
PostgreSQL: usa `pg_dump` (debe estar en el PATH) sobre `FPA_DATABASE_URL` y cifra igual.

Sin `FPA_RESPALDO_CLAVE` el script falla: nunca se guarda un respaldo sin cifrar.

Uso (desde backend/):
    .venv\\Scripts\\python scripts/respaldar_bd.py

Guarda en `backend/backups/respaldo_<AAAAMMDD_HHMMSS>.enc` y conserva los últimos 14 (ADR 0010).
"""

from __future__ import annotations

import os
import shutil
import subprocess  # nosec B404 - pg_dump con argumentos fijos, sin entrada del usuario ni shell
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cryptography.fernet import Fernet, InvalidToken

from fpa.config import settings
from fpa.observabilidad.alertas import alertar
from fpa.observabilidad.metricas import RESPALDO_FALLOS_TOTAL

RAIZ = Path(__file__).resolve().parents[1]
CARPETA_RESPALDOS = RAIZ / "backups"
MAX_RESPALDOS = 14


class RespaldoError(Exception):
    pass


def _clave() -> Fernet:
    clave = os.environ.get("FPA_RESPALDO_CLAVE")
    if not clave:
        raise RespaldoError(
            "Falta FPA_RESPALDO_CLAVE: no se guarda un respaldo sin cifrar. "
            "Genera una con: python -c \"from cryptography.fernet import Fernet; "
            'print(Fernet.generate_key().decode())"'
        )
    try:
        return Fernet(clave.encode())
    except (ValueError, TypeError) as exc:
        raise RespaldoError("FPA_RESPALDO_CLAVE no es una clave Fernet válida") from exc


def _ruta_sqlite(database_url: str) -> Path:
    # sqlite:///./fpa_dev.db o sqlite:////ruta/absoluta.db
    ruta = database_url.removeprefix("sqlite:///")
    return (RAIZ / ruta) if not Path(ruta).is_absolute() else Path(ruta)


def _volcar_sqlite(database_url: str, destino: Path) -> None:
    import sqlite3

    origen = _ruta_sqlite(database_url)
    if not origen.exists():
        raise RespaldoError(f"No existe la base SQLite: {origen}")
    con_origen = sqlite3.connect(origen)
    con_destino = sqlite3.connect(destino)
    try:
        con_origen.backup(con_destino)
    finally:
        con_destino.close()
        con_origen.close()


def _volcar_postgres(database_url: str, destino: Path) -> None:
    partes = urlparse(database_url.replace("postgresql+psycopg://", "postgresql://"))
    if shutil.which("pg_dump") is None:
        raise RespaldoError("pg_dump no está en el PATH; instala el cliente de PostgreSQL")
    entorno = dict(os.environ)
    if partes.password:
        entorno["PGPASSWORD"] = partes.password
    comando = [
        "pg_dump",
        "--format=custom",
        f"--host={partes.hostname}",
        f"--port={partes.port or 5432}",
        f"--username={partes.username}",
        f"--dbname={partes.path.lstrip('/')}",
        f"--file={destino}",
    ]
    resultado = subprocess.run(  # noqa: S603 - argumentos fijos, sin shell=True
        comando, env=entorno, capture_output=True, text=True, timeout=600
    )
    if resultado.returncode != 0:
        raise RespaldoError(f"pg_dump falló: {resultado.stderr.strip()}")


def _rotar(carpeta: Path, max_respaldos: int) -> None:
    respaldos = sorted(carpeta.glob("respaldo_*.enc"), key=lambda p: p.name)
    for viejo in respaldos[:-max_respaldos] if len(respaldos) > max_respaldos else []:
        viejo.unlink(missing_ok=True)


def respaldar(database_url: str | None = None, carpeta: Path = CARPETA_RESPALDOS) -> Path:
    """Crea un respaldo cifrado y devuelve su ruta. Lanza `RespaldoError` si algo falla."""
    fernet = _clave()
    database_url = database_url or settings.database_url
    carpeta.mkdir(parents=True, exist_ok=True)
    marca = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    destino_cifrado = carpeta / f"respaldo_{marca}.enc"

    with tempfile.TemporaryDirectory() as tmp:
        temporal = Path(tmp) / "volcado"
        if database_url.startswith("sqlite"):
            _volcar_sqlite(database_url, temporal)
        elif database_url.startswith("postgresql"):
            _volcar_postgres(database_url, temporal)
        else:
            raise RespaldoError(f"Motor no soportado para respaldo: {database_url}")

        datos = temporal.read_bytes()
        if not datos:
            raise RespaldoError("El volcado quedó vacío; no se guarda un respaldo vacío")
        destino_cifrado.write_bytes(fernet.encrypt(datos))

    _rotar(carpeta, MAX_RESPALDOS)
    return destino_cifrado


def descifrar(ruta_cifrada: Path) -> bytes:
    """Usada por `restaurar_bd.py`: descifra un respaldo con la clave actual."""
    fernet = _clave()
    try:
        return fernet.decrypt(ruta_cifrada.read_bytes())
    except InvalidToken as exc:
        raise RespaldoError(
            "No se pudo descifrar: la clave no corresponde a este respaldo"
        ) from exc


def main() -> int:
    try:
        ruta = respaldar()
    except RespaldoError as exc:
        RESPALDO_FALLOS_TOTAL.inc()
        alertar(f"Falló el respaldo de la base de datos: {exc}")
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Respaldo guardado: {ruta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
