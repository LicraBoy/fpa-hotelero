from collections.abc import Callable, Iterator
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from fpa.db import get_db
from fpa.identidad.dependencias import obtener_proveedor
from fpa.identidad.proveedor import ProveedorDesarrollo
from fpa.main import app
from fpa.modelos import Asignacion, Base, Hotel, Organizacion, Usuario
from fpa.semilla import sembrar_roles


@pytest.fixture
def engine() -> Iterator[Engine]:
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def sesion_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def db(sesion_factory: sessionmaker[Session]) -> Iterator[Session]:
    with sesion_factory() as sesion:
        yield sesion


@pytest.fixture
def cliente(sesion_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    """Cliente de la API con base de datos en memoria e identidad de desarrollo."""

    def _get_db() -> Iterator[Session]:
        with sesion_factory() as sesion:
            yield sesion

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[obtener_proveedor] = ProveedorDesarrollo
    yield TestClient(app)
    app.dependency_overrides.clear()


@dataclass
class Mundo:
    """Dos organizaciones; la primera con dos hoteles (A y B), la segunda con uno (C)."""

    org1: int
    org2: int
    hotel_a: int
    hotel_b: int
    hotel_c: int


def _crear_usuario(
    db: Session, org_id: int, email: str, asignaciones: dict[int, str], activo: bool = True
) -> None:
    roles = sembrar_roles(db)
    usuario = Usuario(organizacion_id=org_id, email=email, nombre=email, activo=activo)
    db.add(usuario)
    db.flush()
    for hotel_id, rol in asignaciones.items():
        db.add(Asignacion(usuario_id=usuario.id, hotel_id=hotel_id, rol_id=roles[rol].id))


@pytest.fixture
def mundo(db: Session) -> Mundo:
    sembrar_roles(db)
    org1 = Organizacion(nombre="Organización Uno")
    org2 = Organizacion(nombre="Organización Dos")
    db.add_all([org1, org2])
    db.flush()
    a = Hotel(organizacion_id=org1.id, codigo="A", nombre="Hotel A")
    b = Hotel(organizacion_id=org1.id, codigo="B", nombre="Hotel B")
    c = Hotel(organizacion_id=org2.id, codigo="C", nombre="Hotel C")
    db.add_all([a, b, c])
    db.flush()
    _crear_usuario(db, org1.id, "analista_a@test.local", {a.id: "analista"})
    _crear_usuario(db, org1.id, "contralor_ab@test.local", {a.id: "contralor", b.id: "contralor"})
    _crear_usuario(db, org1.id, "responsable_a@test.local", {a.id: "responsable_area"})
    _crear_usuario(db, org1.id, "auditoria_b@test.local", {b.id: "auditoria"})
    _crear_usuario(db, org1.id, "inactivo@test.local", {a.id: "contralor"}, activo=False)
    _crear_usuario(db, org2.id, "contralor_c@test.local", {c.id: "contralor"})
    db.commit()
    return Mundo(org1=org1.id, org2=org2.id, hotel_a=a.id, hotel_b=b.id, hotel_c=c.id)


def como(email: str) -> dict[str, str]:
    """Cabecera de identidad de desarrollo para una petición."""
    return {"X-Usuario-Dev": email}


@pytest.fixture
def contar() -> Callable[[Session, type], int]:
    def _contar(db: Session, modelo: type) -> int:
        return len(db.scalars(select(modelo)).all())

    return _contar
