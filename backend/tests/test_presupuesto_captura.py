"""Fase 7.2/7.5: captura por área y objetivo vs. propuesta (servicio puro, sin API) del Budget."""

from decimal import Decimal

import pytest
from conftest import Mundo
from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.modelos import EventoAuditoria, LineaReporte, Usuario, VersionEstructuraReporte
from fpa.modelos.identidad import AsignacionDepartamento
from fpa.modelos.presupuesto import LineaPresupuestoCaptura, LineaPresupuestoMensual
from fpa.servicios.presupuesto_captura import (
    CapturaInvalida,
    capturar_propuesta,
    fijar_objetivo,
    resumen_ciclo,
)
from fpa.servicios.presupuesto_ciclo import crear_ano_fiscal, crear_ciclo, transicionar

D = Decimal


def _usuario_id(db: Session, email: str) -> int:
    return db.scalars(select(Usuario.id).where(Usuario.email == email)).one()


def _estructura_dos_secciones(db: Session, hotel_id: int) -> VersionEstructuraReporte:
    """Rooms (1 detalle) y Admin (2 detalle), para probar la resolución de responsable."""
    version = VersionEstructuraReporte(
        hotel_id=hotel_id,
        nombre_archivo="estructura.xlsx",
        sha256="0" * 64,
        estado="vigente",
        n_lineas=5,
        n_detalle=3,
    )
    db.add(version)
    db.flush()
    rooms = LineaReporte(
        version_id=version.id,
        hotel_id=hotel_id,
        orden=1,
        tipo="seccion",
        nivel=0,
        descripcion="Rooms",
        clave="rooms",
        fila_origen=1,
    )
    admin = LineaReporte(
        version_id=version.id,
        hotel_id=hotel_id,
        orden=2,
        tipo="seccion",
        nivel=0,
        descripcion="Admin",
        clave="admin",
        fila_origen=2,
    )
    db.add_all([rooms, admin])
    db.flush()
    detalle_rooms = LineaReporte(
        version_id=version.id,
        hotel_id=hotel_id,
        orden=3,
        tipo="detalle",
        nivel=1,
        seccion_id=rooms.id,
        descripcion="Mantenimiento de habitaciones",
        clave="mant_hab",
        fila_origen=3,
    )
    detalle_admin_1 = LineaReporte(
        version_id=version.id,
        hotel_id=hotel_id,
        orden=4,
        tipo="detalle",
        nivel=1,
        seccion_id=admin.id,
        descripcion="Papelería",
        clave="papeleria",
        fila_origen=4,
    )
    detalle_admin_2 = LineaReporte(
        version_id=version.id,
        hotel_id=hotel_id,
        orden=5,
        tipo="detalle",
        nivel=1,
        seccion_id=admin.id,
        descripcion="Software",
        clave="software",
        fila_origen=5,
    )
    db.add_all([detalle_rooms, detalle_admin_1, detalle_admin_2])
    db.flush()
    return version


def _ciclo_con_dos_secciones(db: Session, mundo: Mundo):  # type: ignore[no-untyped-def]
    _estructura_dos_secciones(db, mundo.hotel_a)
    ano = crear_ano_fiscal(db, hotel_id=mundo.hotel_a, etiqueta="2026/27", mes_inicio=7, mes_fin=6)
    return crear_ciclo(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        ano_fiscal_id=ano.id,
    )


def _captura_de(db: Session, ciclo_id: int, descripcion: str) -> LineaPresupuestoCaptura:
    linea = db.scalars(select(LineaReporte).where(LineaReporte.descripcion == descripcion)).one()
    return db.scalars(
        select(LineaPresupuestoCaptura).where(
            LineaPresupuestoCaptura.ciclo_id == ciclo_id,
            LineaPresupuestoCaptura.linea_id == linea.id,
        )
    ).one()


# --- inicializar_capturas (vía crear_ciclo)


def test_crear_ciclo_precarga_una_captura_por_linea_de_detalle(db: Session, mundo: Mundo) -> None:
    ciclo = _ciclo_con_dos_secciones(db, mundo)
    capturas = list(
        db.scalars(
            select(LineaPresupuestoCaptura).where(LineaPresupuestoCaptura.ciclo_id == ciclo.id)
        )
    )
    assert len(capturas) == 3  # las 3 líneas de detalle, ninguna de sección
    assert all(c.estado == "pendiente" and c.propuesta_anual is None for c in capturas)


def test_responsable_se_resuelve_cuando_hay_uno_solo_asignado(db: Session, mundo: Mundo) -> None:
    usuario = _usuario_id(db, "responsable_a@test.local")
    db.add(AsignacionDepartamento(usuario_id=usuario, hotel_id=mundo.hotel_a, seccion="Rooms"))
    db.flush()
    ciclo = _ciclo_con_dos_secciones(db, mundo)
    c = _captura_de(db, ciclo.id, "Mantenimiento de habitaciones")
    assert c.responsable_id == usuario


