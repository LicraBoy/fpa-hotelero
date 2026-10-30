"""Budget por cuenta, parte 1: tabla interna de una línea (base × factor / monto fijo)."""

from decimal import Decimal

import pytest
from conftest import Mundo
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_presupuesto_aprobacion import (
    PUEDE_TODO,
    _avanzar_a_revision,
    _captura_de,
    _ciclo_listo,
    _doce_periodos,
    _kw,
    _usuario_id,
)

from fpa.modelos.presupuesto import (
    DetalleLineaPresupuesto,
    LineaPlanDetalle,
    LineaPresupuestoMensual,
)
from fpa.servicios.presupuesto_captura import capturar_propuesta
from fpa.servicios.presupuesto_ciclo import transicionar
from fpa.servicios.presupuesto_detalle import (
    CeldaDetalle,
    DetalleInvalido,
    calcular_importe,
    guardar_detalle,
    leer_detalle,
    leer_detalle_de_version,
)

D = Decimal


def _celdas(base: str = "1000", factor: str = "1.05") -> list[CeldaDetalle]:
    return [
        CeldaDetalle(periodo=p, metodo="factor", base=D(base), factor=D(factor))
        for p in _doce_periodos()
    ]


def test_calcular_importe_factor_y_fijo() -> None:
    assert calcular_importe(
        CeldaDetalle("2026-07", "factor", base=D("28634.109"), factor=D("1.17"))
    ) == D("33501.907530")
    assert calcular_importe(CeldaDetalle("2026-07", "fijo", monto_fijo=D("10000"))) == D("10000")


@pytest.mark.parametrize(
    "celda",
    [
        CeldaDetalle("2026-07", "fijo"),
        CeldaDetalle("2026-07", "factor", base=D("1")),
        CeldaDetalle("2026-07", "factor", factor=D("1.05")),
        CeldaDetalle("2026-07", "otro", base=D("1"), factor=D("1")),
    ],
)
def test_calcular_importe_rechaza_datos_incompletos(celda: CeldaDetalle) -> None:
    with pytest.raises(DetalleInvalido) as e:
        calcular_importe(celda)
    assert e.value.status_code == 422


def test_guardar_detalle_mensualiza_y_fija_la_propuesta(db: Session, mundo: Mundo) -> None:
    ciclo, linea = _ciclo_listo(db, mundo)
    db.commit()
    filas = guardar_detalle(
        db,
        ciclo_id=ciclo.id,
        linea_id=linea.id,
        celdas=_celdas(),
        visibles=None,
        **_kw(mundo),  # type: ignore[arg-type]
    )
    db.commit()
    assert [f.periodo for f in filas] == _doce_periodos()
    assert all(f.importe == D("1050.000000") for f in filas)
    captura = _captura_de(db, ciclo.id, linea.id)
    assert captura.propuesta_anual == D("12600.000000")
    assert captura.estado == "capturada"
    mensual = db.scalars(
        select(LineaPresupuestoMensual).where(
            LineaPresupuestoMensual.linea_captura_id == captura.id
        )
    ).all()
    assert len(mensual) == 12 and sum(m.importe for m in mensual) == D("12600.000000")


def test_guardar_detalle_reemplaza_completo(db: Session, mundo: Mundo) -> None:
    ciclo, linea = _ciclo_listo(db, mundo)
    db.commit()
    kw = _kw(mundo)
    guardar_detalle(db, ciclo_id=ciclo.id, linea_id=linea.id, celdas=_celdas(), visibles=None, **kw)  # type: ignore[arg-type]
    segundas = [CeldaDetalle(p, "fijo", monto_fijo=D("10")) for p in _doce_periodos()]
    guardar_detalle(db, ciclo_id=ciclo.id, linea_id=linea.id, celdas=segundas, visibles=None, **kw)  # type: ignore[arg-type]
    db.commit()
    filas = leer_detalle(
        db, hotel_id=mundo.hotel_a, ciclo_id=ciclo.id, linea_id=linea.id, visibles=None
    )
    assert len(filas) == 12 and {f.metodo for f in filas} == {"fijo"}
    assert _captura_de(db, ciclo.id, linea.id).propuesta_anual == D("120.000000")


def test_guardar_detalle_exige_los_doce_periodos(db: Session, mundo: Mundo) -> None:
    ciclo, linea = _ciclo_listo(db, mundo)
    db.commit()
    with pytest.raises(DetalleInvalido) as e:
        guardar_detalle(
            db,
            ciclo_id=ciclo.id,
            linea_id=linea.id,
            celdas=_celdas()[:11],
            visibles=None,
            **_kw(mundo),  # type: ignore[arg-type]
        )
    assert e.value.status_code == 422


