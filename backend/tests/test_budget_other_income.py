"""Budget por cuenta, parte 1: lector de la hoja `Other Income`, importación al ciclo y API."""

from decimal import Decimal
from io import BytesIO

import pytest
from conftest import Mundo, como
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.ingesta.budget_other_income import leer_other_income_filas
from fpa.modelos import LineaReporte, VersionEstructuraReporte
from fpa.modelos.presupuesto import DetalleLineaPresupuesto
from fpa.servicios.presupuesto_ciclo import crear_ano_fiscal, crear_ciclo, crear_periodo_fiscal

D = Decimal
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ANALISTA = "analista_a@test.local"
CONTRALOR = "contralor_ab@test.local"
MESES = ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun"]
PERIODOS = [f"2026-{m:02d}" for m in range(7, 13)] + [f"2027-{m:02d}" for m in range(1, 7)]


def _fila(concepto: str, celdas: list[object]) -> tuple[object, ...]:
    return (None, concepto) + (None,) * 10 + tuple(celdas)


ENCABEZADO = (None, "Item") + (None,) * 10 + tuple(MESES)


def _hoja(
    formulas: list[tuple[object, ...]], valores: list[tuple[object, ...]]
) -> tuple[list[tuple[object, ...]], list[tuple[object, ...]]]:
    return [ENCABEZADO, *formulas, _fila("Total Expense", [None] * 12)], [
        ENCABEZADO,
        *valores,
        _fila("Total Expense", [None] * 12),
    ]


def _base_de(hoja: str, coord: str) -> object:
    # La base de «Rental Income» (fila 12 de EstAct) es 1000 cada mes.
    return {"D12": 1000, "E12": 1000, "D26": 100}.get(coord, 0)


def test_lee_factor_fijo_y_formula_desconocida() -> None:
    formulas, valores = _hoja(
        [
            _fila(
                "Rental Income",
                ["=('EstAct 25-26 MZT'!D12)*1.05", "='EstAct 25-26 MZT'!E12*1.17"] + [10] * 10,
            ),
            _fila("Misc", [10000] * 12),
            _fila("Rara", ["=SUM(A1:A3)"] + [0] * 11),
        ],
        [
            _fila("Rental Income", [1050, 1170] + [10] * 10),
            _fila("Misc", [10000] * 12),
            _fila("Rara", [7] + [0] * 11),
        ],
    )
    leido = leer_other_income_filas(formulas, valores, _base_de)
    renta, misc, rara = leido.filas
    assert renta.celdas[0].metodo == "factor"
    assert renta.celdas[0].base == D(1000) and renta.celdas[0].factor == D("1.05")
    assert renta.celdas[1].factor == D("1.17") and renta.celdas[1].importe == D(1170)
    assert renta.celdas[2].metodo == "fijo" and renta.celdas[2].monto_fijo == D(10)
    assert misc.total == D(120000) and {c.metodo for c in misc.celdas} == {"fijo"}
    assert rara.celdas[0].metodo == "fijo" and rara.celdas[0].importe == D(7)
    assert any("fórmula no reconocida" in a for a in leido.avisos)


def test_se_detiene_en_el_total_y_pide_encabezado() -> None:
    formulas, valores = _hoja([_fila("Uno", [1] * 12)], [_fila("Uno", [1] * 12)])
    formulas.append(_fila("Despues", [5] * 12))
    valores.append(_fila("Despues", [5] * 12))
    assert [f.concepto for f in leer_other_income_filas(formulas, valores, _base_de).filas] == [
        "Uno"
    ]
    with pytest.raises(ValueError, match="encabezado"):
        leer_other_income_filas([(None, "x")], [(None, "x")], _base_de)


def test_avisa_si_no_cuadra_con_el_budget() -> None:
    formulas, valores = _hoja(
        [_fila("Miscellaneous non taxable", [10000] * 12), _fila("Laundry", [5] * 12)],
        [_fila("Miscellaneous non taxable", [10000] * 12), _fila("Laundry", [5] * 12)],
    )

    def fila_budget(desc: str, mes: int) -> tuple[object, ...]:
        return (None, "028-0101-45010-000", desc) + (mes,) * 12

    budget = [
        (None, "O t h e r   I n c o m e"),
        fila_budget("Miscellaneous non taxable", 6500),
        fila_budget("Laundry", 5),
        (None, None, "T o t a l   O t h e r   I n c o m e"),
        fila_budget("Otra cosa", 99),
    ]
    leido = leer_other_income_filas(formulas, valores, _base_de, budget)
    assert len(leido.avisos) == 1
    assert "Miscellaneous non taxable" in leido.avisos[0] and "78,000.00" in leido.avisos[0]


