from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fpa.db import get_db
from fpa.main import app

client = TestClient(app)


def test_health_responde_ok():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["estado"] == "ok"


def test_ready_con_base_de_datos_disponible():
    r = client.get("/api/ready")
    assert r.status_code == 200
    assert r.json() == {"estado": "listo"}


def test_ready_devuelve_503_sin_filtrar_detalle_si_la_bd_falla():
    class _SesionRota:
        def execute(self, *_a, **_k):
            raise RuntimeError("detalle interno: usuario y ruta secretos")

    app.dependency_overrides[get_db] = lambda: _SesionRota()
    try:
        r = client.get("/api/ready")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 503
    assert "secretos" not in r.text


def test_cors_solo_permite_el_frontend_local():
    ok = client.options("/api/health", headers={
        "Origin": "http://localhost:5180", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5180"
    ajeno = client.options("/api/health", headers={
        "Origin": "http://sitio-malicioso.com", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in ajeno.headers
