"""Omitir cuentas a propósito: versión nueva del mapeo (la aprobada no se edita)."""

from decimal import Decimal

import pytest
from conftest import Mundo
from sqlalchemy import text
from sqlalchemy.orm import Session
from test_versionado_mapeo import Escenario, _mov

from fpa.modelos.saldos import SaldoMensualCuenta
from fpa.repositorios.mapeo import RepositorioMapeo
from fpa.servicios.omitir_cuentas import MOTIVO_NO_SE_OCUPAN, omitir_cuentas
from fpa.servicios.variance import calcular_variance
from fpa.servicios.versionado_mapeo import AprobacionBloqueada, aprobar, excluir_cuenta

D = Decimal


def _aprobado(db: Session, mundo: Mundo, extra: list[tuple[str, str, str]]) -> Escenario:
    """Mapeo aprobado de 2 cuentas; `extra` son cuentas con movimiento sin línea (ya excluidas)."""
    movs = [_mov("4001002.001", "0", "100"), _mov("6009001.001", "30", "0")]
    movs += [_mov(c, d, k) for c, d, k in extra]
    esc = Escenario(db, mundo, movs)
    for codigo, _, _ in extra:
        excluir_cuenta(
            db,
            version_id=esc.borrador.id,  # type: ignore[union-attr]
            cuenta_codigo=codigo,
            motivo="Provisional: pendiente de Contraloría",
            **esc.kw,  # type: ignore[arg-type]
        )
    aprobar(db, version_id=esc.borrador.id, **esc.kw)  # type: ignore[union-attr, arg-type]
    db.commit()
    return esc


def test_omite_la_cuenta_en_una_version_nueva_y_deja_la_anterior_intacta(
    db: Session, mundo: Mundo
) -> None:
    _aprobado(db, mundo, [("4003001.010", "0", "5")])
    # una cuenta nueva con movimiento y sin línea llega después (no se podría aprobar sin omitirla)
    repo = RepositorioMapeo(db, mundo.hotel_a)
    v1 = repo.aprobada()
    assert v1 is not None

    carga_id = db.execute(text("select id from carga_archivo")).scalar_one()
    db.add(
        SaldoMensualCuenta(
            hotel_id=mundo.hotel_a,
            periodo="2026-08",
            cuenta_codigo="6009020",
            suma_debito=D("68.94"),
            suma_credito=D("0"),
            n_movimientos=1,
            carga_id=carga_id,
        )
    )
    db.commit()

    r = omitir_cuentas(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        editor_id=None,
        aprobador_id=None,
        cuentas=["6009020"],
    )
    db.commit()
    assert r.version_numero == v1.numero + 1 and r.omitidas == ["4003001.010", "6009020"]
    nueva = repo.aprobada()
    assert nueva is not None and nueva.id != v1.id
    motivos = {e.cuenta_codigo: e.motivo for e in repo.excluidas(nueva.id)}
    assert motivos == {"4003001.010": MOTIVO_NO_SE_OCUPAN, "6009020": MOTIVO_NO_SE_OCUPAN}
    # la versión anterior quedó reemplazada y con su motivo original
    db.refresh(v1)
    assert v1.estado == "reemplazada"
    assert {e.motivo for e in repo.excluidas(v1.id)} == {"Provisional: pendiente de Contraloría"}


def test_es_idempotente(db: Session, mundo: Mundo) -> None:
    _aprobado(db, mundo, [("4003001.010", "0", "5")])
    kw = {
        "organizacion_id": mundo.org1,
        "hotel_id": mundo.hotel_a,
        "editor_id": None,
        "aprobador_id": None,
    }
    primera = omitir_cuentas(db, cuentas=["4003001.010"], **kw)  # type: ignore[arg-type]
    db.commit()
    assert primera.version_numero is not None  # cambió el motivo provisional por el definitivo
    segunda = omitir_cuentas(db, cuentas=["4003001.010"], **kw)  # type: ignore[arg-type]
    assert segunda.version_numero is None and segunda.ya_estaban == ["4003001.010"]
    assert len(RepositorioMapeo(db, mundo.hotel_a).versiones()) == 2


def test_sin_mapeo_aprobado_se_avisa(db: Session, mundo: Mundo) -> None:
    with pytest.raises(LookupError):
        omitir_cuentas(
            db,
            organizacion_id=mundo.org1,
            hotel_id=mundo.hotel_a,
            editor_id=None,
            aprobador_id=None,
            cuentas=["6009020"],
        )


def test_otra_cuenta_sin_linea_bloquea_la_aprobacion(db: Session, mundo: Mundo) -> None:

    _aprobado(db, mundo, [])
    carga_id = db.execute(text("select id from carga_archivo")).scalar_one()
    for codigo in ("6009020", "6006012.001"):
        db.add(
            SaldoMensualCuenta(
                hotel_id=mundo.hotel_a,
                periodo="2026-08",
                cuenta_codigo=codigo,
                suma_debito=D("10"),
                suma_credito=D("0"),
                n_movimientos=1,
                carga_id=carga_id,
            )
        )
    db.commit()
    with pytest.raises(AprobacionBloqueada):  # solo se omitió una de las dos
        omitir_cuentas(
            db,
            organizacion_id=mundo.org1,
            hotel_id=mundo.hotel_a,
            editor_id=None,
            aprobador_id=None,
            cuentas=["6009020"],
        )


def test_las_omitidas_se_avisan_en_el_variance(db: Session, mundo: Mundo) -> None:
    _aprobado(db, mundo, [("4003001.010", "0", "5")])
    omitir_cuentas(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        editor_id=None,
        aprobador_id=None,
        cuentas=["4003001.010"],
    )
    db.commit()
    r = calcular_variance(db, hotel_id=mundo.hotel_a, periodo="2026-08")
    assert any("4003001.010" in a and "a propósito" in a for a in r.advertencias)
    assert not any("no están en ninguna línea" in a for a in r.advertencias)
