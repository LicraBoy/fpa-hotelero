"""Lectores del formato de Mazatlán (hojas `Ago` y `Jul-Ago`) con un libro sintético."""

from decimal import Decimal
from pathlib import Path

import pytest

from fpa.datos_reales import archivo_real
from fpa.ingesta.formato_variance import (
    Formato,
    detectar_formato,
    detectar_formato_de_hojas,
)
from fpa.ingesta.variance_estructura import TipoLinea
from fpa.ingesta.variance_mzt import (
    HojasMzt,
    leer_estructura_mzt,
    leer_hojas_mzt,
    leer_mapeo_mzt,
    leer_reglas_mzt,
    leer_valores_mensuales_mzt,
    periodos_de_la_hoja,
)
from tests.mzt_sintetico import crear_libro_mzt


@pytest.fixture
def hojas(tmp_path: Path) -> HojasMzt:
    return leer_hojas_mzt(crear_libro_mzt(tmp_path / "mzt.xlsx"))


def test_detecta_el_formato_por_las_hojas(tmp_path: Path) -> None:
    assert detectar_formato(crear_libro_mzt(tmp_path / "m.xlsx")).formato is Formato.MZT
    assert detectar_formato_de_hojas(["Ago", "Base de Datos"]).formato is Formato.VT
    with pytest.raises(ValueError, match="Ago"):
        detectar_formato_de_hojas(["Otra"])


def test_estructura_trata_celdas_en_blanco_como_secciones(hojas: HojasMzt) -> None:
    est = leer_estructura_mzt(hojas)
    assert est.es_valido
    tipos = {linea.descripcion: linea.tipo for linea in est.lineas}
    assert tipos["Income"] is TipoLinea.SECCION
    assert tipos["Rental Income"] is TipoLinea.DETALLE
    assert tipos["Total Income"] is TipoLinea.TOTAL
    assert tipos["Exchange Rate:"] is TipoLinea.INFORMATIVA


def test_reglas_salen_de_la_columna_j(hojas: HojasMzt) -> None:
    est = leer_estructura_mzt(hojas)
    res = leer_reglas_mzt(hojas, est)
    assert not res.errores
    por_fila = {r.fila_origen: r for r in res.reglas}
    assert set(por_fila) == {13, 16, 17}
    assert [s for _, s in por_fila[17].componentes] == [1, -1]


def test_mapeo_toma_signo_de_la_formula_y_completa_con_la_hoja_ago(hojas: HojasMzt) -> None:
    est = leer_estructura_mzt(hojas)
    res = leer_mapeo_mzt(hojas, est)
    assert not res.errores
    v = {(x.fila_origen, x.cuenta_codigo): x for x in res.vinculos}
    assert v[(11, "4002011")].signo == -1 and v[(11, "4002011")].origen == "excel"
    assert v[(14, "6009001.001")].signo == 1 and v[(14, "6009001.002")].signo == 1
    # Laundry no tiene fórmula: el código viene pegado en Ago y pierde el cero final
    assert v[(12, "4002001.01")].origen == "excel_ago"
    assert v[(12, "4002001.01")].signo == -1
    # una cuenta que la fórmula de otra línea ya suma no se agrega por estar listada en Ago!I:O
    assert (12, "4002011") not in v


def test_periodos_de_la_hoja(hojas: HojasMzt) -> None:
    assert periodos_de_la_hoja(hojas.dos_meses) == ["2026-07", "2026-08"]


def test_valores_mensuales_incluyen_tipo_de_cambio(hojas: HojasMzt) -> None:
    val = leer_valores_mensuales_mzt(hojas).por_periodo
    assert val["2026-08"][9].actual == Decimal("17.1337")
    assert val["2026-08"][9].budget == Decimal("18")
    assert val["2026-07"][9].actual == Decimal("17.2175")
    assert val["2026-08"][11].actual == Decimal("120")
    assert val["2026-07"][14].budget == Decimal("45")


REAL = archivo_real("02. MZT August 2026 Variance (Envio).xlsx")


@pytest.mark.skipif(not REAL.exists(), reason="Excel real de Mazatlán no disponible")
def test_archivo_real_se_lee_completo() -> None:
    assert detectar_formato(REAL).formato is Formato.MZT
    h = leer_hojas_mzt(REAL)
    est = leer_estructura_mzt(h)
    assert est.es_valido and len(est.lineas) == 729
    assert len(leer_reglas_mzt(h, est).reglas) == 57  # 54 totales + 3 líneas con otras líneas
    assert leer_mapeo_mzt(h, est).lineas_vinculadas == 495
    assert periodos_de_la_hoja(h.dos_meses) == ["2026-07", "2026-08"]
