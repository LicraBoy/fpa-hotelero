"""Fase 5.5: cadena de hashes de la bitácora, verificación e historial de la cifra."""

import importlib
import inspect
import pkgutil

import pytest
from conftest import Mundo, como
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, sessionmaker
from test_acceso_usuarios import _asignar
from test_versionado_mapeo import Escenario

import fpa.api.v1 as paquete_api
from fpa.modelos import EventoAuditoria
from fpa.modelos.auditoria import AuditoriaInmutable
from fpa.servicios.auditoria import auditar
from fpa.servicios.cadena_auditoria import GENESIS, verificar

CONTRALOR = "contralor_ab@test.local"
ANALISTA = "analista_a@test.local"
AUDITORIA_B = "auditoria_b@test.local"  # solo hotel B
RESPONSABLE = "responsable_a@test.local"
OTRA_ORG = "contralor_c@test.local"


def _evento(db: Session, mundo: Mundo, accion: str = "prueba.evento", org: int | None = None):  # type: ignore[no-untyped-def]
    return auditar(
        db,
        organizacion_id=org or mundo.org1,
        hotel_id=None,
        usuario_id=None,
        accion=accion,
        entidad="prueba",
        entidad_id=1,
        detalle={"a": 1, "b": ["x", None], "ñ": "acento"},
    )


def _fresca(sesion_factory: sessionmaker[Session]) -> Session:
    return sesion_factory()


# --- La cadena ----------------------------------------------------------------------------------


def test_los_eventos_se_encadenan_y_sobreviven_a_la_base(
    db: Session, mundo: Mundo, sesion_factory: sessionmaker[Session]
) -> None:
    a = _evento(db, mundo, "uno")
    b = _evento(db, mundo, "dos")  # misma transacción: se encadena al anterior, no al mismo
    c = _evento(db, mundo, "tres")
    db.commit()
    assert a.hash_previo == GENESIS and b.hash_previo == a.hash and c.hash_previo == b.hash
    assert len({a.hash, b.hash, c.hash}) == 3
    # releído desde la base (las fechas pierden la zona en SQLite) la cadena sigue cuadrando
    with _fresca(sesion_factory) as otra:
        r = verificar(otra, mundo.org1)
    assert r.integra and r.eventos >= 3 and r.ultimo_hash == c.hash


def test_cada_organizacion_tiene_su_propia_cadena(db: Session, mundo: Mundo) -> None:
    _evento(db, mundo, "org1")
    ajeno = _evento(db, mundo, "org2", org=mundo.org2)
    db.commit()
    assert ajeno.hash_previo == GENESIS
    assert verificar(db, mundo.org1).integra and verificar(db, mundo.org2).integra


def test_alterar_un_evento_se_detecta(
    db: Session, mundo: Mundo, sesion_factory: sessionmaker[Session]
) -> None:
    eventos = [_evento(db, mundo, f"e{i}") for i in range(4)]
    db.commit()
    # el ORM no deja, así que se hace directo en la base (como lo haría alguien con acceso a ella)
    db.execute(
        update(EventoAuditoria.__table__)  # type: ignore[arg-type]
        .where(EventoAuditoria.id == eventos[1].id)
        .values(accion="alterada")
    )
    db.commit()
    with _fresca(sesion_factory) as otra:
        r = verificar(otra, mundo.org1)
    assert not r.integra and r.primer_alterado_id == eventos[1].id
    assert "cambió" in (r.motivo or "")


def test_borrar_un_evento_del_medio_se_detecta(
    db: Session, mundo: Mundo, sesion_factory: sessionmaker[Session]
) -> None:
    eventos = [_evento(db, mundo, f"e{i}") for i in range(4)]
    db.commit()
    db.execute(delete(EventoAuditoria.__table__).where(EventoAuditoria.id == eventos[1].id))  # type: ignore[arg-type]
    db.commit()
    with _fresca(sesion_factory) as otra:
        r = verificar(otra, mundo.org1)
    assert not r.integra and r.primer_alterado_id == eventos[2].id
    assert "Falta un evento" in (r.motivo or "")


def test_borrar_el_ultimo_cambia_el_hash_que_se_anoto(db: Session, mundo: Mundo) -> None:
    _evento(db, mundo, "a")
    ultimo = _evento(db, mundo, "b")
    db.commit()
    anotado = verificar(db, mundo.org1).ultimo_hash
    assert anotado == ultimo.hash
    db.execute(delete(EventoAuditoria.__table__).where(EventoAuditoria.id == ultimo.id))  # type: ignore[arg-type]
    db.commit()
    r = verificar(db, mundo.org1)
    assert r.integra  # la base sola no lo nota…
    assert r.ultimo_hash != anotado  # …pero el hash anotado aparte sí delata el faltante


