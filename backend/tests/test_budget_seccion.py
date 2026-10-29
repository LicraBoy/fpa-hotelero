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
from fpa.servicios.presupuesto_detalle import ESTRICTAS, _linea_de_hoja
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
    seccion.descripcion = "Utilities"
    db.commit()
    r = cliente.post(
        _url(mundo, ciclo_id, f"detalle/importar-other-income?seccion_id={ids['seccion']}"),
        files={"archivo": ("budget.xlsx", _libro(), XLSX)},
        headers=como(CONTRALOR),
    )
    assert r.status_code == 422, r.text


# --- Accounting (depto 0115) --------------------------------------------------------------------


def _hoja_accounting() -> list[tuple[object, ...]]:
    return [
        _fila("A c c o u n t i n g", None),
        _fila("028-0115-60010-000", "Salaries", [None] * 12),
        _fila("028-0115-60455-000", "Contract Serv Other", [100.0] * 12),
        _fila("028-0115-60455-000", "Computer Services", [None] * 12),
        _fila("028-0115-61790-000", "Non Deductable", [5.0] * 12),
        _fila(None, "T o t a l   E x p e n s e s", ["#REF!"] * 12),
        _fila("028-0115-61715-000", "A l l o c a t e d   E x p e n s e s", [None] * 12),
        _fila(None, "T o t a l   A c c o u n t i n g", ["#REF!"] * 12),
    ]


def _linea(codigo: str, descripcion: str) -> LineaReporte:
    return LineaReporte(
        version_id=1, hotel_id=1, orden=1, tipo="detalle", nivel=1,
        descripcion=descripcion, clave=descripcion.lower(), fila_origen=1, codigo_corporativo=codigo,
    )  # fmt: skip


def test_accounting_se_lee_hasta_su_total_y_allocated_queda_para_captura() -> None:
    leido = leer_seccion_filas(_hoja_accounting(), None, None, "accounting", "Accounting")
    assert [f.concepto for f in leido.filas] == ["Contract Serv Other", "Non Deductable"]
    assert "«Allocated Expenses»" in next(a for a in leido.avisos if "captura" in a)


def test_las_hojas_de_accounting_emparejan_por_alias_y_no_por_codigo_solo() -> None:
    lineas = [
        _linea("028-0115-60455-000", "Contract Serv Other"),
        _linea("028-0115-60455-000", "Computer Services"),
        _linea("028-0115-61790-000", "Non-Deductible"),
    ]
    alias = ESTRICTAS["accounting"]
    # «Contrac Serv Other» (la hoja) no es «Computer Services», aunque compartan la cuenta 60455
    assert _linea_de_hoja(lineas, "0115", "60455", "Contrac Serv Other", alias) is lineas[0]
    assert _linea_de_hoja(lineas, "0115", "61790", "Non Deductable", alias) is lineas[2]
    # el alias no le quita a una hoja su propia línea: en Mgmt «T & E Local» (alias → «Local Consumes»)
    # sigue emparejando con la línea «T & E Local» cuando el reporte la llama así
    mgmt = [_linea("028-0111-61630-000", "Meals & Entertain"), _linea("028-0111-61630-000", "T & E Local")]
    assert _linea_de_hoja(mgmt, "0111", "61630", "T & E Local", ESTRICTAS["mgmtcheckin"]) is mgmt[1]
    consumes = [_linea("028-0111-61630-000", "Local Consumes")]
    assert _linea_de_hoja(consumes, "0111", "61630", "T & E Local", ESTRICTAS["mgmtcheckin"]) is consumes[0]
    # sin alias no se unen: no se adivina por parecido
    assert _linea_de_hoja(lineas, "0115", "61790", "Non Deductable") is None


@pytest.mark.skipif(not EXCEL_REAL.exists(), reason="no está el Excel real del Budget en docs/")
def test_el_excel_real_trae_las_cuentas_de_gasto_y_avisa_la_nomina() -> None:
    leido = leer_seccion(EXCEL_REAL, SECCION, NOMBRE)
    nombres = {f.concepto for f in leido.filas}
    assert {"Telephone", "Training", "Other Fringe", "Non-Deductible"} <= nombres
    assert "Salaries" not in nombres and any("Salaries" in a for a in leido.avisos)
    assert leido.est_act is not None and leido.budget_previo is not None
    assert all(len(f.celdas) == 12 for f in leido.filas)


# --- Maid & Linen (depto 0114) ------------------------------------------------------------------


