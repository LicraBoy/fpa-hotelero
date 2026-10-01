from collections import defaultdict
from decimal import Decimal

import pytest
from conftest import Mundo
from hypothesis import given
from hypothesis import strategies as st
from sqlalchemy.orm import Session
from test_versionado_mapeo import Escenario, _mov

from fpa.calculo.actual import calcular_actual
from fpa.servicios.actual import actual_del_periodo
from fpa.servicios.versionado_mapeo import aprobar

D = Decimal

# --- Casos pequeños ---------------------------------------------------------------------------


def test_ingreso_acreedor_resulta_positivo_y_gasto_deudor_tambien() -> None:
    netos = {"4001": D("-100"), "6001": D("30")}  # neto = Débito - Crédito
    assert calcular_actual([(1, "4001", -1), (2, "6001", 1)], netos) == {1: D("100"), 2: D("30")}


def test_una_linea_con_varias_cuentas_suma_con_sus_signos() -> None:
    netos = {"A": D("-10"), "B": D("4"), "C": D("1.50")}
    assert calcular_actual([(1, "A", -1), (1, "B", 1), (1, "C", 1)], netos) == {1: D("15.50")}


def test_sin_movimiento_es_cero_y_se_conserva_la_linea() -> None:
    assert calcular_actual([(1, "A", 1)], {}) == {1: D("0")}


def test_cuenta_en_dos_lineas_cuenta_en_ambas() -> None:
    assert calcular_actual([(1, "A", 1), (2, "A", -1)], {"A": D("7")}) == {1: D("7"), 2: D("-7")}


def test_cuenta_sin_vinculo_no_aparece() -> None:
    assert calcular_actual([(1, "A", 1)], {"A": D("1"), "Z": D("999")}) == {1: D("1")}


def test_sin_vinculos_no_hay_resultado() -> None:
    assert calcular_actual([], {"A": D("1")}) == {}


@pytest.mark.parametrize("signo", [0, 2, -3])
def test_signo_invalido_es_error(signo: int) -> None:
    with pytest.raises(ValueError):
        calcular_actual([(1, "A", signo)], {"A": D("1")})


# --- Propiedades ------------------------------------------------------------------------------

monto = st.decimals(min_value=D("-99999999.99"), max_value=D("99999999.99"), places=2)
cuenta = st.sampled_from(["A", "B", "C", "D"])
vinculo = st.tuples(st.integers(1, 5), cuenta, st.sampled_from([1, -1]))


@given(st.lists(vinculo), st.dictionaries(cuenta, monto))
def test_invertir_todos_los_signos_invierte_el_resultado(vinculos, netos) -> None:  # type: ignore[no-untyped-def]
    normal = calcular_actual(vinculos, netos)
    inverso = calcular_actual([(lin, c, -s) for lin, c, s in vinculos], netos)
    assert {k: -v for k, v in normal.items()} == inverso


@given(st.lists(vinculo), st.dictionaries(cuenta, monto))
def test_la_suma_de_las_lineas_es_la_suma_con_signo_de_los_vinculos(vinculos, netos) -> None:  # type: ignore[no-untyped-def]
    esperado = sum((s * netos.get(c, D("0")) for _, c, s in vinculos), D("0"))
    assert sum(calcular_actual(vinculos, netos).values(), D("0")) == esperado


@given(st.lists(vinculo), st.dictionaries(cuenta, monto))
def test_el_orden_de_entrada_no_importa(vinculos, netos) -> None:  # type: ignore[no-untyped-def]
    assert calcular_actual(vinculos, netos) == calcular_actual(list(reversed(vinculos)), netos)


@given(st.lists(vinculo), st.dictionaries(cuenta, monto), st.dictionaries(cuenta, monto))
def test_es_lineal_en_los_netos(vinculos, a, b) -> None:  # type: ignore[no-untyped-def]
    suma: dict[str, Decimal] = defaultdict(lambda: D("0"))
    for origen in (a, b):
        for k, v in origen.items():
            suma[k] += v
    ra, rb = calcular_actual(vinculos, a), calcular_actual(vinculos, b)
    assert calcular_actual(vinculos, suma) == {k: ra[k] + rb[k] for k in ra}


# --- Con base de datos ------------------------------------------------------------------------


def test_servicio_lee_saldos_y_el_mapeo_aprobado(db: Session, mundo: Mundo) -> None:
    esc = Escenario(db, mundo, [_mov("4001002.001", "0", "100"), _mov("6009001.001", "30", "0")])
    aprobar(db, version_id=esc.borrador.id, **esc.kw)  # type: ignore[union-attr, arg-type]
    db.commit()
    esperado = {esc.linea("Ingreso"): D("100"), esc.linea("Gasto"): D("30")}
    assert actual_del_periodo(db, hotel_id=mundo.hotel_a, periodo="2026-08") == esperado
    sin_datos = actual_del_periodo(db, hotel_id=mundo.hotel_a, periodo="2026-09")
    assert sin_datos == {k: D("0") for k in esperado}


def test_sin_mapeo_aprobado_es_error(db: Session, mundo: Mundo) -> None:
    with pytest.raises(LookupError, match="mapeo aprobado"):
        actual_del_periodo(db, hotel_id=mundo.hotel_a, periodo="2026-08")
    with pytest.raises(LookupError):
        actual_del_periodo(db, hotel_id=mundo.hotel_b, periodo="2026-08", version_mapeo_id=999)
