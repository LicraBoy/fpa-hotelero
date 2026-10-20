import base64
import json
from datetime import date
from decimal import Decimal

import pytest
from conftest import Mundo, como
from fastapi.testclient import TestClient
from real_agosto import AgostoReal, agosto_real  # noqa: F401
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_versionado_mapeo import EJEMPLO, Escenario

from fpa.ingesta.contrato import Fuente, ResultadoLectura
from fpa.ingesta.contrato import Movimiento as MovimientoLeido
from fpa.ingesta.variance_estructura import leer_variance_estructura_filas
from fpa.ingesta.variance_reglas import leer_variance_reglas_filas
from fpa.modelos import EventoAuditoria
from fpa.servicios.cargar_archivo import Resolucion, cargar_archivo
from fpa.servicios.cargas import DatosArchivo
from fpa.servicios.drilldown import (
    CursorInvalido,
    codificar_cursor,
    decodificar_cursor,
    desglose_de_linea,
    movimientos_de_cuenta,
    vista_de_asiento,
)
from fpa.servicios.reglas_suma import importar_reglas_suma
from fpa.servicios.variance import calcular_variance
from fpa.servicios.versionado_mapeo import aprobar

D = Decimal
ANALISTA = "analista_a@test.local"
CONTRALOR = "contralor_ab@test.local"
RESPONSABLE = "responsable_a@test.local"
OTRA_ORG = "contralor_c@test.local"


def mov(cuenta: str, debito: str, credito: str, mes: int, dia: int, asiento: str, fila: int):  # type: ignore[no-untyped-def]
    return MovimientoLeido(
        cuenta_codigo=cuenta,
        cuenta_descripcion=f"Cuenta {cuenta}",
        asiento=asiento,
        fecha=date(2026, mes, dia),
        concepto=f"Concepto <b>{fila}</b>",
        debito=D(debito),
        credito=D(credito),
        fila=fila,
    )


# 25 movimientos de gasto (julio y agosto) y 3 de ingreso (agosto)
GASTOS = [
    mov(
        "6009001.001",
        f"{10 + i}.{i:02d}",
        "0",
        7 if i < 10 else 8,
        1 + i % 27,
        f"{7 if i < 10 else 8}.1.{i}",
        i + 1,
    )
    for i in range(25)
]
INGRESOS = [
    mov("4001002.001", "0", "100.50", 8, 5, "8.1.100", 30),
    mov("4001002.001", "0", "200.25", 8, 6, "8.1.101", 31),
    mov("4001002.001", "0", "50.00", 8, 7, "8.1.102", 32),
]


def _preparar(db: Session, mundo: Mundo) -> Escenario:
    """Julio y agosto cargados (dos archivos), mapeo aprobado, reglas de suma importadas."""
    esc = Escenario(db, mundo, [m for m in GASTOS + INGRESOS if m.fecha.month == 8])
    julio = ResultadoLectura(fuente=Fuente.VARIANCE_BASE_DATOS, controla_balance=False)
    julio.movimientos = [m for m in GASTOS if m.fecha.month == 7]
    r = cargar_archivo(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        resultado=julio,
        archivo=DatosArchivo(nombre="julio.xlsx", sha256="j" * 64),
    )
    assert r.resolucion is Resolucion.CREADA
    reglas = leer_variance_reglas_filas(EJEMPLO, leer_variance_estructura_filas(EJEMPLO))
    importar_reglas_suma(db, version=esc.estructura, leidas=reglas, **esc.kw)  # type: ignore[arg-type]
    aprobar(db, version_id=esc.borrador.id, **esc.kw)  # type: ignore[union-attr, arg-type]
    db.commit()
    return esc


def _todas_las_paginas(db: Session, mundo: Mundo, bloque: str, limite: int):  # type: ignore[no-untyped-def]
    cursor, paginas = None, []
    while True:
        p = movimientos_de_cuenta(
            db,
            hotel_id=mundo.hotel_a,
            periodo="2026-08",
            bloque=bloque,  # type: ignore[arg-type]
            cuenta_codigo="6009001.001",
            cursor=cursor,
            limite=limite,
        )
        paginas.append(p)
        cursor = p.siguiente_cursor
        if cursor is None:
            return paginas