def test_las_hojas_y_filas_de_maid_linen_emparejan_por_alias() -> None:
    alias = ESTRICTAS["maidlinen"]
    lineas = [_linea("028-0114-61790-000", "Non-Deductible"), _linea("028-0114-61365-000", "Linens-Replacement")]
    assert _linea_de_hoja(lineas, "0114", "61790", "Non Deductable", alias) is lineas[0]
    assert _linea_de_hoja(lineas, "0114", "61365", "Linens-Replacement", alias) is lineas[1]
    # la nómina del Excel en plural se alinea con el reporte solo por alias confirmado
    assert {alias[k] for k in ("compensations", "incentives", "mealallowances", "miscellaneousexp")} == {
        "compensation", "incentive", "mealallowance", "miscellaneous"
    }  # fmt: skip


# --- Apartment Interior (depto 0118): líneas «PH» -----------------------------------------------


def test_las_hojas_sin_ph_no_caen_en_la_linea_ph() -> None:
    alias = ESTRICTAS["apartmentinterior"]
    lineas = [
        _linea("028-0118-61410-000", "Equipment/Supplies"),
        _linea("028-0118-61410-000", "Equip/Supplies PH"),
        _linea("028-0118-61360-000", "Kit Items-Rplcmnt"),
        _linea("028-0118-61360-000", "Kit Items-Rplcmnt PH"),
    ]
    assert _linea_de_hoja(lineas, "0118", "61410", "Equip-Supplies", alias) is lineas[0]
    assert _linea_de_hoja(lineas, "0118", "61410", "Equip-Supplies PH", alias) is lineas[1]
    assert _linea_de_hoja(lineas, "0118", "61360", "Kit Items-Rplcmnt", alias) is lineas[2]
    assert _linea_de_hoja(lineas, "0118", "61360", "Kit Item-Rplcm PH", alias) is lineas[3]
    # una hoja sin PH no se une por prefijo a una línea que solo existe con PH
    solo_ph = [_linea("028-0118-61480-000", "Materials/Supplies PH")]
    assert _linea_de_hoja(solo_ph, "0118", "61480", "Materials-Supplies", alias) is None


def test_la_fila_de_totales_mezclada_con_la_ultima_partida_no_se_importa() -> None:
    from fpa.ingesta.budget_partidas import leer_hoja_partidas

    def fila(*celdas: object) -> tuple[object, ...]:
        return (None, *celdas)

    filas = [
        (),
        fila("Item", None, "Qty of Items", "Unit of Measure", "Cost", "Extended Cost", "Monthly"),
        fila("TOASTERS", None, 2, "PIECE", 100, 200, "X", None, None, None, None, *([200 / 12] * 12)),
        fila("SPECIAL PACKAGING", None, 1, "PIECE", 10220, 200, "Total Distribution"),
        (),
        (None, None, None, None, None, None, None, None, None, "Mthly", *([0.05] * 12)),
    ]
    h = leer_hoja_partidas("0118-61360 Kit Items-Rplcmnt", filas)
    assert [p.concepto for p in h.partidas] == ["TOASTERS"] and h.total_expense == D(200)
    assert any("SPECIAL PACKAGING" in a and "mezclada" in a for a in h.avisos)


# --- Common Area (depto 0106): alias de nómina -----------------------------------------------------


def test_common_area_alias_de_nomina() -> None:
    alias = ESTRICTAS["commonarea"]
    assert alias["savingsbonus"] == "savingsfund" and alias["mealallowances"] == "mealallowance"


def test_owner_activities_alias_de_nomina() -> None:
    assert ESTRICTAS["owneractivities"] == {"compensations": "compensation"}


# --- Other Taxes, Fees and Insurance (depto 0000): total «Total Other Taxes» y guardia ----------


def test_other_taxes_acepta_el_cierre_total_other_taxes_y_sus_alias() -> None:
    filas = [
        _fila("O t h e r   T a x e s , F e e s   a n d   I n s u r a n c e", None),
        _fila("028-0000-61050-000", "Fees Trustee", [100.0] * 12),
        _fila("028-0000-61790-000", "Non- Deductble", [None] * 12),
        _fila(None, "T o t a l   O t h e r   T a x e s", ["#REF!"] * 12),
    ]
    leido = leer_seccion_filas(filas, None, None, "othertaxesfeesandinsurance", "Other Taxes,Fees and Insurance")
    assert [f.concepto for f in leido.filas] == ["Fees Trustee"]
    alias = ESTRICTAS["othertaxesfeesandinsurance"]
    assert alias["nondeductble"] == "nondeductible" and alias["senioritypremiumacrued"] == "senioritypremium"
    assert alias["admfee4"] == "admfee6"


