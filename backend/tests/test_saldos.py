import os
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from conftest import Mundo, como
from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import strategies as st
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fpa.ingesta.contrato import Fuente, ResultadoLectura
from fpa.ingesta.contrato import Movimiento as MovimientoLeido
from fpa.ingesta.novohit_con130 import leer_con130
from fpa.ingesta.variance_base_datos import leer_variance_base_datos
from fpa.modelos import SaldoMensualCuenta
from fpa.repositorios.saldos import RepositorioSaldos
from fpa.servicios.cargar_archivo import Resolucion, cargar_archivo
from fpa.servicios.cargas import DatosArchivo
from fpa.servicios.saldos import agregar_por_cuenta, recalcular_saldos

D = Decimal
_CARPETA_DOCUMENTOS = Path(
    os.environ.get(
        "FPA_DATOS_REALES", Path.home() / "Desktop" / "PLATAFORMA FP&A E INTELIGENCIA HOTELERA"
    )
)
CON130 = _CARPETA_DOCUMENTOS / "BASE DATOS.xlsx"
VARIANCE = _CARPETA_DOCUMENTOS / "02. VT August 2026 Variance (Envio) (1).xlsx"


# --- Función pura + propiedades -----------------------------------------------------------------

importe = st.tuples(
    st.sampled_from(["A", "B", "C", "D"]),
    st.decimals(min_value=D("0"), max_value=D("99999999.99"), places=2),
    st.decimals(min_value=D("0"), max_value=D("99999999.99"), places=2),
)


def test_agrega_por_cuenta() -> None:
    r = agregar_por_cuenta(
        [("A", D("10.10"), D("0")), ("A", D("0.20"), D("5.00")), ("B", D("1"), D("1"))]
    )
    assert r == {"A": (D("10.30"), D("5.00"), 2), "B": (D("1"), D("1"), 1)}


def test_sin_importes_no_hay_saldos() -> None:
    assert agregar_por_cuenta([]) == {}


@given(st.lists(importe))
def test_propiedad_la_suma_de_los_saldos_es_la_suma_de_los_movimientos(
    importes: list[tuple[str, Decimal, Decimal]],
) -> None:
    saldos = agregar_por_cuenta(importes)
    assert sum((d for d, _, _ in saldos.values()), D("0")) == sum(
        (d for _, d, _ in importes), D("0")
    )
    assert sum((c for _, c, _ in saldos.values()), D("0")) == sum(
        (c for _, _, c in importes), D("0")
    )
    assert sum(n for _, _, n in saldos.values()) == len(importes)


@given(st.lists(importe), st.randoms())
def test_propiedad_el_orden_de_los_movimientos_no_importa(
    importes: list[tuple[str, Decimal, Decimal]], azar: object
) -> None:
    barajados = list(importes)
    azar.shuffle(barajados)  # type: ignore[attr-defined]
    assert agregar_por_cuenta(barajados) == agregar_por_cuenta(importes)


@given(st.lists(importe), st.lists(importe))
def test_propiedad_agregar_por_partes_da_lo_mismo_que_agregar_todo(
    a: list[tuple[str, Decimal, Decimal]], b: list[tuple[str, Decimal, Decimal]]
) -> None:
    combinado: dict[str, list[Decimal | int]] = defaultdict(lambda: [D("0"), D("0"), 0])
    for parte in (agregar_por_cuenta(a), agregar_por_cuenta(b)):
        for cuenta, (d, c, n) in parte.items():
            combinado[cuenta][0] += d  # type: ignore[operator]
            combinado[cuenta][1] += c  # type: ignore[operator]
            combinado[cuenta][2] += n  # type: ignore[operator]
    assert {k: tuple(v) for k, v in combinado.items()} == agregar_por_cuenta([*a, *b])


# --- Con base de datos ------------------------------------------------------------------------


def mov(
    cuenta: str, debito: str, credito: str, dia: int = 10, mes: int = 8, fila: int = 1
) -> MovimientoLeido:
    return MovimientoLeido(
        cuenta_codigo=cuenta,
        cuenta_descripcion="D",
        asiento="8.3.1",
        fecha=date(2026, mes, dia),
        concepto="X",
        debito=D(debito),
        credito=D(credito),
        fila=fila,
    )