def test_responsable_queda_nulo_sin_asignacion_o_con_varias(db: Session, mundo: Mundo) -> None:
    resp_a = _usuario_id(db, "responsable_a@test.local")
    contralor = _usuario_id(db, "contralor_ab@test.local")
    db.add(AsignacionDepartamento(usuario_id=resp_a, hotel_id=mundo.hotel_a, seccion="Admin"))
    db.add(AsignacionDepartamento(usuario_id=contralor, hotel_id=mundo.hotel_a, seccion="Admin"))
    db.flush()
    ciclo = _ciclo_con_dos_secciones(db, mundo)
    rooms_sin_asignar = _captura_de(db, ciclo.id, "Mantenimiento de habitaciones")
    assert rooms_sin_asignar.responsable_id is None
    admin_con_dos = _captura_de(db, ciclo.id, "Papelería")
    assert admin_con_dos.responsable_id is None


# --- capturar_propuesta


def test_capturar_propuesta_feliz(db: Session, mundo: Mundo) -> None:
    ciclo = _ciclo_con_dos_secciones(db, mundo)
    captura = _captura_de(db, ciclo.id, "Papelería")
    db.commit()
    resultado = capturar_propuesta(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        ciclo_id=ciclo.id,
        linea_id=captura.linea_id,
        propuesta_anual=D("12000.00"),
        nota="Estimado del año pasado",
        visibles=None,
    )
    assert resultado.estado == "capturada"
    assert resultado.propuesta_anual == D("12000.00")
    acciones = [e.accion for e in db.scalars(select(EventoAuditoria).order_by(EventoAuditoria.id))]
    assert acciones[-1] == "presupuesto.linea_capturada"


def test_capturar_propuesta_fuera_de_alcance_da_lookup_error(db: Session, mundo: Mundo) -> None:
    ciclo = _ciclo_con_dos_secciones(db, mundo)
    captura = _captura_de(db, ciclo.id, "Papelería")  # de la sección Admin
    db.commit()
    with pytest.raises(LookupError):
        capturar_propuesta(
            db,
            organizacion_id=mundo.org1,
            hotel_id=mundo.hotel_a,
            usuario_id=None,
            ciclo_id=ciclo.id,
            linea_id=captura.linea_id,
            propuesta_anual=D("100.00"),
            nota=None,
            visibles={9999999},  # restringido a otra sección, esta línea no está ahí
        )


def test_capturar_propuesta_rechaza_fuera_de_borrador(db: Session, mundo: Mundo) -> None:
    ciclo = _ciclo_con_dos_secciones(db, mundo)
    captura = _captura_de(db, ciclo.id, "Papelería")
    db.commit()
    from fpa.identidad.permisos import Permiso

    transicionar(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=_usuario_id(db, "analista_a@test.local"),
        puede=dict.fromkeys(Permiso, True),
        ciclo_id=ciclo.id,
        hacia="enviado",
        nota=None,
    )
    db.commit()
    with pytest.raises(CapturaInvalida):
        capturar_propuesta(
            db,
            organizacion_id=mundo.org1,
            hotel_id=mundo.hotel_a,
            usuario_id=None,
            ciclo_id=ciclo.id,
            linea_id=captura.linea_id,
            propuesta_anual=D("100.00"),
            nota=None,
            visibles=None,
        )


def test_cambiar_propuesta_borra_la_mensualizacion_vieja(db: Session, mundo: Mundo) -> None:
    ciclo = _ciclo_con_dos_secciones(db, mundo)
    captura = _captura_de(db, ciclo.id, "Papelería")
    db.commit()
    capturar_propuesta(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        ciclo_id=ciclo.id,
        linea_id=captura.linea_id,
        propuesta_anual=D("1200.00"),
        nota=None,
        visibles=None,
    )
    db.add(
        LineaPresupuestoMensual(
            linea_captura_id=captura.id, periodo="2026-07", importe=D("1200.00")
        )
    )
    captura.perfil_distribucion_id = 1
    db.flush()
    capturar_propuesta(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        ciclo_id=ciclo.id,
        linea_id=captura.linea_id,
        propuesta_anual=D("2400.00"),
        nota=None,
        visibles=None,
    )
    assert captura.perfil_distribucion_id is None
    restantes = list(
        db.scalars(
            select(LineaPresupuestoMensual).where(
                LineaPresupuestoMensual.linea_captura_id == captura.id
            )
        )
    )
    assert restantes == []


# --- fijar_objetivo (Fase 7.5)