def test_una_hoja_que_no_cuadra_con_su_total_no_se_importa_por_partidas() -> None:
    from fpa.ingesta.budget_partidas import PartidaLeida, PartidasLeidas
    from fpa.servicios.presupuesto_detalle import _cuadra_con_su_total

    def hoja(partidas: list[PartidaLeida], total: Decimal | None) -> PartidasLeidas:
        return PartidasLeidas("0000-61520 IVA", "0000", "61520", "IVA", partidas=partidas, total_expense=total)

    buena = PartidaLeida("A", D(2), "pz", D(50), "mensual", [D(100) / 12] * 12, 10)
    assert _cuadra_con_su_total(hoja([buena], D(100)))[0] is True
    assert _cuadra_con_su_total(hoja([buena], None))[0] is True  # sin Total Expense no hay con qué comparar
    # hoja de cálculo: cantidad × costo enorme contra un Total Expense de cero
    cuenta_de_calculo = PartidaLeida("Other Income", D(1_000_000), None, D("1.5"), "estacional", [D(0)] * 12, 11)
    assert _cuadra_con_su_total(hoja([cuenta_de_calculo], D(0)))[0] is False
    # calendario: sus meses suman mucho más que el Total Expense de la hoja
    calendario = PartidaLeida("Activo", D(1), None, D(613_848), "estacional", [D(148_681)] * 12, 12)
    assert _cuadra_con_su_total(hoja([calendario], D(613_848)))[0] is False


def test_owner_services_empareja_filas_y_hojas_con_nombres_distintos_solo_por_alias() -> None:
    alias = ESTRICTAS["ownerservices"]
    lineas = [
        _linea("028-0108-61625-000", "Meals & Entertain"),
        _linea("028-0108-61630-000", "Mileage, Taxi, Parking"),
        _linea("028-0108-61635-000", "Local consumes"),
        _linea("028-0108-61560-000", "Telephone"),
    ]
    assert _linea_de_hoja(lineas, "0108", "61625", "Meals & Entern", alias) is lineas[0]
    assert _linea_de_hoja(lineas, "0108", "61630", "Milleage, Taxis, Par", alias) is lineas[1]
    assert _linea_de_hoja(lineas, "0108", "61635", "Local Consumos", alias) is lineas[2]
    assert _linea_de_hoja(lineas, "0108", "61560", "Telephone-Fax", alias) is lineas[3]
    # sin alias no se unen por parecido
    assert _linea_de_hoja(lineas, "0108", "61625", "Meals & Entern") is None


def test_vds_lee_sus_dos_lineas_negativas_y_el_cierre_cortado_del_total() -> None:
    filas = [
        _fila("V D S   A l l o c a t i o n   C o l l e c t i o n s", None),
        _fila("028-0108-61715-000", "VDS Allocation Collections", [-20093.56] * 12),
        _fila("028-0000-61520-000", "Collection IVA Taxes 16%", [-3214.97] * 12),
        _fila(None, "T o t a l   V D S   A l l o c a t i o n   C", [-23308.53] * 12),
    ]
    leido = leer_seccion_filas(filas, None, None, "vdsallocationcollections", "VDS Allocation Collections")
    assert [(f.concepto, f.celdas[0].importe) for f in leido.filas] == [
        ("VDS Allocation Collections", D("-20093.56")),
        ("Collection IVA Taxes 16%", D("-3214.97")),
    ]
    assert ESTRICTAS["vdsallocationcollections"] == {}


def test_purchasing_distingue_airfare_lodging_y_meals_que_comparten_la_cuenta_61630() -> None:
    alias = ESTRICTAS["purchasing"]
    lineas = [
        _linea("028-0122-61630-000", "Airfare"),
        _linea("028-0122-61630-000", "Lodging"),
        _linea("028-0122-61630-000", "Meals & Entertain"),
        _linea("028-0122-61625-000", "Mileage, Taxi, Parking"),
        _linea("028-0122-61790-000", "Non-Deductible"),
    ]
    assert _linea_de_hoja(lineas, "0122", "61630", "Airfare", alias) is lineas[0]
    assert _linea_de_hoja(lineas, "0122", "61630", "Lodging", alias) is lineas[1]
    assert _linea_de_hoja(lineas, "0122", "61630", "Meals", alias) is lineas[2]
    assert _linea_de_hoja(lineas, "0122", "61625", "Mileage Parking", alias) is lineas[3]
    assert _linea_de_hoja(lineas, "0122", "61790", "Non Deductable", alias) is lineas[4]


# --- Commercial Services: secciones repetidas por ordinal, renglones calculados, hoja «Cafeteria …» ------


