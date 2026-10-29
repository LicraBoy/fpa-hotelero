"""Cuentas de consumo (Diesel, Gas, Electricity, Water & Sewer): 4 bloques mensuales, Budget editable."""

from decimal import Decimal
from pathlib import Path

import pytest
from conftest import Mundo, como
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_budget_other_income import CONTRALOR, PERIODOS, _url

from fpa.ingesta.budget_partidas import leer_hoja_partidas
from fpa.ingesta.budget_seccion import leer_seccion
from fpa.modelos import ConsumoLineaMes, LineaPresupuestoCaptura, LineaReporte, VersionEstructuraReporte
from fpa.servicios.presupuesto_ciclo import crear_ano_fiscal, crear_ciclo, crear_periodo_fiscal
from fpa.servicios.presupuesto_consumo import guardar_consumo_importado

D = Decimal
EXCEL_REAL = Path(__file__).resolve().parents[2] / "docs" / "-1% - MZT Budget 26-27 TC 18.00 Final.xlsx"
MESES = ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun"]


def _hoja_consumo() -> list[tuple[object, ...]]:
    """Una hoja de consumo sintética: 4 bloques de (unidades, costo, total) por mes."""
    filas: list[tuple[object, ...]] = [(), (), (), (), (), (), ()]
    filas.append(
        (None, "Real 24/25\n(Lts)", "Unit Cost", "Total", "Budget 25/26\n(Lts)", "Unit Cost", "Total",
         " Est-Actuals 25-26\n(Lts)", "Unit Cost", "Total", "Budget 26/27\n(Lts)", "Cost", "Extended Cost")
    )  # fmt: skip
    for i, m in enumerate(MESES):
        u = 100 + i
        filas.append(
            (m, u, 10, u * 10, u, 11, u * 11, u + 1, 12, (u + 1) * 12, u + 2, 13, (u + 2) * 13)
        )
    filas.append(())
    filas.append((None, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 13, sum((100 + i + 2) * 13 for i in range(12))))
    return filas


def test_la_hoja_de_consumo_se_lee_con_sus_cuatro_bloques() -> None:
    h = leer_hoja_partidas("0106-61440 Diesel", _hoja_consumo())
    assert h.partidas == [] and h.consumo is not None and h.consumo.unidad == "Lts"
    assert set(h.consumo.bloques) == {"real_prev", "budget_prev", "est_act", "budget"}
    assert h.consumo.bloques["real_prev"][0] == (D(100), D(10), D(1000))
    assert h.consumo.bloques["est_act"][11] == (D(112), D(12), D(1344))
    assert h.consumo.bloques["budget"][5] == (D(107), D(13), D(1391))
    assert h.total_expense == sum((t for _, _, t in h.consumo.bloques["budget"] if t is not None), D(0))


# --- Servicio y API ------------------------------------------------------------------------


def _ciclo(db: Session, mundo: Mundo) -> tuple[int, dict[str, int]]:
    version = VersionEstructuraReporte(
        hotel_id=mundo.hotel_a, nombre_archivo="e.xlsx", sha256="3" * 64, estado="vigente", n_lineas=4, n_detalle=2
    )
    db.add(version)
    db.flush()
    seccion = LineaReporte(
        version_id=version.id, hotel_id=mundo.hotel_a, orden=1, tipo="seccion", nivel=0,
        descripcion="Utilities", clave="util", fila_origen=10,
    )  # fmt: skip
    db.add(seccion)
    db.flush()
    ids = {"seccion": seccion.id}
    for orden, (nombre, codigo) in enumerate(
        [("Gas", "028-0000-61670-000"), ("Water & Sewer", "028-0000-61675-000")], start=2
    ):
        linea = LineaReporte(
            version_id=version.id, hotel_id=mundo.hotel_a, orden=orden, tipo="detalle", nivel=1,
            seccion_id=seccion.id, codigo_corporativo=codigo, descripcion=nombre,
            clave=nombre.lower(), fila_origen=10 + orden,
        )  # fmt: skip
        db.add(linea)
        db.flush()
        ids[nombre] = linea.id
    ano = crear_ano_fiscal(db, hotel_id=mundo.hotel_a, etiqueta="2026/27", mes_inicio=7, mes_fin=6)
    for periodo in PERIODOS:
        crear_periodo_fiscal(db, ano_fiscal_id=ano.id, periodo=periodo)
    ciclo = crear_ciclo(
        db, organizacion_id=mundo.org1, hotel_id=mundo.hotel_a, usuario_id=None, ano_fiscal_id=ano.id
    )
    db.commit()
    return ciclo.id, ids


