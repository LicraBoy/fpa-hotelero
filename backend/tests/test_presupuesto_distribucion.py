"""Fase 7.3: perfiles de distribución y prorrateo mensual del Budget."""

from decimal import Decimal

import pytest
from conftest import Mundo
from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.modelos import EventoAuditoria, LineaReporte, VersionEstructuraReporte
from fpa.modelos.presupuesto import (
    LineaPresupuestoCaptura,
    LineaPresupuestoMensual,
    PerfilDistribucion,
)
from fpa.servicios.presupuesto_ciclo import crear_ano_fiscal, crear_ciclo, crear_periodo_fiscal
from fpa.servicios.presupuesto_distribucion import (
    NOMBRE_UNIFORME,
    DistribucionInvalida,
    crear_perfil,
    fijar_importes_mensuales,
    prorratear_con_perfil,
    repartir,
    sembrar_perfiles_sistema,
    validar_pesos,
)

D = Decimal
MICRO = D("0.000001")


def _doce_periodos(ano_etiqueta: str = "2026/27") -> list[str]:
    return [f"2026-{m:02d}" for m in range(7, 13)] + [f"2027-{m:02d}" for m in range(1, 7)]


def _ano_con_doce_periodos(db: Session, hotel_id: int, etiqueta: str = "2026/27"):  # type: ignore[no-untyped-def]
    ano = crear_ano_fiscal(db, hotel_id=hotel_id, etiqueta=etiqueta, mes_inicio=7, mes_fin=6)
    for periodo in _doce_periodos(etiqueta):
        crear_periodo_fiscal(db, ano_fiscal_id=ano.id, periodo=periodo)
    return ano


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


def _captura(db: Session, mundo: Mundo, propuesta_anual: Decimal) -> LineaPresupuestoCaptura:
    # La estructura debe existir ANTES del ciclo: crear_ciclo (7.1/7.2) congela la estructura
    # vigente y precarga una LineaPresupuestoCaptura por línea de detalle.
    linea = _linea_detalle(db, mundo.hotel_a)
    ano = _ano_con_doce_periodos(db, mundo.hotel_a)
    ciclo = crear_ciclo(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        ano_fiscal_id=ano.id,
    )
    captura = db.scalars(
        select(LineaPresupuestoCaptura).where(
            LineaPresupuestoCaptura.ciclo_id == ciclo.id,
            LineaPresupuestoCaptura.linea_id == linea.id,
        )
    ).one()
    captura.propuesta_anual = propuesta_anual
    captura.estado = "capturada"
    db.flush()
    return captura


# --- validar_pesos --------------------------------------------------------------------------------


def test_validar_pesos_rechaza_longitud_incorrecta() -> None:
    with pytest.raises(DistribucionInvalida):
        validar_pesos([D("1")] * 11)


def test_validar_pesos_rechaza_fuera_de_rango() -> None:
    pesos = [D("1.5")] + [D("0")] * 10 + [D("-0.5")]
    with pytest.raises(DistribucionInvalida):
        validar_pesos(pesos)


def test_validar_pesos_rechaza_suma_incorrecta() -> None:
    with pytest.raises(DistribucionInvalida):
        validar_pesos([D("0.1")] * 12)


def test_validar_pesos_acepta_suma_exacta() -> None:
    validar_pesos([D("0.083333")] * 11 + [D("0.083337")])


# --- sembrar_perfiles_sistema


def test_sembrar_perfiles_sistema_es_idempotente_y_suma_exacta(db: Session) -> None:
    primero = sembrar_perfiles_sistema(db)
    db.commit()
    segundo = sembrar_perfiles_sistema(db)
    assert primero[NOMBRE_UNIFORME].id == segundo[NOMBRE_UNIFORME].id
    assert db.scalar(select(PerfilDistribucion)) is not None
    total = sum((D(p) for p in primero[NOMBRE_UNIFORME].pesos), D(0))
    assert total.quantize(MICRO) == D("1.000000")
    assert len(list(db.scalars(select(PerfilDistribucion)))) == 1


# --- repartir


