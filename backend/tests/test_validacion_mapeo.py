import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from conftest import Mundo
from sqlalchemy.orm import Session

from fpa.ingesta.contrato import Fuente, ResultadoLectura
from fpa.ingesta.contrato import Movimiento as MovimientoLeido
from fpa.ingesta.variance_base_datos import leer_variance_base_datos
from fpa.ingesta.variance_estructura import (
    leer_variance_estructura,
    leer_variance_estructura_filas,
)
from fpa.ingesta.variance_mapeo import leer_variance_mapeo, leer_variance_mapeo_filas
from fpa.modelos.catalogo import CuentaLocal
from fpa.servicios.cargar_archivo import Resolucion, cargar_archivo
from fpa.servicios.cargas import DatosArchivo
from fpa.servicios.estructura_reporte import importar_estructura_reporte
from fpa.servicios.mapeo import importar_mapeo
from fpa.servicios.validacion_mapeo import validar_mapeo

D = Decimal
_CARPETA = Path(
    os.environ.get(
        "FPA_DATOS_REALES", Path.home() / "Desktop" / "PLATAFORMA FP&A E INTELIGENCIA HOTELERA"
    )
)
VARIANCE = _CARPETA / "02. VT August 2026 Variance (Envio) (1).xlsx"
CATALOGO = _CARPETA / "Catalogo de cuentas.xls"


def fila(b=None, c=None, d=None, s=None, t=None):  # type: ignore[no-untyped-def]
    return (None, b, c, d, *([None] * 14), s, t)


EJEMPLO = [
    fila(),
    fila("Account #", "Account Description", "AUGUST"),
    fila(None, None, "Actual"),
    fila("029-0000-1-000", "Ingreso", 100, "=-'4001002.001'!L5", None),
    fila("029-0000-2-000", "Gasto A", 30, "='6009001.001'!L9", None),
    fila("029-0000-3-000", "Gasto B", 30, "='6009001.001'!L9", None),  # misma cuenta, otra línea
    fila("029-0000-4-000", "Vacía", 0, None, None),
]


def _movimiento(cuenta: str, debito: str, credito: str, dia: int = 5) -> MovimientoLeido:
    return MovimientoLeido(
        cuenta_codigo=cuenta,
        cuenta_descripcion=f"Cuenta {cuenta}",
        asiento="8.1.1",
        fecha=date(2026, 8, dia),
        concepto="x",
        debito=D(debito),
        credito=D(credito),
        fila=dia,
    )


def _cargar(db: Session, mundo: Mundo, movimientos: list[MovimientoLeido]) -> None:
    r = ResultadoLectura(fuente=Fuente.VARIANCE_BASE_DATOS, controla_balance=False)
    r.movimientos = movimientos
    res = cargar_archivo(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        resultado=r,
        archivo=DatosArchivo(nombre="m.xlsx", sha256="m" * 64),
    )
    assert res.resolucion is Resolucion.CREADA
    db.commit()


def _mapeo(db: Session, mundo: Mundo, filas=EJEMPLO):  # type: ignore[no-untyped-def]
    est = leer_variance_estructura_filas(filas)
    ver = importar_estructura_reporte(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        resultado=est,
        archivo=DatosArchivo(nombre="v.xlsx", sha256="a" * 64),
    ).version
    assert ver is not None
    res = importar_mapeo(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        version_estructura=ver,
        leido=leer_variance_mapeo_filas(filas, est),
        archivo=DatosArchivo(nombre="v.xlsx", sha256="a" * 64),
    )
    assert res.version is not None
    db.commit()
    return res.version


def test_todo_mapeado_es_aprobable_y_se_informa_lo_demas(db: Session, mundo: Mundo) -> None:
    _cargar(
        db,
        mundo,
        [
            _movimiento("4001002.001", "0", "100"),
            _movimiento("6009001.001", "60", "0"),
            _movimiento("1000001", "5", "0"),  # clase 1: no es de resultados, se ignora
        ],
    )
    version = _mapeo(db, mundo)
    r = validar_mapeo(db, hotel_id=mundo.hotel_a, version_mapeo_id=version.id, periodo="2026-08")
    assert r.aprobable and r.bloqueantes == [] and r.sin_mapear == []
    assert r.cuentas_con_movimiento == 2 and r.cuentas_mapeadas == 2
    assert (
        list(r.en_varias_lineas) == ["6009001.001"] and len(r.en_varias_lineas["6009001.001"]) == 2
    )
    assert r.sin_catalogo == []  # la carga de movimientos ya los dio de alta en el catálogo
    assert len(r.lineas_sin_cuentas) == 1


