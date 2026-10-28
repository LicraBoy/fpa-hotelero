"""Budget por cuenta: importar una sección sin hoja propia (*Mgmt & Check In*) desde el Excel del Budget."""

from decimal import Decimal
from io import BytesIO
from pathlib import Path

import pytest
from conftest import Mundo, como
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy.orm import Session
from test_budget_other_income import CONTRALOR, PERIODOS, XLSX, _url

from fpa.ingesta.budget_seccion import leer_seccion, leer_seccion_filas
from fpa.modelos import LineaReporte, VersionEstructuraReporte
from fpa.servicios.presupuesto_ciclo import crear_ano_fiscal, crear_ciclo, crear_periodo_fiscal

D = Decimal
SECCION = "mgmtcheckin"
NOMBRE = "Mgmt & Check In"
EXCEL_REAL = Path(__file__).resolve().parents[2] / "docs" / "-1% - MZT Budget 26-27 TC 18.00 Final.xlsx"


def _fila(codigo: object, descripcion: object, meses: list[object] | None = None) -> tuple[object, ...]:
    return (None, codigo, descripcion, *(meses or []))


def _hoja_budget() -> list[tuple[object, ...]]:
    return [
        _fila("Account #", "Account Description"),
        _fila("M g m t   &   C h e c k   I n", None),
        _fila("028-0111-60010-000", "Salaries", ["#REF!"] * 12),
        _fila("028-0111-61560-000", "Telephone", [4515.0] * 12),
        _fila("028-0111-61610-000", "Airfare", [0.0] + [100.0] * 11),
        _fila("028-0111-61630-000", "T & E Local", [13671.0] * 12),
        _fila("028-0111-60310-000", "Bank Commissions", [1653.75] * 12),
        _fila("028-0111-60130-000", "Dues, Subscriptions, etc.", [50.0] * 12),
        _fila(None, "T o t a l   E x p e n s e s", ["#REF!"] * 12),
        _fila("028-0111-61715-000", "A l l o c a t e d   E x p e n s e s", ["#REF!"] * 12),
        _fila(None, "T o t a l   M g m t   &   C h e c k   I n", ["#REF!"] * 12),
        _fila("A c c o u n t i n g", None),
    ]


def _hoja_previa(base: float) -> list[tuple[object, ...]]:
    return [
        _fila("M g m t   &   C h e c k   I n", None),
        _fila("028-0111-60010-000", "Salaries", [base] * 12),
        _fila(None, "T o t a l   M g m t   &   C h e c k   I n", [base * 2] * 12),
    ]


def test_el_lector_toma_las_cuentas_con_importes_y_avisa_las_que_traen_ref() -> None:
    leido = leer_seccion_filas(_hoja_budget(), _hoja_previa(10.0), _hoja_previa(7.0), SECCION, NOMBRE)
    assert [f.concepto for f in leido.filas] == [
        "Telephone", "Airfare", "T & E Local", "Bank Commissions", "Dues, Subscriptions, etc."
    ]  # fmt: skip
    assert all(c.metodo == "fijo" for f in leido.filas for c in f.celdas)
    assert leido.filas[1].celdas[0].importe == D(0)  # un cero real se importa como cero
    assert leido.filas[1].celdas[1].importe == D(100)
    # Salaries y Allocated Expenses traen #REF!: no se importan, se avisan
    resumen = next(a for a in leido.avisos if "#REF!" in a)
    assert "2 cuentas" in resumen and "«Salaries»" in resumen and "«Allocated Expenses»" in resumen
    # el bloque inferior sale del renglón «Total …» de las hojas del año previo
    assert leido.est_act == [D(20)] * 12 and leido.budget_previo == [D(14)] * 12


def test_sin_la_seccion_se_rechaza_y_sin_hojas_previas_no_hay_referencias() -> None:
    with pytest.raises(ValueError, match="no trae la sección"):
        leer_seccion_filas([_fila("Otra cosa", None)], None, None, SECCION, NOMBRE)
    leido = leer_seccion_filas(_hoja_budget(), None, None, SECCION, NOMBRE)
    assert leido.est_act is None and leido.budget_previo is None


def test_la_referencia_con_ref_no_se_guarda_y_se_avisa() -> None:
    mala = [
        _fila("M g m t   &   C h e c k   I n", None),
        _fila(None, "T o t a l   M g m t   &   C h e c k   I n", ["#REF!"] * 12),
    ]
    leido = leer_seccion_filas(_hoja_budget(), mala, None, SECCION, NOMBRE)
    assert leido.est_act is None and any("Est-Act" in a for a in leido.avisos)


# --- Importación al ciclo por la API ----------------------------------------------------------


