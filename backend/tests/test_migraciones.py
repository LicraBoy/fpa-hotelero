import os
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from fpa.modelos import Base

RAIZ_BACKEND = Path(__file__).resolve().parents[1]


def _config(url: str) -> Config:
    cfg = Config(str(RAIZ_BACKEND / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def _tablas(url: str) -> set[str]:
    eng = create_engine(url)
    try:
        return set(inspect(eng).get_table_names()) - {"alembic_version"}
    finally:
        eng.dispose()


def _ciclo_completo(url: str) -> None:
    cfg = _config(url)
    command.upgrade(cfg, "head")
    esperadas = set(Base.metadata.tables)
    assert _tablas(url) == esperadas

    # Los modelos y las migraciones no deben desviarse (nadie olvidó generar una migración)
    eng = create_engine(url)
    try:
        with eng.connect() as conexion:
            contexto = MigrationContext.configure(conexion, opts={"compare_type": True})
            assert compare_metadata(contexto, Base.metadata) == []
    finally:
        eng.dispose()

    command.downgrade(cfg, "base")
    assert _tablas(url) == set()


def test_migraciones_suben_y_bajan_en_sqlite(tmp_path: Path) -> None:
    _ciclo_completo(f"sqlite:///{tmp_path / 'migracion.db'}")


@pytest.mark.skipif(
    not os.environ.get("FPA_TEST_POSTGRES_URL"),
    reason="Define FPA_TEST_POSTGRES_URL (base vacía de pruebas) para probar en PostgreSQL",
)
def test_migraciones_suben_y_bajan_en_postgresql() -> None:
    _ciclo_completo(os.environ["FPA_TEST_POSTGRES_URL"])
