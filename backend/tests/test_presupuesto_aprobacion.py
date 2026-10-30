"""Fase 7.4: aprobación y bloqueo del ciclo de presupuesto — genera y reemplaza la VersionPlan."""

from decimal import Decimal

import pytest
from conftest import Mundo
from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.identidad.permisos import Permiso
from fpa.modelos import LineaReporte, Usuario, VersionEstructuraReporte
from fpa.modelos.plan import REEMPLAZADA, VIGENTE, LineaPlan, LineaPlanMensual, VersionPlan
from fpa.modelos.presupuesto import CicloPresupuesto, LineaPresupuestoCaptura
from fpa.servicios.presupuesto_captura import capturar_propuesta
from fpa.servicios.presupuesto_ciclo import (
    CicloInvalido,
    crear_ano_fiscal,
    crear_ciclo,
    crear_periodo_fiscal,
    transicionar,
)
from fpa.servicios.presupuesto_distribucion import (
    NOMBRE_UNIFORME,
    prorratear_con_perfil,
    sembrar_perfiles_sistema,
)

D = Decimal
PUEDE_TODO = dict.fromkeys(Permiso, True)


def _usuario_id(db: Session, email: str) -> int:
    return db.scalars(select(Usuario.id).where(Usuario.email == email)).one()


def _doce_periodos() -> list[str]:
    return [f"2026-{m:02d}" for m in range(7, 13)] + [f"2027-{m:02d}" for m in range(1, 7)]


def _linea_detalle(db: Session, hotel_id: int, descripcion: str = "Mantenimiento") -> LineaReporte:
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
    linea = LineaReporte(
        version_id=version.id,
        hotel_id=hotel_id,
        orden=1,
        tipo="detalle",
        nivel=1,
        descripcion=descripcion,
        clave=descripcion.lower(),
        fila_origen=1,
    )
    db.add(linea)
    db.flush()
    return linea


def _ciclo_listo(db: Session, mundo: Mundo) -> tuple[CicloPresupuesto, LineaReporte]:
    """Un ciclo con una línea de detalle y su calendario fiscal completo, en `borrador`."""
    linea = _linea_detalle(db, mundo.hotel_a)
    ano = crear_ano_fiscal(db, hotel_id=mundo.hotel_a, etiqueta="2026/27", mes_inicio=7, mes_fin=6)
    for periodo in _doce_periodos():
        crear_periodo_fiscal(db, ano_fiscal_id=ano.id, periodo=periodo)
    ciclo = crear_ciclo(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        ano_fiscal_id=ano.id,
    )
    return ciclo, linea


def _captura_de(db: Session, ciclo_id: int, linea_id: int) -> LineaPresupuestoCaptura:
    return db.scalars(
        select(LineaPresupuestoCaptura).where(
            LineaPresupuestoCaptura.ciclo_id == ciclo_id,
            LineaPresupuestoCaptura.linea_id == linea_id,
        )
    ).one()


def _kw(mundo: Mundo) -> dict[str, int | None]:
    return {"organizacion_id": mundo.org1, "hotel_id": mundo.hotel_a, "usuario_id": None}


def _avanzar_a_revision(db: Session, mundo: Mundo, ciclo_id: int) -> None:
    usuario = _usuario_id(db, "analista_a@test.local")
    kw = {
        "organizacion_id": mundo.org1,
        "hotel_id": mundo.hotel_a,
        "usuario_id": usuario,
        "puede": PUEDE_TODO,
    }
    transicionar(db, ciclo_id=ciclo_id, hacia="enviado", nota=None, **kw)  # type: ignore[arg-type]
    transicionar(db, ciclo_id=ciclo_id, hacia="revision", nota=None, **kw)  # type: ignore[arg-type]


