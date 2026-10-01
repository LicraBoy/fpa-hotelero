from decimal import Decimal

import pytest
from conftest import Mundo, como
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from test_versionado_mapeo import EJEMPLO, Escenario, _mov

from fpa.ingesta.variance_estructura import leer_variance_estructura_filas
from fpa.ingesta.variance_reglas import leer_variance_reglas_filas
from fpa.ingesta.variance_valores import ValoresFila
from fpa.servicios.budget import importar_budget
from fpa.servicios.cargas import DatosArchivo
from fpa.servicios.reglas_suma import importar_reglas_suma
from fpa.servicios.versionado_mapeo import aprobar

D = Decimal
ANALISTA = "analista_a@test.local"
CONTRALOR = "contralor_ab@test.local"
RESPONSABLE = "responsable_a@test.local"
OTRA_ORG = "contralor_c@test.local"


def _preparar(db: Session, mundo: Mundo, periodo_corte: str = "2026-08") -> Escenario:
    """Ingreso 100 (Budget 80) y Gasto 30 (Budget 40); el Total es Ingreso − Gasto."""
    esc = Escenario(db, mundo, [_mov("4001002.001", "0", "100"), _mov("6009001.001", "30", "0")])
    reglas = leer_variance_reglas_filas(EJEMPLO, leer_variance_estructura_filas(EJEMPLO))
    importar_reglas_suma(db, version=esc.estructura, leidas=reglas, **esc.kw)  # type: ignore[arg-type]
    aprobar(db, version_id=esc.borrador.id, **esc.kw)  # type: ignore[union-attr, arg-type]
    # Filas de la hoja de ejemplo: 4 = Ingreso, 5 = Gasto, 6 = Total
    valores = {
        4: ValoresFila(4, mes_budget=D("80"), ytd_budget=D("160"), anual_budget=D("960")),
        5: ValoresFila(5, mes_budget=D("40"), ytd_budget=D("80"), anual_budget=D("480")),
        6: ValoresFila(6, mes_budget=D("40"), ytd_budget=D("80"), anual_budget=D("480")),
    }
    importar_budget(
        db,
        version_estructura=esc.estructura,
        valores=valores,
        archivo=DatosArchivo(nombre="b.xlsx", sha256="b" * 64),
        periodo_corte=periodo_corte,
        ano_fiscal="2026/27",
        **esc.kw,  # type: ignore[arg-type]
    )
    db.commit()
    return esc


def _pedir(
    cliente: TestClient, mundo: Mundo, periodo: str = "2026-08", usuario: str = ANALISTA, **q
):  # type: ignore[no-untyped-def]
    params = "&".join([f"periodo={periodo}", *[f"{k}={v}" for k, v in q.items()]])
    return cliente.get(f"/api/v1/hoteles/{mundo.hotel_a}/variance?{params}", headers=como(usuario))


def test_variance_de_agosto_con_convencion_favorable_positiva(
    cliente: TestClient, mundo: Mundo, db: Session
) -> None:
    _preparar(db, mundo)
    r = _pedir(cliente, mundo)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["ano_fiscal"] == "2026/27" and cuerpo["periodos_ytd"] == ["2026-07", "2026-08"]
    # julio no tiene movimientos cargados: se informa, no se oculta
    assert cuerpo["periodos_sin_datos"] == ["2026-07"]
    assert any("incompleto" in a for a in cuerpo["advertencias"])
    por = {x["descripcion"]: x for x in cuerpo["lineas"]}
    ingreso, gasto, total = por["Ingreso"], por["Gasto"], por["Total"]
    assert ingreso["convencion"] == "real_menos_presupuesto"
    assert (ingreso["mes"]["actual"], ingreso["mes"]["budget"], ingreso["mes"]["var"]) == (
        "100.00",
        "80.00",
        "20.00",
    )
    assert ingreso["mes"]["pct"] == "0.250000"
    assert gasto["convencion"] == "presupuesto_menos_real"
    assert (gasto["mes"]["var"], gasto["mes"]["pct"]) == ("10.00", "0.250000")
    # total = Ingreso − Gasto: actual 70, budget 40 -> favorable +30
    assert (total["mes"]["actual"], total["mes"]["budget"], total["mes"]["var"]) == (
        "70.00",
        "40.00",
        "30.00",
    )
    assert total["anual"]["budget"] == "480.00" and total["anual"]["actual"] == "70.00"