def _estructura_mgmt(db: Session, hotel_id: int) -> dict[str, int]:
    version = VersionEstructuraReporte(
        hotel_id=hotel_id, nombre_archivo="e.xlsx", sha256="1" * 64, estado="vigente", n_lineas=7, n_detalle=6
    )
    db.add(version)
    db.flush()
    seccion = LineaReporte(
        version_id=version.id, hotel_id=hotel_id, orden=1, tipo="seccion", nivel=0,
        descripcion=NOMBRE, clave="mgmt", fila_origen=10,
    )  # fmt: skip
    db.add(seccion)
    db.flush()
    ids = {"seccion": seccion.id}
    nombres = [
        "Telephone",
        "Airfare",
        "Bank Commissions",  # mismo nombre que en el Excel: se alinea por nombre exacto
        "Local Consumes",  # en el Excel se llama «T & E Local» (alias de la versión anterior del reporte)
        "Life Insurance",  # NO debe recibir «Insurance»
        "Salaries",
    ]
    for orden, nombre in enumerate(nombres, start=2):
        linea = LineaReporte(
            version_id=version.id, hotel_id=hotel_id, orden=orden, tipo="detalle", nivel=1,
            seccion_id=seccion.id, descripcion=nombre, clave=nombre.lower(), fila_origen=10 + orden,
        )  # fmt: skip
        db.add(linea)
        db.flush()
        ids[nombre] = linea.id
    db.commit()
    return ids


def _ciclo(db: Session, mundo: Mundo) -> tuple[int, dict[str, int]]:
    ids = _estructura_mgmt(db, mundo.hotel_a)
    ano = crear_ano_fiscal(db, hotel_id=mundo.hotel_a, etiqueta="2026/27", mes_inicio=7, mes_fin=6)
    for periodo in PERIODOS:
        crear_periodo_fiscal(db, ano_fiscal_id=ano.id, periodo=periodo)
    ciclo = crear_ciclo(
        db, organizacion_id=mundo.org1, hotel_id=mundo.hotel_a, usuario_id=None, ano_fiscal_id=ano.id
    )
    db.commit()
    return ciclo.id, ids


def _libro() -> bytes:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Budget 26-27 MZT"
    for fila in _hoja_budget():
        ws.append(list(fila))
    for titulo, base in (("EstAct 25-26 MZT", 10.0), ("MZT Budget 25-26", 7.0)):
        hoja = wb.create_sheet(titulo)
        for fila in _hoja_previa(base):
            hoja.append(list(fila))
    salida = BytesIO()
    wb.save(salida)
    return salida.getvalue()


def test_importa_mgmt_por_alias_y_no_confunde_lineas(cliente: TestClient, db: Session, mundo: Mundo) -> None:
    ciclo_id, ids = _ciclo(db, mundo)
    r = cliente.post(
        _url(mundo, ciclo_id, f"detalle/importar-other-income?seccion_id={ids['seccion']}"),
        files={"archivo": ("budget.xlsx", _libro(), XLSX)},
        headers=como(CONTRALOR),
    )
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    # Telephone, Airfare, Bank Commissions y T & E Local (→ Local Consumes) se importan; «Dues» no
    # tiene línea en este reporte
    assert cuerpo["importadas"] == 4
    assert any("Dues" in a and "no tiene línea" in a for a in cuerpo["avisos"])
    assert any("«Life Insurance»" in a and "quedan para captura" in a for a in cuerpo["avisos"])
    # «Salaries» ya se avisó por traer #REF!: no se repite como «no venía en el archivo»
    assert sum("«Salaries»" in a for a in cuerpo["avisos"]) == 1
    celdas = cliente.get(
        _url(mundo, ciclo_id, f"lineas/{ids['Local Consumes']}/detalle"), headers=como(CONTRALOR)
    ).json()
    assert D(celdas[0]["monto_fijo"]) == D(13671) and celdas[0]["metodo"] == "fijo"
    vacio = cliente.get(
        _url(mundo, ciclo_id, f"lineas/{ids['Life Insurance']}/detalle"), headers=como(CONTRALOR)
    ).json()
    assert vacio == []
    hoja = cliente.get(_url(mundo, ciclo_id, f"hojas/{ids['seccion']}"), headers=como(CONTRALOR)).json()
    assert hoja["seccion"] == NOMBRE and D(hoja["est_act"][0]) == D(20) and D(hoja["budget_previo"][0]) == D(14)


def test_una_seccion_que_no_se_importa_se_rechaza(cliente: TestClient, db: Session, mundo: Mundo) -> None:
    ciclo_id, ids = _ciclo(db, mundo)
    seccion = db.get(LineaReporte, ids["seccion"])
    assert seccion is not None
    seccion.descripcion = "Accounting"
    db.commit()
    r = cliente.post(
        _url(mundo, ciclo_id, f"detalle/importar-other-income?seccion_id={ids['seccion']}"),
        files={"archivo": ("budget.xlsx", _libro(), XLSX)},
        headers=como(CONTRALOR),
    )
    assert r.status_code == 422, r.text


@pytest.mark.skipif(not EXCEL_REAL.exists(), reason="no está el Excel real del Budget en docs/")
def test_el_excel_real_trae_las_cuentas_de_gasto_y_avisa_la_nomina() -> None:
    leido = leer_seccion(EXCEL_REAL, SECCION, NOMBRE)
    nombres = {f.concepto for f in leido.filas}
    assert {"Telephone", "Training", "Other Fringe", "Non-Deductible"} <= nombres
    assert "Salaries" not in nombres and any("Salaries" in a for a in leido.avisos)
    assert leido.est_act is not None and leido.budget_previo is not None
    assert all(len(f.celdas) == 12 for f in leido.filas)
