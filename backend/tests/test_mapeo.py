import os
from pathlib import Path

import pytest
from conftest import Mundo
from sqlalchemy.orm import Session

from fpa.ingesta.variance_estructura import leer_variance_estructura_filas
from fpa.ingesta.variance_mapeo import (
    analizar_terminos,
    leer_variance_mapeo,
    leer_variance_mapeo_filas,
)
from fpa.modelos.catalogo import CuentaLocal
from fpa.repositorios.mapeo import RepositorioMapeo
from fpa.repositorios.reporte import RepositorioReporte
from fpa.servicios.cargar_archivo import Resolucion
from fpa.servicios.cargas import DatosArchivo
from fpa.servicios.estructura_reporte import importar_estructura_reporte
from fpa.servicios.mapeo import discrepancias_de_signo, importar_mapeo, signo_esperado

_CARPETA = Path(
    os.environ.get(
        "FPA_DATOS_REALES", Path.home() / "Desktop" / "PLATAFORMA FP&A E INTELIGENCIA HOTELERA"
    )
)
VARIANCE = _CARPETA / "02. VT August 2026 Variance (Envio) (1).xlsx"


def fila(b=None, c=None, d=None, s=None, t=None):  # type: ignore[no-untyped-def]
    return (None, b, c, d, *([None] * 14), s, t)


def hoja(*cuerpo):  # type: ignore[no-untyped-def]
    return [
        fila(),
        fila("Account #", "Account Description", "AUGUST"),
        fila(None, None, "Actual"),
        *cuerpo,
    ]


EJEMPLO = hoja(
    fila(
        "029-0000-1-000",
        "Ingreso",
        100,
        "=-'4001002.001'!L5-'4001002.002'!L6",
        "=-'4001002.001'!L7",
    ),
    fila("029-0000-2-000", "Gasto", 30, "='6009001.001'!L9", "='6009001.001'!L10+'6009006'!L3"),
    fila("029-0000-3-000", "Sin cuentas", 0, None, None),
    fila("029-0000-4-000", "Doble signo", 5, "=+-'4001005.001'!L2", None),
    fila("029-0000-5-000", "Solo budget", 0, None, "='602-0086-000'!L4"),
)


def test_analiza_terminos() -> None:
    assert analizar_terminos("=-'4001'!L1+'6001'!L2") == ([("4001", -1), ("6001", 1)], "")
    assert analizar_terminos("=+-'4001'!L1")[0] == [("4001", -1)]  # type: ignore[index]
    assert analizar_terminos("='602-0086-000'!L3")[0] == [("602-0086-000", 1)]  # type: ignore[index]
    assert analizar_terminos("=D11-S11") == ([], "D11-S11")
    assert analizar_terminos(None) is None and analizar_terminos("texto") is None


def test_mapeo_sintetico() -> None:
    est = leer_variance_estructura_filas(EJEMPLO)
    r = leer_variance_mapeo_filas(EJEMPLO, est)
    assert r.es_valido
    por_linea = {}
    for v in r.vinculos:
        por_linea.setdefault(v.orden, {})[v.cuenta_codigo] = v.signo
    assert por_linea == {
        1: {"4001002.001": -1, "4001002.002": -1},
        2: {"6009001.001": 1, "6009006": 1},  # 6009006 solo estaba en T
        4: {"4001005.001": -1},
        5: {"602-0086-000": 1},
    }
    assert r.lineas_vinculadas == 4
    assert any("solo aparecen en la columna T" in a for a in r.avisos)


def test_sin_formulas_es_error() -> None:
    cuerpo = hoja(fila("029-0000-1-000", "X", 1, None, None))
    assert not leer_variance_mapeo_filas(cuerpo, leer_variance_estructura_filas(cuerpo)).es_valido


def test_signo_esperado() -> None:
    assert signo_esperado("Deudor") == 1
    assert signo_esperado("Acreedor") == -1
    assert signo_esperado(None) is None and signo_esperado("Otro") is None


def _crear_estructura(db: Session, mundo: Mundo, hotel: int):  # type: ignore[no-untyped-def]
    est = leer_variance_estructura_filas(EJEMPLO)
    res = importar_estructura_reporte(
        db,
        organizacion_id=mundo.org1,
        hotel_id=hotel,
        usuario_id=None,
        resultado=est,
        archivo=DatosArchivo(nombre="v.xlsx", sha256="a" * 64),
    )
    assert res.version is not None
    return res.version, est


def _cuenta(db: Session, hotel: int, codigo: str, tipo: str | None) -> None:
    db.add(
        CuentaLocal(
            hotel_id=hotel,
            codigo=codigo,
            clase=codigo[0],
            con_movimientos=True,
            origen="prueba",
            tipo=tipo,
        )
    )
    db.flush()


