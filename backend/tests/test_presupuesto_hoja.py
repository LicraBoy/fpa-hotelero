"""Budget por cuenta, parte 1b: hoja completa de una sección (bloque inferior de Other Income)."""

from decimal import Decimal

from conftest import Mundo, como
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from test_budget_other_income import ANALISTA as ANALISTA_OI
from test_budget_other_income import (
    CONTRALOR,
    PERIODOS,
    XLSX,
    _ciclo,
    _url,
)

from fpa.ingesta.budget_other_income import leer_other_income_filas
from fpa.servicios.presupuesto_hoja import calcular_bloque

D = Decimal
ANALISTA = ANALISTA_OI


def test_bloque_inferior_como_el_excel() -> None:
    # Cifras del Excel de Contraloría (Other Income, filas 36 a 41), tres primeros meses
    totales = [D("113285.396"), D("77707.7434"), D("94680.8098")]
    est_act = [D("153889.01"), D("119354.649"), D("316839.55")]
    previo = [D("106297.3698"), D("99124.227"), D("85544.853")]
    b = calcular_bloque(totales * 4, [None] * 12, est_act * 4, previo * 4)
    assert b.total_con_inflacion[:3] == totales  # sin inflación, el total no cambia
    assert b.variacion[0] == D("47591.6402")  # Est Act − Budget previo
    assert b.variacion_pct[0] == D("0.447722")  # 44.77 %
    assert b.variacion_pct[2] == D("2.703783")  # 270 %


def test_la_inflacion_es_informativa_y_la_acumulada_es_suma_simple() -> None:
    infl = [D("0.01"), D("0.02"), D("0.03")] + [D(0)] * 9
    b = calcular_bloque([D(1000)] * 12, infl, [None] * 12, [None] * 12)
    assert b.acumulada[:4] == [
        D("0.01"),
        D("0.03"),
        D("0.06"),
        D("0.06"),
    ]  # SUM(M33:N33), no compuesta
    assert b.total_con_inflacion[:3] == [D("1010"), D("1020"), D("1030")]
    assert b.variacion == [None] * 12 and b.variacion_pct == [None] * 12


def test_presupuesto_previo_en_cero_no_da_porcentaje() -> None:
    b = calcular_bloque([D(1)] * 12, [None] * 12, [D(5)] * 12, [D(0)] * 12)
    assert b.variacion[0] == D(5) and b.variacion_pct[0] is None


def test_el_lector_trae_inflacion_est_act_y_budget_previo() -> None:
    def fila(etiqueta: str, valores: list[object]) -> tuple[object, ...]:
        return (None,) * 9 + (etiqueta,) + (None, None) + tuple(valores)

    encabezado = (
        (None, "Item")
        + (None,) * 10
        + ("Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun")
    )
    cuenta = (None, "Rental Income") + (None,) * 10 + (100,) * 12
    filas = [
        encabezado,
        cuenta,
        (None, "Total Expense"),
        fila("Mthly", [0.05] + [0] * 11),
        fila("Cum", [0.05] * 12),
        fila("Est Act 26-27", [200] * 12),
        fila("Budget 26-27", [150] * 12),
    ]
    leido = leer_other_income_filas(filas, filas, lambda h, c: 0)
    assert leido.inflacion is not None and leido.inflacion[0] == D("0.05")
    assert leido.est_act == [D(200)] * 12
    assert leido.budget_previo == [D(150)] * 12


def _importar(cliente: TestClient, ciclo_id: int) -> dict[str, object]:
    from io import BytesIO

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Other Income"
    meses = ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    ws.append([None, "Item"] + [None] * 10 + meses)
    ws.append([None, "Rental Income"] + [None] * 10 + [1000.0] * 12)
    ws.append([None, "Laundry Coins"] + [None] * 10 + [200.0] * 12)
    ws.append([None, "Venados"] + [None] * 10 + [300.0] * 12)
    ws.append([None, "Total Expense"])
    ws.append([None] * 9 + ["Mthly"] + [None, None] + [0.01] * 12)
    ws.append([None] * 9 + ["Est Act 26-27"] + [None, None] + [2000.0] * 12)
    ws.append([None] * 9 + ["Budget 26-27"] + [None, None] + [1500.0] * 12)
    salida = BytesIO()
    wb.save(salida)
    return cliente.post(
        _url_ciclo(ciclo_id, "detalle/importar-other-income"),
        files={"archivo": ("b.xlsx", salida.getvalue(), XLSX)},
        headers=como(CONTRALOR),
    ).json()