def test_el_orm_sigue_sin_dejar_modificar_ni_borrar(db: Session, mundo: Mundo) -> None:
    e = _evento(db, mundo)
    db.commit()
    e.accion = "x"
    with pytest.raises(AuditoriaInmutable):
        db.flush()
    db.rollback()
    db.delete(db.scalars(select(EventoAuditoria)).first())
    with pytest.raises(AuditoriaInmutable):
        db.flush()
    db.rollback()


# --- API de verificación ------------------------------------------------------------------------


def test_verificar_por_api_y_permisos(cliente: TestClient, mundo: Mundo, db: Session) -> None:
    _evento(db, mundo)
    db.commit()
    url = f"/api/v1/hoteles/{mundo.hotel_a}/auditoria/verificar"
    ok = cliente.get(url, headers=como(CONTRALOR))
    assert ok.status_code == 200 and ok.json()["integra"] is True and ok.json()["eventos"] >= 1
    assert cliente.get(url, headers=como(ANALISTA)).status_code == 403
    assert cliente.get(url, headers=como(OTRA_ORG)).status_code == 404
    assert cliente.get(url).status_code == 401
    # la auditoría de otro hotel de la misma organización también puede verificar
    assert (
        cliente.get(
            f"/api/v1/hoteles/{mundo.hotel_b}/auditoria/verificar", headers=como(AUDITORIA_B)
        ).status_code
        == 200
    )
    db.execute(
        update(EventoAuditoria.__table__).values(detalle={"cambiado": True})  # type: ignore[arg-type]
    )
    db.commit()
    malo = cliente.get(url, headers=como(CONTRALOR)).json()
    assert malo["integra"] is False and malo["primer_alterado_id"] is not None