def test_importa_borrador_con_numero_y_vinculos(db: Session, mundo: Mundo) -> None:
    version, est = _crear_estructura(db, mundo, mundo.hotel_a)
    leido = leer_variance_mapeo_filas(EJEMPLO, est)
    _cuenta(db, mundo.hotel_a, "4001002.001", "Acreedor")
    res = importar_mapeo(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        version_estructura=version,
        leido=leido,
        archivo=DatosArchivo(nombre="v.xlsx", sha256="a" * 64),
    )
    db.commit()
    assert res.resolucion is Resolucion.CREADA and res.version is not None
    assert (res.version.numero, res.version.estado) == (1, "borrador")
    assert res.n_vinculos == 6 and res.lineas_vinculadas == 4
    assert "4001002.001" not in res.sin_catalogo and "6009006" in res.sin_catalogo
    repo = RepositorioMapeo(db, mundo.hotel_a)
    assert len(repo.vinculos(res.version.id)) == 6
    assert repo.borrador() is not None and repo.aprobada() is None
    lineas = {x.id: x for x in RepositorioReporte(db, mundo.hotel_a).lineas(version.id)}
    assert all(lineas[v.linea_id].tipo == "detalle" for v in repo.vinculos(res.version.id))


def test_segundo_borrador_pide_confirmacion_y_descarta_el_anterior(
    db: Session, mundo: Mundo
) -> None:
    version, est = _crear_estructura(db, mundo, mundo.hotel_a)
    leido = leer_variance_mapeo_filas(EJEMPLO, est)

    def importar(confirmar: bool = False):  # type: ignore[no-untyped-def]
        return importar_mapeo(
            db,
            organizacion_id=mundo.org1,
            hotel_id=mundo.hotel_a,
            usuario_id=None,
            version_estructura=version,
            leido=leido,
            archivo=DatosArchivo(nombre="v.xlsx", sha256="a" * 64),
            confirmar_reemplazo=confirmar,
        )

    importar()
    db.commit()
    assert importar().resolucion is Resolucion.REQUIERE_CONFIRMACION
    segunda = importar(confirmar=True)
    db.commit()
    assert segunda.version is not None and segunda.version.numero == 2
    assert [v.estado for v in RepositorioMapeo(db, mundo.hotel_a).versiones()] == [
        "descartada",
        "borrador",
    ]


def test_discrepancias_de_signo_contra_catalogo(db: Session, mundo: Mundo) -> None:
    version, est = _crear_estructura(db, mundo, mundo.hotel_a)
    for codigo, tipo in [
        ("4001002.001", "Acreedor"),  # signo -1: coincide
        ("4001002.002", "Deudor"),  # signo -1: discrepa
        ("6009001.001", "Deudor"),  # coincide
        ("6009006", None),  # sin tipo: no se puede comparar
    ]:
        _cuenta(db, mundo.hotel_a, codigo, tipo)
    res = importar_mapeo(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        version_estructura=version,
        leido=leer_variance_mapeo_filas(EJEMPLO, est),
        archivo=DatosArchivo(nombre="v.xlsx", sha256="a" * 64),
    )
    assert res.version is not None
    d = discrepancias_de_signo(db, mundo.hotel_a, res.version.id)
    assert [(x.cuenta_codigo, x.signo_mapeo, x.signo_esperado) for x in d] == [
        ("4001002.002", -1, 1)
    ]


def test_aislamiento_del_mapeo(db: Session, mundo: Mundo) -> None:
    version, est = _crear_estructura(db, mundo, mundo.hotel_a)
    res = importar_mapeo(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        version_estructura=version,
        leido=leer_variance_mapeo_filas(EJEMPLO, est),
        archivo=DatosArchivo(nombre="v.xlsx", sha256="a" * 64),
    )
    assert res.version is not None
    otro = RepositorioMapeo(db, mundo.hotel_b)
    assert otro.versiones() == [] and otro.obtener(res.version.id) is None
    assert otro.vinculos(res.version.id) == []
    with pytest.raises(ValueError):  # una estructura de otro hotel no se puede usar
        importar_mapeo(
            db,
            organizacion_id=mundo.org1,
            hotel_id=mundo.hotel_b,
            usuario_id=None,
            version_estructura=version,
            leido=leer_variance_mapeo_filas(EJEMPLO, est),
            archivo=DatosArchivo(nombre="v.xlsx", sha256="a" * 64),
        )


@pytest.mark.skipif(not VARIANCE.exists(), reason="No está el Excel real del Variance")
def test_hoja_ago_real() -> None:
    r = leer_variance_mapeo(VARIANCE)
    assert r.es_valido, r.errores
    # 253 líneas con fórmula en S y T; 10 más solo en T (Budget, sin Actual en agosto)
    assert r.lineas_vinculadas == 263
    en_s = {v.fila_origen for v in r.vinculos}
    assert len(en_s) == 263
    assert {v.signo for v in r.vinculos} == {1, -1}
    assert not any("no reconocidos" in a for a in r.avisos)
    ejemplo = {v.cuenta_codigo: v.signo for v in r.vinculos if v.fila_origen == 12}
    assert ejemplo["4002001.002"] == -1 and ejemplo["602-0086-000"] == -1
    assert ejemplo["6023001.002"] == -1 and ejemplo["4002004"] == -1