# --- Importación al ciclo y API ---------------------------------------------------------------


def _estructura_other_income(db: Session, hotel_id: int) -> tuple[int, dict[str, int]]:
    version = VersionEstructuraReporte(
        hotel_id=hotel_id,
        nombre_archivo="e.xlsx",
        sha256="0" * 64,
        estado="vigente",
        n_lineas=4,
        n_detalle=3,
    )
    db.add(version)
    db.flush()
    seccion = LineaReporte(
        version_id=version.id,
        hotel_id=hotel_id,
        orden=1,
        tipo="seccion",
        nivel=0,
        descripcion="Other Income",
        clave="oi",
        fila_origen=10,
    )
    db.add(seccion)
    db.flush()
    ids: dict[str, int] = {}
    for orden, nombre in enumerate(["Rental Income", "Laundry Coins", "Venados"], start=2):
        linea = LineaReporte(
            version_id=version.id,
            hotel_id=hotel_id,
            orden=orden,
            tipo="detalle",
            nivel=1,
            seccion_id=seccion.id,
            descripcion=nombre,
            clave=nombre.lower(),
            fila_origen=9 + orden,
        )
        db.add(linea)
        db.flush()
        ids[nombre] = linea.id
    db.commit()
    return version.id, ids


def _ciclo(db: Session, mundo: Mundo) -> tuple[int, dict[str, int]]:
    _, ids = _estructura_other_income(db, mundo.hotel_a)
    ano = crear_ano_fiscal(db, hotel_id=mundo.hotel_a, etiqueta="2026/27", mes_inicio=7, mes_fin=6)
    for periodo in PERIODOS:
        crear_periodo_fiscal(db, ano_fiscal_id=ano.id, periodo=periodo)
    ciclo = crear_ciclo(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        ano_fiscal_id=ano.id,
    )
    db.commit()
    return ciclo.id, ids


