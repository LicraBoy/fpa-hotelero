from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from real_agosto import AgostoReal, agosto_real, casi  # noqa: F401

from fpa.calculo.variance import (
    Convencion,
    LineaParaConvencion,
    deducir_convenciones,
    variance,
    variance_pct,
)
from fpa.repositorios.mapeo import RepositorioMapeo

D = Decimal
ING = Convencion.REAL_MENOS_PRESUPUESTO
GASTO = Convencion.PRESUPUESTO_MENOS_REAL

# --- Variance ---------------------------------------------------------------------------------


def test_ingreso_es_real_menos_presupuesto() -> None:
    assert variance(D("120"), D("100"), ING) == D("20")  # vendió más: favorable


def test_gasto_es_presupuesto_menos_real() -> None:
    assert variance(D("120"), D("100"), GASTO) == D("-20")  # gastó más: desfavorable


def test_sin_budget_no_hay_variance_ni_porcentaje() -> None:
    assert variance(D("5"), None, ING) is None
    assert variance_pct(None, D("5")) is None
    assert variance_pct(D("5"), None) is None


# --- Variance % -------------------------------------------------------------------------------


def test_porcentaje_normal() -> None:
    assert variance_pct(D("25"), D("100")) == D("0.25")
    assert variance_pct(D("-25"), D("100")) == D("-0.25")


def test_porcentaje_usa_el_valor_absoluto_del_budget() -> None:
    # Fila 530 del Excel: Budget −36,672 y Var −219,475 dan −5.98, no +5.98
    assert variance_pct(D("-219475.364413557"), D("-36672.4955864428")) == pytest.approx(
        D("-5.98474"), abs=D("0.00001")
    )


@pytest.mark.parametrize(
    ("var", "esperado"), [(D("10"), D("1")), (D("-10"), D("-1")), (D("0"), D("0"))]
)
def test_presupuesto_cero_devuelve_un_valor_definido_no_error(
    var: Decimal, esperado: Decimal
) -> None:
    assert variance_pct(var, D("0")) == esperado
    assert variance_pct(var, D("0.00")) == esperado


@given(
    st.decimals(min_value=D("-1e9"), max_value=D("1e9"), places=2),
    st.decimals(min_value=D("-1e9"), max_value=D("1e9"), places=2),
)
def test_el_porcentaje_siempre_es_un_numero(actual: Decimal, budget: Decimal) -> None:
    for conv in Convencion:
        pct = variance_pct(variance(actual, budget, conv), budget)
        assert pct is not None and pct.is_finite()


@given(st.decimals(min_value=D("-1e9"), max_value=D("1e9"), places=2))
def test_iguales_dan_cero(valor: Decimal) -> None:
    assert variance(valor, valor, ING) == 0 and variance(valor, valor, GASTO) == 0
    assert variance_pct(variance(valor, valor, ING), valor) == 0


@given(
    st.decimals(min_value=D("-1e9"), max_value=D("1e9"), places=2),
    st.decimals(min_value=D("-1e9"), max_value=D("1e9"), places=2),
)
def test_las_dos_convenciones_son_opuestas(actual: Decimal, budget: Decimal) -> None:
    assert variance(actual, budget, ING) == -variance(actual, budget, GASTO)  # type: ignore[operator]


# --- Deducción de la convención ---------------------------------------------------------------


def L(id_: int, tipo: str, seccion: int | None = 1) -> LineaParaConvencion:
    return LineaParaConvencion(id_, tipo, seccion)


def test_detalle_se_deduce_de_los_signos_de_sus_cuentas() -> None:
    lineas = [L(1, "seccion", None), L(2, "detalle"), L(3, "detalle")]
    r = deducir_convenciones(lineas, {2: [("4001", -1), ("4002", -1)], 3: [("6001", 1)]}, {})
    assert r == {2: ING, 3: GASTO}


