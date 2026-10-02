"""Edición del Budget en pantalla: versión nueva desde cambios, con el Actual como referencia."""

from decimal import Decimal
from pathlib import Path

import pytest
from conftest import Mundo, como
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_mzt_integracion import Libro

from fpa.modelos import EventoAuditoria
from fpa.modelos.plan import LineaPlanMensual
from fpa.repositorios.plan import RepositorioPlan
from fpa.repositorios.reporte import RepositorioReporte
from fpa.servicios.budget_edicion import (
    BaseDesactualizada,
    CambioBudget,
    EdicionInvalida,
    crear_version_desde_cambios,
    periodos_de_ano_fiscal,
    vista_edicion,
)
from fpa.servicios.variance import calcular_variance
from fpa.servicios.versionado_mapeo import aprobar
from tests.mzt_sintetico import crear_libro_mzt

D = Decimal
ANALISTA = "analista_a@test.local"
CONTRALOR = "contralor_ab@test.local"
RESPONSABLE = "responsable_a@test.local"
OTRA_ORG = "contralor_c@test.local"
AF = "2026/27"


@pytest.fixture
def libro(db: Session, mundo: Mundo, tmp_path: Path) -> Libro:
    return Libro(db, mundo, crear_libro_mzt(tmp_path / "mzt.xlsx"))


def _ids(libro: Libro) -> dict[int, int]:
    """fila del Excel -> id de la línea."""
    assert libro.estructura is not None
    lineas = RepositorioReporte(libro.db, libro.mundo.hotel_a).lineas(libro.estructura.id)
    return {x.fila_origen: x.id for x in lineas}


def _guardar(libro: Libro, cambios: list[tuple[int, str, str]], **kw):  # type: ignore[no-untyped-def]
    ids = _ids(libro)
    return crear_version_desde_cambios(
        libro.db,
        organizacion_id=libro.mundo.org1,
        hotel_id=libro.mundo.hotel_a,
        usuario_id=None,
        ano_fiscal=AF,
        cambios=[CambioBudget(ids[f], p, D(i)) for f, p, i in cambios],
        **kw,
    )


def test_los_doce_meses_del_ano_fiscal() -> None:
    meses = periodos_de_ano_fiscal(AF)
    assert meses[0] == "2026-07" and meses[-1] == "2027-06" and len(meses) == 12
    assert periodos_de_ano_fiscal("2026", 1)[0] == "2026-01"
    with pytest.raises(EdicionInvalida):
        periodos_de_ano_fiscal("2026/99")


def test_la_vista_trae_budget_y_actual_mes_a_mes(libro: Libro) -> None:
    libro.aprobar_y_cargar_budget()
    vista = vista_edicion(libro.db, hotel_id=libro.mundo.hotel_a, ano_fiscal=AF)
    por_fila = {x.linea.fila_origen: x for x in vista.lineas}
    renta = por_fila[11]
    assert renta.editable
    assert (renta.budget["2026-07"], renta.budget["2026-08"]) == (D("90"), D("110"))
    assert renta.budget["2026-09"] is None  # sin Budget cargado: no es un cero
    assert (renta.actual["2026-07"], renta.actual["2026-08"]) == (D("100"), D("120"))
    assert renta.actual["2026-09"] is None  # sin movimientos cargados: no es un cero
    total = por_fila[13]
    assert not total.editable  # un total sale de su regla
    assert total.budget["2026-08"] == D("110") and total.actual["2026-08"] == D("120")
    assert not por_fila[9].editable  # el tipo de cambio no es de detalle
    assert por_fila[9].actual["2026-08"] == D("17.1337")  # su Actual capturado
    assert vista.version is not None and len(vista.reglas) == 3