# --- Cursor -----------------------------------------------------------------------------------


def test_el_cursor_va_y_viene() -> None:
    assert decodificar_cursor(codificar_cursor(12345)) == 12345


@pytest.mark.parametrize(
    "malo",
    [
        "",
        "no-es-base64!!",
        base64.urlsafe_b64encode(b"no es json").decode(),
        base64.urlsafe_b64encode(json.dumps({"v": 1, "id": -1}).encode()).decode(),
        base64.urlsafe_b64encode(json.dumps({"v": 2, "id": 1}).encode()).decode(),
        base64.urlsafe_b64encode(json.dumps({"v": 1, "id": "1"}).encode()).decode(),
        base64.urlsafe_b64encode(json.dumps({"v": 1, "id": True}).encode()).decode(),
        base64.urlsafe_b64encode(json.dumps({"v": 1, "id": 2**40}).encode()).decode(),
        base64.urlsafe_b64encode(json.dumps([1, 2]).encode()).decode(),
    ],
)
def test_un_cursor_manipulado_se_rechaza(malo: str) -> None:
    with pytest.raises(CursorInvalido):
        decodificar_cursor(malo)


# --- Movimientos: la suma de las páginas es el neto de la cuenta ------------------------------


@pytest.mark.parametrize("limite", [1, 2, 3, 7, 10, 25, 26, 200])
@pytest.mark.parametrize("bloque", ["mes", "ytd"])
def test_las_paginas_suman_el_neto_de_la_cuenta(
    db: Session, mundo: Mundo, bloque: str, limite: int
) -> None:
    _preparar(db, mundo)
    paginas = _todas_las_paginas(db, mundo, bloque, limite)
    ids = [m.id for p in paginas for m in p.movimientos]
    assert len(ids) == len(set(ids)) and ids == sorted(ids)  # sin repetidos, en orden
    esperados = [g for g in GASTOS if bloque == "ytd" or g.fecha.month == 8]
    assert len(ids) == len(esperados) == paginas[0].resumen.n_movimientos
    suma = sum((m.debito - m.credito for p in paginas for m in p.movimientos), D("0"))
    assert suma == paginas[0].resumen.neto == sum((g.debito for g in esperados), D("0"))
    assert all(len(p.movimientos) <= limite for p in paginas)
    assert all(p.siguiente_cursor for p in paginas[:-1]) and paginas[-1].siguiente_cursor is None


@pytest.mark.parametrize("bloque", ["mes", "ytd"])
def test_la_suma_de_los_movimientos_es_la_cifra_del_reporte(
    db: Session, mundo: Mundo, bloque: str
) -> None:
    esc = _preparar(db, mundo)
    r = calcular_variance(db, hotel_id=mundo.hotel_a, periodo="2026-08")
    gasto = r.resultado[esc.linea("Gasto")]
    cifra = gasto.mes.actual if bloque == "mes" else gasto.ytd.actual
    movs = [m for p in _todas_las_paginas(db, mundo, bloque, 4) for m in p.movimientos]
    assert sum((m.debito - m.credito for m in movs), D("0")) == cifra  # signo +1 (Deudor)
    d = desglose_de_linea(
        db,
        hotel_id=mundo.hotel_a,
        periodo="2026-08",
        linea_id=esc.linea("Gasto"),
        bloque=bloque,  # type: ignore[arg-type]
    )
    assert d.cuadra and d.cifra == d.suma == cifra
    assert [(c.cuenta_codigo, c.n_movimientos) for c in d.cuentas] == [
        ("6009001.001", 25 if bloque == "ytd" else 15)
    ]


def test_ingreso_aporta_con_signo_menos_uno(db: Session, mundo: Mundo) -> None:
    esc = _preparar(db, mundo)
    d = desglose_de_linea(
        db, hotel_id=mundo.hotel_a, periodo="2026-08", linea_id=esc.linea("Ingreso"), bloque="mes"
    )
    (cuenta,) = d.cuentas
    assert (cuenta.signo, cuenta.neto, cuenta.aporte) == (-1, D("-350.75"), D("350.75"))
    assert d.cuadra and d.cifra == D("350.75")


