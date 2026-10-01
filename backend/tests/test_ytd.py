from decimal import Decimal

import pytest
from conftest import Mundo
from hypothesis import given
from hypothesis import strategies as st
from sqlalchemy.orm import Session
from test_versionado_mapeo import Escenario, _mov

from fpa.calculo.ano_fiscal import (
    inicio_ano_fiscal,
    periodos_del_ano_fiscal,
    periodos_ytd,
)
from fpa.calculo.ytd import acumular_ytd
from fpa.servicios.actual import actual_ytd_del_periodo
from fpa.servicios.versionado_mapeo import aprobar

D = Decimal

# --- Periodos ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("periodo", "esperado"),
    [
        ("2026-07", ["2026-07"]),  # primer mes del año fiscal
        ("2026-08", ["2026-07", "2026-08"]),
        ("2026-12", ["2026-07", "2026-08", "2026-09", "2026-10", "2026-11", "2026-12"]),
        ("2027-01", ["2026-07", "2026-08", "2026-09", "2026-10", "2026-11", "2026-12", "2027-01"]),
        ("2027-06", periodos_del_ano_fiscal("2026-07")),  # cierre del año fiscal
    ],
)
def test_periodos_ytd_julio_junio(periodo: str, esperado: list[str]) -> None:
    assert periodos_ytd(periodo) == esperado


def test_cierre_de_ano_fiscal_tiene_doce_meses_y_julio_abre_otro() -> None:
    assert len(periodos_ytd("2027-06")) == 12 and periodos_ytd("2027-06")[0] == "2026-07"
    assert periodos_ytd("2027-07") == ["2027-07"]


def test_ano_fiscal_calendario_es_un_parametro() -> None:
    assert periodos_ytd("2026-03", mes_inicio=1) == ["2026-01", "2026-02", "2026-03"]
    assert inicio_ano_fiscal("2026-08", mes_inicio=1) == "2026-01"


@pytest.mark.parametrize("mes_inicio", [0, 13, -1])
def test_mes_de_inicio_invalido(mes_inicio: int) -> None:
    with pytest.raises(ValueError):
        periodos_ytd("2026-08", mes_inicio=mes_inicio)


@given(st.integers(2000, 2100), st.integers(1, 12), st.integers(1, 12))
def test_propiedades_de_periodos_ytd(anio: int, mes: int, inicio: int) -> None:
    periodo = f"{anio:04d}-{mes:02d}"
    ytd = periodos_ytd(periodo, inicio)
    assert 1 <= len(ytd) <= 12 and ytd[-1] == periodo and ytd == sorted(ytd)
    assert ytd[0] == inicio_ano_fiscal(periodo, inicio)
    assert int(ytd[0][5:]) == inicio
    assert set(ytd) <= set(periodos_del_ano_fiscal(periodo, inicio))
    assert len(periodos_del_ano_fiscal(periodo, inicio)) == 12


# --- Acumulado --------------------------------------------------------------------------------


def test_acumula_linea_por_linea() -> None:
    r = acumular_ytd({"2026-07": {1: D("10"), 2: D("5")}, "2026-08": {1: D("2.50")}}, "2026-08")
    assert r.por_linea == {1: D("12.50"), 2: D("5")}
    assert r.periodos == ["2026-07", "2026-08"] and r.completo


def test_primer_mes_es_igual_al_mes() -> None:
    r = acumular_ytd({"2026-07": {1: D("3")}}, "2026-07")
    assert r.por_linea == {1: D("3")} and r.completo


def test_mes_sin_datos_se_informa_y_no_se_oculta() -> None:
    r = acumular_ytd({"2026-08": {1: D("7")}}, "2026-08")  # falta julio
    assert r.sin_datos == ["2026-07"] and not r.completo
    assert r.por_linea == {1: D("7")}


def test_sin_ningun_dato() -> None:
    r = acumular_ytd({}, "2026-09")
    assert r.por_linea == {} and r.sin_datos == ["2026-07", "2026-08", "2026-09"]


def test_meses_de_otro_ano_fiscal_no_entran() -> None:
    r = acumular_ytd({"2026-06": {1: D("100")}, "2026-07": {1: D("1")}}, "2026-08")
    assert r.por_linea == {1: D("1")}


@given(
    st.lists(
        st.decimals(min_value=D("-1000"), max_value=D("1000"), places=2), min_size=1, max_size=6
    )
)
def test_el_ytd_es_la_suma_de_los_meses(valores: list[Decimal]) -> None:
    periodos = periodos_ytd("2026-12")[: len(valores)]
    r = acumular_ytd({p: {1: v} for p, v in zip(periodos, valores, strict=True)}, periodos[-1])
    assert r.por_linea[1] == sum(valores, D("0"))


# --- Con base de datos ------------------------------------------------------------------------


def test_ytd_desde_la_base_con_un_mes_faltante(db: Session, mundo: Mundo) -> None:
    esc = Escenario(db, mundo, [_mov("4001002.001", "0", "100"), _mov("6009001.001", "30", "0")])
    aprobar(db, version_id=esc.borrador.id, **esc.kw)  # type: ignore[union-attr, arg-type]
    db.commit()
    # Solo hay datos de agosto (2026-08): julio falta
    r = actual_ytd_del_periodo(db, hotel_id=mundo.hotel_a, periodo="2026-08")
    assert r.sin_datos == ["2026-07"]
    assert r.por_linea == {esc.linea("Ingreso"): D("100"), esc.linea("Gasto"): D("30")}
