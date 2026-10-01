from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from real_agosto import AgostoReal, agosto_real, casi  # noqa: F401

from fpa.calculo.totales import CicloEnReglas, completar_con_totales, evaluar_totales
from fpa.repositorios.plan import RepositorioPlan
from fpa.servicios.actual import actual_del_periodo, actual_ytd_del_periodo

D = Decimal

# --- Casos pequeños ---------------------------------------------------------------------------


def test_completa_base_y_totales() -> None:
    reglas = {3: [(1, 1), (2, 1)], 4: [(3, 1), (5, -1)]}
    todo = completar_con_totales(reglas, {1: D("10"), 2: D("5"), 5: D("2")})
    assert todo == {1: D("10"), 2: D("5"), 5: D("2"), 3: D("15"), 4: D("13")}


def test_totales_anidados_en_cualquier_orden() -> None:
    # 10 depende de 20, que depende de 30: se resuelve por dependencias, no por posición
    reglas = {10: [(20, 1)], 20: [(30, -1), (1, 1)]}
    assert evaluar_totales(reglas, {1: D("7"), 30: D("2")}) == {10: D("5"), 20: D("5")}


def test_la_regla_manda_sobre_el_valor_base() -> None:
    assert completar_con_totales({2: [(1, 1)]}, {1: D("4"), 2: D("999")})[2] == D("4")


def test_total_sin_componentes_con_valor_es_cero() -> None:
    assert evaluar_totales({1: [(2, 1)]}, {}) == {1: D("0")}


def test_ciclo_indirecto_es_error() -> None:
    with pytest.raises(CicloEnReglas):
        evaluar_totales({1: [(2, 1)], 2: [(3, 1)], 3: [(1, 1)]}, {})


valor = st.decimals(min_value=D("-99999999.99"), max_value=D("99999999.99"), places=2)


@given(st.dictionaries(st.integers(1, 6), valor, min_size=1))
def test_un_total_de_suma_es_la_suma_de_sus_partes(base: dict[int, Decimal]) -> None:
    reglas = {100: [(k, 1) for k in base]}
    assert evaluar_totales(reglas, base)[100] == sum(base.values(), D("0"))


@given(st.dictionaries(st.integers(1, 6), valor, min_size=1))
def test_restar_todo_es_el_negativo(base: dict[int, Decimal]) -> None:
    mas = evaluar_totales({100: [(k, 1) for k in base]}, base)[100]
    menos = evaluar_totales({100: [(k, -1) for k in base]}, base)[100]
    assert menos == -mas


# --- Agosto real ------------------------------------------------------------------------------

# Totales que NO cuadran con el Excel (diferencia > 0.05) y por qué. Cada uno viene de una línea
# de detalle que el Base de Datos no puede reproducir (ver `test_variance_dorada`); un total que
# aparezca o desaparezca de esta lista hace fallar la prueba.
#   25  Total Other Income  <- fila 12: el Excel toma celdas puntuales de la hoja de la cuenta
#   294 Total Other Taxes   <- filas 272, 277, 285, 289, 292: cuentas fuera del Base de Datos
#   336, 533, 535, 573      <- arrastran a 294 (y 25 en 533, 535 y 573)
#   451, 495, 497, 507      <- centavos (0.07) que el propio Excel muestra en sus columnas U/V
FILAS_MES_CON_DIFERENCIA = {25, 294, 336, 451, 495, 497, 507, 533, 535, 573}
FILAS_YTD_CON_DIFERENCIA = {294, 336, 533, 535, 573}


def _diferencias(a: AgostoReal, calculado: dict[int, Decimal], campo: str) -> set[int]:
    filas = set()
    for linea in a.lineas:
        valores = a.valores.get(linea.fila_origen)
        if valores is None or linea.id not in a.reglas:
            continue
        esperado = getattr(valores, campo)
        if esperado is not None and not casi(calculado[linea.id], esperado):
            filas.add(linea.fila_origen)
    return filas


def test_totales_de_actual_de_agosto_contra_el_excel(agosto_real: AgostoReal) -> None:  # noqa: F811
    a = agosto_real
    mes = actual_del_periodo(
        a.db, hotel_id=a.hotel_id, periodo="2026-08", version_mapeo_id=a.version_mapeo_id
    )
    ytd = actual_ytd_del_periodo(
        a.db, hotel_id=a.hotel_id, periodo="2026-08", version_mapeo_id=a.version_mapeo_id
    )
    assert ytd.completo
    # incluye Commercial Services (filas 503 a 530: ingresos, gastos y asignaciones)
    assert len(a.reglas) >= 55
    assert _diferencias(a, completar_con_totales(a.reglas, mes), "mes_actual") == (
        FILAS_MES_CON_DIFERENCIA
    )
    assert _diferencias(a, completar_con_totales(a.reglas, ytd.por_linea), "ytd_actual") == (
        FILAS_YTD_CON_DIFERENCIA
    )


def test_commercial_services_cuadra(agosto_real: AgostoReal) -> None:  # noqa: F811
    a = agosto_real
    mes = actual_del_periodo(
        a.db, hotel_id=a.hotel_id, periodo="2026-08", version_mapeo_id=a.version_mapeo_id
    )
    todo = completar_con_totales(a.reglas, mes)
    por_fila = a.por_fila
    for fila, esperado in (
        (508, D("851410.34")),  # Total Income
        (516, D("787399.55")),  # Total Expenses
        (519, D("64010.79")),  # Profit Commercial Services
        (527, D("320158.65")),  # Total Allocations
        (530, D("-256147.86")),  # Net Profit Commercial Services
    ):
        assert casi(todo[por_fila[fila].id], esperado), (fila, todo[por_fila[fila].id])


@pytest.mark.parametrize("campo", ["mes", "ytd", "anual"])
def test_totales_de_budget_identicos_al_excel(agosto_real: AgostoReal, campo: str) -> None:  # noqa: F811
    a = agosto_real
    base = {
        x.linea_id: getattr(x, campo)
        for x in RepositorioPlan(a.db, a.hotel_id).lineas(a.version_plan_id)
        if getattr(x, campo) is not None
    }
    todo = completar_con_totales(a.reglas, base)
    revisadas = 0
    for linea in a.lineas:
        valores = a.valores.get(linea.fila_origen)
        esperado = getattr(valores, f"{campo}_budget", None) if valores else None
        if linea.id in a.reglas and esperado is not None:
            revisadas += 1
            assert casi(todo[linea.id], esperado, "0.01"), (linea.fila_origen, linea.descripcion)
    assert revisadas >= 50