def test_una_cuenta_de_pasivo_no_vuelve_ingreso_a_la_linea() -> None:
    # IVA por pagar (clase 2, Acreedor): el reporte lo trata como gasto
    lineas = [L(1, "seccion", None), L(2, "detalle")]
    assert deducir_convenciones(lineas, {2: [("2007003", -1)]}, {})[2] == GASTO


def test_detalle_sin_cuentas_sigue_a_su_seccion() -> None:
    lineas = [L(1, "seccion", None), L(2, "detalle"), L(3, "detalle"), L(4, "detalle")]
    r = deducir_convenciones(lineas, {2: [("4001", -1)], 3: [("4002", -1)]}, {})
    assert r[4] == ING  # la sección es de ingresos
    sola = deducir_convenciones([L(1, "seccion", None), L(2, "detalle")], {}, {})
    assert sola[2] == GASTO  # sin información: gasto


def test_total_sigue_a_su_primer_componente_positivo() -> None:
    lineas = [
        L(1, "seccion", None),
        L(2, "detalle"),  # ingreso
        L(3, "detalle"),  # gasto
        L(4, "subtotal"),  # 4 = 2 - 3  (utilidad: sigue al ingreso)
        L(5, "total"),  # 5 = 3 - 2  (sigue al gasto, aunque el ingreso aparezca antes)
    ]
    reglas = {4: [(2, 1), (3, -1)], 5: [(2, -1), (3, 1)]}
    r = deducir_convenciones(lineas, {2: [("4001", -1)], 3: [("6001", 1)]}, reglas)
    assert (r[4], r[5]) == (ING, GASTO)


def test_totales_anidados() -> None:
    lineas = [L(1, "seccion", None), L(2, "detalle"), L(3, "subtotal"), L(4, "total")]
    r = deducir_convenciones(lineas, {2: [("4001", -1)]}, {3: [(2, 1)], 4: [(3, 1)]})
    assert (r[3], r[4]) == (ING, ING)


def test_las_excepciones_mandan_y_las_secciones_no_tienen_convencion() -> None:
    lineas = [L(1, "seccion", None), L(2, "detalle")]
    r = deducir_convenciones(lineas, {2: [("4001", -1)]}, {}, excepciones={2: GASTO})
    assert r == {2: GASTO}


# --- Agosto real: la deducción coincide con lo que hace el Excel ------------------------------


def test_la_convencion_deducida_coincide_con_el_excel(agosto_real: AgostoReal) -> None:  # noqa: F811
    a = agosto_real
    signos: dict[int, list[tuple[str, int]]] = {}
    for v in RepositorioMapeo(a.db, a.hotel_id).vinculos(a.version_mapeo_id):
        signos.setdefault(v.linea_id, []).append((v.cuenta_codigo, v.signo))
    convs = deducir_convenciones(
        [LineaParaConvencion(x.id, x.tipo, x.seccion_id) for x in a.lineas], signos, a.reglas
    )
    revisadas, fallas = 0, []
    for linea in a.lineas:
        v = a.valores.get(linea.fila_origen)
        if linea.tipo == "seccion" or v is None:
            continue
        for actual, budget, var in (
            (v.mes_actual, v.mes_budget, v.mes_var),
            (v.ytd_actual, v.ytd_budget, v.ytd_var),
        ):
            if None in (actual, budget, var) or casi(actual, budget, "0.005"):
                continue  # si Actual = Budget el signo no se distingue
            revisadas += 1
            esperado = variance(actual, budget, convs[linea.id])  # type: ignore[arg-type]
            if not casi(esperado, var, "0.01"):
                fallas.append((linea.fila_origen, linea.descripcion, str(var), str(esperado)))
    assert revisadas > 600
    # Únicas diferencias con el Excel, ambas conocidas:
    #  - fila 8: es el tipo de cambio, no dinero;
    #  - fila 344 (Telephone Profit): el Excel la calcula como gasto (Budget − Actual) aunque
    #    sea una utilidad. Se corrige con `excepciones` si Contraloría confirma que es intencional.
    assert {f[0] for f in fallas} == {8, 344}, fallas