def test_otro_periodo_solo_trae_el_budget_anual(
    cliente: TestClient, mundo: Mundo, db: Session
) -> None:
    _preparar(db, mundo)
    r = _pedir(cliente, mundo, periodo="2026-09")
    assert r.status_code == 200
    cuerpo = r.json()
    ingreso = next(x for x in cuerpo["lineas"] if x["descripcion"] == "Ingreso")
    assert (
        ingreso["mes"]["budget"] is None and ingreso["mes"]["var"] is None
    )  # nunca un 0 inventado
    assert ingreso["ytd"]["budget"] is None
    assert ingreso["anual"]["budget"] == "960.00" and ingreso["anual"]["var"] is not None
    assert any("solo el anual" in a for a in cuerpo["advertencias"])


def test_sin_budget_se_calcula_el_actual_y_se_avisa(
    cliente: TestClient, mundo: Mundo, db: Session
) -> None:
    esc = Escenario(db, mundo, [_mov("4001002.001", "0", "100"), _mov("6009001.001", "30", "0")])
    aprobar(db, version_id=esc.borrador.id, **esc.kw)  # type: ignore[union-attr, arg-type]
    db.commit()
    r = _pedir(cliente, mundo)
    assert r.status_code == 200
    ingreso = next(x for x in r.json()["lineas"] if x["descripcion"] == "Ingreso")
    assert ingreso["mes"]["actual"] == "100.00" and ingreso["mes"]["budget"] is None
    assert any("No hay Budget" in a for a in r.json()["advertencias"])


def test_errores(cliente: TestClient, mundo: Mundo, db: Session) -> None:
    assert _pedir(cliente, mundo).status_code == 404  # sin mapeo aprobado
    _preparar(db, mundo)
    assert _pedir(cliente, mundo, periodo="2026-13").status_code == 422
    assert _pedir(cliente, mundo, version_plan_id=999).status_code == 404
    assert _pedir(cliente, mundo, version_mapeo_id=999).status_code == 404


def test_permisos_y_aislamiento(cliente: TestClient, mundo: Mundo, db: Session) -> None:
    _preparar(db, mundo)
    assert _pedir(cliente, mundo, usuario=CONTRALOR).status_code == 200
    assert _pedir(cliente, mundo, usuario=RESPONSABLE).status_code == 403
    assert _pedir(cliente, mundo, usuario=OTRA_ORG).status_code == 404
    sin_sesion = cliente.get(f"/api/v1/hoteles/{mundo.hotel_a}/variance?periodo=2026-08")
    assert sin_sesion.status_code == 401
    # el hotel B (donde el contralor también tiene acceso) no tiene mapeo: nada del A se filtra
    ajeno = cliente.get(
        f"/api/v1/hoteles/{mundo.hotel_b}/variance?periodo=2026-08", headers=como(CONTRALOR)
    )
    assert ajeno.status_code == 404


@pytest.mark.parametrize("usuario", [ANALISTA, CONTRALOR])
def test_el_resultado_es_deterministico(
    cliente: TestClient, mundo: Mundo, db: Session, usuario: str
) -> None:
    _preparar(db, mundo)
    assert _pedir(cliente, mundo, usuario=usuario).json() == _pedir(cliente, mundo).json()


# --- Filtros y secciones (4.1) ------------------------------------------------------------------


def _descripciones(r) -> list[str]:  # type: ignore[no-untyped-def]
    return [x["descripcion"] for x in r.json()["lineas"]]


