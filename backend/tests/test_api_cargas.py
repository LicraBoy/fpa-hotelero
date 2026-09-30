import io
import os
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from conftest import Mundo, como
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fpa.config import settings
from fpa.modelos import CargaArchivo, EventoAuditoria, Movimiento

_CARPETA_DOCUMENTOS = Path(
    os.environ.get(
        "FPA_DATOS_REALES", Path.home() / "Desktop" / "PLATAFORMA FP&A E INTELIGENCIA HOTELERA"
    )
)
CON130 = _CARPETA_DOCUMENTOS / "BASE DATOS.xlsx"
VARIANCE = _CARPETA_DOCUMENTOS / "02. VT August 2026 Variance (Envio) (1).xlsx"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture(autouse=True)
def almacenamiento(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path / "storage"))
    return tmp_path / "storage"


# --- Archivos de prueba -----------------------------------------------------------------------


def xlsx_variance(filas: list[tuple[Any, ...]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Base de Datos"
    ws.append([])
    ws.append(
        [None, "Mes", "Fecha", "No Cuenta", "Nombre de la Cuenta", "Asiento - Salida",
         "Concepto - Nombre Articulo", "Cantidad", "Costo", "Débito", "Crédito"]
    )  # fmt: skip
    for f in filas:
        ws.append(list(f))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def fila_variance(
    mes: str, fecha: datetime, cuenta: str, debito: float | None, credito: float | None
) -> tuple[Any, ...]:
    return (None, mes, fecha, cuenta, "CUENTA", "8.3.1", "MOV", None, None, debito, credito)


AGOSTO = [
    fila_variance("Agosto", datetime(2026, 8, 5), "4001002.001", None, 100.50),
    fila_variance("Agosto", datetime(2026, 8, 6), "6009001.001", 40.25, None),
]
AGOSTO_CORREGIDO = [
    fila_variance("Agosto", datetime(2026, 8, 5), "4001002.001", None, 120.00),
    fila_variance("Agosto", datetime(2026, 8, 6), "6009001.001", 40.25, None),
]
JULIO = [fila_variance("Julio", datetime(2026, 7, 5), "4001002.001", None, 10.00)]


def xlsx_con130() -> bytes:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(["Torres Mazatlan S.A. de C.V."])
    ws.append(["Mayor Analítico (movimientos por cuentas)"])
    ws.append(
        ["Periodo Septiembre 2026 a Septiembre 2026, Cuentas [1000001.001] hasta [1000001.001]"]
    )
    ws.append(["# ASIENTO", "Fecha", "Tp.Asiento", "Oper.", "Tp.Doc.", "Número", "Fecha",
               "Concepto", "Débito", "Crédito", "Saldo"])  # fmt: skip
    ws.append(["1000"])
    ws.append(
        [
            "1000001.001  BANCO",
            None,
            None,
            None,
            None,
            None,
            None,
            "Saldo anterior",
            None,
            "5.00",
            None,
        ]
    )
    ws.append(
        [
            "9.2.1",
            "01/09/2026",
            "BANCOS/CAJA",
            "REGISTRO",
            "POLIZA",
            "T1",
            "01/09/2026",
            "DEP",
            30,
            None,
            35,
        ]
    )
    ws.append(
        [
            "9.2.2",
            "02/09/2026",
            "BANCOS/CAJA",
            "REGISTRO",
            "POLIZA",
            "T2",
            "02/09/2026",
            "RET",
            None,
            30,
            5,
        ]
    )
    ws.append([None, None, None, None, None, None, None, "Total  BANCO", 30, 30, None])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def zip_con(miembros: dict[str, bytes], base: bool = True) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        if base:
            z.writestr("[Content_Types].xml", "<Types/>")
            z.writestr("xl/workbook.xml", "<workbook/>")
        for nombre, datos in miembros.items():
            z.writestr(nombre, datos)
    return buf.getvalue()


def subir(
    cliente: TestClient,
    mundo: Mundo,
    contenido: bytes,
    nombre: str = "archivo.xlsx",
    fuente: str = "variance_base_datos",
    usuario: str = "analista_a@test.local",
    hotel: int | None = None,
    **datos: str,
):  # type: ignore[no-untyped-def]
    return cliente.post(
        f"/api/v1/hoteles/{hotel or mundo.hotel_a}/cargas",
        files={"archivo": (nombre, contenido, XLSX)},
        data={"fuente": fuente, **datos},
        headers=como(usuario),
    )


def contar(db: Session, modelo: type) -> int:
    db.expire_all()
    return db.scalar(select(func.count()).select_from(modelo)) or 0


def acciones(db: Session) -> list[str]:
    db.expire_all()
    return [e.accion for e in db.scalars(select(EventoAuditoria).order_by(EventoAuditoria.id))]


# --- Flujo normal -----------------------------------------------------------------------------


def test_subir_un_variance_crea_una_carga_por_mes(
    cliente: TestClient, db: Session, mundo: Mundo, almacenamiento: Path
) -> None:
    r = subir(cliente, mundo, xlsx_variance([*JULIO, *AGOSTO]))
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["resolucion"] == "creada"
    assert [c["periodo"] for c in cuerpo["cargas"]] == ["2026-07", "2026-08"]
    agosto = cuerpo["cargas"][1]
    assert (agosto["n_movimientos"], agosto["total_debito"], agosto["total_credito"]) == (
        2,
        "40.25",
        "100.50",
    )
    assert cuerpo["reporte"]["aprobado"] is True
    # el archivo queda guardado con nombre = su hash, y no quedan temporales
    guardado = list((almacenamiento / "cargas" / str(mundo.hotel_a)).glob("*.xlsx"))
    assert [g.stem for g in guardado] == [agosto["sha256"]]
    assert list((almacenamiento / "tmp").glob("*")) == []
    assert contar(db, Movimiento) == 3


def test_subir_un_con130(cliente: TestClient, db: Session, mundo: Mundo) -> None:
    r = subir(cliente, mundo, xlsx_con130(), fuente="con130")
    assert r.status_code == 201, r.text
    (carga,) = r.json()["cargas"]
    assert (carga["periodo"], carga["n_movimientos"]) == ("2026-09", 2)
    assert carga["total_debito"] == carga["total_credito"] == "30.00"


def test_el_mismo_archivo_otra_vez_es_duplicada_y_no_cambia_nada(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    contenido = xlsx_variance(AGOSTO)
    assert subir(cliente, mundo, contenido).status_code == 201
    antes = contar(db, Movimiento)
    r = subir(cliente, mundo, contenido)
    assert r.status_code == 200 and r.json()["resolucion"] == "duplicada"
    assert contar(db, Movimiento) == antes and contar(db, CargaArchivo) == 1


def test_otro_archivo_del_mismo_mes_pide_confirmacion_y_luego_reemplaza(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    subir(cliente, mundo, xlsx_variance(AGOSTO), nombre="original.xlsx")
    corregido = xlsx_variance(AGOSTO_CORREGIDO)
    r = subir(cliente, mundo, corregido, nombre="corregido.xlsx")
    assert r.status_code == 409
    (conflicto,) = r.json()["conflictos"]
    assert conflicto["periodo"] == "2026-08" and conflicto["archivo_vigente"] == "original.xlsx"
    assert (conflicto["credito_vigente"], conflicto["credito_nuevo"]) == ("100.50", "120.00")
    assert contar(db, CargaArchivo) == 1  # nada cambió

    r = subir(cliente, mundo, corregido, nombre="corregido.xlsx", confirmar_reemplazo="true")
    assert r.status_code == 201 and r.json()["resolucion"] == "reemplazada"
    lista = cliente.get(
        f"/api/v1/hoteles/{mundo.hotel_a}/cargas", headers=como("analista_a@test.local")
    ).json()
    assert [(c["estado"], c["nombre_archivo"]) for c in lista] == [
        ("reemplazada", "original.xlsx"),
        ("vigente", "corregido.xlsx"),
    ]


def test_un_control_de_calidad_en_error_rechaza_con_mensaje(
    cliente: TestClient, db: Session, mundo: Mundo, almacenamiento: Path
) -> None:
    r = subir(cliente, mundo, xlsx_variance([*JULIO, *AGOSTO]), periodos="2026-08")
    assert r.status_code == 422
    cuerpo = r.json()
    assert cuerpo["resolucion"] == "rechazada"
    assert any("fuera de los periodos declarados" in m for m in cuerpo["motivos"])
    assert contar(db, CargaArchivo) == 0
    assert not (almacenamiento / "cargas").exists() or not list(
        (almacenamiento / "cargas").rglob("*.xlsx")
    )
    assert acciones(db) == ["carga.rechazada"]


def test_detalle_de_la_carga_incluye_el_reporte_de_calidad(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    carga = subir(cliente, mundo, xlsx_variance(AGOSTO)).json()["cargas"][0]
    r = cliente.get(
        f"/api/v1/hoteles/{mundo.hotel_a}/cargas/{carga['id']}",
        headers=como("direccion_b@test.local"),
    )
    assert r.status_code == 401  # ese usuario no existe: sin sesión
    r = cliente.get(
        f"/api/v1/hoteles/{mundo.hotel_a}/cargas/{carga['id']}",
        headers=como("analista_a@test.local"),
    )
    assert r.status_code == 200
    assert r.json()["controles"]["aprobado"] is True
    otro = cliente.get(
        f"/api/v1/hoteles/{mundo.hotel_b}/cargas/{carga['id']}",
        headers=como("contralor_ab@test.local"),
    )
    assert otro.status_code == 404  # la carga es del hotel A


def test_el_nombre_original_nunca_forma_parte_de_la_ruta(
    cliente: TestClient, db: Session, mundo: Mundo, almacenamiento: Path
) -> None:
    r = subir(cliente, mundo, xlsx_variance(AGOSTO), nombre="../../../etc/passwd/../x.xlsx")
    assert r.status_code == 201
    assert r.json()["cargas"][0]["nombre_archivo"] == "x.xlsx"
    assert all(almacenamiento in p.parents for p in almacenamiento.rglob("*.xlsx"))


# --- Archivos maliciosos o inválidos ------------------------------------------------------------


@pytest.mark.parametrize(
    ("nombre", "estado"),
    [
        ("libro.xlsm", 415),
        ("datos.csv", 415),
        ("viejo.xls", 415),
        ("programa.exe", 415),
        ("libro.xlsx.exe", 415),
        ("libro", 415),
    ],
)
def test_extensiones_no_permitidas(
    cliente: TestClient, db: Session, mundo: Mundo, nombre: str, estado: int
) -> None:
    r = subir(cliente, mundo, xlsx_variance(AGOSTO), nombre=nombre)
    assert r.status_code == estado
    assert contar(db, CargaArchivo) == 0
    assert "carga.archivo_rechazado" in acciones(db)


def test_un_falso_xlsx_de_texto_se_rechaza(cliente: TestClient, db: Session, mundo: Mundo) -> None:
    r = subir(cliente, mundo, b"esto no es un excel, es texto", nombre="falso.xlsx")
    assert r.status_code == 415 and "no es un libro" in r.json()["detail"]


def test_un_zip_que_no_es_excel_se_rechaza(cliente: TestClient, db: Session, mundo: Mundo) -> None:
    r = subir(cliente, mundo, zip_con({"hola.txt": b"x"}, base=False), nombre="zip.xlsx")
    assert r.status_code == 415


def test_archivo_vacio(cliente: TestClient, db: Session, mundo: Mundo) -> None:
    r = subir(cliente, mundo, b"", nombre="vacio.xlsx")
    assert r.status_code == 400


def test_archivo_demasiado_grande(
    cliente: TestClient,
    db: Session,
    mundo: Mundo,
    monkeypatch: pytest.MonkeyPatch,
    almacenamiento: Path,
) -> None:
    monkeypatch.setattr(settings, "carga_max_bytes", 1000)
    r = subir(cliente, mundo, xlsx_variance(AGOSTO))
    assert r.status_code == 413
    assert list((almacenamiento / "tmp").glob("*")) == []  # el parcial se borró


def test_zip_bomb_por_razon_de_compresion(
    cliente: TestClient, db: Session, mundo: Mundo, monkeypatch: pytest.MonkeyPatch
) -> None:
    bomba = zip_con({"xl/worksheets/sheet1.xml": b"\0" * (30 * 1024 * 1024)})
    assert len(bomba) < 200_000  # 30 MB de ceros caben en unos KB
    r = subir(cliente, mundo, bomba, nombre="bomba.xlsx")
    assert r.status_code == 413 and "compresión sospechosa" in r.json()["detail"]


def test_zip_bomb_por_tamano_descomprimido_total(
    cliente: TestClient, db: Session, mundo: Mundo, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "zip_max_descomprimido", 1024 * 1024)
    monkeypatch.setattr(settings, "zip_max_razon", 10_000_000)  # solo probar el tope total
    r = subir(
        cliente, mundo, zip_con({"xl/a.xml": b"\0" * (3 * 1024 * 1024)}), nombre="grande.xlsx"
    )
    assert r.status_code == 413 and "descomprimido" in r.json()["detail"]


def test_demasiadas_entradas(
    cliente: TestClient, db: Session, mundo: Mundo, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "zip_max_entradas", 5)
    contenido = zip_con({f"xl/p{i}.xml": b"x" for i in range(10)})
    assert subir(cliente, mundo, contenido, nombre="muchas.xlsx").status_code == 413


def test_ruta_interna_sospechosa(cliente: TestClient, db: Session, mundo: Mundo) -> None:
    r = subir(cliente, mundo, zip_con({"../../evil.txt": b"x"}), nombre="ruta.xlsx")
    assert r.status_code == 400 and "rutas internas" in r.json()["detail"]


def test_libro_con_macros(cliente: TestClient, db: Session, mundo: Mundo) -> None:
    r = subir(cliente, mundo, zip_con({"xl/vbaProject.bin": b"macro"}), nombre="macro.xlsx")
    assert r.status_code == 415 and "macros" in r.json()["detail"]
    tipos = zip_con(
        {"xl/workbook.xml": b"<w/>", "[Content_Types].xml": b"<Types>macroEnabled</Types>"},
        base=False,
    )
    assert subir(cliente, mundo, tipos, nombre="macro2.xlsx").status_code == 415


def marcar_cifrado(contenido: bytes) -> bytes:
    """Activa el bit de "cifrado" en las cabeceras del ZIP (zipfile no deja escribirlo)."""
    datos = bytearray(contenido)
    for firma, desplazamiento in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        i = datos.find(firma)
        while i != -1:
            datos[i + desplazamiento] |= 0x1
            i = datos.find(firma, i + 4)
    return bytes(datos)


def test_libro_protegido_con_contrasena(cliente: TestClient, db: Session, mundo: Mundo) -> None:
    protegido = marcar_cifrado(zip_con({"xl/secreto.xml": b"cifrado"}))
    r = subir(cliente, mundo, protegido, nombre="clave.xlsx")
    assert r.status_code == 400 and "contraseña" in r.json()["detail"]


def test_lectura_con_formato_equivocado_da_un_mensaje_claro(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    # un Variance subido como si fuera un CON130
    r = subir(cliente, mundo, xlsx_variance(AGOSTO), fuente="con130")
    assert r.status_code == 422 and "# ASIENTO" in r.json()["detail"]
    # un CON130 subido como si fuera un Variance
    r = subir(cliente, mundo, xlsx_con130(), fuente="variance_base_datos")
    assert r.status_code == 422 and "Base de Datos" in r.json()["detail"]
    assert contar(db, CargaArchivo) == 0


def test_parametros_invalidos(cliente: TestClient, db: Session, mundo: Mundo) -> None:
    assert subir(cliente, mundo, xlsx_variance(AGOSTO), fuente="otra").status_code == 422
    assert subir(cliente, mundo, xlsx_variance(AGOSTO), periodos="agosto").status_code == 422
    assert subir(cliente, mundo, xlsx_variance(AGOSTO), periodos="2026-13").status_code == 422


def test_los_rechazos_de_archivo_quedan_en_la_auditoria(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    subir(cliente, mundo, b"texto", nombre="falso.xlsx")
    db.expire_all()
    (evento,) = db.scalars(select(EventoAuditoria)).all()
    assert evento.accion == "carga.archivo_rechazado" and evento.usuario_id is not None
    assert (
        evento.detalle
        and evento.detalle["http"] == 415
        and evento.detalle["archivo"] == "falso.xlsx"
    )


# --- Permisos y aislamiento ---------------------------------------------------------------------


def test_sin_sesion_es_401(cliente: TestClient, mundo: Mundo) -> None:
    r = cliente.post(
        f"/api/v1/hoteles/{mundo.hotel_a}/cargas",
        files={"archivo": ("a.xlsx", xlsx_variance(AGOSTO), XLSX)},
        data={"fuente": "variance_base_datos"},
    )
    assert r.status_code == 401


def test_solo_quien_puede_cargar_carga(cliente: TestClient, db: Session, mundo: Mundo) -> None:
    contenido = xlsx_variance(AGOSTO)
    assert subir(cliente, mundo, contenido, usuario="responsable_a@test.local").status_code == 403
    assert subir(cliente, mundo, contenido, usuario="contralor_c@test.local").status_code == 404
    assert (
        subir(
            cliente, mundo, contenido, usuario="analista_a@test.local", hotel=mundo.hotel_b
        ).status_code
        == 404
    )
    assert contar(db, CargaArchivo) == 0
    assert subir(cliente, mundo, contenido, usuario="contralor_ab@test.local").status_code == 201


def test_las_cargas_de_un_hotel_no_se_ven_desde_otro(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    subir(cliente, mundo, xlsx_variance(AGOSTO), usuario="contralor_ab@test.local")
    en_b = cliente.get(
        f"/api/v1/hoteles/{mundo.hotel_b}/cargas", headers=como("contralor_ab@test.local")
    )
    assert en_b.status_code == 200 and en_b.json() == []
    assert (
        cliente.get(
            f"/api/v1/hoteles/{mundo.hotel_a}/cargas", headers=como("contralor_c@test.local")
        ).status_code
        == 404
    )


def test_solo_contralor_y_auditoria_ven_la_bitacora(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    subir(cliente, mundo, xlsx_variance(AGOSTO), usuario="contralor_ab@test.local")
    url = f"/api/v1/hoteles/{mundo.hotel_a}/auditoria"
    assert cliente.get(url, headers=como("analista_a@test.local")).status_code == 403
    r = cliente.get(url, headers=como("contralor_ab@test.local"))
    assert r.status_code == 200 and [e["accion"] for e in r.json()] == ["carga.creada"]
    assert (
        cliente.get(
            f"/api/v1/hoteles/{mundo.hotel_b}/auditoria", headers=como("auditoria_b@test.local")
        ).json()
        == []
    )


# --- Prueba de salida de la Fase 1, con los Excel reales de Torres --------------------------------


@pytest.mark.skipif(
    not (CON130.exists() and VARIANCE.exists()), reason="Faltan los Excel reales de Torres"
)
def test_salida_de_la_fase_1_por_la_api(cliente: TestClient, db: Session, mundo: Mundo) -> None:
    u = "contralor_ab@test.local"
    base = f"/api/v1/hoteles/{mundo.hotel_a}"

    r = subir(cliente, mundo, VARIANCE.read_bytes(), nombre=VARIANCE.name, usuario=u)
    assert r.status_code == 201, r.text
    assert [(c["periodo"], c["n_movimientos"]) for c in r.json()["cargas"]] == [
        ("2026-07", 3583),
        ("2026-08", 3277),
    ]

    r = subir(cliente, mundo, CON130.read_bytes(), nombre=CON130.name, fuente="con130", usuario=u)
    assert r.status_code == 201, r.text
    (carga,) = r.json()["cargas"]
    assert carga["periodo"] == "2026-09" and carga["n_movimientos"] == 7242
    assert carga["total_debito"] == carga["total_credito"] == "57835193.08"

    # repetir cualquiera de los dos es idempotente
    assert (
        subir(
            cliente, mundo, CON130.read_bytes(), nombre=CON130.name, fuente="con130", usuario=u
        ).status_code
        == 200
    )

    # los saldos de septiembre cuadran con el libro
    saldos = cliente.get(f"{base}/saldos", params={"periodo": "2026-09"}, headers=como(u)).json()
    assert len(saldos) == 366
    from decimal import Decimal

    assert sum((Decimal(s["suma_debito"]) for s in saldos), Decimal("0")) == Decimal("57835193.08")

    # el catálogo acumuló ambos archivos y tiene jerarquía
    arbol = cliente.get(f"{base}/catalogo/arbol", headers=como(u)).json()
    assert len(arbol) > 0

    def contar_nodos(nodos: list[dict[str, Any]]) -> int:
        return sum(1 + contar_nodos(n["hijos"]) for n in nodos)

    def aplanar(nodos: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [x for n in nodos for x in [n, *aplanar(n["hijos"])]]

    nodos = aplanar(arbol)
    titulos = [n for n in nodos if n["es_titulo"]]
    con_mov = [n for n in nodos if n["con_movimientos"]]
    ambas = [n for n in nodos if n["es_titulo"] and n["con_movimientos"]]
    assert (len(titulos), len(con_mov)) == (145, 366 + (296 - 108))
    assert len(nodos) == len(titulos) + len(con_mov) - len(ambas)  # un código puede ser ambas
    assert "4002007" in {n["codigo"] for n in ambas}
    assert contar_nodos(arbol) == len(nodos)

    # un usuario de otro hotel no ve nada de esto
    ajeno = "contralor_c@test.local"
    for ruta in ("cargas", "catalogo/arbol", "saldos?periodo=2026-09", "auditoria"):
        assert cliente.get(f"{base}/{ruta}", headers=como(ajeno)).status_code == 404