def test_cuenta_con_movimiento_sin_vinculo_bloquea(db: Session, mundo: Mundo) -> None:
    _cargar(
        db,
        mundo,
        [_movimiento("4001002.001", "0", "100"), _movimiento("6099999", "12.50", "0")],
    )
    version = _mapeo(db, mundo)
    r = validar_mapeo(db, hotel_id=mundo.hotel_a, version_mapeo_id=version.id, periodo="2026-08")
    assert not r.aprobable
    assert [(c.cuenta_codigo, c.neto) for c in r.sin_mapear] == [("6099999", D("12.50"))]
    assert "1 cuentas" in r.bloqueantes[0]
    assert r.a_dict()["sin_mapear"][0]["neto"] == "12.50"


def test_cuenta_con_neto_cero_no_bloquea(db: Session, mundo: Mundo) -> None:
    _cargar(
        db,
        mundo,
        [_movimiento("6099999", "10", "0", 5), _movimiento("6099999", "0", "10", 6)],
    )
    version = _mapeo(db, mundo)
    assert validar_mapeo(
        db, hotel_id=mundo.hotel_a, version_mapeo_id=version.id, periodo="2026-08"
    ).aprobable


def test_discrepancia_de_signo_se_informa(db: Session, mundo: Mundo) -> None:
    db.add(
        CuentaLocal(
            hotel_id=mundo.hotel_a,
            codigo="4001002.001",
            clase="4",
            con_movimientos=True,
            origen="prueba",
            tipo="Deudor",  # el mapeo la resta: discrepa
        )
    )
    db.flush()
    version = _mapeo(db, mundo)
    r = validar_mapeo(db, hotel_id=mundo.hotel_a, version_mapeo_id=version.id, periodo="2026-08")
    assert [d["cuenta_codigo"] for d in r.discrepancias_signo] == ["4001002.001"]


def test_version_de_otro_hotel_no_existe(db: Session, mundo: Mundo) -> None:
    version = _mapeo(db, mundo)
    with pytest.raises(LookupError):
        validar_mapeo(db, hotel_id=mundo.hotel_b, version_mapeo_id=version.id, periodo="2026-08")


@pytest.mark.skipif(
    not (VARIANCE.exists() and CATALOGO.exists()), reason="No están los Excel reales"
)
def test_agosto_real_no_deja_cuentas_con_actual_sin_vinculo(db: Session, mundo: Mundo) -> None:
    from fpa.ingesta.novohit_con020 import leer_con020
    from fpa.servicios.catalogo_oficial import importar_catalogo

    importar_catalogo(db, hotel_id=mundo.hotel_a, catalogo=leer_con020(CATALOGO))
    lectura = leer_variance_base_datos(VARIANCE)
    res = cargar_archivo(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        resultado=lectura,
        archivo=DatosArchivo(nombre=VARIANCE.name, sha256="r" * 64),
    )
    assert res.resolucion is Resolucion.CREADA
    est = leer_variance_estructura(VARIANCE)
    version_est = importar_estructura_reporte(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        resultado=est,
        archivo=DatosArchivo(nombre=VARIANCE.name, sha256="r" * 64),
    ).version
    assert version_est is not None
    version = importar_mapeo(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        version_estructura=version_est,
        leido=leer_variance_mapeo(VARIANCE),
        archivo=DatosArchivo(nombre=VARIANCE.name, sha256="r" * 64),
    ).version
    assert version is not None
    db.commit()
    for periodo in ("2026-07", "2026-08"):
        r = validar_mapeo(db, hotel_id=mundo.hotel_a, version_mapeo_id=version.id, periodo=periodo)
        assert r.cuentas_con_movimiento > 100
        # Hallazgo real para Contraloría: estas dos cuentas tienen movimiento (4003003 es de unos
        # 3 millones al mes) y NINGUNA línea de la hoja `Ago` las toma. Si algún día se mapean,
        # esta prueba debe actualizarse.
        assert [c.cuenta_codigo for c in r.sin_mapear] == ["4002013", "4003003"]
        assert r.discrepancias_signo == []