def test_filtros_por_tipo_texto_y_seccion(cliente: TestClient, mundo: Mundo, db: Session) -> None:
    _preparar(db, mundo)
    base = f"/api/v1/hoteles/{mundo.hotel_a}/variance?periodo=2026-08"
    h = como(ANALISTA)
    todas = cliente.get(base, headers=h).json()
    assert [x["descripcion"] for x in todas["lineas"]] == ["Ingreso", "Gasto", "Total"]
    solo_totales = cliente.get(f"{base}&tipo=total", headers=h)
    assert _descripciones(solo_totales) == ["Total"]
    detalle_y_total = cliente.get(f"{base}&tipo=total&tipo=detalle", headers=h)
    assert _descripciones(detalle_y_total) == ["Ingreso", "Gasto", "Total"]
    assert _descripciones(cliente.get(f"{base}&q=ING", headers=h)) == ["Ingreso"]  # sin mayúsculas
    assert _descripciones(cliente.get(f"{base}&q=zzz", headers=h)) == []
    # El reporte de ejemplo no tiene secciones: ninguna línea pertenece a una sección inexistente
    assert todas["secciones"] == []
    assert _descripciones(cliente.get(f"{base}&seccion_id=999", headers=h)) == []


def test_filtros_invalidos_son_422(cliente: TestClient, mundo: Mundo, db: Session) -> None:
    _preparar(db, mundo)
    base = f"/api/v1/hoteles/{mundo.hotel_a}/variance?periodo=2026-08"
    h = como(ANALISTA)
    assert cliente.get(f"{base}&tipo=inventado", headers=h).status_code == 422
    assert cliente.get(f"{base}&q={'x' * 101}", headers=h).status_code == 422
    assert cliente.get(f"{base}&seccion_id=abc", headers=h).status_code == 422


def test_la_exclusion_a_proposito_se_advierte(
    cliente: TestClient, mundo: Mundo, db: Session
) -> None:
    from fpa.servicios.versionado_mapeo import excluir_cuenta

    esc = Escenario(db, mundo, [_mov("4001002.001", "0", "100"), _mov("4999999", "0", "5")])
    excluir_cuenta(
        db,
        version_id=esc.borrador.id,  # type: ignore[union-attr]
        cuenta_codigo="4999999",
        motivo="Prueba",
        **esc.kw,  # type: ignore[arg-type]
    )
    aprobar(db, version_id=esc.borrador.id, **esc.kw)  # type: ignore[union-attr, arg-type]
    db.commit()
    r = _pedir(cliente, mundo)
    assert any("4999999" in a and "a propósito" in a for a in r.json()["advertencias"])


def test_secciones_con_su_total() -> None:
    from types import SimpleNamespace as L

    from fpa.servicios.variance import secciones_del_reporte

    lineas = [
        L(id=1, tipo="seccion", descripcion="Ingresos", seccion_id=None),
        L(id=2, tipo="detalle", descripcion="a", seccion_id=1),
        L(id=3, tipo="total", descripcion="Total Ingresos", seccion_id=1),
        L(id=4, tipo="seccion", descripcion="Sin total", seccion_id=None),
        L(id=5, tipo="detalle", descripcion="b", seccion_id=4),
        L(id=6, tipo="seccion", descripcion="Solo subtotal", seccion_id=None),
        L(id=7, tipo="subtotal", descripcion="s", seccion_id=6),
    ]
    r = secciones_del_reporte(lineas)  # type: ignore[arg-type]
    assert [(s.id, s.linea_total_id) for s in r] == [(1, 3), (4, None), (6, 7)]


def test_ids_y_periodos_fuera_de_rango_son_422_no_500(
    cliente: TestClient, mundo: Mundo, db: Session
) -> None:
    _preparar(db, mundo)
    base = f"/api/v1/hoteles/{mundo.hotel_a}/variance"
    h = como(ANALISTA)
    assert cliente.get(f"{base}?periodo=1999-12", headers=h).status_code == 422
    assert cliente.get(f"{base}?periodo=2100-01", headers=h).status_code == 422
    assert (
        cliente.get(
            f"{base}?periodo=2026-08&version_mapeo_id=9223372036854775808", headers=h
        ).status_code
        == 422
    )
    assert cliente.get(f"{base}?periodo=2026-08&version_plan_id=0", headers=h).status_code == 422
    assert (
        cliente.get(
            "/api/v1/hoteles/9223372036854775808/variance?periodo=2026-08", headers=h
        ).status_code
        == 422
    )
    assert (
        cliente.get(
            f"/api/v1/hoteles/{mundo.hotel_a}/mapeo/versiones/9223372036854775808", headers=h
        ).status_code
        == 422
    )