def test_repartir_uniforme_no_divisible_cuadra_exacto() -> None:
    pesos = [D("0.083333")] * 11 + [D("0.083337")]
    importes = repartir(D("100.00"), pesos)
    assert len(importes) == 12
    assert sum(importes, D(0)) == D("100.00")


def test_repartir_ejemplo_mantenimiento_del_diseno() -> None:
    # Jul..Dic: ene=5%, mar=5%, abr=8%, dic=82%, el resto en cero (orden fiscal: jul,ago,...,jun)
    pesos = [D(0)] * 12
    pesos[6] = D("0.05")  # enero (7º mes del año fiscal que empieza en julio)
    pesos[8] = D("0.05")  # marzo
    pesos[9] = D("0.08")  # abril
    pesos[5] = D("0.82")  # diciembre
    importes = repartir(D("1200000.00"), pesos)
    assert sum(importes, D(0)) == D("1200000.00")
    for i, peso in enumerate(pesos):
        if peso == 0:
            assert importes[i] == D("0.000000") or importes[i] == D(0)
    assert importes[5] == D("984000.000000")


def test_repartir_ajusta_residuo_de_redondeo() -> None:
    # Pesos repetitivos sobre un monto no redondo: el producto de cada mes tiene más de 6
    # decimales y el redondeo individual deja un residuo frente al anual que hay que absorber.
    pesos = [D("0.333333"), D("0.333333"), D("0.333334")] + [D(0)] * 9
    importes = repartir(D("10.01"), pesos)
    assert sum(importes, D(0)) == D("10.01")
    # El residuo se absorbe en el último mes con peso distinto de cero (índice 2), no en los ceros.
    assert all(importes[i] == D(0) for i in range(3, 12))


def test_repartir_rechaza_longitud_incorrecta() -> None:
    with pytest.raises(DistribucionInvalida):
        repartir(D("10.00"), [D("1")] * 3)


# --- prorratear_con_perfil


def test_prorratear_con_perfil_crea_doce_lineas_que_reconcilian(db: Session, mundo: Mundo) -> None:
    captura = _captura(db, mundo, D("1200000.00"))
    perfiles = sembrar_perfiles_sistema(db)
    db.commit()
    filas = prorratear_con_perfil(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        linea_captura_id=captura.id,
        perfil_distribucion_id=perfiles[NOMBRE_UNIFORME].id,
    )
    assert len(filas) == 12
    assert sum((f.importe for f in filas), D(0)) == D("1200000.00")
    assert captura.perfil_distribucion_id == perfiles[NOMBRE_UNIFORME].id
    acciones = [e.accion for e in db.scalars(select(EventoAuditoria).order_by(EventoAuditoria.id))]
    assert acciones[-1] == "presupuesto.linea_prorrateada"


def test_prorratear_reemplaza_filas_previas_sin_duplicar(db: Session, mundo: Mundo) -> None:
    captura = _captura(db, mundo, D("360000.00"))
    perfiles = sembrar_perfiles_sistema(db)
    otro = crear_perfil(
        db,
        hotel_id=mundo.hotel_a,
        nombre="A la mitad del año",
        pesos=[D(0)] * 5 + [D("1.000000")] + [D(0)] * 6,
    )
    db.commit()
    kw = {"organizacion_id": mundo.org1, "hotel_id": mundo.hotel_a, "usuario_id": None}
    prorratear_con_perfil(
        db, linea_captura_id=captura.id, perfil_distribucion_id=perfiles[NOMBRE_UNIFORME].id, **kw
    )
    prorratear_con_perfil(db, linea_captura_id=captura.id, perfil_distribucion_id=otro.id, **kw)
    filas = list(
        db.scalars(
            select(LineaPresupuestoMensual).where(
                LineaPresupuestoMensual.linea_captura_id == captura.id
            )
        )
    )
    assert len(filas) == 12
    assert sum((f.importe for f in filas), D(0)) == D("360000.00")