def test_un_total_se_desglosa_en_sus_componentes(db: Session, mundo: Mundo) -> None:
    esc = _preparar(db, mundo)
    d = desglose_de_linea(
        db, hotel_id=mundo.hotel_a, periodo="2026-08", linea_id=esc.linea("Total"), bloque="mes"
    )
    assert [(c.descripcion, c.signo) for c in d.componentes] == [("Ingreso", 1), ("Gasto", -1)]
    assert d.cuentas == [] and d.cuadra
    assert d.cifra == D("350.75") - sum((g.debito for g in GASTOS if g.fecha.month == 8), D("0"))


def test_una_linea_con_cifra_no_trae_motivos_de_cero(db: Session, mundo: Mundo) -> None:
    esc = _preparar(db, mundo)
    d = desglose_de_linea(
        db, hotel_id=mundo.hotel_a, periodo="2026-08", linea_id=esc.linea("Gasto"), bloque="mes"
    )
    assert d.motivos_cero == []
    assert [c.estado for c in d.cuentas] == ["con_movimientos"]
    assert d.codigo_corporativo == "029-0000-2-000"


def test_actual_en_cero_porque_el_mes_no_tiene_carga(db: Session, mundo: Mundo) -> None:
    esc = _preparar(db, mundo)
    d = desglose_de_linea(
        db, hotel_id=mundo.hotel_a, periodo="2026-09", linea_id=esc.linea("Gasto"), bloque="mes"
    )
    assert d.cifra == D("0")
    assert [m.codigo for m in d.motivos_cero] == ["mes_sin_carga"]
    # sigue diciendo qué cuentas usa la línea, aunque no tengan movimientos
    assert [(c.cuenta_codigo, c.estado) for c in d.cuentas] == [("6009001.001", "sin_movimientos")]


def test_actual_en_cero_con_cuentas_sin_movimientos_en_un_mes_cargado(
    db: Session, mundo: Mundo
) -> None:
    esc = _preparar(db, mundo)
    # julio tiene gastos pero no ingresos: el Ingreso de julio sale en 0 con su mes cargado
    d = desglose_de_linea(
        db, hotel_id=mundo.hotel_a, periodo="2026-07", linea_id=esc.linea("Ingreso"), bloque="mes"
    )
    assert d.cifra == D("0")
    assert [m.codigo for m in d.motivos_cero] == ["cuentas_sin_movimientos"]
    assert [c.estado for c in d.cuentas] == ["sin_movimientos"]


def test_linea_inexistente_o_seccion(db: Session, mundo: Mundo) -> None:
    _preparar(db, mundo)
    with pytest.raises(LookupError):
        desglose_de_linea(db, hotel_id=mundo.hotel_a, periodo="2026-08", linea_id=999, bloque="mes")


def test_limite_fuera_de_rango(db: Session, mundo: Mundo) -> None:
    _preparar(db, mundo)
    for limite in (0, 201):
        with pytest.raises(ValueError):
            movimientos_de_cuenta(
                db,
                hotel_id=mundo.hotel_a,
                periodo="2026-08",
                bloque="mes",
                cuenta_codigo="6009001.001",
                limite=limite,
            )


def test_cuenta_sin_movimientos_da_una_pagina_vacia(db: Session, mundo: Mundo) -> None:
    _preparar(db, mundo)
    p = movimientos_de_cuenta(
        db, hotel_id=mundo.hotel_a, periodo="2026-08", bloque="mes", cuenta_codigo="9999999"
    )
    assert p.movimientos == [] and p.siguiente_cursor is None and p.resumen.n_movimientos == 0


def test_solo_cuentan_las_cargas_vigentes_y_el_hotel(db: Session, mundo: Mundo) -> None:
    _preparar(db, mundo)
    otro = movimientos_de_cuenta(
        db, hotel_id=mundo.hotel_b, periodo="2026-08", bloque="mes", cuenta_codigo="6009001.001"
    )
    assert otro.movimientos == [] and otro.resumen.n_movimientos == 0