def test_fijar_objetivo_feliz_no_toca_estado_ni_mensualizacion(db: Session, mundo: Mundo) -> None:
    ciclo = _ciclo_con_dos_secciones(db, mundo)
    captura = _captura_de(db, ciclo.id, "Papelería")
    db.commit()
    capturar_propuesta(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        ciclo_id=ciclo.id,
        linea_id=captura.linea_id,
        propuesta_anual=D("1200.00"),
        nota=None,
        visibles=None,
    )
    estado_previo = captura.estado
    resultado = fijar_objetivo(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        ciclo_id=ciclo.id,
        linea_id=captura.linea_id,
        objetivo=D("1500.00"),
        visibles=None,
    )
    assert resultado.objetivo == D("1500.00")
    assert resultado.estado == estado_previo  # el objetivo no cambia el estado de captura
    assert resultado.propuesta_anual == D("1200.00")  # ni toca la propuesta
    acciones = [e.accion for e in db.scalars(select(EventoAuditoria).order_by(EventoAuditoria.id))]
    assert acciones[-1] == "presupuesto.linea_objetivo"


def test_fijar_objetivo_fuera_de_alcance_da_lookup_error(db: Session, mundo: Mundo) -> None:
    ciclo = _ciclo_con_dos_secciones(db, mundo)
    captura = _captura_de(db, ciclo.id, "Papelería")
    db.commit()
    with pytest.raises(LookupError):
        fijar_objetivo(
            db,
            organizacion_id=mundo.org1,
            hotel_id=mundo.hotel_a,
            usuario_id=None,
            ciclo_id=ciclo.id,
            linea_id=captura.linea_id,
            objetivo=D("100.00"),
            visibles=set(),
        )


def test_fijar_objetivo_rechaza_fuera_de_borrador(db: Session, mundo: Mundo) -> None:
    from fpa.identidad.permisos import Permiso

    ciclo = _ciclo_con_dos_secciones(db, mundo)
    captura = _captura_de(db, ciclo.id, "Papelería")
    db.commit()
    transicionar(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=_usuario_id(db, "analista_a@test.local"),
        puede=dict.fromkeys(Permiso, True),
        ciclo_id=ciclo.id,
        hacia="enviado",
        nota=None,
    )
    db.commit()
    with pytest.raises(CapturaInvalida):
        fijar_objetivo(
            db,
            organizacion_id=mundo.org1,
            hotel_id=mundo.hotel_a,
            usuario_id=None,
            ciclo_id=ciclo.id,
            linea_id=captura.linea_id,
            objetivo=D("100.00"),
            visibles=None,
        )


# --- resumen_ciclo (Fase 7.5)


def test_resumen_ciclo_cobertura_y_sumas_por_seccion(db: Session, mundo: Mundo) -> None:
    ciclo = _ciclo_con_dos_secciones(db, mundo)
    rooms = _captura_de(db, ciclo.id, "Mantenimiento de habitaciones")
    papeleria = _captura_de(db, ciclo.id, "Papelería")
    db.commit()
    kw = {"organizacion_id": mundo.org1, "hotel_id": mundo.hotel_a, "usuario_id": None}
    capturar_propuesta(
        db,
        ciclo_id=ciclo.id,
        linea_id=rooms.linea_id,
        propuesta_anual=D("1000.00"),
        nota=None,
        visibles=None,
        **kw,  # type: ignore[arg-type]
    )
    fijar_objetivo(
        db,
        ciclo_id=ciclo.id,
        linea_id=rooms.linea_id,
        objetivo=D("1100.00"),
        visibles=None,
        **kw,  # type: ignore[arg-type]
    )
    fijar_objetivo(
        db,
        ciclo_id=ciclo.id,
        linea_id=papeleria.linea_id,
        objetivo=D("500.00"),
        visibles=None,
        **kw,  # type: ignore[arg-type]
    )
    # "Software" (Admin) se queda sin capturar y sin objetivo.
    r = resumen_ciclo(db, ciclo=ciclo)
    assert r.total_lineas == 3
    assert r.lineas_capturadas == 1
    assert r.cobertura_pct == D("33.33")
    assert r.suma_objetivo == D("1600.00")
    assert r.suma_propuesta == D("1000.00")
    por_nombre = {s.seccion: s for s in r.por_seccion}
    assert por_nombre["Rooms"].total_lineas == 1
    assert por_nombre["Rooms"].cobertura_pct == D("100.00")
    assert por_nombre["Admin"].total_lineas == 2
    assert por_nombre["Admin"].lineas_capturadas == 0
    assert por_nombre["Admin"].cobertura_pct == D("0.00")
    assert por_nombre["Admin"].suma_objetivo == D("500.00")
