"""Fase 5.4: flujo de cierre del Variance, versiones congeladas y candados."""

import io
from decimal import Decimal

import pytest
import test_versionado_mapeo as tv
from conftest import Mundo, como
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_versionado_mapeo import Escenario

from fpa.ingesta.contrato import Fuente, ResultadoLectura
from fpa.modelos import CierreTransicion, EventoAuditoria
from fpa.modelos.cierre import TransicionInmutable
from fpa.servicios.cargar_archivo import Resolucion, cargar_archivo
from fpa.servicios.cargas import DatosArchivo
from fpa.servicios.cierre_candado import PeriodoCerrado, exigir_abierto
from fpa.servicios.versionado_mapeo import (
    aprobar,
    crear_borrador_desde,
    excluir_cuenta,
    quitar_vinculo,
)

CONTRALOR = "contralor_ab@test.local"
ANALISTA = "analista_a@test.local"
RESPONSABLE = "responsable_a@test.local"
OTRA_ORG = "contralor_c@test.local"
D = Decimal


def _url(mundo: Mundo, ruta: str) -> str:
    return f"/api/v1/hoteles/{mundo.hotel_a}/{ruta}"


def _pasar(cliente, mundo, hacia, usuario=CONTRALOR, nota=None, periodo="2026-08"):  # type: ignore[no-untyped-def]
    return cliente.post(
        _url(mundo, f"cierres/{periodo}/transiciones"),
        json={"hacia": hacia, "nota": nota},
        headers=como(usuario),
    )


def _hasta_revisado(cliente, mundo):  # type: ignore[no-untyped-def]
    assert _pasar(cliente, mundo, "comentado", ANALISTA).status_code == 200
    assert _pasar(cliente, mundo, "revisado", ANALISTA).status_code == 200


def _variance(cliente, mundo, usuario=ANALISTA):  # type: ignore[no-untyped-def]
    r = cliente.get(_url(mundo, "variance?periodo=2026-08"), headers=como(usuario))
    assert r.status_code == 200, r.text
    return {x["descripcion"]: x["mes"]["actual"] for x in r.json()["lineas"]}


# --- Flujo --------------------------------------------------------------------------------------


def test_un_periodo_sin_cierre_esta_en_borrador(
    cliente: TestClient, mundo: Mundo, esc: Escenario
) -> None:
    r = cliente.get(_url(mundo, "cierres/2026-08"), headers=como(ANALISTA)).json()
    assert r["estado"] == "borrador" and r["historial"] == []
    assert [t["hacia"] for t in r["transiciones_posibles"]] == ["comentado"]
    # el contralor ve ahí solo lo que su rol permite en este estado
    c = cliente.get(_url(mundo, "cierres/2026-08"), headers=como(CONTRALOR)).json()
    assert [t["hacia"] for t in c["transiciones_posibles"]] == ["comentado"]