def lectura(*movs: MovimientoLeido) -> ResultadoLectura:
    return ResultadoLectura(
        fuente=Fuente.VARIANCE_BASE_DATOS, controla_balance=False, movimientos=list(movs)
    )


def cargar(
    db: Session,
    mundo: Mundo,
    res: ResultadoLectura,
    sha: str,
    confirmar: bool = False,
    hotel: int | None = None,
):  # type: ignore[no-untyped-def]
    r = cargar_archivo(
        db,
        organizacion_id=mundo.org1,
        hotel_id=hotel or mundo.hotel_a,
        usuario_id=None,
        resultado=res,
        archivo=DatosArchivo("x.xlsx", sha),
        confirmar_reemplazo=confirmar,
    )
    db.commit()
    return r


def filas(db: Session, hotel: int, periodo: str) -> dict[str, tuple[Decimal, Decimal, int]]:
    return {
        s.cuenta_codigo: (s.suma_debito, s.suma_credito, s.n_movimientos)
        for s in RepositorioSaldos(db, hotel).del_periodo(periodo)
    }


def test_la_carga_calcula_los_saldos_de_cada_periodo(db: Session, mundo: Mundo) -> None:
    cargar(
        db,
        mundo,
        lectura(
            mov("4001", "0", "100.50"),
            mov("4001", "0", "20.00", fila=2),
            mov("6009", "30.25", "0", fila=3),
            mov("6009", "5.00", "0", mes=7, fila=4),
        ),
        "a" * 64,
    )
    assert filas(db, mundo.hotel_a, "2026-08") == {
        "4001": (D("0"), D("120.50"), 2),
        "6009": (D("30.25"), D("0"), 1),
    }
    assert filas(db, mundo.hotel_a, "2026-07") == {"6009": (D("5.00"), D("0"), 1)}
    neto = {
        s.cuenta_codigo: s.neto for s in RepositorioSaldos(db, mundo.hotel_a).del_periodo("2026-08")
    }
    assert neto == {"4001": D("-120.50"), "6009": D("30.25")}  # Débito − Crédito


def test_recalcular_es_idempotente(db: Session, mundo: Mundo) -> None:
    cargar(
        db, mundo, lectura(mov("4001", "0", "10.00"), mov("6009", "3.00", "0", fila=2)), "a" * 64
    )
    antes = filas(db, mundo.hotel_a, "2026-08")
    for _ in range(3):
        assert recalcular_saldos(db, hotel_id=mundo.hotel_a, periodo="2026-08") == 2
    db.commit()
    assert filas(db, mundo.hotel_a, "2026-08") == antes
    total = db.scalar(select(func.count()).select_from(SaldoMensualCuenta))
    assert total == 2


def test_al_reemplazar_un_periodo_los_saldos_siguen_a_la_carga_vigente(
    db: Session, mundo: Mundo
) -> None:
    cargar(db, mundo, lectura(mov("4001", "0", "100.00")), "a" * 64)
    duplicada = cargar(db, mundo, lectura(mov("4001", "0", "100.00")), "a" * 64)
    assert duplicada.resolucion == Resolucion.DUPLICADA
    assert filas(db, mundo.hotel_a, "2026-08") == {"4001": (D("0"), D("100.00"), 1)}

    nueva = lectura(mov("4001", "0", "150.00"), mov("6009", "7.00", "0", fila=2))
    assert cargar(db, mundo, nueva, "b" * 64).resolucion == Resolucion.REQUIERE_CONFIRMACION
    assert filas(db, mundo.hotel_a, "2026-08") == {"4001": (D("0"), D("100.00"), 1)}  # sin cambio
    cargar(db, mundo, nueva, "b" * 64, confirmar=True)
    assert filas(db, mundo.hotel_a, "2026-08") == {
        "4001": (D("0"), D("150.00"), 1),
        "6009": (D("7.00"), D("0"), 1),
    }
    carga_vigente = RepositorioSaldos(db, mundo.hotel_a).del_periodo("2026-08")[0].carga_id
    assert carga_vigente is not None


def test_sin_carga_vigente_no_hay_saldos(db: Session, mundo: Mundo) -> None:
    assert recalcular_saldos(db, hotel_id=mundo.hotel_a, periodo="2026-01") == 0


