import os
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from conftest import Mundo
from sqlalchemy.orm import Session
from xls_sintetico import catalogo_basico

from fpa.ingesta.contrato import Cuenta, Fuente, ResultadoLectura
from fpa.ingesta.contrato import Movimiento as MovimientoLeido
from fpa.ingesta.novohit_con020 import leer_con020, leer_con020_filas
from fpa.ingesta.novohit_con130 import leer_con130
from fpa.ingesta.variance_base_datos import leer_variance_base_datos
from fpa.repositorios.catalogo import RepositorioCatalogo
from fpa.servicios.cargar_archivo import cargar_archivo
from fpa.servicios.cargas import DatosArchivo
from fpa.servicios.catalogo_oficial import importar_catalogo

D = Decimal
_CARPETA_DOCUMENTOS = Path(
    os.environ.get(
        "FPA_DATOS_REALES", Path.home() / "Desktop" / "PLATAFORMA FP&A E INTELIGENCIA HOTELERA"
    )
)
CATALOGO = _CARPETA_DOCUMENTOS / "Catalogo de cuentas.xls"
CON130 = _CARPETA_DOCUMENTOS / "BASE DATOS.xlsx"
VARIANCE = _CARPETA_DOCUMENTOS / "02. VT August 2026 Variance (Envio) (1).xlsx"


def importar(db: Session, hotel_id: int, filas: list[list[str]] | None = None):  # type: ignore[no-untyped-def]
    catalogo = leer_con020_filas(filas if filas is not None else catalogo_basico())
    assert catalogo.errores == []
    resumen = importar_catalogo(db, hotel_id=hotel_id, catalogo=catalogo)
    db.commit()
    return resumen


def mov(cuenta: str, descripcion: str = "D", fila: int = 1) -> MovimientoLeido:
    return MovimientoLeido(
        cuenta_codigo=cuenta,
        cuenta_descripcion=descripcion,
        asiento="8.3.1",
        fecha=date(2026, 8, 10),
        concepto="X",
        debito=D("1.00"),
        credito=D("0"),
        fila=fila,
    )


def cargar(db: Session, mundo: Mundo, movs: list[MovimientoLeido], sha: str = "a" * 64):  # type: ignore[no-untyped-def]
    lectura = ResultadoLectura(
        fuente=Fuente.VARIANCE_BASE_DATOS,
        controla_balance=False,
        movimientos=movs,
        cuentas={m.cuenta_codigo: Cuenta(m.cuenta_codigo, m.cuenta_descripcion, 1) for m in movs},
    )
    r = cargar_archivo(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        resultado=lectura,
        archivo=DatosArchivo("x.xlsx", sha),
    )
    db.commit()
    return r


def control(resultado: Any, codigo: str) -> dict[str, Any] | None:
    controles = resultado.cargas[0].controles["controles"]
    return next((c for c in controles if c["codigo"] == codigo), None)


def test_importa_titulos_y_cuentas_con_su_jerarquia(db: Session, mundo: Mundo) -> None:
    resumen = importar(db, mundo.hotel_a)
    assert (resumen.total_titulos, resumen.total_cuentas) == (6, 5)
    assert resumen.creadas == 11 and resumen.hubo_cambios
    cat = RepositorioCatalogo(db, mundo.hotel_a).por_codigo()

    assert (cat["4"].descripcion, cat["4"].nivel, cat["4"].padre_codigo) == ("INGRESOS", 0, None)
    assert cat["4"].es_titulo and cat["4"].en_catalogo_oficial and cat["4"].tipo is None
    assert (cat["4001"].padre_codigo, cat["4001"].nivel) == ("40", 2)

    base = cat["4001002"]  # cuenta base con subcuenta = grupo
    assert (base.padre_codigo, base.nivel, base.tipo) == ("4001", 3, "Acreedor")
    assert base.es_titulo and base.auxiliar and not base.con_movimientos

    sub = cat["4001002.001"]
    assert (sub.padre_codigo, sub.nivel, sub.clase) == ("4001002", 4, "4")
    assert (sub.tipo, sub.grupo_ef, sub.depto_ef, sub.depto_ti) == (
        "Acreedor",
        "INCOME",
        "BAR",
        "CENTRO INGRESO",
    )
    assert sub.cuenta_sat == "401.01 Ventas" and sub.activa and not sub.es_titulo

    sueldos = cat["6009001.001"]
    assert (sueldos.tipo, sueldos.depto_ef, sueldos.padre_codigo) == (
        "Deudor",
        "MGT & CHECK IN",
        "6009001",
    )
    inactiva = cat["6009002"]
    assert inactiva.descripcion == "SERVICIO A DUEÑOS" and not inactiva.activa
    assert inactiva.padre_codigo == "6009" and not inactiva.es_titulo


