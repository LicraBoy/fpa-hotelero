import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from fpa.ingesta.contrato import Fuente, ResultadoLectura
from fpa.ingesta.variance_base_datos import (
    leer_variance_base_datos,
    leer_variance_base_datos_filas,
)

D = Decimal
_CARPETA_DOCUMENTOS = Path(
    os.environ.get(
        "FPA_DATOS_REALES", Path.home() / "Desktop" / "PLATAFORMA FP&A E INTELIGENCIA HOTELERA"
    )
)
VARIANCE = _CARPETA_DOCUMENTOS / "02. VT August 2026 Variance (Envio) (1).xlsx"

# Encabezado como viene en el archivo real: con los caracteres dañados de Débito y Crédito
ENCABEZADO = (
    None,
    "Mes",
    "Fecha",
    "No Cuenta",
    "Nombre de la Cuenta",
    "Asiento - Salida",
    "Concepto - Nombre Articulo",
    "Cantidad",
    "Costo",
    "D�bito",
    "Cr�dito",
)


def fila(
    mes="Agosto",
    fecha=None,
    cuenta="4001002.001",
    nombre="INGRESOS",
    asiento="8.3.1",
    concepto="X",
    cantidad=None,
    costo=None,
    debito=None,
    credito=None,
):  # type: ignore[no-untyped-def]
    fecha = fecha or datetime(2026, 8, 1)
    return (None, mes, fecha, cuenta, nombre, asiento, concepto, cantidad, costo, debito, credito)


def hoja(*cuerpo):  # type: ignore[no-untyped-def]
    return [(None,) * 11, ENCABEZADO, *cuerpo]


def test_lee_movimientos_y_totales() -> None:
    r = leer_variance_base_datos_filas(
        hoja(fila(debito=59.95), fila(cuenta="6009001.001", nombre="SUELDOS", credito=10.5))
    )
    assert r.fuente == Fuente.VARIANCE_BASE_DATOS
    assert len(r.movimientos) == 2
    assert r.total_debito == D("59.95") and r.total_credito == D("10.50")
    assert r.movimientos[0].cuenta_codigo == "4001002.001"
    assert r.movimientos[0].fecha == date(2026, 8, 1)
    assert r.errores == []


def test_no_controla_balance_y_es_valido_aunque_no_cuadre() -> None:
    r = leer_variance_base_datos_filas(hoja(fila(debito=100)))
    assert r.controla_balance is False
    assert not r.cuadra_debito_credito
    assert r.es_valido


def test_encabezado_con_caracteres_daniados_o_correctos() -> None:
    bueno = (*ENCABEZADO[:9], "Débito", "Crédito")
    r = leer_variance_base_datos_filas([bueno, fila(debito=1)])
    assert len(r.movimientos) == 1


def test_sin_encabezado_es_error_claro() -> None:
    with pytest.raises(ValueError, match="Base de Datos"):
        leer_variance_base_datos_filas([("a", "b"), ("c", "d")])


def test_asiento_numerico_de_inventario_se_convierte_a_texto_y_trae_cantidad_y_costo() -> None:
    r = leer_variance_base_datos_filas(
        hoja(fila(cuenta="5001004.001", asiento=12345, cantidad=2.5, costo=10.3333, debito=25.83))
    )
    m = r.movimientos[0]
    assert m.asiento == "12345"
    assert m.cantidad == D("2.5")
    assert m.costo == D("10.3333")  # no se redondea a centavos


def test_codigo_numerico_con_decimales_se_rechaza_por_riesgo_de_ceros_perdidos() -> None:
    r = leer_variance_base_datos_filas(hoja(fila(cuenta=4002001.01, debito=1)))
    assert any("ceros finales" in e for e in r.errores)
    assert r.movimientos == []


def test_codigo_entero_se_acepta_como_texto() -> None:
    r = leer_variance_base_datos_filas(hoja(fila(cuenta=2007003, debito=1)))
    assert r.movimientos[0].cuenta_codigo == "2007003"


def test_codigo_con_guiones_es_valido() -> None:
    r = leer_variance_base_datos_filas(hoja(fila(cuenta="602-0086-000", debito=1)))
    assert r.movimientos[0].cuenta_codigo == "602-0086-000"


def test_fecha_invalida_y_monto_invalido_son_errores() -> None:
    r = leer_variance_base_datos_filas(
        hoja(fila(fecha="no es fecha", debito=1), fila(debito="abc"), fila())
    )
    assert any("fecha inválida" in e for e in r.errores)
    assert any("monto inválido" in e for e in r.errores)
    assert len(r.movimientos) == 1  # solo se conserva la fila sin importe (queda en cero)


def test_movimiento_sin_importe_se_conserva_en_cero_con_aviso() -> None:
    r = leer_variance_base_datos_filas(hoja(fila(concepto="INCENTIVOS CHEF")))
    assert len(r.movimientos) == 1
    assert r.movimientos[0].debito == D("0") and r.movimientos[0].credito == D("0")
    assert r.errores == []
    assert any("sin Débito ni Crédito" in a for a in r.avisos)


def test_mes_en_texto_distinto_al_de_la_fecha_es_aviso_no_error() -> None:
    r = leer_variance_base_datos_filas(hoja(fila(mes="Julio", debito=1)))
    assert len(r.movimientos) == 1
    assert r.errores == []
    assert any("mes en texto distinto" in a for a in r.avisos)


def test_filas_vacias_se_ignoran_y_filas_sin_cuenta_avisan() -> None:
    r = leer_variance_base_datos_filas(
        hoja((None,) * 11, fila(cuenta=None, debito=1), fila(debito=2))
    )
    assert len(r.movimientos) == 1
    assert any("sin No Cuenta" in a for a in r.avisos)


def test_cuenta_con_dos_nombres_avisa() -> None:
    r = leer_variance_base_datos_filas(hoja(fila(nombre="A", debito=1), fila(nombre="B", debito=1)))
    assert any("2 nombres distintos" in a for a in r.avisos)


@pytest.mark.skipif(not VARIANCE.exists(), reason="El Excel del Variance no está en la carpeta")
def test_archivo_real_julio_y_agosto_2026() -> None:
    r: ResultadoLectura = leer_variance_base_datos(VARIANCE)
    assert len(r.movimientos) == 6860
    assert len(r.cuentas) == 296
    assert r.periodos == ["2026-07", "2026-08"]
    por_periodo = {p: sum(1 for m in r.movimientos if m.periodo == p) for p in r.periodos}
    assert por_periodo == {"2026-07": 3583, "2026-08": 3277}
    assert r.total_debito == D("12650614.04")
    assert r.total_credito == D("12037735.88")
    assert not r.cuadra_debito_credito  # es un subconjunto del libro: no debe cuadrar
    assert r.es_valido
    assert r.errores == []
    assert any("4389" in a for a in r.avisos)  # la línea "INCENTIVOS CHEF" de agosto sin importe
    assert {c[0] for c in r.cuentas} == {"4", "5", "6"}  # solo cuentas de resultados
    assert (r.fecha_min, r.fecha_max) == (date(2026, 7, 1), date(2026, 8, 31))
