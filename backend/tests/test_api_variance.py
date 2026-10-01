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
