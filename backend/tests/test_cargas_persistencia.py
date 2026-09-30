import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from conftest import Mundo
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from fpa.ingesta.contrato import Fuente, ResultadoLectura
from fpa.ingesta.contrato import Movimiento as MovimientoLeido
from fpa.ingesta.novohit_con130 import leer_con130
from fpa.ingesta.variance_base_datos import leer_variance_base_datos
from fpa.modelos import CargaArchivo, EstadoCarga, Movimiento
from fpa.repositorios.cargas import RepositorioCargas
from fpa.servicios.cargas import CargaInvalida, DatosArchivo, registrar_carga

D = Decimal
_CARPETA_DOCUMENTOS = Path(
    os.environ.get(
        "FPA_DATOS_REALES", Path.home() / "Desktop" / "PLATAFORMA FP&A E INTELIGENCIA HOTELERA"
    )
)
CON130 = _CARPETA_DOCUMENTOS / "BASE DATOS.xlsx"
VARIANCE = _CARPETA_DOCUMENTOS / "02. VT August 2026 Variance (Envio) (1).xlsx"
ARCHIVO = DatosArchivo(nombre="prueba.xlsx", sha256="a" * 64, tamano_bytes=123)


def mov(
    fecha: date, debito: str, credito: str = "0", fila: int = 1, **extra: object
) -> MovimientoLeido:
    return MovimientoLeido(
        cuenta_codigo="1000001.001",
        cuenta_descripcion="BANCO",
        asiento="9.2.1",
        fecha=fecha,
        concepto="MOV",
        debito=D(debito),
        credito=D(credito),
        fila=fila,
        **extra,  # type: ignore[arg-type]
    )


def lectura(*movs: MovimientoLeido, balance: bool = False) -> ResultadoLectura:
    return ResultadoLectura(
        fuente=Fuente.VARIANCE_BASE_DATOS, controla_balance=balance, movimientos=list(movs)
    )


def contar(db: Session, modelo: type) -> int:
    return db.scalar(select(func.count()).select_from(modelo)) or 0


def test_crea_una_carga_vigente_por_periodo_con_totales_exactos(db: Session, mundo: Mundo) -> None:
    res = lectura(
        mov(date(2026, 7, 31), "0.10"),
        mov(date(2026, 7, 15), "99999999999999.99", "0.01", fila=2),
        mov(date(2026, 8, 1), "5.50", fila=3),
    )
    cargas = registrar_carga(
        db, hotel_id=mundo.hotel_a, usuario_id=None, resultado=res, archivo=ARCHIVO
    )
    db.commit()
    assert [c.periodo for c in cargas] == ["2026-07", "2026-08"]
    julio, agosto = cargas
    assert julio.n_movimientos == 2 and agosto.n_movimientos == 1
    assert julio.total_debito == D("99999999999999.99") + D("0.10")
    assert julio.total_credito == D("0.01")
    assert (julio.fecha_min, julio.fecha_max) == (date(2026, 7, 15), date(2026, 7, 31))
    assert all(c.estado == EstadoCarga.VIGENTE.value for c in cargas)
    assert all(c.fuente == Fuente.VARIANCE_BASE_DATOS.value for c in cargas)
    assert julio.sha256 == "a" * 64
    movs = RepositorioCargas(db, mundo.hotel_a).movimientos_de_carga(julio.id)
    assert sorted(m.debito for m in movs) == [D("0.10"), D("99999999999999.99")]
    assert {m.periodo for m in movs} == {"2026-07"}


def test_cantidad_y_costo_conservan_sus_decimales(db: Session, mundo: Mundo) -> None:
    res = lectura(
        mov(date(2026, 8, 1), "25.83", cantidad=D("2.5"), costo=D("10.333333")),
    )
    carga = registrar_carga(
        db, hotel_id=mundo.hotel_a, usuario_id=None, resultado=res, archivo=ARCHIVO
    )[0]
    db.commit()
    m = RepositorioCargas(db, mundo.hotel_a).movimientos_de_carga(carga.id)[0]
    assert m.cantidad == D("2.5") and m.costo == D("10.333333")


