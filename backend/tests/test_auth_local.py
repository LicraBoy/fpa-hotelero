"""Identidad local (ADR 0005): login, bloqueo, sesiones, contraseña, TOTP y CSRF."""

from collections.abc import Iterator
from datetime import timedelta

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from fpa.config import settings
from fpa.identidad.dependencias import obtener_proveedor
from fpa.identidad.proveedor import ProveedorDesarrollo, crear_proveedor
from fpa.main import app
from fpa.modelos import EventoAuditoria, Sesion, Usuario
from fpa.modelos.base import ahora_utc
from fpa.seguridad.credenciales import errores_de_politica, hashear
from tests.conftest import Mundo

CLAVE = "Clave-de-prueba-91"
EMAIL = "contralor_ab@test.local"


@pytest.fixture
def real(
    cliente: TestClient, monkeypatch: pytest.MonkeyPatch, mundo: Mundo
) -> Iterator[TestClient]:
    """Cliente con el proveedor de sesión real (sin la cabecera de desarrollo)."""
    monkeypatch.setattr(settings, "cookie_segura", False)
    monkeypatch.setattr(settings, "entorno", "produccion")
    app.dependency_overrides[obtener_proveedor] = crear_proveedor
    yield cliente
    app.dependency_overrides[obtener_proveedor] = ProveedorDesarrollo


@pytest.fixture(autouse=True)
def con_clave(sesion_factory: sessionmaker[Session], mundo: Mundo) -> None:
    with sesion_factory() as db:
        for usuario in db.scalars(select(Usuario)):
            usuario.password_hash = hashear(CLAVE)
        db.commit()


def _login(c: TestClient, email: str = EMAIL, password: str = CLAVE, **extra: str):  # type: ignore[no-untyped-def]
    return c.post("/api/v1/auth/login", json={"email": email, "password": password, **extra})


def test_sin_sesion_es_401(real: TestClient, mundo: Mundo) -> None:
    assert real.get("/api/v1/yo").status_code == 401
    assert real.get("/api/v1/auth/estado").json()["autenticado"] is False


def test_login_correcto_abre_sesion_y_no_filtra_el_hash(real: TestClient, mundo: Mundo) -> None:
    r = _login(real)
    assert r.status_code == 200
    assert "password_hash" not in r.text and "argon2" not in r.text and "totp_secreto" not in r.text
    assert "httponly" in r.headers["set-cookie"].lower()
    assert "samesite=strict" in r.headers["set-cookie"].lower()
    assert real.get("/api/v1/yo").status_code == 200
    assert real.get("/api/v1/auth/estado").json()["autenticado"] is True


def test_contrasena_mal_y_usuario_inexistente_responden_igual(real: TestClient) -> None:
    a = _login(real, password="otra-clave-123")
    b = _login(real, email="nadie@test.local")
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_bloqueo_tras_intentos_fallidos(real: TestClient, mundo: Mundo) -> None:
    for _ in range(settings.login_max_intentos):
        assert _login(real, password="mala-clave-1").status_code == 401
    # Ya bloqueada: ni con la clave correcta
    assert _login(real).status_code == 429


def test_cuenta_inactiva_no_entra(real: TestClient) -> None:
    assert _login(real, email="inactivo@test.local").status_code == 401


def test_logout_revoca_la_sesion(real: TestClient, sesion_factory: sessionmaker[Session]) -> None:
    _login(real)
    assert real.post("/api/v1/auth/logout").status_code == 204
    assert real.get("/api/v1/yo").status_code == 401


def test_sesion_caducada_por_inactividad_o_por_duracion(
    real: TestClient, sesion_factory: sessionmaker[Session]
) -> None:
    _login(real)
    with sesion_factory() as db:
        s = db.scalars(select(Sesion)).one()
        s.ultimo_uso = ahora_utc() - timedelta(minutes=settings.sesion_inactividad_min + 5)
        db.commit()
    assert real.get("/api/v1/yo").status_code == 401
    _login(real)
    with sesion_factory() as db:
        s = db.scalars(select(Sesion).order_by(Sesion.id.desc())).first()
        assert s is not None
        s.expira_en = ahora_utc() - timedelta(minutes=1)
        db.commit()
    assert real.get("/api/v1/yo").status_code == 401