def test_aprobar_genera_version_plan_mensualizada(db: Session, mundo: Mundo) -> None:
    ciclo, linea = _ciclo_listo(db, mundo)
    captura = _captura_de(db, ciclo.id, linea.id)
    db.commit()
    capturar_propuesta(
        db,
        ciclo_id=ciclo.id,
        linea_id=linea.id,
        propuesta_anual=D("1200000.00"),
        nota=None,
        visibles=None,
        **_kw(mundo),  # type: ignore[arg-type]
    )
    perfiles = sembrar_perfiles_sistema(db)
    db.commit()
    prorratear_con_perfil(
        db,
        linea_captura_id=captura.id,
        perfil_distribucion_id=perfiles[NOMBRE_UNIFORME].id,
        **_kw(mundo),  # type: ignore[arg-type]
    )
    db.commit()
    _avanzar_a_revision(db, mundo, ciclo.id)
    db.commit()
    usuario = _usuario_id(db, "contralor_ab@test.local")
    ciclo_aprobado = transicionar(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=usuario,
        puede=PUEDE_TODO,
        ciclo_id=ciclo.id,
        hacia="aprobado",
        nota=None,
    )
    assert ciclo_aprobado.estado == "aprobado"
    assert ciclo_aprobado.version_plan_resultante_id is not None
    assert ciclo_aprobado.aprobado_en is not None
    version = db.get(VersionPlan, ciclo_aprobado.version_plan_resultante_id)
    assert version is not None and version.estado == VIGENTE and version.ano_fiscal == "2026/27"
    lp = db.scalars(select(LineaPlan).where(LineaPlan.version_plan_id == version.id)).one()
    assert lp.anual == D("1200000.000000")
    mensuales = list(
        db.scalars(select(LineaPlanMensual).where(LineaPlanMensual.version_plan_id == version.id))
    )
    assert len(mensuales) == 12
    assert sum((m.importe for m in mensuales), D(0)) == D("1200000.00")


def test_aprobar_sin_mensualizar_falla(db: Session, mundo: Mundo) -> None:
    ciclo, linea = _ciclo_listo(db, mundo)
    db.commit()
    capturar_propuesta(
        db,
        ciclo_id=ciclo.id,
        linea_id=linea.id,
        propuesta_anual=D("1000.00"),
        nota=None,
        visibles=None,
        **_kw(mundo),  # type: ignore[arg-type]
    )
    db.commit()
    _avanzar_a_revision(db, mundo, ciclo.id)
    db.commit()
    with pytest.raises(CicloInvalido):
        transicionar(
            db,
            organizacion_id=mundo.org1,
            hotel_id=mundo.hotel_a,
            usuario_id=_usuario_id(db, "contralor_ab@test.local"),
            puede=PUEDE_TODO,
            ciclo_id=ciclo.id,
            hacia="aprobado",
            nota=None,
        )


def test_aprobar_sin_nada_capturado_falla(db: Session, mundo: Mundo) -> None:
    ciclo, _linea = _ciclo_listo(db, mundo)
    db.commit()
    _avanzar_a_revision(db, mundo, ciclo.id)
    db.commit()
    with pytest.raises(CicloInvalido):
        transicionar(
            db,
            organizacion_id=mundo.org1,
            hotel_id=mundo.hotel_a,
            usuario_id=_usuario_id(db, "contralor_ab@test.local"),
            puede=PUEDE_TODO,
            ciclo_id=ciclo.id,
            hacia="aprobado",
            nota=None,
        )


def _aprobar(db: Session, mundo: Mundo, ciclo_id: int) -> CicloPresupuesto:
    return transicionar(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=_usuario_id(db, "contralor_ab@test.local"),
        puede=PUEDE_TODO,
        ciclo_id=ciclo_id,
        hacia="aprobado",
        nota=None,
    )


def test_bloquear_tras_aprobar(db: Session, mundo: Mundo) -> None:
    ciclo, linea = _ciclo_listo(db, mundo)
    captura = _captura_de(db, ciclo.id, linea.id)
    db.commit()
    capturar_propuesta(
        db,
        ciclo_id=ciclo.id,
        linea_id=linea.id,
        propuesta_anual=D("100.00"),
        nota=None,
        visibles=None,
        **_kw(mundo),  # type: ignore[arg-type]
    )
    perfiles = sembrar_perfiles_sistema(db)
    db.commit()
    prorratear_con_perfil(
        db,
        linea_captura_id=captura.id,
        perfil_distribucion_id=perfiles[NOMBRE_UNIFORME].id,
        **_kw(mundo),  # type: ignore[arg-type]
    )
    db.commit()
    _avanzar_a_revision(db, mundo, ciclo.id)
    db.commit()
    _aprobar(db, mundo, ciclo.id)
    db.commit()
    bloqueado = transicionar(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=_usuario_id(db, "contralor_ab@test.local"),
        puede=PUEDE_TODO,
        ciclo_id=ciclo.id,
        hacia="bloqueado",
        nota=None,
    )
    assert bloqueado.estado == "bloqueado"


