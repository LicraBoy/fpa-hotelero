"""Pruebas de respaldo/restauración cifrados (ADR 0010, Fase 6.4): el ensayo de restauración
"con diferencia cero" que pide el plan, hecho automático sobre una base SQLite de prueba."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from scripts.respaldar_bd import RespaldoError, descifrar, respaldar
from scripts.restaurar_bd import main as restaurar_main


def _crear_sqlite_de_prueba(ruta: Path) -> None:
    con = sqlite3.connect(ruta)
    con.execute("create table cuenta (codigo text primary key, descripcion text)")
    con.executemany("insert into cuenta values (?, ?)", [("4001", "Ingresos"), ("6001", "Nómina")])
    con.commit()
    con.close()


def _huella(ruta: Path) -> str:
    con = sqlite3.connect(ruta)
    filas = list(con.execute("select * from cuenta order by codigo"))
    con.close()
    return repr(filas)


@pytest.fixture
def clave(monkeypatch: pytest.MonkeyPatch) -> str:
    clave = Fernet.generate_key().decode()
    monkeypatch.setenv("FPA_RESPALDO_CLAVE", clave)
    return clave


def test_respaldo_sin_clave_falla(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FPA_RESPALDO_CLAVE", raising=False)
    with pytest.raises(RespaldoError, match="FPA_RESPALDO_CLAVE"):
        respaldar(f"sqlite:///{tmp_path / 'x.db'}", carpeta=tmp_path / "backups")


def test_restaurar_reproduce_los_mismos_datos_diferencia_cero(tmp_path: Path, clave: str) -> None:
    origen = tmp_path / "original.db"
    _crear_sqlite_de_prueba(origen)
    huella_original = _huella(origen)

    carpeta_respaldos = tmp_path / "backups"
    ruta_respaldo = respaldar(f"sqlite:///{origen}", carpeta=carpeta_respaldos)
    assert ruta_respaldo.exists()

    datos = descifrar(ruta_respaldo)
    restaurado = tmp_path / "restaurado.db"
    restaurado.write_bytes(datos)

    assert _huella(restaurado) == huella_original


def test_restaurar_con_clave_distinta_falla(tmp_path: Path, clave: str) -> None:
    origen = tmp_path / "original.db"
    _crear_sqlite_de_prueba(origen)
    ruta_respaldo = respaldar(f"sqlite:///{origen}", carpeta=tmp_path / "backups")

    import os

    os.environ["FPA_RESPALDO_CLAVE"] = Fernet.generate_key().decode()  # otra clave
    with pytest.raises(RespaldoError, match="no corresponde"):
        descifrar(ruta_respaldo)


def test_rotacion_conserva_solo_los_ultimos_14(tmp_path: Path, clave: str) -> None:
    origen = tmp_path / "original.db"
    _crear_sqlite_de_prueba(origen)
    carpeta = tmp_path / "backups"
    for _ in range(16):
        respaldar(f"sqlite:///{origen}", carpeta=carpeta)
    assert len(list(carpeta.glob("respaldo_*.enc"))) <= 14


def test_restaurar_bd_cli_escribe_el_archivo_destino(
    tmp_path: Path, clave: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    origen = tmp_path / "original.db"
    _crear_sqlite_de_prueba(origen)
    ruta_respaldo = respaldar(f"sqlite:///{origen}", carpeta=tmp_path / "backups")
    destino = tmp_path / "restaurado_cli.db"

    import sys

    monkeypatch.setattr(
        sys, "argv", ["restaurar_bd.py", str(ruta_respaldo), "--destino", str(destino)]
    )
    assert restaurar_main() == 0
    assert _huella(destino) == _huella(origen)