def test_importar_dos_veces_no_cambia_nada(db: Session, mundo: Mundo) -> None:
    importar(db, mundo.hotel_a)
    otra = importar(db, mundo.hotel_a)
    assert not otra.hubo_cambios
    assert (otra.creadas, otra.actualizadas, otra.sin_cambio) == (0, 0, 11)


def test_el_catalogo_oficial_completa_lo_que_ya_estaba_por_movimientos(
    db: Session, mundo: Mundo
) -> None:
    cargar(
        db,
        mundo,
        [mov("4001002.001", "NOMBRE DE MOVIMIENTO"), mov("9999999", "SOLO MOVIMIENTOS", 2)],
    )
    antes = RepositorioCatalogo(db, mundo.hotel_a).por_codigo()
    assert antes["4001002.001"].sin_jerarquia and antes["4001002.001"].tipo is None

    resumen = importar(db, mundo.hotel_a)
    cat = RepositorioCatalogo(db, mundo.hotel_a).por_codigo()
    sub = cat["4001002.001"]
    assert sub.con_movimientos and sub.en_catalogo_oficial  # conserva sus movimientos
    assert sub.descripcion == "INGRESOS DE BAR BEBIDAS"  # el nombre oficial manda
    assert (sub.tipo, sub.padre_codigo, sub.sin_jerarquia) == ("Acreedor", "4001002", False)
    # una cuenta con movimientos que no está en el catálogo oficial se conserva y se reporta
    assert not cat["9999999"].en_catalogo_oficial and cat["9999999"].con_movimientos
    assert resumen.fuera_del_catalogo == ["9999999"]


def test_los_movimientos_posteriores_no_pisan_el_nombre_oficial(db: Session, mundo: Mundo) -> None:
    importar(db, mundo.hotel_a)
    cargar(db, mundo, [mov("4001002.001", "NOMBRE DISTINTO DEL MOVIMIENTO")])
    cat = RepositorioCatalogo(db, mundo.hotel_a).por_codigo()
    assert cat["4001002.001"].descripcion == "INGRESOS DE BAR BEBIDAS"


def test_inactivas_con_movimientos_se_reportan(db: Session, mundo: Mundo) -> None:
    cargar(db, mundo, [mov("6009002", "DUEÑOS")])
    assert importar(db, mundo.hotel_a).inactivas_con_movimientos == ["6009002"]


def test_la_calidad_avisa_de_cuentas_fuera_del_catalogo_oficial_e_inactivas(
    db: Session, mundo: Mundo
) -> None:
    importar(db, mundo.hotel_a)
    r = cargar(db, mundo, [mov("4001002.001"), mov("5555555", fila=2), mov("6009002", fila=3)])
    fuera = control(r, "cuentas_fuera_del_catalogo_oficial")
    assert fuera and fuera["severidad"] == "aviso" and fuera["ejemplos"] == ["5555555"]
    inactivas = control(r, "movimientos_en_cuentas_inactivas")
    assert inactivas and inactivas["severidad"] == "aviso" and inactivas["ejemplos"] == ["6009002"]
    assert r.cargas  # solo avisos: la carga se acepta


def test_sin_catalogo_oficial_no_hay_esos_controles(db: Session, mundo: Mundo) -> None:
    r = cargar(db, mundo, [mov("4001002.001")])
    assert control(r, "cuentas_fuera_del_catalogo_oficial") is None


def test_el_catalogo_acumula_las_cuentas_de_catalogos_anteriores(db: Session, mundo: Mundo) -> None:
    """Cada catálogo es una foto de un mes: una cuenta que hoy no viene puede venir en otro."""
    importar(db, mundo.hotel_a)
    sin_sueldos = [f for f in catalogo_basico() if f[0] != "6009001"]
    cargar(db, mundo, [mov("6009001.001", "SUELDOS")])  # con movimientos, como en el Variance
    resumen = importar(db, mundo.hotel_a, sin_sueldos)
    cat = RepositorioCatalogo(db, mundo.hotel_a).por_codigo()
    sueldos = cat["6009001.001"]
    assert sueldos.en_catalogo_oficial and sueldos.tipo == "Deudor"  # se conserva completa
    assert sueldos.depto_ef == "MGT & CHECK IN" and sueldos.padre_codigo == "6009001"
    assert sorted(resumen.ya_no_vienen) == ["6009001", "6009001.001"]
    assert resumen.fuera_del_catalogo == []  # no es "desconocida": estuvo en un catálogo oficial
    # y si un catálogo posterior la vuelve a traer, no cambia nada
    assert not importar(db, mundo.hotel_a).hubo_cambios


