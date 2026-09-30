import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from conftest import Mundo, como
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.ingesta.contrato import Cuenta, Fuente, ResultadoLectura, Titulo
from fpa.ingesta.contrato import Movimiento as MovimientoLeido
from fpa.ingesta.novohit_con130 import leer_con130
from fpa.ingesta.variance_base_datos import leer_variance_base_datos
from fpa.modelos import CuentaLocal, Movimiento
from fpa.repositorios.catalogo import RepositorioCatalogo
from fpa.servicios.cargar_archivo import Resolucion, cargar_archivo
from fpa.servicios.cargas import DatosArchivo
from fpa.servicios.catalogo import (
    CatalogoInconsistente,
    actualizar_catalogo,
    calcular_niveles,
    calcular_padres,
)

D = Decimal
_CARPETA_DOCUMENTOS = Path(
    os.environ.get(
        "FPA_DATOS_REALES", Path.home() / "Desktop" / "PLATAFORMA FP&A E INTELIGENCIA HOTELERA"
    )
)
CON130 = _CARPETA_DOCUMENTOS / "BASE DATOS.xlsx"
VARIANCE = _CARPETA_DOCUMENTOS / "02. VT August 2026 Variance (Envio) (1).xlsx"


# --- Funciones puras --------------------------------------------------------------------------


def test_padre_es_el_titulo_mas_largo_que_es_prefijo() -> None:
    titulos = {"1", "10", "1000", "1002", "1000001"}
    padres = calcular_padres(titulos, ["1000001.001", "1000003", "1002", "1000001", "1"])
    assert padres == {
        "1000001.001": "1000001",
        "1000003": "1000",  # cuenta sin punto bajo el título 1000
        "1002": "10",
        "1000001": "1000",
        "1": None,
    }


def test_un_titulo_no_es_su_propio_padre_y_sin_titulos_no_hay_padre() -> None:
    assert calcular_padres({"1000"}, ["1000"]) == {"1000": None}
    assert calcular_padres(set(), ["4001002.001"]) == {"4001002.001": None}


def test_subcuenta_con_punto_cuelga_de_su_codigo_base_si_se_conoce() -> None:
    padres = calcular_padres(
        set(), ["4002007", "4002007.001"], conocidos={"4002007", "4002007.001"}
    )
    assert padres == {"4002007": None, "4002007.001": "4002007"}


def test_niveles_y_ciclos() -> None:
    assert calcular_niveles({"1": None, "10": "1", "1000": "10", "1000.1": "1000"}) == {
        "1": 0,
        "10": 1,
        "1000": 2,
        "1000.1": 3,
    }
    assert "X" not in calcular_niveles({"X": "no-existe"})  # padre desconocido: sin nivel
    with pytest.raises(CatalogoInconsistente, match="Ciclo"):
        calcular_niveles({"a": "b", "b": "a"})


# --- Actualización del catálogo ---------------------------------------------------------------


def mov(
    codigo: str, descripcion: str = "D", dia: int = 10, mes: int = 9, fila: int = 1
) -> MovimientoLeido:
    return MovimientoLeido(
        cuenta_codigo=codigo,
        cuenta_descripcion=descripcion,
        asiento="9.2.1",
        fecha=date(2026, mes, dia),
        concepto="X",
        debito=D("1.00"),
        credito=D("0"),
        fila=fila,
    )


def lectura(
    movs: list[MovimientoLeido], titulos: list[Titulo] | None = None, fuente: Fuente = Fuente.CON130
) -> ResultadoLectura:
    return ResultadoLectura(
        fuente=fuente,
        controla_balance=False,
        movimientos=movs,
        titulos=titulos or [],
        cuentas={m.cuenta_codigo: Cuenta(m.cuenta_codigo, m.cuenta_descripcion, 1) for m in movs},
    )


def test_construye_el_arbol_con_titulos_y_cuentas(db: Session, mundo: Mundo) -> None:
    res = lectura(
        [mov("1000001.001", "BANBAJIO")],
        [
            Titulo("1", None, 1),
            Titulo("10", None, 2),
            Titulo("1000", None, 3),
            Titulo("1000001", "BANCOS MONEDA NACIONAL", 4),
        ],
    )
    resumen = actualizar_catalogo(db, hotel_id=mundo.hotel_a, resultado=res)
    db.commit()
    assert (resumen.creadas, resumen.actualizadas) == (5, 0)
    cat = RepositorioCatalogo(db, mundo.hotel_a).por_codigo()
    assert cat["1"].nivel == 0 and cat["1"].padre_codigo is None and cat["1"].es_titulo
    assert (cat["1000001"].padre_codigo, cat["1000001"].nivel) == ("1000", 3)
    hoja = cat["1000001.001"]
    assert hoja.con_movimientos and not hoja.es_titulo and not hoja.sin_jerarquia
    assert (hoja.padre_codigo, hoja.nivel, hoja.clase) == ("1000001", 4, "1")
    assert hoja.descripcion == "BANBAJIO"


