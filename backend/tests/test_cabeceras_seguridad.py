import pytest
from conftest import Mundo, como
from fastapi.testclient import TestClient

from fpa.seguridad.cabeceras import CABECERAS_API

RUTAS = [
    "/api/health",
    "/api/v1/yo",
    "/api/v1/hoteles",
]


@pytest.mark.parametrize("ruta", RUTAS)
def test_toda_respuesta_de_la_api_lleva_las_cabeceras(
    cliente: TestClient, mundo: Mundo, ruta: str
) -> None:
    r = cliente.get(ruta, headers=como("analista_a@test.local"))
    assert r.status_code == 200
    for nombre, valor in CABECERAS_API.items():
        assert r.headers[nombre] == valor, nombre
    assert r.headers["Cache-Control"] == "no-store"
    assert r.headers["Content-Security-Policy"] == "default-src 'none'; frame-ancestors 'none'"


def test_tambien_los_errores_las_llevan(cliente: TestClient, mundo: Mundo) -> None:
    for r in (
        cliente.get("/api/v1/yo"),  # 401
        cliente.get("/api/v1/hoteles/999", headers=como("analista_a@test.local")),  # 404
        cliente.get("/api/v1/ruta-que-no-existe"),  # 404 de ruta
    ):
        assert r.status_code in (401, 404)
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        assert "default-src 'none'" in r.headers["Content-Security-Policy"]


def test_no_se_pisa_un_cache_control_explicito(cliente: TestClient) -> None:
    # `setdefault`: una ruta que fije su propia política (p. ej. una descarga) la conserva
    assert "no-store" in cliente.get("/api/health").headers["Cache-Control"]


def test_la_documentacion_queda_fuera_de_la_politica_de_la_api(cliente: TestClient) -> None:
    # Swagger UI necesita cargar sus propios scripts: no se le aplica `default-src 'none'`
    r = cliente.get("/docs")
    assert "Content-Security-Policy" not in r.headers