def test_recorrido_completo_con_historial_y_bitacora(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    _hasta_revisado(cliente, mundo)
    r = cliente.get(_url(mundo, "cierres/2026-08"), headers=como(CONTRALOR)).json()
    assert {t["hacia"] for t in r["transiciones_posibles"]} == {"aprobado", "borrador"}
    assert _pasar(cliente, mundo, "aprobado", CONTRALOR, "Listo para Dirección").status_code == 200
    assert _pasar(cliente, mundo, "bloqueado", CONTRALOR).status_code == 200
    h = cliente.get(_url(mundo, "cierres/2026-08"), headers=como(CONTRALOR)).json()
    assert [(x["desde"], x["hacia"]) for x in h["historial"]] == [
        ("borrador", "comentado"),
        ("comentado", "revisado"),
        ("revisado", "aprobado"),
        ("aprobado", "bloqueado"),
    ]
    assert h["historial"][2]["nota"] == "Listo para Dirección"
    assert h["estado"] == "bloqueado" and h["transiciones_posibles"] == []
    acciones = [e.accion for e in db.scalars(select(EventoAuditoria).order_by(EventoAuditoria.id))]
    assert acciones[-4:] == [
        "cierre.comentado",
        "cierre.revisado",
        "cierre.aprobado",
        "cierre.bloqueado",
    ]
    lista = cliente.get(_url(mundo, "cierres"), headers=como(CONTRALOR)).json()
    assert lista == [{"periodo": "2026-08", "estado": "bloqueado"}]


@pytest.mark.parametrize("hacia", ["revisado", "aprobado", "bloqueado", "inventado"])
def test_las_transiciones_invalidas_dan_409(
    cliente: TestClient, mundo: Mundo, esc: Escenario, hacia: str
) -> None:
    assert _pasar(cliente, mundo, hacia).status_code == 409


def test_devolver_y_reabrir_piden_nota(cliente: TestClient, mundo: Mundo, esc: Escenario) -> None:
    _hasta_revisado(cliente, mundo)
    assert _pasar(cliente, mundo, "borrador", ANALISTA).status_code == 422
    assert _pasar(cliente, mundo, "borrador", ANALISTA, "   ").status_code == 422
    assert _pasar(cliente, mundo, "borrador", ANALISTA, "Falta explicar Gasto").status_code == 200
    _hasta_revisado(cliente, mundo)
    _pasar(cliente, mundo, "aprobado")
    assert _pasar(cliente, mundo, "borrador", CONTRALOR).status_code == 422
    assert _pasar(cliente, mundo, "borrador", CONTRALOR, "Llegó un ajuste").status_code == 200


def test_un_bloqueado_ya_no_se_reabre(cliente: TestClient, mundo: Mundo, esc: Escenario) -> None:
    _hasta_revisado(cliente, mundo)
    _pasar(cliente, mundo, "aprobado")
    _pasar(cliente, mundo, "bloqueado")
    assert _pasar(cliente, mundo, "borrador", CONTRALOR, "quiero abrirlo").status_code == 409


def test_permisos_por_transicion(cliente: TestClient, mundo: Mundo, esc: Escenario) -> None:
    _hasta_revisado(cliente, mundo)
    assert _pasar(cliente, mundo, "aprobado", ANALISTA).status_code == 403  # solo el Contralor
    _pasar(cliente, mundo, "aprobado", CONTRALOR)
    assert _pasar(cliente, mundo, "bloqueado", ANALISTA).status_code == 403
    assert _pasar(cliente, mundo, "borrador", ANALISTA, "x").status_code == 403
    # el responsable de departamento ni siquiera lee el cierre; otra organización tampoco
    assert cliente.get(_url(mundo, "cierres/2026-08"), headers=como(RESPONSABLE)).status_code == 403
    assert cliente.get(_url(mundo, "cierres/2026-08"), headers=como(OTRA_ORG)).status_code == 404
    assert cliente.get(_url(mundo, "cierres/2026-08")).status_code == 401
    assert cliente.get(_url(mundo, "cierres/2026-13"), headers=como(CONTRALOR)).status_code == 422


# --- Versiones congeladas -----------------------------------------------------------------------


def test_aprobar_congela_versiones_cargas_y_cifras(
    cliente: TestClient, mundo: Mundo, esc: Escenario
) -> None:
    _hasta_revisado(cliente, mundo)
    c = _pasar(cliente, mundo, "aprobado").json()
    assert c["version_mapeo_id"] == esc.borrador.id  # type: ignore[union-attr]
    assert c["version_estructura_id"] == esc.estructura.id
    assert len(c["huella_cifras"]) == 64
    assert c["congelado"]["periodos_ytd"] == ["2026-07", "2026-08"]
    agosto = next(x for x in c["congelado"]["cargas"] if x["periodo"] == "2026-08")
    assert agosto["sha256"] == "m" * 64 and agosto["archivo"] == "m.xlsx"


def _nuevo_mapeo_sin_gasto(esc: Escenario, db: Session, mundo: Mundo) -> int:
    nuevo = crear_borrador_desde(
        db, organizacion_id=mundo.org1, hotel_id=mundo.hotel_a, usuario_id=None
    )
    quitar_vinculo(
        db,
        version_id=nuevo.id,
        linea_id=esc.linea("Gasto"),
        cuenta_codigo="6009001.001",
        **esc.kw,  # type: ignore[arg-type]
    )
    excluir_cuenta(db, version_id=nuevo.id, cuenta_codigo="6009001.001", motivo="prueba", **esc.kw)  # type: ignore[arg-type]
    aprobar(db, version_id=nuevo.id, **esc.kw)  # type: ignore[arg-type]
    db.commit()
    return nuevo.id


def test_el_variance_de_un_periodo_cerrado_no_cambia_con_un_mapeo_nuevo(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    antes = _variance(cliente, mundo)
    assert antes["Gasto"] == "30.00"
    _hasta_revisado(cliente, mundo)
    _pasar(cliente, mundo, "aprobado")
    _nuevo_mapeo_sin_gasto(esc, db, mundo)
    # cerrado: sigue con el mapeo con que se aprobó
    assert _variance(cliente, mundo) == antes
    v = cliente.get(_url(mundo, "variance?periodo=2026-08"), headers=como(ANALISTA)).json()
    assert v["version_mapeo_id"] == esc.borrador.id  # type: ignore[union-attr]
    # otro periodo (sin cierre) sí usa el mapeo nuevo
    otro = cliente.get(_url(mundo, "variance?periodo=2026-07"), headers=como(ANALISTA)).json()
    assert otro["version_mapeo_id"] != esc.borrador.id  # type: ignore[union-attr]
    # al reabrir, el periodo vuelve a calcularse con el mapeo vigente
    _pasar(cliente, mundo, "borrador", CONTRALOR, "Revisar el nuevo mapeo")
    assert _variance(cliente, mundo)["Gasto"] == "0.00"


def test_el_desglose_y_el_excel_usan_el_mapeo_congelado(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    _hasta_revisado(cliente, mundo)
    _pasar(cliente, mundo, "aprobado")
    _nuevo_mapeo_sin_gasto(esc, db, mundo)
    d = cliente.get(
        _url(mundo, f"variance/lineas/{esc.linea('Gasto')}/desglose?periodo=2026-08"),
        headers=como(ANALISTA),
    ).json()
    assert d["cifra"] == "30.00" and d["cuadra"] is True
    from openpyxl import load_workbook

    x = cliente.get(_url(mundo, "variance/exportar?periodo=2026-08"), headers=como(ANALISTA))
    libro = load_workbook(io.BytesIO(x.content))
    notas = [c.value for c in libro["Notas"]["A"] if c.value]
    assert "Estado del cierre: aprobado" in notas
    assert f"Mapeo de cuentas: versión {esc.borrador.id}" in notas  # type: ignore[union-attr]


# --- Candados -----------------------------------------------------------------------------------


def _recarga(db: Session, mundo: Mundo, sha: str = "n" * 64, mes: int = 8):  # type: ignore[no-untyped-def]
    r = ResultadoLectura(fuente=Fuente.VARIANCE_BASE_DATOS, controla_balance=False)
    m = tv._mov("6009001.001", "99", "0")
    r.movimientos = [m.__class__(**{**m.__dict__, "fecha": m.fecha.replace(month=mes)})]
    return cargar_archivo(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        resultado=r,
        archivo=DatosArchivo(nombre="otro.xlsx", sha256=sha),
        confirmar_reemplazo=True,
    )


def test_un_periodo_cerrado_rechaza_recargas_y_una_reabierto_las_acepta(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    _hasta_revisado(cliente, mundo)
    _pasar(cliente, mundo, "aprobado")
    for mes in (8, 7):  # el mes del cierre y un mes de su acumulado
        r = _recarga(db, mundo, mes=mes)
        assert r.resolucion is Resolucion.RECHAZADA
        assert "cierre de 2026-08" in r.motivos[0]
    # el mismo archivo ya cargado no cambia nada: no se rechaza
    mismo = _recarga(db, mundo, sha="m" * 64)
    assert mismo.resolucion is not Resolucion.RECHAZADA
    # un mes fuera del acumulado no está protegido
    assert _recarga(db, mundo, sha="o" * 64, mes=9).resolucion is Resolucion.CREADA
    _pasar(cliente, mundo, "borrador", CONTRALOR, "Reabrir para recargar")
    assert _recarga(db, mundo, sha="p" * 64, mes=8).resolucion is Resolucion.REEMPLAZADA


def test_los_meses_protegidos_son_los_del_acumulado(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    exigir_abierto(db, mundo.hotel_a, ["2026-07", "2026-08"])  # sin cierre, todo abierto
    _hasta_revisado(cliente, mundo)
    exigir_abierto(db, mundo.hotel_a, ["2026-07", "2026-08"])  # revisado todavía no protege
    _pasar(cliente, mundo, "aprobado")
    with pytest.raises(PeriodoCerrado):
        exigir_abierto(db, mundo.hotel_a, ["2026-07"])
    exigir_abierto(db, mundo.hotel_a, ["2026-06", "2026-09"])


def test_un_cierre_bloqueado_no_admite_comentarios(
    cliente: TestClient, mundo: Mundo, esc: Escenario
) -> None:
    cuerpo = {
        "linea_id": esc.linea("Ingreso"),
        "periodo": "2026-08",
        "bloque": "mes",
        "texto": "ok",
    }
    c = cliente.post(_url(mundo, "comentarios"), json=cuerpo, headers=como(ANALISTA))
    assert c.status_code == 201
    _hasta_revisado(cliente, mundo)
    _pasar(cliente, mundo, "aprobado")
    # aprobado todavía permite explicar; bloqueado ya no
    r = cliente.post(
        _url(mundo, f"comentarios/{c.json()['id']}/respuestas"),
        json={"texto": "x"},
        headers=como(ANALISTA),
    )
    assert r.status_code == 201
    _pasar(cliente, mundo, "bloqueado")
    assert (
        cliente.post(_url(mundo, "comentarios"), json=cuerpo, headers=como(ANALISTA)).status_code
        == 409
    )
    r = cliente.post(
        _url(mundo, f"comentarios/{c.json()['id']}/respuestas"),
        json={"texto": "y"},
        headers=como(ANALISTA),
    )
    assert r.status_code == 409
    # leer sigue permitido
    assert (
        cliente.get(_url(mundo, "comentarios?periodo=2026-08"), headers=como(ANALISTA)).status_code
        == 200
    )


def test_las_transiciones_no_se_pueden_modificar_ni_borrar(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    _pasar(cliente, mundo, "comentado", ANALISTA)
    t = db.scalars(select(CierreTransicion)).one()
    t.nota = "alterada"
    with pytest.raises(TransicionInmutable):
        db.flush()
    db.rollback()
    t = db.scalars(select(CierreTransicion)).one()
    db.delete(t)
    with pytest.raises(TransicionInmutable):
        db.flush()
    db.rollback()
