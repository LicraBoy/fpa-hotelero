"""Fase 5.2: secciones asignadas a responsables y administración de usuarios."""

import pytest
import test_versionado_mapeo as tv
from conftest import Mundo, como
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_versionado_mapeo import Escenario, fila

from fpa.config import settings
from fpa.identidad.dependencias import obtener_proveedor
from fpa.identidad.proveedor import crear_proveedor
from fpa.main import app
from fpa.modelos import AsignacionDepartamento, EventoAuditoria, Usuario
from fpa.seguridad.credenciales import verificar
from fpa.servicios.versionado_mapeo import aprobar

CONTRALOR = "contralor_ab@test.local"
ANALISTA = "analista_a@test.local"
RESPONSABLE = "responsable_a@test.local"
AUDITORIA_B = "auditoria_b@test.local"  # solo hotel B

# Dos secciones: Rooms (Ingreso) y Admin (Gasto)
ESTRUCTURA = [
    fila(),
    fila("Account #", "Account Description", "AUGUST"),
    fila(None, None, "Actual"),
    fila("R o o m s"),
    fila("029-0000-1-000", "Ingreso", 100, "=-'4001002.001'!L5", None),
    fila(None, "T o t a l  R o o m s", 100, "=S5", None),
    fila("A d m i n"),
    fila("029-0000-2-000", "Gasto", 30, "='6009001.001'!L9", None),
]


@pytest.fixture
def esc(db: Session, mundo: Mundo, monkeypatch: pytest.MonkeyPatch) -> Escenario:
    monkeypatch.setattr(tv, "EJEMPLO", ESTRUCTURA)
    e = Escenario(
        db, mundo, [tv._mov("4001002.001", "0", "100"), tv._mov("6009001.001", "30", "0")]
    )
    aprobar(db, version_id=e.borrador.id, **e.kw)  # type: ignore[union-attr, arg-type]
    db.commit()
    return e


def _asignar(db: Session, mundo: Mundo, *secciones: str) -> None:
    usuario = db.scalars(select(Usuario).where(Usuario.email == RESPONSABLE)).one()
    for s in secciones:
        db.add(AsignacionDepartamento(usuario_id=usuario.id, hotel_id=mundo.hotel_a, seccion=s))
    db.commit()


def _url(mundo: Mundo, ruta: str) -> str:
    return f"/api/v1/hoteles/{mundo.hotel_a}/{ruta}"


# --- Responsable: solo lo suyo ------------------------------------------------------------------


def test_el_responsable_sin_secciones_no_ve_lineas(
    cliente: TestClient, mundo: Mundo, esc: Escenario
) -> None:
    r = cliente.get(_url(mundo, "variance?periodo=2026-08"), headers=como(RESPONSABLE))
    assert r.status_code == 200
    assert r.json()["lineas"] == [] and r.json()["secciones"] == []