def test_el_catalogo_de_cada_hotel_es_independiente(db: Session, mundo: Mundo) -> None:
    importar(db, mundo.hotel_a)
    assert RepositorioCatalogo(db, mundo.hotel_b).todas() == []
    assert len(RepositorioCatalogo(db, mundo.hotel_a).todas()) == 11


# --- Con los archivos reales de Torres ----------------------------------------------------------


@pytest.mark.skipif(not CATALOGO.exists(), reason="El catálogo real no está en la carpeta")
def test_catalogo_real_completo_con_jerarquia_y_nombres(db: Session, mundo: Mundo) -> None:
    catalogo = leer_con020(CATALOGO)
    resumen = importar_catalogo(db, hotel_id=mundo.hotel_a, catalogo=catalogo)
    db.commit()
    assert resumen.creadas == 1238 + 68 and resumen.titulos_con_nombre_nuevo == 68
    cat = RepositorioCatalogo(db, mundo.hotel_a).por_codigo()
    assert len(cat) == 1306
    for codigo, nombre in (
        ("1", "ACTIVO"),
        ("2", "PASIVO"),
        ("4", "INGRESOS"),
        ("5", "COSTO"),
        ("6", "GASTOS"),
    ):
        assert cat[codigo].descripcion == nombre and cat[codigo].nivel == 0
    assert cat["1000"].descripcion == "BANCOS" and cat["1000"].padre_codigo == "10"
    assert cat["1000001"].padre_codigo == "1000" and cat["1000001"].es_titulo
    assert cat["1000001.001"].padre_codigo == "1000001"
    # todo el árbol cuelga de una clase, sin ciclos ni huérfanos
    for c in cat.values():
        if c.padre_codigo is not None:
            assert c.nivel == cat[c.padre_codigo].nivel + 1  # type: ignore[operator]
        else:
            assert c.nivel == 0 and len(c.codigo) == 1
    # departamentos: los grupos de 4 dígitos de la clase 6 son los del Variance
    assert cat["6009"].descripcion == "GERENCIA Y RECEPCION"
    assert cat["6014"].descripcion == "RESTAURANTE" and cat["6010"].descripcion == "AMA DE LLAVES"
    # idempotente
    assert not importar_catalogo(db, hotel_id=mundo.hotel_a, catalogo=catalogo).hubo_cambios


@pytest.mark.skipif(
    not (CATALOGO.exists() and CON130.exists()), reason="Faltan los archivos reales de Torres"
)
def test_catalogo_real_mas_con130_de_septiembre(db: Session, mundo: Mundo) -> None:
    importar_catalogo(db, hotel_id=mundo.hotel_a, catalogo=leer_con020(CATALOGO))
    db.commit()
    r = cargar_archivo(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        resultado=leer_con130(CON130),
        archivo=DatosArchivo("con130.xlsx", "b" * 64),
    )
    db.commit()
    assert r.cargas
    fuera = control(r, "cuentas_fuera_del_catalogo_oficial")
    assert fuera and fuera["severidad"] == "ok"  # las 366 cuentas están en el catálogo oficial
    cat = RepositorioCatalogo(db, mundo.hotel_a).por_codigo()
    con_mov = [c for c in cat.values() if c.con_movimientos]
    assert len(con_mov) == 366 and all(
        c.en_catalogo_oficial and not c.sin_jerarquia for c in con_mov
    )
    # los 145 títulos del CON130 ya tienen nombre (50 no lo traían en el reporte de movimientos)
    titulos_con130 = {t.codigo for t in leer_con130(CON130).titulos}
    assert all(cat[t].descripcion for t in titulos_con130)
    assert all(cat[c.codigo].tipo in ("Deudor", "Acreedor") for c in con_mov)


@pytest.mark.skipif(
    not (CATALOGO.exists() and VARIANCE.exists()), reason="Faltan los archivos reales de Torres"
)
def test_catalogo_real_contra_el_variance_hay_87_cuentas_fuera(db: Session, mundo: Mundo) -> None:
    importar_catalogo(db, hotel_id=mundo.hotel_a, catalogo=leer_con020(CATALOGO))
    db.commit()
    r = cargar_archivo(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        resultado=leer_variance_base_datos(VARIANCE),
        archivo=DatosArchivo("variance.xlsx", "c" * 64),
    )
    db.commit()
    fuera = control(r, "cuentas_fuera_del_catalogo_oficial")
    assert fuera and fuera["severidad"] == "aviso" and fuera["resumen"].startswith("87 ")
