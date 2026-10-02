"""Prueba dorada de **Mazatlán**: el motor reproduce las hojas `Ago` (agosto) y `Jul-Ago` (julio).

Se carga el Excel real igual que la demostración (movimientos, estructura, reglas, mapeo, Budget
mes a mes y valores capturados) y se compara cada línea con el Actual y el Budget que Contraloría
pegó. Lo que no se reproduce está en `EXCEPCIONES`, cada una con su causa; una diferencia fuera de
esa lista (o una excepción que deje de serlo) hace fallar la prueba. Tolerancia: 0.10 en importes.

El Excel de Mazatlán **no trae acumulado**: el del sistema es julio + agosto, así que se compara
contra la suma de los dos meses del Excel.
"""

import os
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from fpa import demo_agosto
from fpa.config import settings
from fpa.ingesta.variance_mzt import ValoresMes, leer_hojas_mzt, leer_valores_mensuales_mzt
from fpa.modelos import Base
from fpa.repositorios.mapeo import RepositorioMapeo
from fpa.semilla import sembrar_roles, sembrar_torres
from fpa.servicios.variance import ReporteVariance, calcular_variance

D = Decimal
_CARPETA = Path(
    os.environ.get(
        "FPA_DATOS_REALES", Path.home() / "Desktop" / "PLATAFORMA FP&A E INTELIGENCIA HOTELERA"
    )
)
EXCEL = next(
    (
        p
        for p in (_CARPETA / demo_agosto.EXCEL, demo_agosto.DOCS_ADR / demo_agosto.EXCEL)
        if p.exists()
    ),
    None,
)
pytestmark = pytest.mark.skipif(EXCEL is None, reason="No está el Excel real de Mazatlán")

# fila del Excel -> causa. Son 13 de las 693 líneas con cifras.
EXCEPCIONES = {
    # --- el Excel no calcula la línea aunque `Ago!I:O` lista su cuenta ------------------------
    16: "Cleaning Service Income: sin fórmula (el Excel muestra 0); `Ago!I:O` lista la 4002011",
    313: "Non-Deductible: sin fórmula; `Ago!I:O` lista la 6004043 (Excel 0.97 en agosto)",
    314: "Adm Fee 6%: sin fórmula en julio; el Excel pega 102,454.51 y `Ago!I:O` lista 4003001.002",
    # --- la fórmula suma celdas fijas de hojas de cuentas que no están en Base de Datos ---------
    19: "Miscellaneous Taxable: la fórmula resta celdas L5/L12 de hojas ('4002001.007', '6019001')",
    70: "Bank Commissions: la fórmula suma la celda L5 de una cuenta ajena ('6-1-01-100-050')",
    304: "Bank Commissions (otra sección): la fórmula suma la celda L5 de '6019132'",
    308: "Audit Fees: la fórmula suma celdas de cuentas ajenas ('6-0-20-35', '6-1-01-100-500')",
    317: "IVA Taxes 16%: cuentas de pasivo ('2007001', '2-1-70-20') que Base de Datos no trae",
    318: "Income Tax: cuentas de activo ('1005003', '1-1-10-90') que Base de Datos no trae",
    # --- totales que arrastran las anteriores ------------------------------------------------
    32: "Total Other Income: arrastra 16 y 19",
    76: "Total Expenses: arrastra 70",
    78: "Total Mgmt & Check In: arrastra 70",
    319: "Total Other Taxes: arrastra 308, 317 y 318",
}
# Variance (Var y %) que no coincide aunque el Actual y el Budget sí. fila -> causa
EXCEPCIONES_VAR = {
    **dict.fromkeys(
        (92, 175, 214, 272, 315, 326, 327, 332, 378),
        "Sin Budget en el Excel: el Excel muestra Var 0; el motor no inventa un cero (None)",
    ),
    **dict.fromkeys(
        (362, 363, 465, 518, 566, 676, 677, 678, 679, 680, 681, 682, 683, 696, 709, 713),
        "Convención de signo: el Excel usa Actual - Budget; el motor, sin cuentas que lo "
        "indiquen, la toma de la sección (por validar con Contraloría)",
    ),
    **dict.fromkeys(
        (615, 617),
        "Money Exchange: el Var del Excel no es Actual - Budget ni Budget - Actual de sus propias "
        "columnas (arrastra una diferencia del propio Excel)",
    ),
}
# Cuentas con movimiento que el Excel no toma en ninguna línea (hallazgos para Contraloría)
EXCLUIDAS = {"4003001.010", "4003001.020", "4002020"}


@pytest.fixture(scope="module")
def mazatlan() -> Iterator[tuple[sessionmaker[Session], int]]:
    mp = pytest.MonkeyPatch()
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    fabrica = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    mp.setattr(settings, "entorno", "desarrollo")
    mp.setattr(demo_agosto, "SessionLocal", fabrica)
    with fabrica() as db:
        sembrar_roles(db)
        hotel_id = sembrar_torres(db).id
        db.commit()
    demo_agosto.cargar_demo(_CARPETA, imprimir=lambda *_: None)
    yield fabrica, hotel_id
    mp.undo()
    engine.dispose()


def _referencia() -> dict[str, dict[int, ValoresMes]]:
    assert EXCEL is not None
    return leer_valores_mensuales_mzt(leer_hojas_mzt(EXCEL)).por_periodo


def _reporte(mazatlan: tuple[sessionmaker[Session], int], periodo: str) -> ReporteVariance:
    fabrica, hotel_id = mazatlan
    with fabrica() as db:
        return calcular_variance(db, hotel_id=hotel_id, periodo=periodo)