def test_es_idempotente(db: Session, mundo: Mundo) -> None:
    res = lectura([mov("1000001.001")], [Titulo("1000001", "BANCOS", 1)])
    actualizar_catalogo(db, hotel_id=mundo.hotel_a, resultado=res)
    otra = actualizar_catalogo(db, hotel_id=mundo.hotel_a, resultado=res)
    assert (otra.creadas, otra.actualizadas) == (0, 0)


def test_cuenta_sin_jerarquia_la_recibe_cuando_llega_el_con130(db: Session, mundo: Mundo) -> None:
    # 1) Variance (julio-agosto): el código 4002007 tiene movimientos y no hay títulos
    actualizar_catalogo(
        db,
        hotel_id=mundo.hotel_a,
        resultado=lectura([mov("4002007", mes=8)], fuente=Fuente.VARIANCE_BASE_DATOS),
    )
    cat = RepositorioCatalogo(db, mundo.hotel_a).por_codigo()
    assert cat["4002007"].sin_jerarquia and cat["4002007"].padre_codigo is None

    # 2) CON130 (septiembre): 4002007 aparece como TÍTULO y trae una subcuenta con movimientos
    septiembre = lectura(
        [mov("4002007.001")],
        [Titulo("4", None, 1), Titulo("4002", None, 2), Titulo("4002007", "OTROS", 3)],
    )
    resumen = actualizar_catalogo(db, hotel_id=mundo.hotel_a, resultado=septiembre)
    cat = RepositorioCatalogo(db, mundo.hotel_a).por_codigo()
    assert resumen.actualizadas >= 1
    viejo = cat["4002007"]
    assert viejo.con_movimientos and viejo.es_titulo  # es las dos cosas a la vez
    assert not viejo.sin_jerarquia and viejo.padre_codigo == "4002"
    assert cat["4002007.001"].padre_codigo == "4002007"
    assert cat["4002007.001"].nivel == viejo.nivel + 1  # type: ignore[operator]


def test_el_catalogo_de_cada_hotel_es_independiente(db: Session, mundo: Mundo) -> None:
    actualizar_catalogo(db, hotel_id=mundo.hotel_a, resultado=lectura([mov("1000001.001")]))
    assert RepositorioCatalogo(db, mundo.hotel_b).todas() == []
    actualizar_catalogo(db, hotel_id=mundo.hotel_b, resultado=lectura([mov("2000001.001")]))
    assert [c.codigo for c in RepositorioCatalogo(db, mundo.hotel_a).todas()] == ["1000001.001"]


# --- Integración con la carga -----------------------------------------------------------------


def cargar(db: Session, mundo: Mundo, res: ResultadoLectura, sha: str):  # type: ignore[no-untyped-def]
    r = cargar_archivo(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        resultado=res,
        archivo=DatosArchivo("x.xlsx", sha),
    )
    db.commit()
    return r


def test_la_carga_alimenta_el_catalogo_y_avisa_de_cuentas_nuevas(db: Session, mundo: Mundo) -> None:
    primera = cargar(db, mundo, lectura([mov("A1")]), "a" * 64)
    codigos = {c["codigo"] for c in primera.cargas[0].controles["controles"]}  # type: ignore[index]
    assert "cuentas_nuevas" not in codigos  # primera carga: todo es nuevo, no se avisa
    segunda = cargar(db, mundo, lectura([mov("A1", mes=10), mov("B2", mes=10, fila=2)]), "b" * 64)
    assert segunda.resolucion == Resolucion.CREADA
    nuevas = next(
        c
        for c in segunda.cargas[0].controles["controles"]
        if c["codigo"] == "cuentas_nuevas"  # type: ignore[index]
    )
    assert nuevas["severidad"] == "aviso" and nuevas["ejemplos"] == ["B2"]
    assert set(RepositorioCatalogo(db, mundo.hotel_a).por_codigo()) == {"A1", "B2"}


def test_si_la_carga_falla_el_catalogo_tampoco_cambia(db: Session, mundo: Mundo) -> None:
    mala = lectura(
        [
            mov("A1"),
            MovimientoLeido("B2", "D", "9.2.1", date(2026, 9, 1), "X", D("1.234"), D("0"), 2),
        ]
    )
    with pytest.raises(Exception, match="más de 2 decimales"):
        cargar(db, mundo, mala, "c" * 64)
    db.rollback()
    assert RepositorioCatalogo(db, mundo.hotel_a).todas() == []


# --- API --------------------------------------------------------------------------------------