def test_es_todo_o_nada_si_falla_a_la_mitad(db: Session, mundo: Mundo) -> None:
    # Julio es válido; agosto trae un monto con tres decimales, que la base rechaza.
    res = lectura(mov(date(2026, 7, 1), "10.00"), mov(date(2026, 8, 1), "1.234", fila=2))
    with pytest.raises(Exception, match="más de 2 decimales"):
        registrar_carga(db, hotel_id=mundo.hotel_a, usuario_id=None, resultado=res, archivo=ARCHIVO)
    assert contar(db, CargaArchivo) == 0
    assert contar(db, Movimiento) == 0
    # y la sesión sigue utilizable
    ok = registrar_carga(
        db,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        resultado=lectura(mov(date(2026, 7, 1), "10.00")),
        archivo=ARCHIVO,
    )
    db.commit()
    assert len(ok) == 1 and contar(db, Movimiento) == 1


@pytest.mark.parametrize(
    ("resultado", "mensaje"),
    [
        (ResultadoLectura(fuente=Fuente.CON130), "no trae movimientos"),
        (
            ResultadoLectura(movimientos=[mov(date(2026, 9, 1), "1")]),
            "no indica su fuente",
        ),
        (
            ResultadoLectura(
                fuente=Fuente.CON130,
                controla_balance=False,
                movimientos=[mov(date(2026, 9, 1), "1")],
                errores=["algo falló"],
            ),
            "errores",
        ),
        (
            ResultadoLectura(
                fuente=Fuente.CON130,
                controla_balance=True,
                movimientos=[mov(date(2026, 9, 1), "1")],
            ),
            "errores",
        ),
    ],
)
def test_rechaza_lecturas_que_no_se_pueden_guardar(
    db: Session, mundo: Mundo, resultado: ResultadoLectura, mensaje: str
) -> None:
    if not resultado.errores and resultado.controla_balance and resultado.movimientos:
        # un CON130 que no cuadra: el lector habría agregado el error; aquí lo simulamos
        resultado.errores.append("Débito total distinto de Crédito total")
    with pytest.raises(CargaInvalida, match=mensaje):
        registrar_carga(
            db, hotel_id=mundo.hotel_a, usuario_id=None, resultado=resultado, archivo=ARCHIVO
        )
    assert contar(db, CargaArchivo) == 0


def test_solo_una_carga_vigente_por_hotel_y_periodo(db: Session, mundo: Mundo) -> None:
    res = lectura(mov(date(2026, 8, 1), "1"))
    primera = registrar_carga(
        db, hotel_id=mundo.hotel_a, usuario_id=None, resultado=res, archivo=ARCHIVO
    )[0]
    db.commit()
    with pytest.raises(IntegrityError):
        registrar_carga(db, hotel_id=mundo.hotel_a, usuario_id=None, resultado=res, archivo=ARCHIVO)
    db.rollback()
    # otro hotel, mismo periodo: permitido
    registrar_carga(db, hotel_id=mundo.hotel_b, usuario_id=None, resultado=res, archivo=ARCHIVO)
    db.commit()
    # si la primera se reemplaza, ya puede haber otra vigente en ese hotel
    primera.estado = EstadoCarga.REEMPLAZADA.value
    db.commit()
    registrar_carga(db, hotel_id=mundo.hotel_a, usuario_id=None, resultado=res, archivo=ARCHIVO)
    db.commit()
    assert contar(db, CargaArchivo) == 3


def test_repositorio_solo_ve_su_hotel(db: Session, mundo: Mundo) -> None:
    res = lectura(mov(date(2026, 8, 1), "1"))
    carga_a = registrar_carga(
        db, hotel_id=mundo.hotel_a, usuario_id=None, resultado=res, archivo=ARCHIVO
    )[0]
    registrar_carga(db, hotel_id=mundo.hotel_b, usuario_id=None, resultado=res, archivo=ARCHIVO)
    db.commit()
    repo_a, repo_b = RepositorioCargas(db, mundo.hotel_a), RepositorioCargas(db, mundo.hotel_b)
    assert [c.id for c in repo_a.listar()] == [carga_a.id]
    assert repo_b.obtener(carga_a.id) is None
    assert repo_b.movimientos_de_carga(carga_a.id) == []
    assert repo_b.vigente_de_periodo("2026-08") is not None
    assert repo_b.vigente_de_periodo("2026-08").id != carga_a.id  # type: ignore[union-attr]
    assert len(repo_a.movimientos_vigentes("2026-08")) == 1