def _cerca(a: Decimal | None, b: Decimal | None) -> bool:
    if a is None or b is None:
        return a is b
    return abs(a - b) <= D("0.10")


@pytest.mark.parametrize("periodo", ["2026-08", "2026-07"])
def test_el_mes_reproduce_actual_y_budget_del_excel(
    mazatlan: tuple[sessionmaker[Session], int], periodo: str
) -> None:
    r = _reporte(mazatlan, periodo)
    referencia = _referencia()[periodo]
    comparadas, distintas = 0, set()
    for linea in r.lineas:
        esperado = referencia.get(linea.fila_origen)
        if esperado is None or esperado.actual is None:
            continue
        if linea.tipo == "informativa" and linea.id not in r.capturadas:
            continue
        comparadas += 1
        mes = r.resultado[linea.id].mes
        if not _cerca(mes.actual, esperado.actual):
            distintas.add(linea.fila_origen)
        if esperado.budget is not None:
            assert _cerca(mes.budget, esperado.budget), f"Budget fila {linea.fila_origen}"
    assert comparadas >= 690
    assert distintas <= set(EXCEPCIONES), (
        f"Diferencias nuevas: {sorted(distintas - set(EXCEPCIONES))}"
    )
    # cada mes explica su parte: ninguna excepción debe ser un falso positivo en ambos meses
    assert distintas, "Si ya no hay diferencias, revisa la lista de excepciones"


def test_ninguna_excepcion_esta_de_mas(mazatlan: tuple[sessionmaker[Session], int]) -> None:
    vistas: set[int] = set()
    for periodo in ("2026-08", "2026-07"):
        r = _reporte(mazatlan, periodo)
        referencia = _referencia()[periodo]
        for linea in r.lineas:
            esperado = referencia.get(linea.fila_origen)
            if (
                esperado is not None
                and esperado.actual is not None
                and (not _cerca(r.resultado[linea.id].mes.actual, esperado.actual))
            ):
                vistas.add(linea.fila_origen)
    assert vistas == set(EXCEPCIONES)


def test_el_acumulado_es_la_suma_de_julio_y_agosto(
    mazatlan: tuple[sessionmaker[Session], int],
) -> None:
    r = _reporte(mazatlan, "2026-08")
    assert r.periodos_ytd == ["2026-07", "2026-08"] and not r.periodos_sin_datos
    jul, ago = _referencia()["2026-07"], _referencia()["2026-08"]
    comparadas = 0
    for linea in r.lineas:
        if linea.tipo == "informativa" or linea.fila_origen in EXCEPCIONES:
            continue
        a, b = jul.get(linea.fila_origen), ago.get(linea.fila_origen)
        if a is None or b is None or a.actual is None or b.actual is None:
            continue
        comparadas += 1
        ytd = r.resultado[linea.id].ytd
        assert _cerca(ytd.actual, a.actual + b.actual), f"Actual YTD fila {linea.fila_origen}"
        if a.budget is not None and b.budget is not None:
            assert _cerca(ytd.budget, a.budget + b.budget), f"Budget YTD fila {linea.fila_origen}"
    assert comparadas >= 600


def test_el_tipo_de_cambio_trae_actual_budget_y_variacion(
    mazatlan: tuple[sessionmaker[Session], int],
) -> None:
    for periodo, actual in (("2026-08", D("17.1337")), ("2026-07", D("17.2175"))):
        r = _reporte(mazatlan, periodo)
        linea = next(x for x in r.lineas if x.fila_origen == 9)
        mes = r.resultado[linea.id].mes
        assert (mes.actual, mes.budget) == (actual, D("18"))
        assert mes.var == D("18") - actual
        assert mes.pct == (D("18") - actual) / D("18")
        assert r.resultado[linea.id].ytd.budget is None  # un tipo de cambio no se acumula


def test_las_cuentas_excluidas_son_las_documentadas(
    mazatlan: tuple[sessionmaker[Session], int],
) -> None:
    fabrica, hotel_id = mazatlan
    with fabrica() as db:
        repo = RepositorioMapeo(db, hotel_id)
        aprobada = repo.aprobada()
        assert aprobada is not None
        assert {e.cuenta_codigo for e in repo.excluidas(aprobada.id)} == EXCLUIDAS


@pytest.mark.parametrize("periodo", ["2026-08", "2026-07"])
def test_variance_y_porcentaje_coinciden_salvo_las_excepciones(
    mazatlan: tuple[sessionmaker[Session], int], periodo: str
) -> None:
    r = _reporte(mazatlan, periodo)
    referencia = _referencia()[periodo]
    distintas: set[int] = set()
    for linea in r.lineas:
        esperado = referencia.get(linea.fila_origen)
        if esperado is None or esperado.var is None or linea.fila_origen in EXCEPCIONES:
            continue
        if linea.tipo == "informativa" and linea.id not in r.capturadas:
            continue
        mes = r.resultado[linea.id].mes
        if (
            mes.var is None
            or abs(mes.var - esperado.var) > D("0.10")
            or (
                esperado.pct is not None
                and (mes.pct is None or abs(mes.pct - esperado.pct) > D("0.0001"))
            )
        ):
            distintas.add(linea.fila_origen)
    assert distintas == set(EXCEPCIONES_VAR), (
        f"Nuevas: {sorted(distintas - set(EXCEPCIONES_VAR))}; "
        f"sobran: {sorted(set(EXCEPCIONES_VAR) - distintas)}"
    )