def test_guardar_crea_una_version_nueva_sin_tocar_la_anterior(libro: Libro) -> None:
    libro.aprobar_y_cargar_budget()
    hotel = libro.mundo.hotel_a
    antes = RepositorioPlan(libro.db, hotel).vigente("budget", AF)
    assert antes is not None
    mensuales_antes = {
        (x.linea_id, x.periodo): x.importe
        for x in RepositorioPlan(libro.db, hotel).mensuales(antes.id)
    }
    r = _guardar(libro, [(11, "2026-09", "130"), (14, "2026-08", "60")], base_version_id=antes.id)
    libro.db.commit()
    assert r.version is not None and r.version.numero == antes.numero + 1
    libro.db.refresh(antes)
    assert antes.estado == "reemplazada"
    despues = {
        (x.linea_id, x.periodo): x.importe
        for x in RepositorioPlan(libro.db, hotel).mensuales(antes.id)
    }
    assert despues == mensuales_antes  # la versión anterior no cambió
    ids = _ids(libro)
    nuevos = {
        (x.linea_id, x.periodo): x.importe
        for x in libro.db.scalars(
            select(LineaPlanMensual).where(LineaPlanMensual.version_plan_id == r.version.id)
        )
    }
    assert nuevos[(ids[11], "2026-09")] == D("130")
    assert nuevos[(ids[11], "2026-08")] == D("110")  # lo no editado se conserva
    assert (ids[13], "2026-08") not in nuevos  # un total no se guarda: se recalcula
    assert "budget.editado" in [e.accion for e in libro.db.scalars(select(EventoAuditoria))]


def test_el_variance_usa_la_version_editada_y_recalcula_los_totales(libro: Libro) -> None:
    libro.aprobar_y_cargar_budget()
    _guardar(libro, [(14, "2026-08", "60")])
    libro.db.commit()
    r = calcular_variance(libro.db, hotel_id=libro.mundo.hotel_a, periodo="2026-08")
    por = {x.descripcion: r.resultado[x.id] for x in r.lineas}
    assert por["Salaries"].mes.budget == D("60")
    assert por["Total Expenses"].mes.budget == D("60")  # el total sigue a su componente
    assert por["Salaries"].ytd.budget == D("105")  # 45 de julio + 60 de agosto
    assert por["Rental Income"].mes.budget == D("110")  # lo demás no cambió


def test_se_puede_crear_el_primer_budget_desde_cero(libro: Libro) -> None:
    assert libro.mapeo is not None
    aprobar(libro.db, version_id=libro.mapeo.id, **libro.kw)  # type: ignore[arg-type]
    r = _guardar(libro, [(11, "2026-08", "500")])
    libro.db.commit()
    assert r.version is not None and r.version.numero == 1
    vista = vista_edicion(libro.db, hotel_id=libro.mundo.hotel_a, ano_fiscal=AF)
    renta = next(x for x in vista.lineas if x.linea.fila_origen == 11)
    assert renta.budget["2026-08"] == D("500") and renta.budget["2026-07"] is None


@pytest.mark.parametrize(
    ("cambio", "texto"),
    [
        ((13, "2026-08", "5"), "total"),  # línea con regla
        ((9, "2026-08", "5"), "total"),  # línea informativa
        ((11, "2027-09", "5"), "no es del año fiscal"),
        ((11, "2026-08", "9" * 20), "no válido"),
        ((11, "2026-08", "110"), "iguales"),  # mismo importe que la versión actual
    ],
)
def test_cambios_no_validos_se_rechazan(
    libro: Libro, cambio: tuple[int, str, str], texto: str
) -> None:
    libro.aprobar_y_cargar_budget()
    with pytest.raises(EdicionInvalida, match=texto):
        _guardar(libro, [cambio])


def test_linea_inexistente_o_sin_cambios(libro: Libro) -> None:
    libro.aprobar_y_cargar_budget()
    with pytest.raises(EdicionInvalida, match="no pertenece"):
        crear_version_desde_cambios(
            libro.db,
            organizacion_id=libro.mundo.org1,
            hotel_id=libro.mundo.hotel_a,
            usuario_id=None,
            ano_fiscal=AF,
            cambios=[CambioBudget(10**9, "2026-08", D("1"))],
        )
    with pytest.raises(EdicionInvalida, match="No hay cambios"):
        _guardar(libro, [])


