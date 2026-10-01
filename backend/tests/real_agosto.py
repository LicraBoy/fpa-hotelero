"""Agosto 2026 real, cargado una sola vez por módulo de pruebas (es lento).

Carga en una base en memoria: movimientos de julio y agosto (hoja "Base de Datos"), estructura,
reglas de suma, mapeo (borrador, sin aprobar) y Budget del Excel de Contraloría. Si el Excel no
está, las pruebas que usan `agosto_real` se saltan.
"""

import os
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from fpa.ingesta.variance_base_datos import leer_variance_base_datos
from fpa.ingesta.variance_estructura import (
    ResultadoEstructura,
    leer_filas_hoja,
    leer_variance_estructura_filas,
)
from fpa.ingesta.variance_mapeo import leer_variance_mapeo_filas
from fpa.ingesta.variance_reglas import leer_variance_reglas_filas
from fpa.ingesta.variance_valores import ValoresFila, leer_variance_valores
from fpa.modelos import Base, Hotel, LineaReporte, Organizacion
from fpa.repositorios.reporte import RepositorioReporte
from fpa.servicios.budget import importar_budget
from fpa.servicios.cargar_archivo import Resolucion, cargar_archivo
from fpa.servicios.cargas import DatosArchivo
from fpa.servicios.estructura_reporte import importar_estructura_reporte
from fpa.servicios.mapeo import importar_mapeo
from fpa.servicios.reglas_suma import importar_reglas_suma, reglas_como_mapa

CARPETA = Path(
    os.environ.get(
        "FPA_DATOS_REALES", Path.home() / "Desktop" / "PLATAFORMA FP&A E INTELIGENCIA HOTELERA"
    )
)
VARIANCE = CARPETA / "02. VT August 2026 Variance (Envio) (1).xlsx"
CON130 = CARPETA / "BASE DATOS.xlsx"


@dataclass
class AgostoReal:
    db: Session
    organizacion_id: int
    hotel_id: int
    estructura: ResultadoEstructura
    lineas: list[LineaReporte]
    version_estructura_id: int
    version_mapeo_id: int
    version_plan_id: int
    reglas: dict[int, list[tuple[int, int]]]
    valores: dict[int, ValoresFila]  # por fila de Excel

    @property
    def por_fila(self) -> dict[int, LineaReporte]:
        return {x.fila_origen: x for x in self.lineas}


@pytest.fixture(scope="module")
def agosto_real() -> Iterator[AgostoReal]:
    if not VARIANCE.exists():
        pytest.skip("No está el Excel real del Variance")
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    org = Organizacion(nombre="Real")
    db.add(org)
    db.flush()
    hotel = Hotel(organizacion_id=org.id, codigo="T", nombre="Torres")
    db.add(hotel)
    db.flush()
    kw = {"organizacion_id": org.id, "hotel_id": hotel.id, "usuario_id": None}
    archivo = DatosArchivo(nombre=VARIANCE.name, sha256="a" * 64)

    carga = cargar_archivo(
        db,
        resultado=leer_variance_base_datos(VARIANCE),
        archivo=DatosArchivo(nombre=VARIANCE.name, sha256="b" * 64),
        **kw,
    )
    assert carga.resolucion is Resolucion.CREADA

    filas = leer_filas_hoja(VARIANCE)
    estructura = leer_variance_estructura_filas(filas)
    version = importar_estructura_reporte(db, resultado=estructura, archivo=archivo, **kw).version
    assert version is not None
    importar_reglas_suma(
        db, version=version, leidas=leer_variance_reglas_filas(filas, estructura), **kw
    )
    mapeo = importar_mapeo(
        db,
        version_estructura=version,
        leido=leer_variance_mapeo_filas(filas, estructura),
        archivo=archivo,
        **kw,
    ).version
    assert mapeo is not None
    valores = leer_variance_valores(VARIANCE)
    plan = importar_budget(
        db,
        version_estructura=version,
        valores=valores,
        archivo=archivo,
        periodo_corte="2026-08",
        ano_fiscal="2026/27",
        **kw,
    ).version
    assert plan is not None
    db.commit()
    yield AgostoReal(
        db=db,
        organizacion_id=org.id,
        hotel_id=hotel.id,
        estructura=estructura,
        lineas=RepositorioReporte(db, hotel.id).lineas(version.id),
        version_estructura_id=version.id,
        version_mapeo_id=mapeo.id,
        version_plan_id=plan.id,
        reglas=reglas_como_mapa(db, hotel.id, version.id),
        valores=valores,
    )
    db.close()
    engine.dispose()


def casi(a: Decimal | None, b: Decimal | None, tolerancia: str = "0.05") -> bool:
    """¿Igual dentro de la tolerancia (el propio Excel acumula diferencias de centavos)?"""
    if a is None or b is None:
        return a is b
    return abs(a - b) <= Decimal(tolerancia)
