"""Fase 7.1: calendario fiscal y las transiciones del ciclo de captura del Budget."""

import pytest
from conftest import Mundo
from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.identidad.permisos import Permiso
from fpa.modelos import (
    CicloTransicion,
    EventoAuditoria,
    LineaReporte,
    Usuario,
    VersionEstructuraReporte,
)
from fpa.modelos.cierre import TransicionInmutable
from fpa.servicios.presupuesto_ciclo import (
    CicloInvalido,
    crear_ano_fiscal,
    crear_ciclo,
    crear_periodo_fiscal,
    generar_periodos_fiscales,
    historial,
    transicionar,
)

PUEDE_TODO = dict.fromkeys(Permiso, True)
PUEDE_NADA: dict[Permiso, bool] = {}


def _usuario_id(db: Session, email: str) -> int:
    return db.scalars(select(Usuario.id).where(Usuario.email == email)).one()


def _ano(db: Session, mundo: Mundo, etiqueta: str = "2026/27"):  # type: ignore[no-untyped-def]
    return crear_ano_fiscal(db, hotel_id=mundo.hotel_a, etiqueta=etiqueta, mes_inicio=7, mes_fin=6)


def _estructura_vigente(db: Session, hotel_id: int) -> VersionEstructuraReporte:
    version = VersionEstructuraReporte(
        hotel_id=hotel_id,
        nombre_archivo="estructura.xlsx",
        sha256="0" * 64,
        estado="vigente",
        n_lineas=1,
        n_detalle=1,
    )
    db.add(version)
    db.flush()
    db.add(
        LineaReporte(
            version_id=version.id,
            hotel_id=hotel_id,
            orden=1,
            tipo="detalle",
            nivel=1,
            descripcion="Mantenimiento",
            clave="mantenimiento",
            fila_origen=1,
        )
    )
    db.flush()
    return version


def _ano_con_estructura(db: Session, mundo: Mundo, etiqueta: str = "2026/27"):  # type: ignore[no-untyped-def]
    _estructura_vigente(db, mundo.hotel_a)
    return _ano(db, mundo, etiqueta)


def test_crear_ano_fiscal_y_periodo(db: Session, mundo: Mundo) -> None:
    ano = _ano(db, mundo)
    assert ano.estado == "abierto" and ano.mes_inicio == 7
    periodo = crear_periodo_fiscal(db, ano_fiscal_id=ano.id, periodo="2026-07")
    assert periodo.estado == "abierto"
    with pytest.raises(CicloInvalido):
        crear_periodo_fiscal(db, ano_fiscal_id=ano.id, periodo="2026-07")
    with pytest.raises(CicloInvalido):
        crear_periodo_fiscal(db, ano_fiscal_id=ano.id, periodo="2026-13")


def test_no_se_duplica_un_ano_fiscal(db: Session, mundo: Mundo) -> None:
    _ano(db, mundo)
    with pytest.raises(CicloInvalido):
        _ano(db, mundo)


def test_generar_periodos_fiscales_es_idempotente(db: Session, mundo: Mundo) -> None:
    ano = _ano(db, mundo)
    primero = generar_periodos_fiscales(db, ano_fiscal_id=ano.id)
    assert [p.periodo for p in primero] == [
        f"2026-{m:02d}" for m in range(7, 13)
    ] + [f"2027-{m:02d}" for m in range(1, 7)]
    segundo = generar_periodos_fiscales(db, ano_fiscal_id=ano.id)
    assert [p.id for p in primero] == [p.id for p in segundo]


def test_crear_ciclo_sin_estructura_vigente_falla(db: Session, mundo: Mundo) -> None:
    ano = _ano(db, mundo)  # sin _estructura_vigente
    with pytest.raises(CicloInvalido):
        crear_ciclo(
            db,
            organizacion_id=mundo.org1,
            hotel_id=mundo.hotel_a,
            usuario_id=None,
            ano_fiscal_id=ano.id,
        )


def test_crear_ciclo_feliz_y_rechazo_de_duplicado(db: Session, mundo: Mundo) -> None:
    ano = _ano_con_estructura(db, mundo)
    usuario = _usuario_id(db, "analista_a@test.local")
    ciclo = crear_ciclo(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=usuario,
        ano_fiscal_id=ano.id,
    )
    assert ciclo.estado == "borrador" and ciclo.numero == 1
    with pytest.raises(CicloInvalido):
        crear_ciclo(
            db,
            organizacion_id=mundo.org1,
            hotel_id=mundo.hotel_a,
            usuario_id=usuario,
            ano_fiscal_id=ano.id,
        )
    acciones = [e.accion for e in db.scalars(select(EventoAuditoria).order_by(EventoAuditoria.id))]
    assert acciones[-1] == "presupuesto.ciclo_creado"


def test_un_segundo_ciclo_se_abre_tras_bloquear_el_anterior(db: Session, mundo: Mundo) -> None:
    ano = _ano_con_estructura(db, mundo)
    usuario = _usuario_id(db, "analista_a@test.local")
    kw = {"organizacion_id": mundo.org1, "hotel_id": mundo.hotel_a, "usuario_id": usuario}
    primero = crear_ciclo(db, ano_fiscal_id=ano.id, **kw)  # type: ignore[arg-type]
    primero.estado = "bloqueado"  # fuera de alcance de 7.1: se simula el estado final de 7.4
    db.flush()
    segundo = crear_ciclo(db, ano_fiscal_id=ano.id, **kw)  # type: ignore[arg-type]
    assert segundo.numero == 2