def test_movimientos_vigentes_ignora_cargas_reemplazadas(db: Session, mundo: Mundo) -> None:
    res = lectura(mov(date(2026, 8, 1), "1"))
    vieja = registrar_carga(
        db, hotel_id=mundo.hotel_a, usuario_id=None, resultado=res, archivo=ARCHIVO
    )[0]
    vieja.estado = EstadoCarga.REEMPLAZADA.value
    db.flush()
    nueva = registrar_carga(
        db,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        resultado=lectura(mov(date(2026, 8, 2), "7"), mov(date(2026, 8, 3), "8", fila=2)),
        archivo=DatosArchivo("otra.xlsx", "b" * 64),
    )[0]
    db.commit()
    repo = RepositorioCargas(db, mundo.hotel_a)
    vigentes = repo.movimientos_vigentes("2026-08")
    assert {m.carga_id for m in vigentes} == {nueva.id}
    assert len(vigentes) == 2
    assert len(repo.movimientos_de_carga(vieja.id)) == 1  # el historial se conserva


# --- Con los archivos reales de Torres ---------------------------------------------------------


@pytest.mark.skipif(not VARIANCE.exists(), reason="El Excel del Variance no está en la carpeta")
def test_variance_real_se_guarda_como_dos_cargas(db: Session, mundo: Mundo) -> None:
    res = leer_variance_base_datos(VARIANCE)
    cargas = registrar_carga(
        db, hotel_id=mundo.hotel_a, usuario_id=None, resultado=res, archivo=ARCHIVO
    )
    db.commit()
    assert [(c.periodo, c.n_movimientos) for c in cargas] == [("2026-07", 3583), ("2026-08", 3277)]
    assert sum((c.total_debito for c in cargas), D("0")) == D("12650614.04")
    assert sum((c.total_credito for c in cargas), D("0")) == D("12037735.88")
    assert contar(db, Movimiento) == 6860
    # lo guardado es idéntico a lo leído: sumas por carga desde la base de datos
    repo = RepositorioCargas(db, mundo.hotel_a)
    for c in cargas:
        guardados = repo.movimientos_de_carga(c.id)
        assert sum((m.debito for m in guardados), D("0")) == c.total_debito
        assert sum((m.credito for m in guardados), D("0")) == c.total_credito


@pytest.mark.skipif(not CON130.exists(), reason="BASE DATOS.xlsx no está en la carpeta")
def test_con130_real_se_guarda_como_una_carga(db: Session, mundo: Mundo) -> None:
    res = leer_con130(CON130)
    (carga,) = registrar_carga(
        db, hotel_id=mundo.hotel_a, usuario_id=None, resultado=res, archivo=ARCHIVO
    )
    db.commit()
    assert carga.periodo == "2026-09" and carga.n_movimientos == 7242
    assert carga.total_debito == carga.total_credito == D("57835193.08")
    assert contar(db, Movimiento) == 7242


@pytest.mark.skipif(
    not (CON130.exists() and VARIANCE.exists()), reason="Faltan los Excel reales de Torres"
)
def test_los_textos_reales_caben_en_las_columnas() -> None:
    """Guarda contra PostgreSQL (que sí rechaza textos largos; SQLite no)."""
    columnas = Movimiento.__table__.columns
    for res in (leer_con130(CON130), leer_variance_base_datos(VARIANCE)):
        campos = {
            "cuenta_codigo": "cuenta_codigo",
            "cuenta_descripcion": "cuenta_descripcion",
            "asiento": "asiento",
            "tp_asiento": "tp_asiento",
            "operacion": "operacion",
            "tp_doc": "tp_doc",
            "numero": "numero",
            "concepto": "concepto",
        }
        for atributo, columna in campos.items():
            limite = columnas[columna].type.length  # type: ignore[attr-defined]
            mayor = max(len(getattr(m, atributo) or "") for m in res.movimientos)
            assert mayor <= limite, f"{columna}: {mayor} > {limite}"
