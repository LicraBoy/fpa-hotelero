import os
from decimal import Decimal
from pathlib import Path

import pytest
from conftest import Mundo
from sqlalchemy.orm import Session

from fpa.ingesta.variance_estructura import (
    TipoLinea,
    leer_variance_estructura,
    leer_variance_estructura_filas,
)
from fpa.ingesta.variance_reglas import (
    analizar_formula,
    leer_variance_reglas,
    leer_variance_reglas_filas,
)
from fpa.repositorios.reporte import RepositorioReporte
from fpa.servicios.cargas import DatosArchivo
from fpa.servicios.estructura_reporte import importar_estructura_reporte
from fpa.servicios.reglas_suma import (
    CicloEnReglas,
    evaluar_totales,
    importar_reglas_suma,
    reglas_como_mapa,
)

D = Decimal
_CARPETA = Path(
    os.environ.get(
        "FPA_DATOS_REALES", Path.home() / "Desktop" / "PLATAFORMA FP&A E INTELIGENCIA HOTELERA"
    )
)
VARIANCE = _CARPETA / "02. VT August 2026 Variance (Envio) (1).xlsx"


def fila(b=None, c=None, d=None, s=None):  # type: ignore[no-untyped-def]
    return (None, b, c, d, *([None] * 14), s)


def hoja(*cuerpo):  # type: ignore[no-untyped-def]
    return [
        fila(),
        fila("Account #", "Account Description", "AUGUST"),
        fila(None, None, "Actual"),
        *cuerpo,
    ]


# filas Excel: 4 = detalle, 5 = detalle, 6 = total, 7 = detalle, 8 = resta
EJEMPLO = hoja(
    fila("029-0000-1-000", "Ingreso", 100, "=-'4001'!L1"),
    fila("029-0000-2-000", "Otro", 40, "=-'4002'!L1"),
    fila(None, "T o t a l   I n g r e s o s", 140, "=SUM(S4:S5)"),
    fila("029-0000-3-000", "Gasto", 30, "='6001'!L1"),
    fila(None, "N e t   P r o f i t", 110, "=S6-S7"),
)


def test_analiza_formulas() -> None:
    assert analizar_formula("=SUM(S29:S68)") == [("+", 29, 68)]
    assert analizar_formula("=S69+S70") == [("+", 69, 69), ("+", 70, 70)]
    assert analizar_formula("=+S533-S534") == [("+", 533, 533), ("-", 534, 534)]
    assert analizar_formula("=S9-SUM(S1:S3)") == [("+", 9, 9), ("-", 1, 3)]


@pytest.mark.parametrize("texto", ["=D5-S5", "=S1*2", "=__import__('os')", "texto", "="])
def test_formula_no_reconocida_se_rechaza(texto: str) -> None:
    assert analizar_formula(texto) is None


def test_reglas_sinteticas_reproducen_los_totales() -> None:
    est = leer_variance_estructura_filas(EJEMPLO)
    r = leer_variance_reglas_filas(EJEMPLO, est)
    assert r.es_valido and len(r.reglas) == 2
    por_orden = {x.orden: x for x in est.lineas}
    total, neto = r.reglas
    assert [por_orden[o].descripcion for o, _ in total.componentes] == ["Ingreso", "Otro"]
    assert [s for _, s in neto.componentes] == [1, -1]
    valores = {1: D("100"), 2: D("40"), 4: D("30")}
    out = evaluar_totales({x.orden: x.componentes for x in r.reglas}, valores)
    assert out == {3: D("140"), 5: D("110")}


def test_ciclo_es_error() -> None:
    with pytest.raises(CicloEnReglas):
        evaluar_totales({1: [(2, 1)], 2: [(1, 1)]}, {})


def test_componente_sin_valor_cuenta_cero() -> None:
    assert evaluar_totales({1: [(2, 1), (3, -1)]}, {2: D("5")}) == {1: D("5")}


def test_total_sin_formula_queda_sin_regla_con_aviso() -> None:
    cuerpo = hoja(
        fila("029-0000-1-000", "X", 1, "='4001'!L1"), fila(None, "T o t a l   X", 1, None)
    )
    r = leer_variance_reglas_filas(cuerpo, leer_variance_estructura_filas(cuerpo))
    assert r.reglas == [] and any("sin fórmula" in a for a in r.avisos)


def test_importar_reglas_en_base_y_reemplazo(db: Session, mundo: Mundo) -> None:
    est = leer_variance_estructura_filas(EJEMPLO)
    res = importar_estructura_reporte(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        resultado=est,
        archivo=DatosArchivo(nombre="v.xlsx", sha256="a" * 64),
    )
    version = res.version
    assert version is not None
    leidas = leer_variance_reglas_filas(EJEMPLO, est)
    for _ in range(2):  # reimportar es idempotente
        n = importar_reglas_suma(
            db,
            organizacion_id=mundo.org1,
            hotel_id=mundo.hotel_a,
            usuario_id=None,
            version=version,
            leidas=leidas,
        )
        assert n == 2
    db.commit()
    repo = RepositorioReporte(db, mundo.hotel_a)
    assert len(repo.reglas(version.id)) == 4
    por_id = {x.id: x for x in repo.lineas(version.id)}
    valores = {
        x.id: D(v)
        for x, v in zip(repo.lineas(version.id), ["100", "40", "0", "30", "0"], strict=True)
    }
    out = evaluar_totales(reglas_como_mapa(db, mundo.hotel_a, version.id), valores)
    assert {por_id[k].descripcion: v for k, v in out.items()} == {
        "Total Ingresos": D("140"),
        "Net Profit": D("110"),
    }
    assert RepositorioReporte(db, mundo.hotel_b).reglas(version.id) == []


@pytest.mark.skipif(not VARIANCE.exists(), reason="No está el Excel real del Variance")
def test_hoja_ago_real_reproduce_todos_los_totales() -> None:
    import openpyxl

    est = leer_variance_estructura(VARIANCE)
    reg = leer_variance_reglas(VARIANCE)
    assert reg.es_valido and len(reg.reglas) >= 40
    wb = openpyxl.load_workbook(VARIANCE, read_only=True, data_only=True)
    try:
        filas = [tuple(r) for r in wb["Ago"].iter_rows(max_col=4, values_only=True)]
    finally:
        wb.close()
    pegado = {
        x.orden: D(str(filas[x.fila_origen - 1][3] or 0))
        for x in est.lineas
        if x.tipo is not TipoLinea.SECCION
    }
    reglas = {x.orden: x.componentes for x in reg.reglas}
    calculado = evaluar_totales(reglas, pegado)
    for orden, valor in calculado.items():
        assert abs(valor - pegado[orden]) < D("0.05"), (orden, valor, pegado[orden])