def _url_ciclo(ciclo_id: int, ruta: str) -> str:
    return f"/api/v1/hoteles/1/presupuesto/ciclos/{ciclo_id}/{ruta}"


def test_hoja_completa_por_api(cliente: TestClient, db: Session, mundo: Mundo) -> None:
    ciclo_id, ids = _ciclo(db, mundo)
    assert mundo.hotel_a == 1
    cuerpo = _importar(cliente, ciclo_id)
    assert cuerpo["importadas"] == 3
    seccion_id = _seccion_de(db, ids["Rental Income"])

    r = cliente.get(_url(mundo, ciclo_id, f"hojas/{seccion_id}"), headers=como(CONTRALOR))
    assert r.status_code == 200, r.text
    h = r.json()
    assert h["seccion"] == "Other Income" and h["periodos"] == PERIODOS
    assert [c["descripcion"] for c in h["cuentas"]] == [
        "Rental Income",
        "Laundry Coins",
        "Venados",
    ]
    assert [D(x) for x in h["totales"]] == [D(1500)] * 12
    assert D(h["inflacion"][0]) == D("0.01") and D(h["acumulada"][1]) == D("0.02")
    assert D(h["total_con_inflacion"][0]) == D("1515")
    assert D(h["est_act"][0]) == D(2000) and D(h["variacion"][0]) == D(500)
    assert D(h["variacion_pct"][0]) == D("0.333333") and h["origen"] == "excel"


def _seccion_de(db: Session, linea_id: int) -> int:
    from fpa.modelos import LineaReporte

    seccion = db.get(LineaReporte, linea_id)
    assert seccion is not None and seccion.seccion_id is not None
    return seccion.seccion_id


def test_la_inflacion_se_guarda_completa_y_no_cambia_el_budget(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    ciclo_id, ids = _ciclo(db, mundo)
    _importar(cliente, ciclo_id)
    seccion_id = _seccion_de(db, ids["Rental Income"])
    antes = cliente.get(
        _url(mundo, ciclo_id, f"hojas/{seccion_id}"), headers=como(CONTRALOR)
    ).json()
    r = cliente.put(
        _url(mundo, ciclo_id, f"hojas/{seccion_id}/inflacion"),
        json={"inflacion": dict.fromkeys(PERIODOS, "0.05")},
        headers=como(CONTRALOR),
    )
    assert r.status_code == 200, r.text
    h = r.json()
    assert D(h["total_con_inflacion"][0]) == D("1575")
    assert h["totales"] == antes["totales"]  # el Budget de las cuentas no se movió


def test_inflacion_incompleta_o_fuera_de_rango_es_422(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    ciclo_id, ids = _ciclo(db, mundo)
    seccion_id = _seccion_de(db, ids["Rental Income"])
    url = _url(mundo, ciclo_id, f"hojas/{seccion_id}/inflacion")
    r = cliente.put(
        url, json={"inflacion": dict.fromkeys(PERIODOS[:11], "0.05")}, headers=como(CONTRALOR)
    )
    assert r.status_code == 422
    r = cliente.put(url, json={"inflacion": dict.fromkeys(PERIODOS, "2")}, headers=como(CONTRALOR))
    assert r.status_code == 422


def test_el_analista_lee_la_hoja_pero_no_guarda_inflacion(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    ciclo_id, ids = _ciclo(db, mundo)
    seccion_id = _seccion_de(db, ids["Rental Income"])
    assert (
        cliente.get(
            _url(mundo, ciclo_id, f"hojas/{seccion_id}"), headers=como(ANALISTA)
        ).status_code
        == 200
    )
    r = cliente.put(
        _url(mundo, ciclo_id, f"hojas/{seccion_id}/inflacion"),
        json={"inflacion": dict.fromkeys(PERIODOS, "0.05")},
        headers=como(ANALISTA),
    )
    assert r.status_code == 403


def test_una_seccion_que_no_existe_es_404(cliente: TestClient, db: Session, mundo: Mundo) -> None:
    ciclo_id, _ = _ciclo(db, mundo)
    r = cliente.get(_url(mundo, ciclo_id, "hojas/99999"), headers=como(CONTRALOR))
    assert r.status_code == 404
