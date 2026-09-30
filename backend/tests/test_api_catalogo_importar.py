import os
from pathlib import Path
from typing import Any

import pytest
from conftest import Mundo, como
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from xls_sintetico import a_xls, catalogo_basico, cuenta

from fpa.config import settings
from fpa.modelos import CuentaLocal, EventoAuditoria
from fpa.seguridad.archivos import FIRMA_OLE2

_CARPETA_DOCUMENTOS = Path(
    os.environ.get(
        "FPA_DATOS_REALES", Path.home() / "Desktop" / "PLATAFORMA FP&A E INTELIGENCIA HOTELERA"
    )
)
CATALOGO = _CARPETA_DOCUMENTOS / "Catalogo de cuentas.xls"
XLS = "application/vnd.ms-excel"


@pytest.fixture(autouse=True)
def almacenamiento(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path / "storage"))
    return tmp_path / "storage"


def importar(
    cliente: TestClient,
    mundo: Mundo,
    contenido: bytes,
    nombre: str = "Catalogo de cuentas.xls",
    usuario: str = "analista_a@test.local",
    hotel: int | None = None,
):  # type: ignore[no-untyped-def]
    return cliente.post(
        f"/api/v1/hoteles/{hotel or mundo.hotel_a}/catalogo/importar",
        files={"archivo": (nombre, contenido, XLS)},
        headers=como(usuario),
    )


def n_cuentas(db: Session) -> int:
    db.expire_all()
    return db.scalar(select(func.count()).select_from(CuentaLocal)) or 0


def acciones(db: Session) -> list[str]:
    db.expire_all()
    return [e.accion for e in db.scalars(select(EventoAuditoria).order_by(EventoAuditoria.id))]


def test_importar_crea_el_catalogo_y_responde_el_resumen(
    cliente: TestClient, db: Session, mundo: Mundo, almacenamiento: Path
) -> None:
    r = importar(cliente, mundo, a_xls(catalogo_basico()))
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["resolucion"] == "importado"
    assert (cuerpo["total_cuentas"], cuerpo["total_titulos"], cuerpo["creadas"]) == (5, 6, 11)
    assert cuerpo["titulos_con_nombre_nuevo"] == 6
    assert any("6009002" in a for a in cuerpo["avisos"])  # cuenta inactiva
    assert n_cuentas(db) == 11
    assert acciones(db) == ["catalogo.importado"]
    guardados = list((almacenamiento / "catalogos" / str(mundo.hotel_a)).glob("*.xls"))
    assert len(guardados) == 1
    assert list((almacenamiento / "tmp").glob("*")) == []  # sin temporales