def _importar(db: Session, mundo: Mundo, ciclo_id: int, linea_id: int) -> None:
    h = leer_hoja_partidas("0000-61670 Gas", _hoja_consumo())
    assert h.consumo is not None
    guardar_consumo_importado(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        ciclo_id=ciclo_id,
        linea_id=linea_id,
        unidad=h.consumo.unidad,
        bloques=h.consumo.bloques,
        visibles=None,
    )
    db.commit()


def test_importar_el_consumo_deja_el_budget_de_la_cuenta_y_la_hoja_lo_muestra_todo(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    ciclo_id, ids = _ciclo(db, mundo)
    _importar(db, mundo, ciclo_id, ids["Gas"])
    h = cliente.get(_url(mundo, ciclo_id, f"lineas/{ids['Gas']}/hoja"), headers=como(CONTRALOR)).json()
    assert h["partidas"] == [] and h["consumo"]["unidad"] == "Lts"
    assert len(h["consumo"]["budget"]) == 12 and D(h["consumo"]["budget"][0]["total"]) == D(1326)
    assert D(h["consumo"]["real_prev"][0]["costo_unitario"]) == D(10)
    esperado = sum((100 + i + 2) * 13 for i in range(12))
    assert sum(D(x) for x in h["total_con_inflacion"]) == D(esperado)
    detalle = cliente.get(_url(mundo, ciclo_id, f"lineas/{ids['Gas']}/detalle"), headers=como(CONTRALOR)).json()
    assert [D(c["monto_fijo"]) for c in detalle][:2] == [D(1326), D(1339)]


def test_editar_un_mes_recalcula_su_total_y_el_budget_sin_tocar_los_demas(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    ciclo_id, ids = _ciclo(db, mundo)
    _importar(db, mundo, ciclo_id, ids["Gas"])
    r = cliente.put(
        _url(mundo, ciclo_id, f"lineas/{ids['Gas']}/consumo"),
        json={"meses": [{"periodo": PERIODOS[0], "unidades": "200", "costo_unitario": "15.5"}]},
        headers=como(CONTRALOR),
    )
    assert r.status_code == 200, r.text
    h = r.json()
    assert D(h["consumo"]["budget"][0]["total"]) == D(3100) and D(h["consumo"]["budget"][1]["total"]) == D(1339)
    assert D(h["total_con_inflacion"][0]) == D(3100)
    # los otros tres bloques son del Excel y no se editan
    assert D(h["consumo"]["est_act"][0]["total"]) == D(1212)


def test_la_edicion_mes_a_mes_queda_bloqueada_y_hay_validaciones(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    ciclo_id, ids = _ciclo(db, mundo)
    _importar(db, mundo, ciclo_id, ids["Gas"])
    mal = cliente.put(
        _url(mundo, ciclo_id, f"lineas/{ids['Gas']}/consumo"),
        json={"meses": [{"periodo": PERIODOS[0], "unidades": "-1", "costo_unitario": "1"}]},
        headers=como(CONTRALOR),
    )
    assert mal.status_code == 422
    fuera = cliente.put(
        _url(mundo, ciclo_id, f"lineas/{ids['Gas']}/consumo"),
        json={"meses": [{"periodo": "2030-01", "unidades": "1", "costo_unitario": "1"}]},
        headers=como(CONTRALOR),
    )
    assert fuera.status_code == 422
    # sin consumo, la cuenta de Water no se puede editar como consumo
    sin = cliente.put(
        _url(mundo, ciclo_id, f"lineas/{ids['Water & Sewer']}/consumo"),
        json={"meses": [{"periodo": PERIODOS[0], "unidades": "1", "costo_unitario": "1"}]},
        headers=como(CONTRALOR),
    )
    assert sin.status_code == 409


def test_quitar_el_consumo_vuelve_al_editor_mensual_y_conserva_el_budget(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    ciclo_id, ids = _ciclo(db, mundo)
    _importar(db, mundo, ciclo_id, ids["Gas"])
    assert cliente.delete(_url(mundo, ciclo_id, f"lineas/{ids['Gas']}/consumo"), headers=como(CONTRALOR)).status_code == 204
    captura = db.scalar(select(LineaPresupuestoCaptura).where(LineaPresupuestoCaptura.linea_id == ids["Gas"]))
    db.refresh(captura)
    assert captura is not None and not captura.usa_consumo
    assert db.scalars(select(ConsumoLineaMes)).first() is None
    detalle = cliente.get(_url(mundo, ciclo_id, f"lineas/{ids['Gas']}/detalle"), headers=como(CONTRALOR)).json()
    assert D(detalle[0]["monto_fijo"]) == D(1326)  # el Budget sigue como importe fijo


def test_water_lleva_consumo_y_partidas_a_la_vez_sin_pisarse(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    ciclo_id, ids = _ciclo(db, mundo)
    agua = ids["Water & Sewer"]
    _importar(db, mundo, ciclo_id, agua)
    estacional = ["100"] + ["0"] * 11
    cuerpo = {
        "partidas": [
            {"concepto": "CONTRATO", "cantidad": "1", "unidad": None, "costo": "100", "metodo": "estacional", "meses": estacional}
        ],
        "inflacion": {p: "0.05" for p in PERIODOS},
    }
    r = cliente.put(_url(mundo, ciclo_id, f"lineas/{agua}/partidas"), json=cuerpo, headers=como(CONTRALOR))
    assert r.status_code == 200, r.text
    h = r.json()
    assert len(h["partidas"]) == 1 and h["consumo"] is not None
    # julio: consumo 1326 + partida 100 × 1.05; agosto: solo consumo
    assert D(h["total_con_inflacion"][0]) == D(1326) + D("105")
    assert D(h["total_con_inflacion"][1]) == D(1339)
    # quitar las partidas deja el Budget solo con el consumo
    assert cliente.delete(_url(mundo, ciclo_id, f"lineas/{agua}/partidas"), headers=como(CONTRALOR)).status_code == 204
    detalle = cliente.get(_url(mundo, ciclo_id, f"lineas/{agua}/detalle"), headers=como(CONTRALOR)).json()
    assert D(detalle[0]["monto_fijo"]) == D(1326)
    # y editar el consumo con partidas presentes tampoco pierde la parte de partidas
    cliente.put(_url(mundo, ciclo_id, f"lineas/{agua}/partidas"), json=cuerpo, headers=como(CONTRALOR))
    e = cliente.put(
        _url(mundo, ciclo_id, f"lineas/{agua}/consumo"),
        json={"meses": [{"periodo": PERIODOS[0], "unidades": "10", "costo_unitario": "10"}]},
        headers=como(CONTRALOR),
    )
    assert D(e.json()["total_con_inflacion"][0]) == D(100) + D("105")


@pytest.mark.skipif(not EXCEL_REAL.exists(), reason="no está el Excel real del Budget en docs/")
def test_el_excel_real_trae_las_cuatro_hojas_de_consumo_con_sus_totales() -> None:
    esperado = {
        "0106-61440 Diesel": ("commonarea", "Common Area", D("1416553.10")),
        "0000-61670 Gas": ("utilities", "Utilities", D("1252011.61")),
        "0000-61660 Electricity": ("utilities", "Utilities", D("6541183.68")),
        "0000-61675 Water & Sewer 1-2": ("utilities", "Utilities", D("3488564.85")),
    }
    for hoja, (seccion, nombre, total) in esperado.items():
        leido = leer_seccion(EXCEL_REAL, seccion, nombre)
        h = next(x for x in leido.partidas if x.hoja.strip() == hoja)
        assert h.consumo is not None and len(h.consumo.bloques["budget"]) == 12, hoja
        suma = sum((t for _, _, t in h.consumo.bloques["budget"] if t is not None), D(0))
        assert abs(suma - total) < D("0.01"), (hoja, suma)
        for bloque in ("real_prev", "budget_prev", "est_act"):
            assert len(h.consumo.bloques[bloque]) == 12