def test_vista_de_asiento(db: Session, mundo: Mundo) -> None:
    _preparar(db, mundo)
    v = vista_de_asiento(db, hotel_id=mundo.hotel_a, periodo="2026-08", asiento="8.1.100")
    assert [m.cuenta_codigo for m in v.movimientos] == ["4001002.001"]
    assert (v.debito, v.credito, v.cuadra, v.truncado) == (D("0"), D("100.50"), False, False)
    assert (
        vista_de_asiento(db, hotel_id=mundo.hotel_a, periodo="2026-08", asiento="x").movimientos
        == []
    )


# --- API --------------------------------------------------------------------------------------


def _url(mundo: Mundo, ruta: str, hotel: int | None = None) -> str:
    return f"/api/v1/hoteles/{hotel or mundo.hotel_a}/{ruta}"


def test_api_recorrido_completo_y_sumas(cliente: TestClient, mundo: Mundo, db: Session) -> None:
    esc = _preparar(db, mundo)
    h = como(ANALISTA)
    d = cliente.get(
        _url(mundo, f"variance/lineas/{esc.linea('Gasto')}/desglose?periodo=2026-08&bloque=ytd"),
        headers=h,
    ).json()
    assert d["cuadra"] is True and d["cuentas"][0]["n_movimientos"] == 25
    cuenta = d["cuentas"][0]["cuenta_codigo"]

    vistos, cursor, paginas = [], None, 0
    while True:
        q = "periodo=2026-08&bloque=ytd&limite=10" + (f"&cursor={cursor}" if cursor else "")
        r = cliente.get(_url(mundo, f"variance/cuentas/{cuenta}/movimientos?{q}"), headers=h)
        assert r.status_code == 200, r.text
        pagina = r.json()
        vistos += pagina["movimientos"]
        paginas += 1
        cursor = pagina["siguiente_cursor"]
        if not cursor:
            break
    assert paginas == 3 and len(vistos) == 25
    suma = sum((D(m["neto"]) for m in vistos), D("0"))
    assert suma == D(pagina["resumen"]["neto"]) == D(d["cifra"]) == D(d["suma"])
    # el texto de un concepto con HTML viaja tal cual (la pantalla lo muestra como texto)
    assert "<b>" in vistos[0]["concepto"]

    asiento = vistos[0]["asiento"]
    a = cliente.get(_url(mundo, f"asientos/{asiento}?periodo={vistos[0]['periodo']}"), headers=h)
    assert a.status_code == 200 and a.json()["movimientos"][0]["cuenta_codigo"] == cuenta


def test_api_cursor_y_parametros_invalidos(cliente: TestClient, mundo: Mundo, db: Session) -> None:
    _preparar(db, mundo)
    h = como(ANALISTA)
    base = _url(mundo, "variance/cuentas/6009001.001/movimientos?periodo=2026-08")
    assert cliente.get(f"{base}&cursor=basura", headers=h).status_code == 422
    assert cliente.get(f"{base}&limite=0", headers=h).status_code == 422
    assert cliente.get(f"{base}&limite=201", headers=h).status_code == 422
    assert cliente.get(f"{base}&bloque=anual", headers=h).status_code == 422
    assert (
        cliente.get(_url(mundo, "variance/cuentas/6009001.001/movimientos"), headers=h).status_code
        == 422
    )
    assert (
        cliente.get(
            _url(mundo, "variance/cuentas/%27%20OR%201%3D1/movimientos?periodo=2026-08"), headers=h
        ).status_code
        == 422
    )
    assert (
        cliente.get(
            _url(mundo, "variance/lineas/999/desglose?periodo=2026-08"), headers=h
        ).status_code
        == 404
    )
    assert (
        cliente.get(_url(mundo, "asientos/no-existe?periodo=2026-08"), headers=h).status_code == 404
    )