def test_una_base_vieja_no_se_puede_editar(libro: Libro) -> None:
    libro.aprobar_y_cargar_budget()
    base = RepositorioPlan(libro.db, libro.mundo.hotel_a).vigente("budget", AF)
    assert base is not None
    _guardar(libro, [(11, "2026-09", "130")], base_version_id=base.id)
    libro.db.commit()
    with pytest.raises(BaseDesactualizada):
        _guardar(libro, [(11, "2026-10", "140")], base_version_id=base.id)


# --- API ----------------------------------------------------------------------------------------


def _cuerpo(
    libro: Libro, cambios: list[tuple[int, str, str]], base: int | None
) -> dict[str, object]:
    ids = _ids(libro)
    return {
        "ano_fiscal": AF,
        "base_version_id": base,
        "cambios": [{"linea_id": ids[f], "periodo": p, "importe": i} for f, p, i in cambios],
    }


def test_api_ver_y_guardar(cliente: TestClient, mundo: Mundo, libro: Libro) -> None:
    libro.aprobar_y_cargar_budget()
    base = f"/api/v1/hoteles/{mundo.hotel_a}/budget"
    r = cliente.get(f"{base}/edicion?ano_fiscal=2026/27", headers=como(ANALISTA))
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert len(cuerpo["periodos"]) == 12 and cuerpo["version"]["numero"] == 1
    renta = next(x for x in cuerpo["lineas"] if x["descripcion"] == "Rental Income")
    assert renta["editable"] and D(renta["meses"][1]["budget"]) == D("110")
    assert D(renta["meses"][1]["actual"]) == D("120")

    g = cliente.post(
        f"{base}/versiones",
        json=_cuerpo(libro, [(11, "2026-09", "130.5")], cuerpo["version"]["id"]),
        headers=como(ANALISTA),
    )
    assert g.status_code == 201, g.text
    assert g.json()["version"]["numero"] == 2
    # editar otra vez sobre la versión vieja: alguien más ya guardó
    viejo = cliente.post(
        f"{base}/versiones",
        json=_cuerpo(libro, [(11, "2026-10", "1")], cuerpo["version"]["id"]),
        headers=como(ANALISTA),
    )
    assert viejo.status_code == 409


def test_api_rechaza_lo_no_valido_y_respeta_permisos(
    cliente: TestClient, mundo: Mundo, libro: Libro
) -> None:
    libro.aprobar_y_cargar_budget()
    url = f"/api/v1/hoteles/{mundo.hotel_a}/budget/versiones"
    malo = _cuerpo(libro, [(13, "2026-08", "5")], None)  # un total
    assert cliente.post(url, json=malo, headers=como(ANALISTA)).status_code == 422
    for importe in ("NaN", "Infinity", "1e400"):
        c = _cuerpo(libro, [(11, "2026-08", importe)], None)
        assert cliente.post(url, json=c, headers=como(ANALISTA)).status_code == 422
    ok = _cuerpo(libro, [(11, "2026-09", "1")], None)
    assert cliente.post(url, json=ok, headers=como(RESPONSABLE)).status_code == 403
    assert cliente.post(url, json=ok).status_code == 401
    assert cliente.post(url, json=ok, headers=como(OTRA_ORG)).status_code == 404
    edicion = f"/api/v1/hoteles/{mundo.hotel_a}/budget/edicion?ano_fiscal=2026/27"
    assert cliente.get(edicion, headers=como(RESPONSABLE)).status_code == 403
    assert cliente.get(edicion).status_code == 401
    assert cliente.get(edicion.replace("2026/27", "xx"), headers=como(CONTRALOR)).status_code == 422