def test_toda_la_actividad_de_la_aplicacion_deja_una_cadena_integra(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    h = como(CONTRALOR)
    base = f"/api/v1/hoteles/{mundo.hotel_a}"
    cuerpo = {
        "linea_id": esc.linea("Ingreso"),
        "periodo": "2026-08",
        "bloque": "mes",
        "texto": "ok",
    }
    assert cliente.post(f"{base}/comentarios", json=cuerpo, headers=h).status_code == 201
    for hacia in ("comentado", "revisado", "aprobado"):
        assert (
            cliente.post(
                f"{base}/cierres/2026-08/transiciones", json={"hacia": hacia}, headers=h
            ).status_code
            == 200
        )
    r = cliente.get(f"{base}/auditoria/verificar", headers=h).json()
    assert r["integra"] is True and r["eventos"] >= 4


# --- Toda ruta de escritura deja rastro ---------------------------------------------------------

# Rutas cuyo manejador no llama a `auditar` directamente: delegan en un servicio que sí lo hace.
DELEGAN_EN_SERVICIO = {
    "/hoteles/{hotel_id}/budget/versiones": "servicios.budget (budget.importado/editado)",
    "/hoteles/{hotel_id}/budget/capturados": "servicios.valores_capturados (actual.capturado)",
    "/hoteles/{hotel_id}/cierres/{periodo}/transiciones": "servicios.cierre (cierre.*)",
    "/hoteles/{hotel_id}/mapeo/versiones": "servicios.versionado_mapeo (mapeo.*)",
    "/hoteles/{hotel_id}/mapeo/versiones/{version_id}/vinculos": "servicios.versionado_mapeo",
    "/hoteles/{hotel_id}/mapeo/versiones/{version_id}/exclusiones": "servicios.versionado_mapeo",
    "/hoteles/{hotel_id}/mapeo/versiones/{version_id}/descartar": "servicios.versionado_mapeo",
    "/hoteles/{hotel_id}/mapeo/versiones/{version_id}/aprobar": "servicios.versionado_mapeo",
    "/hoteles/{hotel_id}/reporte/convenciones": "servicios.estructura_reporte (convenciones.*)",
}


def _rutas_de_escritura():  # type: ignore[no-untyped-def]
    for modulo in pkgutil.iter_modules(paquete_api.__path__):
        router = getattr(importlib.import_module(f"fpa.api.v1.{modulo.name}"), "router", None)
        for ruta in getattr(router, "routes", []):
            metodos = getattr(ruta, "methods", set()) & {"POST", "PUT", "PATCH", "DELETE"}
            if metodos:
                yield modulo.name, ruta


def test_toda_ruta_que_escribe_audita_o_esta_declarada_como_delegada() -> None:
    sin_rastro = []
    for modulo, ruta in _rutas_de_escritura():
        audita = "auditar(" in inspect.getsource(ruta.endpoint)
        if not audita and ruta.path not in DELEGAN_EN_SERVICIO:
            sin_rastro.append(f"{modulo}: {sorted(ruta.methods)} {ruta.path}")
    assert not sin_rastro, (
        "Estas rutas escriben datos pero no dejan evento en la bitácora (llama a `auditar` o "
        "decláralas en DELEGAN_EN_SERVICIO si un servicio lo hace): " + "; ".join(sin_rastro)
    )


def test_las_rutas_delegadas_existen() -> None:
    existentes = {ruta.path for _, ruta in _rutas_de_escritura()}
    assert set(DELEGAN_EN_SERVICIO) <= existentes


# --- Historial de la cifra ----------------------------------------------------------------------


def test_el_historial_de_una_linea_junta_carga_mapeo_comentario_y_cierre(
    cliente: TestClient, mundo: Mundo, esc: Escenario
) -> None:
    h = como(ANALISTA)
    base = f"/api/v1/hoteles/{mundo.hotel_a}"
    cuerpo = {
        "linea_id": esc.linea("Ingreso"),
        "periodo": "2026-08",
        "bloque": "mes",
        "texto": "Congreso",
    }
    cliente.post(f"{base}/comentarios", json=cuerpo, headers=h)
    cliente.post(f"{base}/cierres/2026-08/transiciones", json={"hacia": "comentado"}, headers=h)
    r = cliente.get(
        f"{base}/variance/lineas/{esc.linea('Ingreso')}/historial?periodo=2026-08", headers=h
    )
    assert r.status_code == 200, r.text
    hechos = r.json()["hechos"]
    tipos = [x["tipo"] for x in hechos]
    assert {"carga", "mapeo", "comentario", "cierre"} <= set(tipos)
    assert [x["fecha"] for x in hechos] == sorted(x["fecha"] for x in hechos)
    carga = next(x for x in hechos if x["tipo"] == "carga")
    assert "m.xlsx" in carga["titulo"] and carga["detalle"] is not None
    coment = next(x for x in hechos if x["tipo"] == "comentario")
    assert coment["detalle"] == "Congreso" and coment["usuario"] == ANALISTA


def test_el_historial_registra_los_cambios_de_mapeo_de_esa_linea(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    from fpa.servicios.versionado_mapeo import agregar_vinculo, crear_borrador_desde

    nuevo = crear_borrador_desde(
        db, organizacion_id=mundo.org1, hotel_id=mundo.hotel_a, usuario_id=None
    )
    agregar_vinculo(
        db,
        version_id=nuevo.id,
        linea_id=esc.linea("Gasto"),
        cuenta_codigo="6009001.002",
        signo=1,
        **esc.kw,  # type: ignore[arg-type]
    )
    db.commit()
    base = f"/api/v1/hoteles/{mundo.hotel_a}"
    r = cliente.get(
        f"{base}/variance/lineas/{esc.linea('Gasto')}/historial?periodo=2026-08",
        headers=como(ANALISTA),
    ).json()
    assert any(x["titulo"] == "Cuenta vinculada: 6009001.002" for x in r["hechos"])
    otra = cliente.get(
        f"{base}/variance/lineas/{esc.linea('Ingreso')}/historial?periodo=2026-08",
        headers=como(ANALISTA),
    ).json()
    assert not any("6009001.002" in x["titulo"] for x in otra["hechos"])


def test_el_historial_del_responsable_solo_trae_lo_de_su_linea(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    _asignar(db, mundo, "Rooms")
    base = f"/api/v1/hoteles/{mundo.hotel_a}"
    cuerpo = {"linea_id": esc.linea("Ingreso"), "periodo": "2026-08", "bloque": "mes", "texto": "x"}
    cliente.post(f"{base}/comentarios", json=cuerpo, headers=como(ANALISTA))
    cliente.post(
        f"{base}/cierres/2026-08/transiciones", json={"hacia": "comentado"}, headers=como(ANALISTA)
    )
    h = como(RESPONSABLE)
    r = cliente.get(
        f"{base}/variance/lineas/{esc.linea('Ingreso')}/historial?periodo=2026-08", headers=h
    ).json()
    assert {x["tipo"] for x in r["hechos"]} == {"comentario"}  # sin cargas ni cierre
    ajena = cliente.get(
        f"{base}/variance/lineas/{esc.linea('Gasto')}/historial?periodo=2026-08", headers=h
    )
    assert ajena.status_code == 404


def test_historial_valida_permiso_y_datos(
    cliente: TestClient, mundo: Mundo, esc: Escenario
) -> None:
    base = f"/api/v1/hoteles/{mundo.hotel_a}"
    ruta = f"{base}/variance/lineas/{esc.linea('Ingreso')}/historial?periodo=2026-08"
    assert cliente.get(ruta).status_code == 401
    assert cliente.get(ruta, headers=como(OTRA_ORG)).status_code == 404
    assert (
        cliente.get(
            f"{base}/variance/lineas/999999/historial?periodo=2026-08", headers=como(ANALISTA)
        ).status_code
        == 404
    )
    assert (
        cliente.get(
            f"{base}/variance/lineas/{esc.linea('Rooms')}/historial?periodo=2026-08",
            headers=como(ANALISTA),
        ).status_code
        == 404
    )
    assert (
        cliente.get(ruta.replace("2026-08", "2026-13"), headers=como(ANALISTA)).status_code == 422
    )
