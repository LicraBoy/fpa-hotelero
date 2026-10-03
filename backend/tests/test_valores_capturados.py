"""Actual capturado a mano (tipo de cambio de cada mes) y su efecto en el Variance."""

from decimal import Decimal
from pathlib import Path

import pytest
from conftest import Mundo, como
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_mzt_integracion import Libro

from fpa.modelos import EventoAuditoria
from fpa.modelos.plan import ValorCapturado
from fpa.repositorios.reporte import RepositorioReporte
from fpa.servicios.budget_edicion import vista_edicion
from fpa.servicios.valores_capturados import (
    CapturaInvalida,
    ValorEntrada,
    capturar_actuales,
    lineas_capturables,
)
from fpa.servicios.variance import calcular_variance
from tests.mzt_sintetico import crear_libro_mzt

D = Decimal
ANALISTA = "analista_a@test.local"


@pytest.fixture
def libro(db: Session, mundo: Mundo, tmp_path: Path) -> Libro:
    return Libro(db, mundo, crear_libro_mzt(tmp_path / "mzt.xlsx"))


def _ids(libro: Libro) -> dict[int, int]:
    assert libro.estructura is not None
    lineas = RepositorioReporte(libro.db, libro.mundo.hotel_a).lineas(libro.estructura.id)
    return {x.fila_origen: x.id for x in lineas}


def _capturar(libro: Libro, valores: list[tuple[int, str, str | None]]) -> int:
    ids = _ids(libro)
    return capturar_actuales(
        libro.db,
        organizacion_id=libro.mundo.org1,
        hotel_id=libro.mundo.hotel_a,
        usuario_id=None,
        valores=[ValorEntrada(ids[f], p, None if i is None else D(i)) for f, p, i in valores],
    )


def test_solo_se_capturan_lineas_sin_cuentas_ni_total(libro: Libro) -> None:
    libro.aprobar_y_cargar_budget()
    ids = _ids(libro)
    capturables = lineas_capturables(libro.db, libro.mundo.hotel_a)
    assert ids[9] in capturables  # el tipo de cambio
    assert ids[11] not in capturables  # Rental Income: sale de la cuenta 4002011
    assert ids[13] not in capturables  # un total sale de sus partes


def test_captura_guarda_actualiza_y_borra(libro: Libro) -> None:
    libro.aprobar_y_cargar_budget()
    assert _capturar(libro, [(9, "2026-09", "17.5")]) == 1
    libro.db.commit()
    ids = _ids(libro)

    def valor() -> ValorCapturado | None:
        libro.db.expire_all()
        return libro.db.scalar(
            select(ValorCapturado).where(
                ValorCapturado.linea_id == ids[9], ValorCapturado.periodo == "2026-09"
            )
        )

    v = valor()
    assert v is not None and v.importe == D("17.5") and v.origen == "manual"
    assert _capturar(libro, [(9, "2026-09", "17.5")]) == 0  # el mismo valor no cambia nada
    assert _capturar(libro, [(9, "2026-09", "17.9")]) == 1
    assert _capturar(libro, [(9, "2026-09", None)]) == 1  # vacío = borrar
    libro.db.commit()
    assert valor() is None
    acciones = [e.accion for e in libro.db.scalars(select(EventoAuditoria))]
    assert acciones.count("actual.capturado") == 3  # cada cambio deja su rastro


def test_corregir_un_valor_del_excel_lo_marca_como_manual(libro: Libro) -> None:
    libro.aprobar_y_cargar_budget()
    assert _capturar(libro, [(9, "2026-08", "17.2")]) == 1  # el Excel decía 17.1337
    libro.db.commit()
    vista = vista_edicion(libro.db, hotel_id=libro.mundo.hotel_a, ano_fiscal="2026/27")
    cambio = next(x for x in vista.lineas if x.linea.fila_origen == 9)
    assert cambio.actual["2026-08"] == D("17.2") and cambio.origen_actual["2026-08"] == "manual"
    assert cambio.origen_actual["2026-07"] == "excel"  # julio sigue como vino del Excel


@pytest.mark.parametrize(
    ("valor", "texto"),
    [
        ((11, "2026-09", "5"), "sale de cuentas"),  # Rental Income tiene cuenta
        ((13, "2026-09", "5"), "sale de cuentas"),  # un total
        ((9, "2026-13", "5"), "no es válido"),
        ((9, "2026-09", "9" * 20), "Importe no válido"),
    ],
)
def test_valores_no_validos_se_rechazan_sin_guardar_nada(
    libro: Libro, valor: tuple[int, str, str], texto: str
) -> None:
    libro.aprobar_y_cargar_budget()
    with pytest.raises(CapturaInvalida, match=texto):
        _capturar(libro, [(9, "2026-09", "17.5"), valor])  # el primero es válido: no se guarda
    assert (
        libro.db.scalar(select(ValorCapturado).where(ValorCapturado.periodo == "2026-09")) is None
    )