def test_los_saldos_de_un_hotel_no_se_mezclan_con_los_de_otro(db: Session, mundo: Mundo) -> None:
    cargar(db, mundo, lectura(mov("4001", "0", "10.00")), "a" * 64, hotel=mundo.hotel_a)
    cargar(db, mundo, lectura(mov("4001", "0", "99.00")), "b" * 64, hotel=mundo.hotel_b)
    assert filas(db, mundo.hotel_a, "2026-08") == {"4001": (D("0"), D("10.00"), 1)}
    assert filas(db, mundo.hotel_b, "2026-08") == {"4001": (D("0"), D("99.00"), 1)}


def test_api_de_saldos(cliente: TestClient, db: Session, mundo: Mundo) -> None:
    cargar(
        db, mundo, lectura(mov("4001", "0", "10.10"), mov("6009", "3.00", "0", fila=2)), "a" * 64
    )
    url = f"/api/v1/hoteles/{mundo.hotel_a}/saldos"
    r = cliente.get(url, params={"periodo": "2026-08"}, headers=como("analista_a@test.local"))
    assert r.status_code == 200
    assert r.json() == [
        {
            "cuenta_codigo": "4001",
            "suma_debito": "0.00",
            "suma_credito": "10.10",
            "neto": "-10.10",
            "n_movimientos": 1,
        },
        {
            "cuenta_codigo": "6009",
            "suma_debito": "3.00",
            "suma_credito": "0.00",
            "neto": "3.00",
            "n_movimientos": 1,
        },
    ]


def test_api_de_saldos_permisos_y_validacion(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    cargar(db, mundo, lectura(mov("4001", "0", "10.10")), "a" * 64)
    url = f"/api/v1/hoteles/{mundo.hotel_a}/saldos"
    params = {"periodo": "2026-08"}
    assert cliente.get(url, params=params).status_code == 401
    # el responsable de área no tiene saldos:leer; dirección sí
    assert (
        cliente.get(url, params=params, headers=como("responsable_a@test.local")).status_code == 403
    )
    assert (
        cliente.get(
            url, params={"periodo": "2026-13"}, headers=como("analista_a@test.local")
        ).status_code
        == 422
    )
    assert (
        cliente.get(
            url, params={"periodo": "agosto"}, headers=como("analista_a@test.local")
        ).status_code
        == 422
    )
    assert (
        cliente.get(url, params=params, headers=como("contralor_c@test.local")).status_code == 404
    )
    otro = f"/api/v1/hoteles/{mundo.hotel_b}/saldos"
    assert (
        cliente.get(otro, params=params, headers=como("analista_a@test.local")).status_code == 404
    )


# --- Con los archivos reales de Torres ---------------------------------------------------------


@pytest.mark.skipif(not CON130.exists(), reason="BASE DATOS.xlsx no está en la carpeta")
def test_con130_real_saldos_coinciden_con_los_totales_por_cuenta_del_reporte(
    db: Session, mundo: Mundo
) -> None:
    res = leer_con130(CON130)
    cargar(db, mundo, res, "a" * 64)
    saldos = filas(db, mundo.hotel_a, "2026-09")
    assert len(saldos) == 366
    assert sum((d for d, _, _ in saldos.values()), D("0")) == D("57835193.08")
    assert sum((c for _, c, _ in saldos.values()), D("0")) == D("57835193.08")
    for codigo, cuenta in res.cuentas.items():  # contra la fila "Total" de cada cuenta
        assert saldos[codigo][0] == cuenta.total_debito_reporte
        assert saldos[codigo][1] == cuenta.total_credito_reporte


@pytest.mark.skipif(not VARIANCE.exists(), reason="El Excel del Variance no está en la carpeta")
def test_variance_real_saldos_por_mes(db: Session, mundo: Mundo) -> None:
    res = leer_variance_base_datos(VARIANCE)
    cargar(db, mundo, res, "a" * 64)
    for periodo, esperados in (("2026-07", 3583), ("2026-08", 3277)):
        saldos = filas(db, mundo.hotel_a, periodo)
        assert sum(n for _, _, n in saldos.values()) == esperados
    total_d = sum(
        (d for p in ("2026-07", "2026-08") for d, _, _ in filas(db, mundo.hotel_a, p).values()),
        D("0"),
    )
    total_c = sum(
        (c for p in ("2026-07", "2026-08") for _, c, _ in filas(db, mundo.hotel_a, p).values()),
        D("0"),
    )
    assert (total_d, total_c) == (D("12650614.04"), D("12037735.88"))