def test_api_arbol_del_catalogo(cliente: TestClient, db: Session, mundo: Mundo) -> None:
    res = lectura(
        [mov("1000001.001", "BANBAJIO"), mov("1000001.002", "TARJETAS"), mov("4001002.001", "BAR")],
        [Titulo("1", None, 1), Titulo("1000001", "BANCOS", 2)],
    )
    cargar(db, mundo, res, "d" * 64)
    url = f"/api/v1/hoteles/{mundo.hotel_a}/catalogo/arbol"
    r = cliente.get(url, headers=como("analista_a@test.local"))
    assert r.status_code == 200
    raices = r.json()
    assert [n["codigo"] for n in raices] == ["1", "4001002.001"]  # la cuenta sin jerarquía es raíz
    assert raices[1]["sin_jerarquia"] is True
    banco = raices[0]["hijos"][0]
    assert banco["codigo"] == "1000001" and banco["nivel"] == 1
    assert [h["codigo"] for h in banco["hijos"]] == ["1000001.001", "1000001.002"]
    assert banco["hijos"][0]["con_movimientos"] is True and banco["hijos"][0]["nivel"] == 2


def test_api_arbol_respeta_permisos_y_aislamiento(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    cargar(db, mundo, lectura([mov("1000001.001")]), "e" * 64)
    url_a = f"/api/v1/hoteles/{mundo.hotel_a}/catalogo/arbol"
    assert cliente.get(url_a).status_code == 401
    assert cliente.get(url_a, headers=como("responsable_a@test.local")).status_code == 200
    assert cliente.get(url_a, headers=como("contralor_c@test.local")).status_code == 404
    url_b = f"/api/v1/hoteles/{mundo.hotel_b}/catalogo/arbol"
    assert cliente.get(url_b, headers=como("analista_a@test.local")).status_code == 404
    assert cliente.get(url_b, headers=como("contralor_ab@test.local")).json() == []


# --- Con los archivos reales de Torres ---------------------------------------------------------


def _comprobar_arbol(db: Session, hotel_id: int) -> dict[str, CuentaLocal]:
    cat = RepositorioCatalogo(db, hotel_id).por_codigo()
    for c in cat.values():
        if c.padre_codigo is not None:
            padre = cat[c.padre_codigo]  # el padre existe
            assert padre.nivel is not None and c.nivel == padre.nivel + 1
    return cat


@pytest.mark.skipif(not CON130.exists(), reason="BASE DATOS.xlsx no está en la carpeta")
def test_con130_real_arma_el_arbol_completo(db: Session, mundo: Mundo) -> None:
    res = leer_con130(CON130)
    cargar(db, mundo, res, "f" * 64)
    cat = _comprobar_arbol(db, mundo.hotel_a)
    titulos = [c for c in cat.values() if c.es_titulo]
    cuentas = [c for c in cat.values() if c.con_movimientos]
    assert len(titulos) == 145 and len(cuentas) == 366 and len(cat) == 511
    assert all(c.padre_codigo is not None and not c.sin_jerarquia for c in cuentas)
    assert {c.clase for c in cat.values()} == {"1", "2", "4", "5", "6"}
    # Invariante: toda cuenta que aparece en un movimiento existe en el catálogo
    en_movimientos = set(db.scalars(select(Movimiento.cuenta_codigo).distinct()))
    assert en_movimientos <= set(cat)
    assert cat["1000001.001"].descripcion == "BANBAJIO PS 023240518 0201"
    assert cat["1000001.001"].padre_codigo == "1000001"


@pytest.mark.skipif(
    not (CON130.exists() and VARIANCE.exists()), reason="Faltan los Excel reales de Torres"
)
def test_catalogo_acumula_variance_y_luego_con130(db: Session, mundo: Mundo) -> None:
    cargar(db, mundo, leer_variance_base_datos(VARIANCE), "a" * 64)  # julio-agosto
    antes = _comprobar_arbol(db, mundo.hotel_a)
    assert len([c for c in antes.values() if c.con_movimientos]) == 296
    assert all(c.sin_jerarquia for c in antes.values() if c.padre_codigo is None)

    cargar(db, mundo, leer_con130(CON130), "b" * 64)  # septiembre
    cat = _comprobar_arbol(db, mundo.hotel_a)
    con_mov = [c for c in cat.values() if c.con_movimientos]
    assert len(con_mov) == 366 + (296 - 108)  # 108 cuentas se repiten entre ambos archivos
    en_movimientos = set(db.scalars(select(Movimiento.cuenta_codigo).distinct()))
    assert en_movimientos == {c.codigo for c in con_mov}
    # 4002007 fue cuenta con movimientos en agosto y es título en septiembre: ahora es las dos
    ambas = [c for c in cat.values() if c.con_movimientos and c.es_titulo]
    assert any(c.codigo == "4002007" for c in ambas)
    # El CON130 dio jerarquía a las cuentas del Variance cuyo título conoce
    for c in antes.values():
        if c.sin_jerarquia and cat[c.codigo].padre_codigo is not None:
            assert not cat[c.codigo].sin_jerarquia