def test_api_permisos_y_aislamiento(cliente: TestClient, mundo: Mundo, db: Session) -> None:
    esc = _preparar(db, mundo)
    rutas = [
        f"variance/lineas/{esc.linea('Gasto')}/desglose?periodo=2026-08",
        "variance/cuentas/6009001.001/movimientos?periodo=2026-08",
        "asientos/8.1.100?periodo=2026-08",
    ]
    for ruta in rutas:
        assert cliente.get(_url(mundo, ruta), headers=como(CONTRALOR)).status_code == 200
        assert cliente.get(_url(mundo, ruta), headers=como(ANALISTA)).status_code == 200
        # el responsable sin secciones asignadas no ve línea, cuenta ni (nunca) asientos
        sin_acceso = 403 if ruta.startswith("asientos") else 404
        assert cliente.get(_url(mundo, ruta), headers=como(RESPONSABLE)).status_code == sin_acceso
        assert cliente.get(_url(mundo, ruta), headers=como(OTRA_ORG)).status_code == 404
        assert cliente.get(_url(mundo, ruta)).status_code == 401
        # El hotel B (donde el contralor sí tiene acceso) no ve nada del A: ni su mapeo ni sus
        # movimientos. Una cuenta sin movimientos da una página vacía, no los datos de otro hotel.
        r = cliente.get(_url(mundo, ruta, hotel=mundo.hotel_b), headers=como(CONTRALOR))
        if "movimientos" in ruta:
            assert r.status_code == 200
            assert r.json()["movimientos"] == [] and r.json()["resumen"]["n_movimientos"] == 0
        else:
            assert r.status_code == 404


def test_api_la_primera_consulta_queda_en_la_bitacora_sin_contenido(
    cliente: TestClient, mundo: Mundo, db: Session
) -> None:
    _preparar(db, mundo)
    base = _url(mundo, "variance/cuentas/6009001.001/movimientos?periodo=2026-08&limite=5")
    primera = cliente.get(base, headers=como(ANALISTA)).json()
    cliente.get(f"{base}&cursor={primera['siguiente_cursor']}", headers=como(ANALISTA))
    db.expire_all()
    eventos = [e for e in db.scalars(select(EventoAuditoria)) if e.accion == "drilldown.consultado"]
    assert len(eventos) == 1  # solo la primera página; las siguientes no ensucian la bitácora
    assert eventos[0].detalle == {
        "cuenta": "6009001.001",
        "periodo": "2026-08",
        "bloque": "mes",
        "n_movimientos": 15,
    }


# --- Agosto real: la suma de lo mostrado es la cifra, en TODAS las líneas ---------------------


def test_agosto_real_cada_linea_cuadra_con_sus_partes(agosto_real: AgostoReal) -> None:  # noqa: F811
    a = agosto_real
    sin_cuadrar, revisadas = [], 0
    for linea in a.lineas:
        if linea.tipo == "seccion":
            continue
        for bloque in ("mes", "ytd"):
            d = desglose_de_linea(
                a.db,
                hotel_id=a.hotel_id,
                periodo="2026-08",
                linea_id=linea.id,
                bloque=bloque,  # type: ignore[arg-type]
                version_mapeo_id=a.version_mapeo_id,
            )
            revisadas += 1
            if not d.cuadra:
                sin_cuadrar.append((linea.fila_origen, bloque))
    assert revisadas > 900 and sin_cuadrar == []


def test_agosto_real_los_movimientos_suman_el_neto_de_cuentas_grandes(
    agosto_real: AgostoReal,  # noqa: F811
) -> None:
    a = agosto_real
    # incluye la cuenta con más movimientos del Excel (5001004.001, ~2,000 filas)
    for cuenta in ("5001004.001", "5001002.002", "6006035.001", "4001005.001", "6009001.001"):
        for bloque in ("mes", "ytd"):
            cursor, suma, n = None, D("0"), 0
            while True:
                p = movimientos_de_cuenta(
                    a.db,
                    hotel_id=a.hotel_id,
                    periodo="2026-08",
                    bloque=bloque,  # type: ignore[arg-type]
                    cuenta_codigo=cuenta,
                    cursor=cursor,
                    limite=200,
                )
                suma += sum((m.debito - m.credito for m in p.movimientos), D("0"))
                n += len(p.movimientos)
                cursor = p.siguiente_cursor
                if cursor is None:
                    break
            assert suma == p.resumen.neto and n == p.resumen.n_movimientos, (cuenta, bloque)
            assert n > 0
