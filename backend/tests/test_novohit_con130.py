import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from fpa.ingesta.novohit_con130 import leer_con130, leer_con130_filas

# El Excel real de Torres NO vive en el repositorio. Se busca en la carpeta de documentos
# (o en la ruta de la variable FPA_DATOS_REALES). Si no existe, la prueba se salta.
_CARPETA_DOCUMENTOS = Path(
    os.environ.get(
        "FPA_DATOS_REALES", Path.home() / "Desktop" / "PLATAFORMA FP&A E INTELIGENCIA HOTELERA"
    )
)
BASE_DATOS = _CARPETA_DOCUMENTOS / "BASE DATOS.xlsx"
D = Decimal

# Columnas: G=# ASIENTO/cuenta, H=Fecha, I=Tp.Asiento, J=Oper., K=Tp.Doc., L=Número,
# M=Fecha, N=Concepto, O=Débito, P=Crédito, Q=Saldo (como el export real de Novohit)
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


def fila(
    asiento=None,
    fecha=None,
    tp=None,
    oper=None,
    doc=None,
    numero=None,
    fecha2=None,
    concepto=None,
    debito=None,
    credito=None,
    saldo=None,
):
    return (asiento, fecha, tp, oper, doc, numero, fecha2, concepto, debito, credito, saldo)


def reporte(*cuerpo):
    cabecera = [
        ("Torres Mazatlan S.A. de C.V.", None),
        ("Mayor Analítico (movimientos por cuentas)", None),
        ("Periodo Septiembre 2026 a Septiembre 2026", None),
    ]
    filas = [fila(*(c[0],) + (None,) * 10) for c in cabecera]
    filas.append(ENCABEZADO)
    filas.append(fila("1"))  # título de jerarquía
    filas.append(fila("1000"))
    filas.append(fila("1000001 BANCOS MONEDA NACIONAL"))  # grupo: sin Saldo anterior
    filas.extend(cuerpo)
    return filas


def cuenta_simple():
    return [
        fila("1000001.001  BANBAJIO PS", concepto="Saldo anterior", credito="2,171,953.32"),
        fila(
            "9.2.1",
            "01/09/2026",
            "BANCOS/CAJA",
            "REGISTRO",
            "POLIZA",
            "T0106",
            "01/09/2026",
            "TRASPASO",
            credito=4499993.3,
            saldo=-2328039.98,
        ),
        fila(
            "9.2.2",
            "01/09/2026",
            "BANCOS/CAJA",
            "REGISTRO",
            "POLIZA",
            "D0105",
            "01/09/2026",
            "Dep factura 4474",
            debito=3000000,
            saldo=671960.02,
        ),
        fila(concepto="Total  BANBAJIO PS", debito=3000000, credito="4,499,993.30"),
    ]


def test_clasifica_movimientos_y_omite_titulos_saldos_y_totales():
    r = leer_con130_filas(
        reporte(
            *cuenta_simple(),
            fila(concepto="Total BANCOS MONEDA NACIONAL", debito=3000000, credito=4499993.3),
        )
    )
    assert len(r.movimientos) == 2
    assert [m.asiento for m in r.movimientos] == ["9.2.1", "9.2.2"]
    assert r.movimientos[0].cuenta_codigo == "1000001.001"
    assert r.movimientos[0].cuenta_descripcion == "BANBAJIO PS"
    assert r.movimientos[0].fecha == date(2026, 9, 1)
    assert len(r.totales_grupo) == 1
    assert r.periodo_texto.startswith("Periodo Septiembre 2026")
    assert r.empresa == "Torres Mazatlan S.A. de C.V."


def test_montos_como_texto_con_comas_y_como_numero():
    r = leer_con130_filas(reporte(*cuenta_simple()))
    assert r.movimientos[0].credito == D("4499993.30")
    assert r.total_credito == D("4499993.30")
    assert r.total_debito == D("3000000.00")


def test_saldo_anterior_no_entra_al_calculo_ni_es_movimiento():
    r = leer_con130_filas(reporte(*cuenta_simple()))
    cuenta = r.cuentas["1000001.001"]
    assert cuenta.saldo_anterior == D("2171953.32")
    assert cuenta.suma_debito == D("3000000.00")
    assert cuenta.suma_credito == D("4499993.30")