def test_importar_el_mismo_catalogo_otra_vez_no_cambia_nada(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    contenido = a_xls(catalogo_basico())
    assert importar(cliente, mundo, contenido).status_code == 201
    r = importar(cliente, mundo, contenido)
    assert r.status_code == 200 and r.json()["resolucion"] == "sin_cambio"
    assert n_cuentas(db) == 11
    assert acciones(db) == ["catalogo.importado", "catalogo.sin_cambio"]


def test_el_arbol_muestra_nombres_tipo_y_clasificaciones(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    importar(cliente, mundo, a_xls(catalogo_basico()))
    arbol = cliente.get(
        f"/api/v1/hoteles/{mundo.hotel_a}/catalogo/arbol", headers=como("analista_a@test.local")
    ).json()
    raices = {n["codigo"]: n for n in arbol}
    assert raices["4"]["descripcion"] == "INGRESOS" and raices["6"]["descripcion"] == "GASTOS"
    bar = raices["4"]["hijos"][0]["hijos"][0]["hijos"][0]["hijos"][
        0
    ]  # 4 > 40 > 4001 > 4001002 > .001
    assert bar["codigo"] == "4001002.001"
    assert (bar["tipo"], bar["grupo_ef"], bar["depto_ef"]) == ("Acreedor", "INCOME", "BAR")
    assert bar["cuenta_sat"] == "401.01 Ventas" and bar["en_catalogo_oficial"] is True


def test_solo_quien_tiene_el_permiso_importa(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    contenido = a_xls(catalogo_basico())
    assert (
        importar(cliente, mundo, contenido, usuario="responsable_a@test.local").status_code == 403
    )
    assert importar(cliente, mundo, contenido, usuario="contralor_c@test.local").status_code == 404
    assert importar(cliente, mundo, contenido, hotel=mundo.hotel_b).status_code == 404
    assert n_cuentas(db) == 0
    assert importar(cliente, mundo, contenido, usuario="contralor_ab@test.local").status_code == 201


def test_sin_sesion_es_401(cliente: TestClient, mundo: Mundo) -> None:
    r = cliente.post(
        f"/api/v1/hoteles/{mundo.hotel_a}/catalogo/importar",
        files={"archivo": ("c.xls", a_xls(catalogo_basico()), XLS)},
    )
    assert r.status_code == 401


def test_el_catalogo_queda_solo_en_su_hotel(cliente: TestClient, db: Session, mundo: Mundo) -> None:
    importar(cliente, mundo, a_xls(catalogo_basico()), usuario="contralor_ab@test.local")
    en_b = cliente.get(
        f"/api/v1/hoteles/{mundo.hotel_b}/catalogo/arbol", headers=como("contralor_ab@test.local")
    )
    assert en_b.status_code == 200 and en_b.json() == []


# --- Archivos inválidos o peligrosos ---------------------------------------------------------


@pytest.mark.parametrize(
    ("nombre", "estado"),
    [
        ("catalogo.xlsx", 415),
        ("catalogo.xlsm", 415),
        ("catalogo.csv", 415),
        ("catalogo.xls.exe", 415),
        ("catalogo", 415),
    ],
)
def test_extensiones_no_permitidas(
    cliente: TestClient, db: Session, mundo: Mundo, nombre: str, estado: int
) -> None:
    r = importar(cliente, mundo, a_xls(catalogo_basico()), nombre=nombre)
    assert r.status_code == estado
    assert n_cuentas(db) == 0 and "catalogo.archivo_rechazado" in acciones(db)


def test_un_falso_xls_de_texto_se_rechaza(cliente: TestClient, db: Session, mundo: Mundo) -> None:
    r = importar(cliente, mundo, b"esto no es un excel", nombre="falso.xls")
    assert r.status_code == 415 and "no es un libro" in r.json()["detail"]


def test_un_xls_con_macros_se_rechaza(cliente: TestClient, db: Session, mundo: Mundo) -> None:
    con_macros = a_xls(catalogo_basico()) + "_VBA_PROJECT".encode("utf-16-le")
    assert con_macros[:8] == FIRMA_OLE2
    r = importar(cliente, mundo, con_macros, nombre="macros.xls")
    assert r.status_code == 415 and "macros" in r.json()["detail"]
    assert n_cuentas(db) == 0


def test_un_ole2_que_no_es_excel_se_rechaza(cliente: TestClient, db: Session, mundo: Mundo) -> None:
    r = importar(cliente, mundo, FIRMA_OLE2 + b"\x00" * 600, nombre="roto.xls")
    assert r.status_code == 422 and "xls" in r.json()["detail"].lower()
    assert n_cuentas(db) == 0


def test_archivo_vacio_y_archivo_demasiado_grande(
    cliente: TestClient, db: Session, mundo: Mundo, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert importar(cliente, mundo, b"", nombre="vacio.xls").status_code == 400
    monkeypatch.setattr(settings, "carga_max_bytes", 1000)
    assert importar(cliente, mundo, a_xls(catalogo_basico())).status_code == 413


def test_un_catalogo_con_datos_invalidos_se_rechaza_con_el_motivo(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    filas = [*catalogo_basico(), cuenta("6009003", "", "X", tipo="Raro")]
    r = importar(cliente, mundo, a_xls(filas))
    assert r.status_code == 422
    cuerpo: dict[str, Any] = r.json()
    assert cuerpo["resolucion"] == "rechazado"
    assert any("6009003" in m and "TIPO" in m for m in cuerpo["motivos"])
    assert n_cuentas(db) == 0 and "catalogo.rechazado" in acciones(db)


def test_el_nombre_original_nunca_forma_parte_de_la_ruta(
    cliente: TestClient, db: Session, mundo: Mundo, almacenamiento: Path
) -> None:
    r = importar(cliente, mundo, a_xls(catalogo_basico()), nombre="../../../etc/passwd/../x.xls")
    assert r.status_code == 201
    assert all(almacenamiento in p.parents for p in almacenamiento.rglob("*.xls"))


# --- Con el archivo real de Torres -----------------------------------------------------------


@pytest.mark.skipif(not CATALOGO.exists(), reason="El catálogo real no está en la carpeta")
def test_importar_el_catalogo_real_por_la_api(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    r = importar(
        cliente,
        mundo,
        CATALOGO.read_bytes(),
        nombre=CATALOGO.name,
        usuario="contralor_ab@test.local",
    )
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert (cuerpo["total_cuentas"], cuerpo["total_titulos"], cuerpo["creadas"]) == (1238, 68, 1306)
    assert n_cuentas(db) == 1306
    assert (
        importar(
            cliente,
            mundo,
            CATALOGO.read_bytes(),
            nombre=CATALOGO.name,
            usuario="contralor_ab@test.local",
        ).status_code
        == 200
    )
    arbol = cliente.get(
        f"/api/v1/hoteles/{mundo.hotel_a}/catalogo/arbol", headers=como("contralor_ab@test.local")
    ).json()
    assert {n["codigo"]: n["descripcion"] for n in arbol} == {
        "1": "ACTIVO",
        "2": "PASIVO",
        "3": "CAPITAL",
        "4": "INGRESOS",
        "5": "COSTO",
        "6": "GASTOS",
    }
