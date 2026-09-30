import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from fpa.ingesta.contrato import Fuente, Movimiento, ResultadoLectura
from fpa.ingesta.novohit_con130 import leer_con130, leer_con130_filas

D = Decimal
_CARPETA_DOCUMENTOS = Path(
    os.environ.get(
        "FPA_DATOS_REALES", Path.home() / "Desktop" / "PLATAFORMA FP&A E INTELIGENCIA HOTELERA"
    )
)
BASE_DATOS = _CARPETA_DOCUMENTOS / "BASE DATOS.xlsx"

ENCABEZADO = (
    "# ASIENTO",
    "Fecha",
    "Tp.Asiento",
    "Oper.",
    "Tp.Doc.",
    "Número",
    "Fecha",
    "Concepto",
    "Débito",
    "Crédito",
    "Saldo",
)


def _fila(asiento=None, fecha=None, concepto=None, debito=None, credito=None):  # type: ignore[no-untyped-def]
    return (asiento, fecha, None, None, None, None, None, concepto, debito, credito, None)


def _reporte(*cuerpo):  # type: ignore[no-untyped-def]
    return [ENCABEZADO, *cuerpo]


def _mov(debito: str, credito: str, dia: int = 1, mes: int = 9) -> Movimiento:
    return Movimiento(
        cuenta_codigo="1000001.001",
        cuenta_descripcion="BANCO",
        asiento="9.2.1",
        fecha=date(2026, mes, dia),
        concepto="X",
        debito=D(debito),
        credito=D(credito),
        fila=1,
    )


def test_movimiento_tiene_campos_opcionales_y_periodo() -> None:
    m = _mov("10.00", "0.00")
    assert m.cantidad is None and m.costo is None and m.tp_asiento is None
    assert m.periodo == "2026-09"


def test_resultado_calcula_periodos_y_rango_de_fechas() -> None:
    r = ResultadoLectura(
        movimientos=[_mov("5", "0", 3, 8), _mov("0", "5", 20, 9), _mov("1", "1", 1, 8)]
    )
    assert r.periodos == ["2026-08", "2026-09"]
    assert r.fecha_min == date(2026, 8, 1)
    assert r.fecha_max == date(2026, 9, 20)


def test_resultado_vacio_no_tiene_rango() -> None:
    r = ResultadoLectura()
    assert r.periodos == [] and r.fecha_min is None and r.fecha_max is None


def test_fuente_sin_balance_es_valida_aunque_debito_y_credito_difieran() -> None:
    desbalanceado = [_mov("100", "0")]
    assert not ResultadoLectura(movimientos=desbalanceado).es_valido
    assert ResultadoLectura(movimientos=desbalanceado, controla_balance=False).es_valido


def test_un_error_invalida_aunque_no_se_controle_el_balance() -> None:
    r = ResultadoLectura(controla_balance=False, errores=["algo falló"])
    assert not r.es_valido


def test_con130_captura_titulos_de_jerarquia_con_y_sin_descripcion() -> None:
    filas = _reporte(
        _fila("1"),
        _fila("10"),
        _fila("1000"),
        _fila("1000001 BANCOS MONEDA NACIONAL"),
        _fila("1000001.001  BANBAJIO PS", concepto="Saldo anterior", credito="10.00"),
        _fila("9.2.1", "01/09/2026", concepto="MOV", debito=10),
        _fila(concepto="Total  BANBAJIO PS", debito=10, credito="0"),
    )
    r = leer_con130_filas(filas)
    assert [(t.codigo, t.descripcion) for t in r.titulos] == [
        ("1", None),
        ("10", None),
        ("1000", None),
        ("1000001", "BANCOS MONEDA NACIONAL"),
    ]
    # los movimientos y las cuentas no se mezclan con los títulos
    assert len(r.movimientos) == 1
    assert list(r.cuentas) == ["1000001.001"]


def test_con130_reporta_fuente_y_periodos() -> None:
    filas = _reporte(
        _fila("1000001.001  BANCO", concepto="Saldo anterior", debito="1.00"),
        _fila("9.2.1", "01/09/2026", concepto="A", debito=5),
        _fila("9.2.2", "30/09/2026", concepto="B", credito=5),
        _fila(concepto="Total  BANCO", debito=5, credito=5),
    )
    r = leer_con130_filas(filas)
    assert r.fuente == Fuente.CON130
    assert r.periodos == ["2026-09"]
    assert (r.fecha_min, r.fecha_max) == (date(2026, 9, 1), date(2026, 9, 30))
    assert r.es_valido


@pytest.mark.skipif(not BASE_DATOS.exists(), reason="BASE DATOS.xlsx no está en la carpeta")
def test_archivo_real_jerarquia_completa() -> None:
    r = leer_con130(BASE_DATOS)
    assert len(r.titulos) == 145
    assert ("1000001", "BANCOS MONEDA NACIONAL") in {(t.codigo, t.descripcion) for t in r.titulos}
    assert r.periodos == ["2026-09"]
    codigos_titulo = {t.codigo for t in r.titulos}
    # toda cuenta con movimientos tiene algún título ancestro (por prefijo de código)
    sin_ancestro = [
        c for c in r.cuentas if not any(c.startswith(t) and t != c for t in codigos_titulo)
    ]
    assert sin_ancestro == []
    # ninguna cuenta con movimientos es a la vez un título
    assert not (set(r.cuentas) & codigos_titulo)