def test_prorratear_sin_propuesta_anual_falla(db: Session, mundo: Mundo) -> None:
    captura = _captura(db, mundo, D("0"))
    captura.propuesta_anual = None
    db.flush()
    perfiles = sembrar_perfiles_sistema(db)
    db.commit()
    with pytest.raises(DistribucionInvalida):
        prorratear_con_perfil(
            db,
            organizacion_id=mundo.org1,
            hotel_id=mundo.hotel_a,
            usuario_id=None,
            linea_captura_id=captura.id,
            perfil_distribucion_id=perfiles[NOMBRE_UNIFORME].id,
        )


def test_prorratear_sin_doce_periodos_falla(db: Session, mundo: Mundo) -> None:
    linea = _linea_detalle(db, mundo.hotel_a)
    ano = crear_ano_fiscal(db, hotel_id=mundo.hotel_a, etiqueta="2026/27", mes_inicio=7, mes_fin=6)
    crear_periodo_fiscal(db, ano_fiscal_id=ano.id, periodo="2026-07")  # solo uno, no doce
    ciclo = crear_ciclo(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        ano_fiscal_id=ano.id,
    )
    captura = db.scalars(
        select(LineaPresupuestoCaptura).where(
            LineaPresupuestoCaptura.ciclo_id == ciclo.id,
            LineaPresupuestoCaptura.linea_id == linea.id,
        )
    ).one()
    captura.propuesta_anual = D("1200.00")
    db.flush()
    perfiles = sembrar_perfiles_sistema(db)
    db.commit()
    with pytest.raises(DistribucionInvalida):
        prorratear_con_perfil(
            db,
            organizacion_id=mundo.org1,
            hotel_id=mundo.hotel_a,
            usuario_id=None,
            linea_captura_id=captura.id,
            perfil_distribucion_id=perfiles[NOMBRE_UNIFORME].id,
        )


def test_perfil_de_otro_hotel_no_se_puede_usar(db: Session, mundo: Mundo) -> None:
    captura = _captura(db, mundo, D("1200.00"))
    perfil_b = crear_perfil(
        db, hotel_id=mundo.hotel_b, nombre="Solo de B", pesos=[D("0.083333")] * 11 + [D("0.083337")]
    )
    db.commit()
    with pytest.raises(LookupError):
        prorratear_con_perfil(
            db,
            organizacion_id=mundo.org1,
            hotel_id=mundo.hotel_a,
            usuario_id=None,
            linea_captura_id=captura.id,
            perfil_distribucion_id=perfil_b.id,
        )


# --- fijar_importes_mensuales


def test_fijar_importes_mensuales_feliz_limpia_perfil(db: Session, mundo: Mundo) -> None:
    captura = _captura(db, mundo, D("120.00"))
    db.commit()
    periodos = _doce_periodos()
    importes = {p: D("10.00") for p in periodos}
    filas = fijar_importes_mensuales(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        linea_captura_id=captura.id,
        importes=importes,
    )
    assert len(filas) == 12
    assert captura.perfil_distribucion_id is None
    acciones = [e.accion for e in db.scalars(select(EventoAuditoria).order_by(EventoAuditoria.id))]
    assert acciones[-1] == "presupuesto.linea_mensualizada_manual"


def test_fijar_importes_mensuales_rechaza_suma_incorrecta(db: Session, mundo: Mundo) -> None:
    captura = _captura(db, mundo, D("120.00"))
    db.commit()
    importes = {p: D("10.00") for p in _doce_periodos()}
    importes[_doce_periodos()[0]] = D("11.00")  # ya no cuadra con 120.00
    with pytest.raises(DistribucionInvalida):
        fijar_importes_mensuales(
            db,
            organizacion_id=mundo.org1,
            hotel_id=mundo.hotel_a,
            usuario_id=None,
            linea_captura_id=captura.id,
            importes=importes,
        )


def test_fijar_importes_mensuales_rechaza_periodo_faltante(db: Session, mundo: Mundo) -> None:
    captura = _captura(db, mundo, D("110.00"))
    db.commit()
    importes = {p: D("10.00") for p in _doce_periodos()[:11]}  # falta uno
    with pytest.raises(DistribucionInvalida):
        fijar_importes_mensuales(
            db,
            organizacion_id=mundo.org1,
            hotel_id=mundo.hotel_a,
            usuario_id=None,
            linea_captura_id=captura.id,
            importes=importes,
        )
