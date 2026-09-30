import pytest
from conftest import Mundo, como
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.config import settings
from fpa.db import get_db
from fpa.identidad.dependencias import obtener_proveedor
from fpa.identidad.permisos import PERMISOS_POR_ROL, Permiso, RolCodigo, rol_tiene_permiso
from fpa.main import app
from fpa.modelos import Asignacion, Hotel, Organizacion, Rol, Usuario
from fpa.semilla import USUARIOS_DESARROLLO, sembrar_torres


def test_sin_cabecera_es_401(cliente: TestClient, mundo: Mundo) -> None:
    assert cliente.get("/api/v1/yo").status_code == 401


def test_usuario_desconocido_es_401(cliente: TestClient, mundo: Mundo) -> None:
    assert cliente.get("/api/v1/yo", headers=como("nadie@test.local")).status_code == 401


def test_usuario_inactivo_es_401(cliente: TestClient, mundo: Mundo) -> None:
    assert cliente.get("/api/v1/yo", headers=como("inactivo@test.local")).status_code == 401


def test_yo_devuelve_roles_por_hotel(cliente: TestClient, mundo: Mundo) -> None:
    r = cliente.get("/api/v1/yo", headers=como("contralor_ab@test.local"))
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["organizacion_id"] == mundo.org1
    assert {int(k): v for k, v in cuerpo["roles_por_hotel"].items()} == {
        mundo.hotel_a: "contralor",
        mundo.hotel_b: "contralor",
    }


def test_hoteles_lista_solo_los_asignados(cliente: TestClient, mundo: Mundo) -> None:
    r = cliente.get("/api/v1/hoteles", headers=como("analista_a@test.local"))
    assert [h["id"] for h in r.json()] == [mundo.hotel_a]
    r = cliente.get("/api/v1/hoteles", headers=como("contralor_ab@test.local"))
    assert sorted(h["id"] for h in r.json()) == sorted([mundo.hotel_a, mundo.hotel_b])


def test_en_produccion_la_identidad_de_desarrollo_se_rechaza(
    sesion_factory, mundo: Mundo, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Seguro por defecto: sin OIDC configurado nadie entra, ni con la cabecera de desarrollo."""

    def _get_db():  # type: ignore[no-untyped-def]
        with sesion_factory() as sesion:
            yield sesion

    monkeypatch.setattr(settings, "entorno", "produccion")
    app.dependency_overrides[get_db] = _get_db
    try:
        assert obtener_proveedor.__name__ == "obtener_proveedor"
        r = TestClient(app).get("/api/v1/yo", headers=como("contralor_ab@test.local"))
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 401


def test_el_entorno_por_defecto_es_produccion() -> None:
    assert type(settings).model_fields["entorno"].default == "produccion"


@pytest.mark.parametrize("rol", list(RolCodigo))
def test_matriz_de_permisos(rol: RolCodigo) -> None:
    esperados = PERMISOS_POR_ROL[rol]
    for permiso in Permiso:
        assert rol_tiene_permiso(rol, permiso) == (permiso in esperados)


def test_solo_contralor_y_auditoria_leen_la_auditoria() -> None:
    con_permiso = {r for r in RolCodigo if rol_tiene_permiso(r, Permiso.AUDITORIA_LEER)}
    assert con_permiso == {RolCodigo.CONTRALOR, RolCodigo.AUDITORIA}


def test_responsable_de_area_no_puede_cargar_archivos() -> None:
    assert not rol_tiene_permiso(RolCodigo.RESPONSABLE_AREA, Permiso.CARGA_CREAR)
    assert rol_tiene_permiso(RolCodigo.ANALISTA, Permiso.CARGA_CREAR)


def test_rol_desconocido_no_tiene_permisos() -> None:
    assert not rol_tiene_permiso("inventado", Permiso.HOTEL_LEER)


def test_semilla_es_idempotente(db: Session) -> None:
    sembrar_torres(db)
    db.commit()
    primero = (
        len(db.scalars(select(Organizacion)).all()),
        len(db.scalars(select(Hotel)).all()),
        len(db.scalars(select(Usuario)).all()),
        len(db.scalars(select(Asignacion)).all()),
        len(db.scalars(select(Rol)).all()),
    )
    sembrar_torres(db)
    db.commit()
    segundo = (
        len(db.scalars(select(Organizacion)).all()),
        len(db.scalars(select(Hotel)).all()),
        len(db.scalars(select(Usuario)).all()),
        len(db.scalars(select(Asignacion)).all()),
        len(db.scalars(select(Rol)).all()),
    )
    assert primero == segundo == (1, 1, len(USUARIOS_DESARROLLO), len(USUARIOS_DESARROLLO), 5)