def test_linea_inexistente_repetida_o_lista_vacia(libro: Libro) -> None:
    libro.aprobar_y_cargar_budget()
    with pytest.raises(CapturaInvalida, match="no pertenece"):
        capturar_actuales(
            libro.db,
            organizacion_id=libro.mundo.org1,
            hotel_id=libro.mundo.hotel_a,
            usuario_id=None,
            valores=[ValorEntrada(10**9, "2026-09", D("1"))],
        )
    with pytest.raises(CapturaInvalida, match="repetido"):
        _capturar(libro, [(9, "2026-09", "1"), (9, "2026-09", "2")])
    with pytest.raises(CapturaInvalida, match="No hay valores"):
        _capturar(libro, [])


def test_el_acumulado_del_tipo_de_cambio_es_el_promedio_y_su_variacion_va_al_reves(
    libro: Libro,
) -> None:
    libro.aprobar_y_cargar_budget()
    r = calcular_variance(libro.db, hotel_id=libro.mundo.hotel_a, periodo="2026-08")
    linea = next(x for x in r.lineas if x.fila_origen == 9)
    cambio = r.resultado[linea.id]
    # mes: Presupuesto − Actual
    assert (cambio.mes.actual, cambio.mes.budget) == (D("17.1337"), D("18"))
    assert cambio.mes.var == D("0.8663")
    # acumulado = promedio de los meses capturados; su Presupuesto = 18
    assert cambio.ytd.actual == (D("17.2175") + D("17.1337")) / 2
    assert cambio.ytd.budget == D("18")


def test_sin_captura_el_tipo_de_cambio_no_tiene_variacion(libro: Libro) -> None:
    libro.aprobar_y_cargar_budget()
    antes = calcular_variance(libro.db, hotel_id=libro.mundo.hotel_a, periodo="2026-09")
    linea = next(x for x in antes.lineas if x.fila_origen == 9)
    assert antes.resultado[linea.id].mes.var is None and linea.id not in antes.capturadas
    assert any("sin cuentas no tienen Actual capturado" in a for a in antes.advertencias)
    _capturar(libro, [(9, "2026-09", "17.0")])
    libro.db.commit()
    despues = calcular_variance(libro.db, hotel_id=libro.mundo.hotel_a, periodo="2026-09")
    assert linea.id in despues.capturadas
    assert despues.resultado[linea.id].mes.actual == D("17.0")
    # el acumulado de septiembre promedia los tres meses
    esperado = (D("17.2175") + D("17.1337") + D("17.0")) / 3
    assert despues.resultado[linea.id].ytd.actual == esperado


# --- API ----------------------------------------------------------------------------------------


def test_api_captura_y_la_vista_la_devuelve(
    cliente: TestClient, mundo: Mundo, libro: Libro
) -> None:
    libro.aprobar_y_cargar_budget()
    ids = _ids(libro)
    base = f"/api/v1/hoteles/{mundo.hotel_a}/budget"
    r = cliente.put(
        f"{base}/capturados",
        json={"valores": [{"linea_id": ids[9], "periodo": "2026-09", "importe": "17.3"}]},
        headers=como(ANALISTA),
    )
    assert r.status_code == 200 and r.json() == {"guardados": 1}
    vista = cliente.get(f"{base}/edicion?ano_fiscal=2026/27", headers=como(ANALISTA)).json()
    cambio = next(x for x in vista["lineas"] if x["linea_id"] == ids[9])
    assert cambio["actual_editable"] is True and cambio["editable"] is True
    sep = next(m for m in cambio["meses"] if m["periodo"] == "2026-09")
    assert D(sep["actual"]) == D("17.3") and sep["actual_origen"] == "manual"
    renta = next(x for x in vista["lineas"] if x["descripcion"] == "Rental Income")
    assert renta["actual_editable"] is False


def test_api_rechaza_lo_no_valido_y_respeta_permisos(
    cliente: TestClient, mundo: Mundo, libro: Libro
) -> None:
    libro.aprobar_y_cargar_budget()
    ids = _ids(libro)
    url = f"/api/v1/hoteles/{mundo.hotel_a}/budget/capturados"

    def cuerpo(linea: int, importe: object = "1") -> dict[str, object]:
        return {"valores": [{"linea_id": linea, "periodo": "2026-09", "importe": importe}]}

    assert cliente.put(url, json=cuerpo(ids[11]), headers=como(ANALISTA)).status_code == 422
    for malo in ("NaN", "Infinity", "1e400"):
        r = cliente.put(url, json=cuerpo(ids[9], malo), headers=como(ANALISTA))
        assert r.status_code == 422, malo
    assert cliente.put(url, json={"valores": []}, headers=como(ANALISTA)).status_code == 422
    ok = cuerpo(ids[9])
    assert cliente.put(url, json=ok, headers=como("responsable_a@test.local")).status_code == 403
    assert cliente.put(url, json=ok).status_code == 401
    assert cliente.put(url, json=ok, headers=como("contralor_c@test.local")).status_code == 404