def test_guardar_detalle_fuera_de_captura_es_409(db: Session, mundo: Mundo) -> None:
    ciclo, linea = _ciclo_listo(db, mundo)
    db.commit()
    guardar_detalle(
        db, ciclo_id=ciclo.id, linea_id=linea.id, celdas=_celdas(), visibles=None, **_kw(mundo)
    )  # type: ignore[arg-type]
    db.commit()
    _avanzar_a_revision(db, mundo, ciclo.id)
    db.commit()
    with pytest.raises(DetalleInvalido) as e:
        guardar_detalle(
            db,
            ciclo_id=ciclo.id,
            linea_id=linea.id,
            celdas=_celdas(),
            visibles=None,
            **_kw(mundo),  # type: ignore[arg-type]
        )
    assert e.value.status_code == 409


def test_linea_fuera_de_alcance_es_404(db: Session, mundo: Mundo) -> None:
    ciclo, linea = _ciclo_listo(db, mundo)
    db.commit()
    with pytest.raises(LookupError):
        guardar_detalle(
            db,
            ciclo_id=ciclo.id,
            linea_id=linea.id,
            celdas=_celdas(),
            visibles=set(),
            **_kw(mundo),  # type: ignore[arg-type]
        )


def test_capturar_otra_propuesta_borra_el_detalle(db: Session, mundo: Mundo) -> None:
    ciclo, linea = _ciclo_listo(db, mundo)
    db.commit()
    kw = _kw(mundo)
    guardar_detalle(db, ciclo_id=ciclo.id, linea_id=linea.id, celdas=_celdas(), visibles=None, **kw)  # type: ignore[arg-type]
    db.commit()
    capturar_propuesta(
        db,
        ciclo_id=ciclo.id,
        linea_id=linea.id,
        propuesta_anual=D("500"),
        nota=None,
        visibles=None,
        **kw,  # type: ignore[arg-type]
    )
    db.commit()
    assert not leer_detalle(
        db, hotel_id=mundo.hotel_a, ciclo_id=ciclo.id, linea_id=linea.id, visibles=None
    )


def test_aprobar_congela_el_detalle_en_la_version(db: Session, mundo: Mundo) -> None:
    ciclo, linea = _ciclo_listo(db, mundo)
    db.commit()
    guardar_detalle(
        db, ciclo_id=ciclo.id, linea_id=linea.id, celdas=_celdas(), visibles=None, **_kw(mundo)
    )  # type: ignore[arg-type]
    db.commit()
    _avanzar_a_revision(db, mundo, ciclo.id)
    db.commit()
    aprobado = transicionar(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=_usuario_id(db, "contralor_ab@test.local"),
        puede=PUEDE_TODO,
        ciclo_id=ciclo.id,
        hacia="aprobado",
        nota=None,
    )
    db.commit()
    assert aprobado.version_plan_resultante_id is not None
    congelado = leer_detalle_de_version(
        db,
        hotel_id=mundo.hotel_a,
        version_plan_id=aprobado.version_plan_resultante_id,
        linea_id=linea.id,
    )
    assert len(congelado) == 12 and all(f.importe == D("1050.000000") for f in congelado)

    # Reabrir y volver a editar el ciclo no altera lo que sustentó la versión ya emitida.
    transicionar(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=_usuario_id(db, "contralor_ab@test.local"),
        puede=PUEDE_TODO,
        ciclo_id=ciclo.id,
        hacia="borrador",
        nota="ajuste",
    )
    db.commit()
    guardar_detalle(
        db,
        ciclo_id=ciclo.id,
        linea_id=linea.id,
        celdas=[CeldaDetalle(p, "fijo", monto_fijo=D("1")) for p in _doce_periodos()],
        visibles=None,
        **_kw(mundo),  # type: ignore[arg-type]
    )
    db.commit()
    otra_vez = db.scalars(
        select(LineaPlanDetalle).where(
            LineaPlanDetalle.version_plan_id == aprobado.version_plan_resultante_id
        )
    ).all()
    assert len(otra_vez) == 12 and all(f.importe == D("1050.000000") for f in otra_vez)
    assert db.scalars(select(DetalleLineaPresupuesto)).all()


def test_detalle_de_version_ajena_es_404(db: Session, mundo: Mundo) -> None:
    with pytest.raises(LookupError):
        leer_detalle_de_version(db, hotel_id=mundo.hotel_a, version_plan_id=99999, linea_id=1)