def test_sesion_revocada_en_la_base_deja_de_funcionar(
    real: TestClient, sesion_factory: sessionmaker[Session]
) -> None:
    _login(real)
    assert real.get("/api/v1/yo").status_code == 200
    with sesion_factory() as db:
        db.scalars(select(Sesion)).one().revocada_en = ahora_utc()
        db.commit()
    assert real.get("/api/v1/yo").status_code == 401


def test_la_base_solo_guarda_el_hash_del_token(
    real: TestClient, sesion_factory: sessionmaker[Session]
) -> None:
    _login(real)
    token = real.cookies.get(settings.cookie_nombre)
    with sesion_factory() as db:
        assert token and db.scalars(select(Sesion)).one().token_hash != token


def test_cabecera_de_desarrollo_no_autentica_en_produccion(real: TestClient) -> None:
    r = real.get("/api/v1/yo", headers={"X-Usuario-Dev": EMAIL})
    assert r.status_code == 401


def test_cambiar_password_valida_politica_y_cierra_otras_sesiones(
    real: TestClient, sesion_factory: sessionmaker[Session]
) -> None:
    _login(real)
    mala = real.post("/api/v1/auth/cambiar-password", json={"actual": CLAVE, "nueva": "corta1"})
    assert mala.status_code == 422
    mal_actual = real.post(
        "/api/v1/auth/cambiar-password", json={"actual": "no-es-esa-1", "nueva": "Otra-clave-5678"}
    )
    assert mal_actual.status_code == 400
    ok = real.post(
        "/api/v1/auth/cambiar-password", json={"actual": CLAVE, "nueva": "Otra-clave-5678"}
    )
    assert ok.status_code == 204
    assert real.get("/api/v1/yo").status_code == 200  # la sesión actual sigue
    assert _login(real, password=CLAVE).status_code == 401
    assert _login(real, password="Otra-clave-5678").status_code == 200


def test_politica_de_contrasena() -> None:
    assert errores_de_politica("abc", "x@y.z")
    assert errores_de_politica("sololetrasaqui", "x@y.z")
    assert errores_de_politica("contrasena", "x@y.z")
    assert errores_de_politica("Pedro12345678", "pedro@y.z")
    assert not errores_de_politica("Buena-clave-77", "x@y.z")


def test_totp_activacion_y_login_con_codigo(real: TestClient) -> None:
    _login(real)
    inicio = real.post("/api/v1/auth/mfa/iniciar").json()
    assert inicio["uri"].startswith("otpauth://totp/")
    codigo = pyotp.TOTP(inicio["secreto"]).now()
    assert real.post("/api/v1/auth/mfa/confirmar", json={"codigo": "000000"}).status_code == 422
    assert real.post("/api/v1/auth/mfa/confirmar", json={"codigo": codigo}).status_code == 204
    real.post("/api/v1/auth/logout")
    # Sin código ya no entra; con código sí
    assert _login(real).status_code == 401
    assert _login(real, codigo="111111").status_code == 401
    assert _login(real, codigo=pyotp.TOTP(inicio["secreto"]).now()).status_code == 200
    # Para desactivarlo hace falta la contraseña
    assert real.post("/api/v1/auth/mfa/desactivar", json={"password": "mala"}).status_code == 400
    assert real.post("/api/v1/auth/mfa/desactivar", json={"password": CLAVE}).status_code == 204


def test_origen_ajeno_con_cookie_se_rechaza(real: TestClient) -> None:
    _login(real)
    r = real.post("/api/v1/auth/logout", headers={"Origin": "https://malo.example"})
    assert r.status_code == 403
    r = real.post("/api/v1/auth/logout", headers={"Origin": settings.cors_origins[0]})
    assert r.status_code == 204


def test_eventos_de_auditoria_de_acceso(
    real: TestClient, sesion_factory: sessionmaker[Session]
) -> None:
    _login(real, password="mala-clave-1")
    _login(real)
    real.post("/api/v1/auth/logout")
    with sesion_factory() as db:
        acciones = [
            e.accion for e in db.scalars(select(EventoAuditoria).order_by(EventoAuditoria.id))
        ]
    assert acciones == ["auth.login_fallido", "auth.login", "auth.logout"]
