"""Aislamiento entre hoteles y organizaciones (Blueprint §34, Arquitectura §4.4)."""

from collections.abc import Iterator

import pytest
from conftest import Mundo, como
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from fpa.db import get_db
from fpa.identidad.dependencias import ContextoHotel, hotel_autorizado, obtener_proveedor
from fpa.identidad.permisos import Permiso
from fpa.identidad.proveedor import ProveedorDesarrollo


def test_usuario_del_hotel_a_no_lee_el_hotel_b(cliente: TestClient, mundo: Mundo) -> None:
    propio = cliente.get(f"/api/v1/hoteles/{mundo.hotel_a}", headers=como("analista_a@test.local"))
    ajeno = cliente.get(f"/api/v1/hoteles/{mundo.hotel_b}", headers=como("analista_a@test.local"))
    assert propio.status_code == 200
    assert ajeno.status_code == 404


def test_usuario_de_otra_organizacion_no_ve_hoteles_ajenos(
    cliente: TestClient, mundo: Mundo
) -> None:
    for hotel in (mundo.hotel_a, mundo.hotel_b):
        r = cliente.get(f"/api/v1/hoteles/{hotel}", headers=como("contralor_c@test.local"))
        assert r.status_code == 404
    r = cliente.get(f"/api/v1/hoteles/{mundo.hotel_c}", headers=como("contralor_c@test.local"))
    assert r.status_code == 200


def test_contralor_con_dos_hoteles_ve_ambos(cliente: TestClient, mundo: Mundo) -> None:
    for hotel in (mundo.hotel_a, mundo.hotel_b):
        r = cliente.get(f"/api/v1/hoteles/{hotel}", headers=como("contralor_ab@test.local"))
        assert r.status_code == 200
        assert r.json()["id"] == hotel


def test_hotel_ajeno_y_hotel_inexistente_responden_igual(cliente: TestClient, mundo: Mundo) -> None:
    """No se revela si un hotel existe: ambos casos dan exactamente la misma respuesta."""
    ajeno = cliente.get(f"/api/v1/hoteles/{mundo.hotel_c}", headers=como("analista_a@test.local"))
    inexistente = cliente.get("/api/v1/hoteles/99999", headers=como("analista_a@test.local"))
    assert ajeno.status_code == inexistente.status_code == 404
    assert ajeno.json() == inexistente.json()


def test_sin_sesion_no_se_ve_ningun_hotel(cliente: TestClient, mundo: Mundo) -> None:
    assert cliente.get(f"/api/v1/hoteles/{mundo.hotel_a}").status_code == 401


# --- Permisos dentro del hotel propio (403) ---------------------------------------------------


@pytest.fixture
def cliente_con_ruta_protegida(sesion_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    app = FastAPI()

    @app.post("/hoteles/{hotel_id}/prueba")
    def _prueba(
        contexto: ContextoHotel = Depends(hotel_autorizado(Permiso.CARGA_CREAR)),
    ) -> dict[str, int]:
        return {"hotel_id": contexto.hotel_id}

    def _get_db() -> Iterator[Session]:
        with sesion_factory() as sesion:
            yield sesion

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[obtener_proveedor] = ProveedorDesarrollo
    yield TestClient(app)


def test_analista_puede_y_responsable_no_en_su_propio_hotel(
    cliente_con_ruta_protegida: TestClient, mundo: Mundo
) -> None:
    c = cliente_con_ruta_protegida
    url = f"/hoteles/{mundo.hotel_a}/prueba"
    assert c.post(url, headers=como("analista_a@test.local")).status_code == 200
    assert c.post(url, headers=como("contralor_ab@test.local")).status_code == 200
    assert c.post(url, headers=como("responsable_a@test.local")).status_code == 403


def test_el_permiso_depende_del_hotel_no_solo_del_usuario(
    cliente_con_ruta_protegida: TestClient, mundo: Mundo
) -> None:
    """auditoria_b solo tiene rol en B: en A es un hotel ajeno (404), en B no puede cargar (403)."""
    c = cliente_con_ruta_protegida
    assert (
        c.post(
            f"/hoteles/{mundo.hotel_a}/prueba", headers=como("auditoria_b@test.local")
        ).status_code
        == 404
    )
    assert (
        c.post(
            f"/hoteles/{mundo.hotel_b}/prueba", headers=como("auditoria_b@test.local")
        ).status_code
        == 403
    )