def test_reabrir_pide_nota_y_no_toca_la_version_anterior(db: Session, mundo: Mundo) -> None:
    ciclo, linea = _ciclo_listo(db, mundo)
    captura = _captura_de(db, ciclo.id, linea.id)
    db.commit()
    capturar_propuesta(
        db,
        ciclo_id=ciclo.id,
        linea_id=linea.id,
        propuesta_anual=D("100.00"),
        nota=None,
        visibles=None,
        **_kw(mundo),  # type: ignore[arg-type]
    )
    perfiles = sembrar_perfiles_sistema(db)
    db.commit()
    prorratear_con_perfil(
        db,
        linea_captura_id=captura.id,
        perfil_distribucion_id=perfiles[NOMBRE_UNIFORME].id,
        **_kw(mundo),  # type: ignore[arg-type]
    )
    db.commit()
    _avanzar_a_revision(db, mundo, ciclo.id)
    db.commit()
    aprobado = _aprobar(db, mundo, ciclo.id)
    db.commit()
    version_id = aprobado.version_plan_resultante_id
    usuario = _usuario_id(db, "contralor_ab@test.local")
    with pytest.raises(CicloInvalido):
        transicionar(
            db,
            organizacion_id=mundo.org1,
            hotel_id=mundo.hotel_a,
            usuario_id=usuario,
            puede=PUEDE_TODO,
            ciclo_id=ciclo.id,
            hacia="borrador",
            nota=None,
        )
    reabierto = transicionar(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=usuario,
        puede=PUEDE_TODO,
        ciclo_id=ciclo.id,
        hacia="borrador",
        nota="Ajuste pendiente",
    )
    assert reabierto.estado == "borrador"
    version = db.get(VersionPlan, version_id)
    assert version is not None and version.estado == VIGENTE  # no se toca al reabrir


def test_segunda_aprobacion_reemplaza_la_anterior(db: Session, mundo: Mundo) -> None:
    ciclo, linea = _ciclo_listo(db, mundo)
    captura = _captura_de(db, ciclo.id, linea.id)
    db.commit()
    perfiles = sembrar_perfiles_sistema(db)
    db.commit()
    capturar_propuesta(
        db,
        ciclo_id=ciclo.id,
        linea_id=linea.id,
        propuesta_anual=D("100.00"),
        nota=None,
        visibles=None,
        **_kw(mundo),  # type: ignore[arg-type]
    )
    prorratear_con_perfil(
        db,
        linea_captura_id=captura.id,
        perfil_distribucion_id=perfiles[NOMBRE_UNIFORME].id,
        **_kw(mundo),  # type: ignore[arg-type]
    )
    db.commit()
    _avanzar_a_revision(db, mundo, ciclo.id)
    db.commit()
    primera = _aprobar(db, mundo, ciclo.id)
    db.commit()
    primera_version_id = primera.version_plan_resultante_id

    usuario = _usuario_id(db, "contralor_ab@test.local")
    transicionar(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=usuario,
        puede=PUEDE_TODO,
        ciclo_id=ciclo.id,
        hacia="borrador",
        nota="Corrección",
    )
    db.commit()
    capturar_propuesta(
        db,
        ciclo_id=ciclo.id,
        linea_id=linea.id,
        propuesta_anual=D("200.00"),
        nota=None,
        visibles=None,
        **_kw(mundo),  # type: ignore[arg-type]
    )
    prorratear_con_perfil(
        db,
        linea_captura_id=captura.id,
        perfil_distribucion_id=perfiles[NOMBRE_UNIFORME].id,
        **_kw(mundo),  # type: ignore[arg-type]
    )
    db.commit()
    _avanzar_a_revision(db, mundo, ciclo.id)
    db.commit()
    segunda = _aprobar(db, mundo, ciclo.id)
    db.commit()

    primera_version = db.get(VersionPlan, primera_version_id)
    segunda_version = db.get(VersionPlan, segunda.version_plan_resultante_id)
    assert primera_version is not None and primera_version.estado == REEMPLAZADA
    assert segunda_version is not None and segunda_version.estado == VIGENTE
    assert segunda_version.numero == primera_version.numero + 1
    # La versión reemplazada conserva sus cifras originales (criterio de aceptación 3 de Fase 7).
    lp_primera = db.scalars(
        select(LineaPlan).where(LineaPlan.version_plan_id == primera_version.id)
    ).one()
    assert lp_primera.anual == D("100.000000")