def test_recorrido_hasta_revision_y_bitacora(db: Session, mundo: Mundo) -> None:
    ano = _ano_con_estructura(db, mundo)
    usuario = _usuario_id(db, "analista_a@test.local")
    kw = {"organizacion_id": mundo.org1, "hotel_id": mundo.hotel_a, "usuario_id": usuario}
    ciclo = crear_ciclo(db, ano_fiscal_id=ano.id, **kw)  # type: ignore[arg-type]
    ciclo = transicionar(db, ciclo_id=ciclo.id, hacia="enviado", nota=None, puede=PUEDE_TODO, **kw)  # type: ignore[arg-type]
    assert ciclo.estado == "enviado"
    ciclo = transicionar(db, ciclo_id=ciclo.id, hacia="revision", nota=None, puede=PUEDE_TODO, **kw)  # type: ignore[arg-type]
    assert ciclo.estado == "revision"
    h = historial(db, ciclo)
    assert [(t.desde, t.hacia) for t in h] == [("borrador", "enviado"), ("enviado", "revision")]
    acciones = [e.accion for e in db.scalars(select(EventoAuditoria).order_by(EventoAuditoria.id))]
    assert acciones[-2:] == ["presupuesto.enviado", "presupuesto.revision"]


@pytest.mark.parametrize("hacia", ["revision", "aprobado", "bloqueado", "inventado"])
def test_las_transiciones_invalidas_dan_409(db: Session, mundo: Mundo, hacia: str) -> None:
    ano = _ano_con_estructura(db, mundo)
    usuario = _usuario_id(db, "analista_a@test.local")
    kw = {"organizacion_id": mundo.org1, "hotel_id": mundo.hotel_a, "usuario_id": usuario}
    ciclo = crear_ciclo(db, ano_fiscal_id=ano.id, **kw)  # type: ignore[arg-type]
    with pytest.raises(CicloInvalido) as info:
        transicionar(db, ciclo_id=ciclo.id, hacia=hacia, nota=None, puede=PUEDE_TODO, **kw)  # type: ignore[arg-type]
    assert info.value.status_code == 409


def test_devolver_pide_nota(db: Session, mundo: Mundo) -> None:
    ano = _ano_con_estructura(db, mundo)
    usuario = _usuario_id(db, "analista_a@test.local")
    kw = {"organizacion_id": mundo.org1, "hotel_id": mundo.hotel_a, "usuario_id": usuario}
    ciclo = crear_ciclo(db, ano_fiscal_id=ano.id, **kw)  # type: ignore[arg-type]
    ciclo = transicionar(db, ciclo_id=ciclo.id, hacia="enviado", nota=None, puede=PUEDE_TODO, **kw)  # type: ignore[arg-type]
    with pytest.raises(CicloInvalido) as info:
        transicionar(db, ciclo_id=ciclo.id, hacia="borrador", nota=None, puede=PUEDE_TODO, **kw)  # type: ignore[arg-type]
    assert info.value.status_code == 422
    with pytest.raises(CicloInvalido):
        transicionar(db, ciclo_id=ciclo.id, hacia="borrador", nota="   ", puede=PUEDE_TODO, **kw)  # type: ignore[arg-type]
    ciclo = transicionar(
        db, ciclo_id=ciclo.id, hacia="borrador", nota="Falta un dato", puede=PUEDE_TODO, **kw  # type: ignore[arg-type]
    )
    assert ciclo.estado == "borrador"


def test_permiso_insuficiente_da_403(db: Session, mundo: Mundo) -> None:
    ano = _ano_con_estructura(db, mundo)
    usuario = _usuario_id(db, "analista_a@test.local")
    kw = {"organizacion_id": mundo.org1, "hotel_id": mundo.hotel_a, "usuario_id": usuario}
    ciclo = crear_ciclo(db, ano_fiscal_id=ano.id, **kw)  # type: ignore[arg-type]
    with pytest.raises(CicloInvalido) as info:
        transicionar(db, ciclo_id=ciclo.id, hacia="enviado", nota=None, puede=PUEDE_NADA, **kw)  # type: ignore[arg-type]
    assert info.value.status_code == 403


def test_las_transiciones_no_se_pueden_modificar_ni_borrar(db: Session, mundo: Mundo) -> None:
    ano = _ano_con_estructura(db, mundo)
    usuario = _usuario_id(db, "analista_a@test.local")
    kw = {"organizacion_id": mundo.org1, "hotel_id": mundo.hotel_a, "usuario_id": usuario}
    ciclo = crear_ciclo(db, ano_fiscal_id=ano.id, **kw)  # type: ignore[arg-type]
    transicionar(db, ciclo_id=ciclo.id, hacia="enviado", nota=None, puede=PUEDE_TODO, **kw)  # type: ignore[arg-type]
    db.commit()
    t = db.scalars(select(CicloTransicion)).one()
    t.nota = "alterada"
    with pytest.raises(TransicionInmutable):
        db.flush()
    db.rollback()
    t = db.scalars(select(CicloTransicion)).one()
    db.delete(t)
    with pytest.raises(TransicionInmutable):
        db.flush()
    db.rollback()