def test_total_por_cuenta_verificado():
    r = leer_con130_filas(reporte(*cuenta_simple()))
    assert r.cuentas["1000001.001"].total_verificado is True
    assert not [e for e in r.errores if "Total" in e]


def test_detecta_total_que_no_coincide():
    filas = cuenta_simple()
    filas[-1] = fila(concepto="Total  BANBAJIO PS", debito=3000000, credito=4499993.0)
    r = leer_con130_filas(reporte(*filas))
    assert r.cuentas["1000001.001"].total_verificado is False
    assert any("no coincide" in e for e in r.errores)
    assert not r.es_valido


def test_detecta_debito_distinto_de_credito():
    r = leer_con130_filas(reporte(*cuenta_simple()))
    assert not r.cuadra_debito_credito  # la cuenta sola no cuadra
    assert any("distinto de Crédito" in e for e in r.errores)


def test_cuenta_de_ultimo_nivel_sin_punto():
    # algunas cuentas de último nivel no traen subcuenta (ej. 1000003)
    filas = [
        fila("1000003 BANCOS COMPLEMENTARIA DLLS", concepto="Saldo anterior", debito="43,355.71"),
        fila("9.2.15", "08/09/2026", concepto="TRASPASO", debito=144384.3, saldo=187740.01),
        fila("9.2.19", "10/09/2026", concepto="COMISION", credito=18.61, saldo=187721.4),
        fila(concepto="Total BANCOS COMPLEMENTARIA DLLS", debito=144384.3, credito=18.61),
    ]
    r = leer_con130_filas(reporte(*filas))
    assert r.cuentas["1000003"].total_verificado is True
    assert len(r.movimientos) == 2


def test_movimiento_sin_cuenta_abierta_es_error():
    r = leer_con130_filas(reporte(fila("9.2.1", "01/09/2026", concepto="X", debito=10)))
    assert any("sin cuenta abierta" in e for e in r.errores)


def test_cuenta_sin_fila_total_genera_aviso():
    filas = cuenta_simple()[:-1]
    r = leer_con130_filas(reporte(*filas))
    assert r.cuentas["1000001.001"].total_verificado is None
    assert any("no trae fila 'Total'" in e for e in r.avisos)


def test_monto_invalido_es_error():
    r = leer_con130_filas(
        reporte(
            fila("1000003 X", concepto="Saldo anterior", debito=0),
            fila("9.2.1", "01/09/2026", concepto="X", debito="abc"),
        )
    )
    assert any("monto inválido" in e for e in r.errores)


def _cuenta_con_movimiento_sin_importe(saldo_antes, saldo_del_cero):
    return [
        fila("1000001.001  BANCO", concepto="Saldo anterior", credito="0.00"),
        fila("9.2.1", "01/09/2026", concepto="DEP", debito=100, saldo=saldo_antes),
        # Novohit deja en blanco el importe de un movimiento de cero
        fila("9.3.20", "30/09/2026", concepto="AJUSTE EN CERO", saldo=saldo_del_cero),
        fila(concepto="Total  BANCO", debito=100, credito=0),
        # la contrapartida, para que el reporte cuadre (Débito = Crédito)
        fila("4001002.001  INGRESOS", concepto="Saldo anterior", credito="0.00"),
        fila("9.2.1", "01/09/2026", concepto="VENTA", credito=100, saldo=-100),
        fila(concepto="Total  INGRESOS", debito=0, credito=100),
    ]


def test_movimiento_de_importe_cero_se_acepta_como_cero_con_un_aviso():
    r = leer_con130_filas(reporte(*_cuenta_con_movimiento_sin_importe(100, 100)))
    assert r.errores == [] and r.es_valido
    cero = next(m for m in r.movimientos if m.concepto == "AJUSTE EN CERO")
    assert (cero.debito, cero.credito, cero.concepto) == (D("0"), D("0"), "AJUSTE EN CERO")
    assert len(r.movimientos) == 3
    assert len(r.avisos) == 1 and "1 movimientos sin Débito ni Crédito" in r.avisos[0]
    assert r.cuentas["1000001.001"].total_verificado is True