def test_el_responsable_ve_solo_sus_secciones(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    _asignar(db, mundo, "Rooms")
    r = cliente.get(_url(mundo, "variance?periodo=2026-08"), headers=como(RESPONSABLE)).json()
    assert [s["descripcion"] for s in r["secciones"]] == ["Rooms"]
    assert {x["descripcion"] for x in r["lineas"]} == {"Ingreso", "Total Rooms"}
    assert r["advertencias"] == []
    # el analista sigue viendo todo
    todo = cliente.get(_url(mundo, "variance?periodo=2026-08"), headers=como(ANALISTA)).json()
    assert {x["descripcion"] for x in todo["lineas"]} >= {"Ingreso", "Gasto"}


def test_el_responsable_no_ve_el_desglose_de_otra_seccion(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    _asignar(db, mundo, "Rooms")
    h = como(RESPONSABLE)
    suyo = cliente.get(
        _url(mundo, f"variance/lineas/{esc.linea('Ingreso')}/desglose?periodo=2026-08"), headers=h
    )
    ajeno = cliente.get(
        _url(mundo, f"variance/lineas/{esc.linea('Gasto')}/desglose?periodo=2026-08"), headers=h
    )
    assert suyo.status_code == 200
    assert ajeno.status_code == 404


def test_el_responsable_no_ve_movimientos_de_cuentas_ajenas(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    _asignar(db, mundo, "Rooms")
    h = como(RESPONSABLE)
    propia = "variance/cuentas/4001002.001/movimientos?periodo=2026-08"
    ajena = "variance/cuentas/6009001.001/movimientos?periodo=2026-08"
    assert cliente.get(_url(mundo, propia), headers=h).status_code == 200
    assert cliente.get(_url(mundo, ajena), headers=h).status_code == 404


def test_el_responsable_no_exporta_ni_ve_asientos(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    _asignar(db, mundo, "Rooms")
    h = como(RESPONSABLE)
    assert (
        cliente.get(_url(mundo, "variance/exportar?periodo=2026-08"), headers=h).status_code == 403
    )
    assert cliente.get(_url(mundo, "asientos/8.1.1?periodo=2026-08"), headers=h).status_code == 403
    # quien no está restringido sí puede
    assert (
        cliente.get(
            _url(mundo, "variance/exportar?periodo=2026-08"), headers=como(ANALISTA)
        ).status_code
        == 200
    )


def test_un_total_no_revela_componentes_de_otra_seccion(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    _asignar(db, mundo, "Rooms")
    total = esc.linea("Total Rooms")
    r = cliente.get(
        _url(mundo, f"variance/lineas/{total}/desglose?periodo=2026-08"), headers=como(RESPONSABLE)
    )
    assert r.status_code == 200
    assert {c["descripcion"] for c in r.json()["componentes"]} <= {"Ingreso"}


# --- Matriz rol × endpoint ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("usuario", "ruta", "esperado"),
    [
        (CONTRALOR, "usuarios", 200),
        (ANALISTA, "usuarios", 403),
        (RESPONSABLE, "usuarios", 403),
        (AUDITORIA_B, "usuarios", 404),  # sin acceso al hotel A
        (CONTRALOR, "variance?periodo=2026-08", 200),
        (ANALISTA, "variance?periodo=2026-08", 200),
        (RESPONSABLE, "variance?periodo=2026-08", 200),
        (AUDITORIA_B, "variance?periodo=2026-08", 404),
        (RESPONSABLE, "variance/exportar?periodo=2026-08", 403),
        (ANALISTA, "variance/exportar?periodo=2026-08", 200),
        (RESPONSABLE, "auditoria", 403),
        (CONTRALOR, "auditoria", 200),
        (RESPONSABLE, "cargas", 403),
        (ANALISTA, "cargas", 200),
    ],
)
def test_matriz_rol_por_endpoint(
    cliente: TestClient, mundo: Mundo, esc: Escenario, usuario: str, ruta: str, esperado: int
) -> None:
    assert cliente.get(_url(mundo, ruta), headers=como(usuario)).status_code == esperado


def test_sin_sesion_las_rutas_de_usuarios_dan_401(cliente: TestClient, mundo: Mundo) -> None:
    assert cliente.get(_url(mundo, "usuarios")).status_code == 401
    assert cliente.post(_url(mundo, "usuarios"), json={}).status_code == 401


# --- Administración de usuarios -----------------------------------------------------------------


def _crear(cliente: TestClient, mundo: Mundo, **extra):  # type: ignore[no-untyped-def]
    cuerpo = {"email": "Nuevo@Test.Local", "nombre": "Persona Nueva", "rol": "analista", **extra}
    return cliente.post(_url(mundo, "usuarios"), json=cuerpo, headers=como(CONTRALOR))


def test_listar_trae_usuarios_roles_y_secciones(
    cliente: TestClient, mundo: Mundo, esc: Escenario
) -> None:
    r = cliente.get(_url(mundo, "usuarios"), headers=como(CONTRALOR)).json()
    correos = {u["email"] for u in r["usuarios"]}
    assert {CONTRALOR, ANALISTA, RESPONSABLE} <= correos
    assert "contralor_c@test.local" not in correos  # otra organización
    assert r["secciones_disponibles"] == ["Rooms", "Admin"]
    assert r["roles_por_seccion"] == ["responsable_area"]
    assert "password_hash" not in str(r) and "totp_secreto" not in str(r)


def test_crear_usuario_da_una_clave_temporal_que_funciona_y_se_audita(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    r = _crear(cliente, mundo, rol="responsable_area", secciones=["Admin", "Rooms"])
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["usuario"]["email"] == "nuevo@test.local"
    assert cuerpo["usuario"]["secciones"] == ["Admin", "Rooms"]
    clave = cuerpo["password_temporal"]
    usuario = db.scalars(select(Usuario).where(Usuario.email == "nuevo@test.local")).one()
    assert usuario.debe_cambiar_password and verificar(usuario.password_hash, clave)
    # la clave no aparece en la bitácora ni se puede volver a consultar
    eventos = db.scalars(
        select(EventoAuditoria).where(EventoAuditoria.accion == "usuario.creado")
    ).all()
    assert len(eventos) == 1 and clave not in str(eventos[0].detalle)
    de_nuevo = cliente.get(_url(mundo, "usuarios"), headers=como(CONTRALOR)).text
    assert clave not in de_nuevo


def test_crear_valida_rol_correo_secciones_y_duplicados(
    cliente: TestClient, mundo: Mundo, esc: Escenario
) -> None:
    assert _crear(cliente, mundo, rol="inventado").status_code == 422
    assert _crear(cliente, mundo, email="sin-arroba").status_code == 422
    assert (
        _crear(cliente, mundo, rol="responsable_area", secciones=["No existe"]).status_code == 422
    )
    assert _crear(cliente, mundo, email=ANALISTA).status_code == 409  # ya tiene acceso
    assert _crear(cliente, mundo, email="contralor_c@test.local").status_code == 409  # otra org


def test_quien_no_es_contralor_no_administra(
    cliente: TestClient, mundo: Mundo, esc: Escenario
) -> None:
    cuerpo = {"email": "x@test.local", "nombre": "X", "rol": "contralor"}
    r = cliente.post(_url(mundo, "usuarios"), json=cuerpo, headers=como(ANALISTA))
    assert r.status_code == 403


def test_cambiar_rol_y_secciones_queda_auditado_con_antes_y_despues(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    uid = db.scalars(select(Usuario).where(Usuario.email == RESPONSABLE)).one().id
    r = cliente.patch(
        _url(mundo, f"usuarios/{uid}"), json={"secciones": ["Rooms"]}, headers=como(CONTRALOR)
    )
    assert r.status_code == 200 and r.json()["secciones"] == ["Rooms"]
    # pasar a analista borra las secciones (ya no aplican)
    r = cliente.patch(
        _url(mundo, f"usuarios/{uid}"), json={"rol": "analista"}, headers=como(CONTRALOR)
    )
    assert r.json()["rol"] == "analista" and r.json()["secciones"] == []
    eventos = db.scalars(
        select(EventoAuditoria).where(EventoAuditoria.accion == "usuario.actualizado")
    ).all()
    assert len(eventos) == 2
    assert eventos[1].detalle["antes"]["rol"] == "responsable_area"  # type: ignore[index]
    assert eventos[1].detalle["despues"]["rol"] == "analista"  # type: ignore[index]


def test_el_cambio_de_rol_se_nota_en_la_siguiente_peticion(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    uid = db.scalars(select(Usuario).where(Usuario.email == ANALISTA)).one().id
    assert cliente.get(_url(mundo, "cargas"), headers=como(ANALISTA)).status_code == 200
    cliente.patch(
        _url(mundo, f"usuarios/{uid}"), json={"rol": "responsable_area"}, headers=como(CONTRALOR)
    )
    assert cliente.get(_url(mundo, "cargas"), headers=como(ANALISTA)).status_code == 403


def test_no_se_puede_dejar_al_hotel_sin_contralor_ni_quitarse_el_rol(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    yo = db.scalars(select(Usuario).where(Usuario.email == CONTRALOR)).one().id
    h = como(CONTRALOR)
    assert (
        cliente.patch(
            _url(mundo, f"usuarios/{yo}"), json={"rol": "analista"}, headers=h
        ).status_code
        == 409
    )
    assert (
        cliente.patch(_url(mundo, f"usuarios/{yo}"), json={"activo": False}, headers=h).status_code
        == 409
    )
    # el único otro Contralor del hotel A es el inactivo: bajarlo de rango no debe romper nada, pero
    # un Contralor nuevo desactivado por el único activo sí lo dejaría sin respaldo
    r = _crear(cliente, mundo, email="otro@test.local", rol="contralor")
    otro = r.json()["usuario"]["usuario_id"]
    assert (
        cliente.patch(
            _url(mundo, f"usuarios/{otro}"), json={"activo": False}, headers=h
        ).status_code
        == 200
    )


def test_desactivar_cierra_sus_sesiones_y_no_puede_entrar(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    uid = db.scalars(select(Usuario).where(Usuario.email == ANALISTA)).one().id
    r = cliente.patch(
        _url(mundo, f"usuarios/{uid}"), json={"activo": False}, headers=como(CONTRALOR)
    )
    assert r.status_code == 200 and r.json()["activo"] is False
    assert cliente.get(_url(mundo, "cargas"), headers=como(ANALISTA)).status_code == 401


def test_usuario_de_otro_hotel_u_organizacion_es_404(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    ajeno = db.scalars(select(Usuario).where(Usuario.email == "contralor_c@test.local")).one().id
    h = como(CONTRALOR)
    assert (
        cliente.patch(_url(mundo, f"usuarios/{ajeno}"), json={"nombre": "x"}, headers=h).status_code
        == 404
    )
    assert (
        cliente.post(_url(mundo, f"usuarios/{ajeno}/restablecer-password"), headers=h).status_code
        == 404
    )
    assert cliente.post(_url(mundo, f"usuarios/{ajeno}/desbloquear"), headers=h).status_code == 404


def test_restablecer_password_y_desbloquear(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    usuario = db.scalars(select(Usuario).where(Usuario.email == ANALISTA)).one()
    from datetime import timedelta

    from fpa.modelos.base import ahora_utc

    usuario.intentos_fallidos = 3
    usuario.bloqueado_hasta = ahora_utc() + timedelta(minutes=10)
    db.commit()
    h = como(CONTRALOR)
    r = cliente.post(_url(mundo, f"usuarios/{usuario.id}/restablecer-password"), headers=h)
    clave = r.json()["password_temporal"]
    db.refresh(usuario)
    assert verificar(usuario.password_hash, clave) and usuario.bloqueado_hasta is None
    assert usuario.debe_cambiar_password
    acciones = {e.accion for e in db.scalars(select(EventoAuditoria))}
    assert "usuario.password_restablecida" in acciones
    usuario.bloqueado_hasta = ahora_utc() + timedelta(minutes=10)
    db.commit()
    assert (
        cliente.post(_url(mundo, f"usuarios/{usuario.id}/desbloquear"), headers=h).status_code
        == 204
    )
    db.refresh(usuario)
    assert usuario.bloqueado_hasta is None


def test_con_sesion_real_el_responsable_tambien_queda_acotado(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La restricción vive en el Principal: vale igual con cabecera de desarrollo o con sesión."""
    _asignar(db, mundo, "Rooms")
    monkeypatch.setattr(settings, "cookie_segura", False)
    app.dependency_overrides[obtener_proveedor] = crear_proveedor
    from fpa.seguridad.credenciales import hashear

    usuario = db.scalars(select(Usuario).where(Usuario.email == RESPONSABLE)).one()
    usuario.password_hash = hashear("Clave-de-prueba-91")
    db.commit()
    r = cliente.post(
        "/api/v1/auth/login", json={"email": RESPONSABLE, "password": "Clave-de-prueba-91"}
    )
    assert r.status_code == 200
    v = cliente.get(_url(mundo, "variance?periodo=2026-08")).json()
    assert {x["descripcion"] for x in v["lineas"]} == {"Ingreso", "Total Rooms"}