def _hoja_comercial() -> list[tuple[object, ...]]:
    return [
        _fila("S t o r e", None),
        _fila("028-0128-44055-000", "Store Gross Sales", [100.0] * 12),
        _fila("028-0128-61280-000", "Less Discount", [10.0] * 12),
        _fila(None, "N e t   S a l e s   S t o r e", [90.0] * 12),
        _fila("028-0128-61275-000", "Cost of Sales", [40.0] * 12),
        _fila(None, "G r o s s   P r o f i t   S t o r e", [50.0] * 12),
        _fila(None, None, [0.65] * 12),
        _fila("S t o r e", None),
        _fila("028-0128-61560-000", "Telephone", [7.0] * 12),
        _fila("028-0128-61790-000", "Non Deductable", [1.0] * 12),
        _fila(None, "T o t a l   E x p e n s e s", [8.0] * 12),
        _fila("028-0128-61715-000", "A l l o c a t e d   E x p e n s e s", [None] * 12),
        _fila("C a f e t e r i a", None),
    ]


def test_las_secciones_repetidas_se_leen_por_ordinal_y_sin_renglones_calculados() -> None:
    ventas = leer_seccion_filas(_hoja_comercial(), None, None, "store", "Store")
    assert [f.concepto for f in ventas.filas] == ["Store Gross Sales", "Less Discount", "Cost of Sales"]
    gastos = leer_seccion_filas(_hoja_comercial(), None, None, "store#2", "Store")
    assert [f.concepto for f in gastos.filas] == ["Telephone", "Non Deductable"]
    assert any("Allocated Expenses" in a for a in gastos.avisos)  # sin importes: queda para captura
    with pytest.raises(ValueError, match="no trae la sección"):
        leer_seccion_filas(_hoja_comercial(), None, None, "store#3", "Store")


def test_las_hojas_de_cafeteria_no_llevan_codigo_y_la_promotion_de_restaurant_cambia_de_cuenta() -> None:
    from fpa.ingesta.budget_partidas import datos_de_hoja

    assert datos_de_hoja("Cafeteria Materials-Supplies") == ("5036", "", "Materials-Supplies")
    assert datos_de_hoja("0124-60160 Promotion") == ("0124", "60160", "Promotion")
    cafe = [_linea("028-5036-61480-000", "Materials/Supplies"), _linea("028-5036-61410-000", "Equipment")]
    assert _linea_de_hoja(cafe, "5036", "", "Materials-Supplies") is cafe[0]
    restaurante = [_linea("028-0124-60170-000", "Promotion")]
    assert _linea_de_hoja(restaurante, "0124", "60160", "Promotion") is restaurante[0]
    agencia = [_linea("028-0120-60310-000", "Bank Commissions"), _linea("028-0120-61781-000", "Miscellaneous/non deductibles")]
    alias = ESTRICTAS["travelagency"]
    assert _linea_de_hoja(agencia, "0120", "60310", "Bank Commisions", alias) is agencia[0]
    assert _linea_de_hoja(agencia, "0120", "61781", "Miscellaneous No Ded", alias) is agencia[1]


def test_it_systems_empareja_hojas_abreviadas_y_la_telephone_del_departamento_0000() -> None:
    alias = ESTRICTAS["itsystems"]
    lineas = [
        _linea("028-1136-61350-000", "Repairs & Maintenance EQUIPMENT"),
        _linea("028-1136-61380-000", "Repairs & Maint Desktop SOFTWARE"),
        _linea("028-1136-61635-000", "Meals & Entertain"),
        _linea("028-1136-61800-000", "Postage/Express Mail"),
        _linea("028-1136-61560-000", "Telephone"),
    ]
    assert _linea_de_hoja(lineas, "1136", "61350", "Rep & Maint EQUIP", alias) is lineas[0]
    assert _linea_de_hoja(lineas, "1136", "61380", "Rep & Maint D SOF", alias) is lineas[1]
    assert _linea_de_hoja(lineas, "1136", "61635", "Meals & Enternt N", alias) is lineas[2]
    assert _linea_de_hoja(lineas, "1136", "61800", "Postage Express M", alias) is lineas[3]
    # la hoja de Telephone se llama `0000-60560`: pertenece a la línea 1136-61560
    assert _linea_de_hoja(lineas, "0000", "60560", "Telephone", alias) is lineas[4]


def test_legal_acepta_sus_alias_y_el_total_previo_con_ref_se_suma_de_sus_cuentas() -> None:
    assert ESTRICTAS["legal"]["nondeductexp"] == "nondeductible"
    previa = [
        _fila("L e g a l", None),
        _fila("030-0130-61560-000", "Telephone", [10.0] * 12),
        _fila("030-0130-61800-000", "Postage", [5.0] * 12),
        _fila("030-0130-60010-000", "Salaries", ["#REF!"] * 12),
        _fila(None, "T o t a l   L e g a l", ["#REF!"] * 12),
    ]
    leido = leer_seccion_filas(previa, previa, previa, "legal", "Legal")
    assert leido.est_act == [D(15)] * 12 and leido.budget_previo == [D(15)] * 12