def test_movimiento_sin_importe_pero_con_saldo_que_cambia_es_error():
    # el saldo pasó de 100 a 250 sin importe: se perdió un importe, no se puede cargar
    r = leer_con130_filas(reporte(*_cuenta_con_movimiento_sin_importe(100, 250)))
    assert any("el saldo cambia de 100" in e for e in r.errores)
    assert not r.es_valido


def test_movimiento_sin_importe_al_inicio_de_la_cuenta_se_acepta():
    # sin movimiento anterior no hay con qué comparar el saldo
    r = leer_con130_filas(
        reporte(
            fila("1000001.001  BANCO", concepto="Saldo anterior", credito="0.00"),
            fila("9.3.20", "30/09/2026", concepto="CERO", saldo=0),
            fila(concepto="Total  BANCO", debito=0, credito=0),
        )
    )
    assert r.es_valido and len(r.avisos) == 1


def test_encabezado_con_fecha_desde_hasta_se_toma_como_periodo():
    filas = reporte(*cuenta_simple())
    filas[2] = ("Fecha desde: 01/09/2026 hasta: 30/09/2026, Cuentas [1000001.001]", *filas[2][1:])
    assert leer_con130_filas(filas).periodo_texto.startswith("Fecha desde: 01/09/2026")


def test_sin_encabezado_no_es_con130():
    with pytest.raises(ValueError, match="CON130"):
        leer_con130_filas([("a", "b"), ("c", "d")])


def test_ignora_columnas_auxiliares_a_la_izquierda():
    # BASE DATOS agrega A..F antes de "# ASIENTO"; el lector debe ubicarse por el encabezado
    aux = ("mes", "fecha", "cod", "desc", None, "aux")
    filas = [aux + f for f in reporte(*cuenta_simple())]
    r = leer_con130_filas(filas)
    assert len(r.movimientos) == 2
    assert r.movimientos[0].cuenta_codigo == "1000001.001"


@pytest.mark.skipif(not BASE_DATOS.exists(), reason="BASE DATOS.xlsx no está en la carpeta")
def test_archivo_real_septiembre_2026():
    r = leer_con130(BASE_DATOS)
    assert len(r.movimientos) == 7242
    assert len(r.cuentas) == 366
    assert r.total_debito == r.total_credito == D("57835193.08")
    assert r.errores == [] and r.avisos == []
    assert all(c.total_verificado for c in r.cuentas.values())
    assert min(m.fecha for m in r.movimientos) == date(2026, 9, 1)
    assert max(m.fecha for m in r.movimientos) == date(2026, 9, 30)
    assert r.es_valido


SEPTIEMBRE_XLS = _CARPETA_DOCUMENTOS / "SEPTIEMBRE 2026.xls"
SEPTIEMBRE_XLS_EN_REPO = Path(__file__).resolve().parents[2] / "docs" / "SEPTIEMBRE 2026.xls"
_XLS_REAL = next((p for p in (SEPTIEMBRE_XLS, SEPTIEMBRE_XLS_EN_REPO) if p.exists()), None)


@pytest.mark.skipif(_XLS_REAL is None, reason="SEPTIEMBRE 2026.xls no está disponible")
def test_archivo_real_septiembre_xls_completo():
    from fpa.calidad.evaluacion import evaluar

    r = leer_con130(_XLS_REAL)
    assert r.es_valido and r.errores == []
    assert len(r.movimientos) == 8280 and len(r.cuentas) == 544
    assert r.total_debito == r.total_credito == D("66323973.22")
    assert all(c.total_verificado for c in r.cuentas.values())
    assert len([m for m in r.movimientos if m.debito == 0 and m.credito == 0]) >= 18
    assert any("18 movimientos sin Débito ni Crédito" in a for a in r.avisos)
    assert r.periodo_texto.startswith("Fecha desde: 01/09/2026 hasta: 30/09/2026")
    assert evaluar(r).aprobado