def _libro(filas: list[tuple[str, list[float]]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Other Income"
    ws.append([None, "Item"] + [None] * 10 + MESES)
    for concepto, meses in filas:
        ws.append([None, concepto] + [None] * 10 + meses)
    ws.append([None, "Total Expense"])
    salida = BytesIO()
    wb.save(salida)
    return salida.getvalue()


def _url(mundo: Mundo, ciclo_id: int, ruta: str) -> str:
    return f"/api/v1/hoteles/{mundo.hotel_a}/presupuesto/ciclos/{ciclo_id}/{ruta}"


def test_importa_other_income_a_las_lineas_del_ciclo(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    ciclo_id, ids = _ciclo(db, mundo)
    libro = _libro(
        [
            ("Rental Income", [100.0] * 12),
            ("Laundry Coins", [10.0] * 12),
            ("Algo que no existe en el reporte", [1.0] * 12),
        ]
    )
    r = cliente.post(
        _url(mundo, ciclo_id, "detalle/importar-other-income"),
        files={"archivo": ("budget.xlsx", libro, XLSX)},
        headers=como(CONTRALOR),
    )
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["importadas"] == 2
    assert any("Algo que no existe" in a for a in cuerpo["avisos"])
    assert any("Venados" in a for a in cuerpo["avisos"])

    r2 = cliente.get(
        _url(mundo, ciclo_id, f"lineas/{ids['Rental Income']}/detalle"), headers=como(CONTRALOR)
    )
    assert r2.status_code == 200
    celdas = r2.json()
    assert [c["periodo"] for c in celdas] == PERIODOS
    assert all(D(c["importe"]) == D(100) and c["metodo"] == "fijo" for c in celdas)
    lineas = cliente.get(_url(mundo, ciclo_id, "lineas"), headers=como(CONTRALOR)).json()
    renta = next(x for x in lineas if x["linea_id"] == ids["Rental Income"])
    assert D(renta["propuesta_anual"]) == D(1200)


def test_importar_rechaza_un_libro_sin_la_hoja(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    ciclo_id, _ = _ciclo(db, mundo)
    wb = Workbook()
    salida = BytesIO()
    wb.save(salida)
    r = cliente.post(
        _url(mundo, ciclo_id, "detalle/importar-other-income"),
        files={"archivo": ("budget.xlsx", salida.getvalue(), XLSX)},
        headers=como(CONTRALOR),
    )
    assert r.status_code == 422
    assert "Other Income" in r.json()["detail"]


def test_importar_exige_permiso_de_captura(cliente: TestClient, db: Session, mundo: Mundo) -> None:
    ciclo_id, _ = _ciclo(db, mundo)
    r = cliente.post(
        _url(mundo, ciclo_id, "detalle/importar-other-income"),
        files={"archivo": ("budget.xlsx", _libro([("Rental Income", [1.0] * 12)]), XLSX)},
        headers=como("auditoria_b@test.local"),
    )
    assert r.status_code in (403, 404)


def test_put_detalle_calcula_y_get_lo_devuelve(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    ciclo_id, ids = _ciclo(db, mundo)
    celdas = [
        {"periodo": p, "metodo": "factor", "base": "1000", "factor": "1.17"} for p in PERIODOS
    ]
    r = cliente.put(
        _url(mundo, ciclo_id, f"lineas/{ids['Rental Income']}/detalle"),
        json={"celdas": celdas},
        headers=como(CONTRALOR),
    )
    assert r.status_code == 200, r.text
    assert all(D(c["importe"]) == D("1170") for c in r.json())
    guardado = db.scalars(select(DetalleLineaPresupuesto)).all()
    assert len(guardado) == 12


def test_put_detalle_incompleto_es_422(cliente: TestClient, db: Session, mundo: Mundo) -> None:
    ciclo_id, ids = _ciclo(db, mundo)
    celdas = [{"periodo": p, "metodo": "fijo", "monto_fijo": "1"} for p in PERIODOS[:11]]
    r = cliente.put(
        _url(mundo, ciclo_id, f"lineas/{ids['Rental Income']}/detalle"),
        json={"celdas": celdas},
        headers=como(CONTRALOR),
    )
    assert r.status_code == 422


def test_put_detalle_con_datos_faltantes_es_422(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    ciclo_id, ids = _ciclo(db, mundo)
    celdas = [{"periodo": p, "metodo": "factor", "base": "1000"} for p in PERIODOS]
    r = cliente.put(
        _url(mundo, ciclo_id, f"lineas/{ids['Rental Income']}/detalle"),
        json={"celdas": celdas},
        headers=como(CONTRALOR),
    )
    assert r.status_code == 422


def test_detalle_de_version_ajena_es_404(cliente: TestClient, db: Session, mundo: Mundo) -> None:
    r = cliente.get(
        f"/api/v1/hoteles/{mundo.hotel_a}/presupuesto/versiones/99999/lineas/1/detalle",
        headers=como(CONTRALOR),
    )
    assert r.status_code == 404


def test_analista_no_puede_guardar_detalle(cliente: TestClient, db: Session, mundo: Mundo) -> None:
    ciclo_id, ids = _ciclo(db, mundo)
    celdas = [{"periodo": p, "metodo": "fijo", "monto_fijo": "1"} for p in PERIODOS]
    r = cliente.put(
        _url(mundo, ciclo_id, f"lineas/{ids['Rental Income']}/detalle"),
        json={"celdas": celdas},
        headers=como(ANALISTA),
    )
    assert r.status_code == 403


def test_el_ruido_de_flotantes_de_excel_se_redondea_a_seis_decimales() -> None:
    formulas, valores = _hoja(
        [_fila("Rental Income", ["='EstAct 25-26 MZT'!D99*1.05"] + [0] * 11)],
        [_fila("Rental Income", [64498.675500000005] + [0] * 11)],
    )
    celda = (
        leer_other_income_filas(formulas, valores, lambda h, c: 61427.310000000005)
        .filas[0]
        .celdas[0]
    )
    assert celda.base == D("61427.310000") and celda.importe == D("64498.675500")
