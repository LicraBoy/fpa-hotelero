"""Fase 5.3: comentarios por línea y periodo, hilo, estatus, responsable y evidencia."""

import io
from pathlib import Path

import pytest
from conftest import Mundo, como
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_acceso_usuarios import _asignar
from test_versionado_mapeo import Escenario

from fpa.config import settings
from fpa.modelos import (
    AdjuntoComentario,
    ComentarioLinea,
    ComentarioRevision,
    EventoAuditoria,
    Usuario,
)

CONTRALOR = "contralor_ab@test.local"
ANALISTA = "analista_a@test.local"
RESPONSABLE = "responsable_a@test.local"
AUDITORIA_B = "auditoria_b@test.local"
OTRA_ORG = "contralor_c@test.local"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _url(mundo: Mundo, ruta: str = "comentarios") -> str:
    return f"/api/v1/hoteles/{mundo.hotel_a}/{ruta}"


def _comentar(  # type: ignore[no-untyped-def]
    cliente: TestClient,
    mundo: Mundo,
    esc: Escenario,
    usuario: str = ANALISTA,
    linea: str = "Ingreso",
    **extra,
):
    cuerpo = {
        "linea_id": esc.linea(linea),
        "periodo": "2026-08",
        "bloque": "mes",
        "texto": "Mayor ocupación por el congreso",
        **extra,
    }
    return cliente.post(_url(mundo), json=cuerpo, headers=como(usuario))


def _uid(db: Session, email: str) -> int:
    return db.scalars(select(Usuario).where(Usuario.email == email)).one().id


@pytest.fixture(autouse=True)
def almacenamiento(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))


# --- Crear y listar -----------------------------------------------------------------------------


def test_crear_listar_y_contar(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    r = _comentar(cliente, mundo, esc)
    assert r.status_code == 201, r.text
    c = r.json()
    assert (
        c["estatus"] == "pendiente"
        and c["linea_descripcion"] == "Ingreso"
        and c["respuestas"] == []
    )
    lista = cliente.get(_url(mundo, "comentarios?periodo=2026-08"), headers=como(CONTRALOR)).json()
    assert [x["id"] for x in lista["comentarios"]] == [c["id"]]
    assert lista["puede_resolver"] is True
    assert (
        cliente.get(_url(mundo, "comentarios?periodo=2026-09"), headers=como(CONTRALOR)).json()[
            "comentarios"
        ]
        == []
    )
    n = cliente.get(
        _url(mundo, "comentarios/conteos?periodo=2026-08"), headers=como(CONTRALOR)
    ).json()
    assert n["por_linea"][str(esc.linea("Ingreso"))]["mes"] == {"total": 1, "pendientes": 1}


def test_el_texto_con_html_se_guarda_tal_cual(
    cliente: TestClient, mundo: Mundo, esc: Escenario
) -> None:
    texto = "<script>alert(1)</script> <b>x</b>"
    r = _comentar(cliente, mundo, esc, texto=texto)
    assert r.json()["texto"] == texto  # la pantalla lo muestra como texto


@pytest.mark.parametrize(
    "cambio",
    [
        {"texto": "   "},
        {"texto": "x" * 2001},
        {"periodo": "2026-13"},
        {"bloque": "anual"},
        {"linea_id": 0},
    ],
)
def test_datos_invalidos_dan_422(
    cliente: TestClient, mundo: Mundo, esc: Escenario, cambio: dict[str, object]
) -> None:
    assert _comentar(cliente, mundo, esc, **cambio).status_code == 422


def test_linea_inexistente_o_seccion_es_404(
    cliente: TestClient, mundo: Mundo, esc: Escenario
) -> None:
    assert _comentar(cliente, mundo, esc, linea_id=99999).status_code == 404
    seccion = esc.linea("Rooms")
    assert _comentar(cliente, mundo, esc, linea_id=seccion).status_code == 404


def test_permisos_y_aislamiento(cliente: TestClient, mundo: Mundo, esc: Escenario) -> None:
    c = _comentar(cliente, mundo, esc).json()
    # Dirección y Auditoría leen, pero no escriben
    assert _comentar(cliente, mundo, esc, usuario="auditoria_b@test.local").status_code == 404
    assert (
        cliente.get(_url(mundo, "comentarios?periodo=2026-08"), headers=como(OTRA_ORG)).status_code
        == 404
    )
    assert cliente.get(_url(mundo, "comentarios?periodo=2026-08")).status_code == 401
    assert cliente.post(_url(mundo), json={}).status_code == 401
    assert c["id"]


# --- Secciones del responsable ------------------------------------------------------------------


def test_el_responsable_solo_comenta_y_ve_lo_suyo(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    _asignar(db, mundo, "Rooms")
    assert _comentar(cliente, mundo, esc, usuario=RESPONSABLE, linea="Ingreso").status_code == 201
    assert _comentar(cliente, mundo, esc, usuario=RESPONSABLE, linea="Gasto").status_code == 404
    ajeno = _comentar(cliente, mundo, esc, usuario=ANALISTA, linea="Gasto").json()
    ve = cliente.get(_url(mundo, "comentarios?periodo=2026-08"), headers=como(RESPONSABLE)).json()
    assert {x["linea_descripcion"] for x in ve["comentarios"]} == {"Ingreso"}
    # tampoco por id: ni responder, ni editar, ni cambiar estatus
    h = como(RESPONSABLE)
    assert (
        cliente.post(
            _url(mundo, f"comentarios/{ajeno['id']}/respuestas"), json={"texto": "x"}, headers=h
        ).status_code
        == 404
    )
    assert (
        cliente.put(
            _url(mundo, f"comentarios/{ajeno['id']}/estatus"),
            json={"estatus": "explicado"},
            headers=h,
        ).status_code
        == 404
    )
    n = cliente.get(_url(mundo, "comentarios/conteos?periodo=2026-08"), headers=h).json()
    assert list(n["por_linea"]) == [str(esc.linea("Ingreso"))]


# --- Hilo, edición, estatus y responsable -------------------------------------------------------


def test_responder_editar_y_conservar_el_historial(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    c = _comentar(cliente, mundo, esc).json()
    r = cliente.post(
        _url(mundo, f"comentarios/{c['id']}/respuestas"),
        json={"texto": "Confirmado con Recepción"},
        headers=como(CONTRALOR),
    )
    assert r.status_code == 201 and r.json()["respuestas"][0]["texto"] == "Confirmado con Recepción"
    # solo el autor edita
    base = _url(mundo, f"comentarios/{c['id']}")
    assert cliente.patch(base, json={"texto": "otro"}, headers=como(CONTRALOR)).status_code == 403
    e = cliente.patch(base, json={"texto": "Mayor ocupación (congreso)"}, headers=como(ANALISTA))
    assert e.status_code == 200 and e.json()["editado"] is True
    versiones = db.scalars(
        select(ComentarioRevision.texto)
        .where(ComentarioRevision.comentario_id == c["id"])
        .order_by(ComentarioRevision.id)
    ).all()
    assert versiones == ["Mayor ocupación por el congreso", "Mayor ocupación (congreso)"]


def test_estatus_y_quien_puede_cambiarlo(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    _asignar(db, mundo, "Rooms")
    c = _comentar(cliente, mundo, esc).json()  # lo escribe el analista
    ruta = _url(mundo, f"comentarios/{c['id']}/estatus")
    # el responsable de departamento no es autor ni responsable del hilo
    assert (
        cliente.put(ruta, json={"estatus": "explicado"}, headers=como(RESPONSABLE)).status_code
        == 403
    )
    assert (
        cliente.put(ruta, json={"estatus": "explicado"}, headers=como(ANALISTA)).json()["estatus"]
        == "explicado"
    )
    # aprobar exige comentario:resolver
    assert (
        cliente.put(ruta, json={"estatus": "aprobado"}, headers=como(RESPONSABLE)).status_code
        == 403
    )
    assert (
        cliente.put(ruta, json={"estatus": "aprobado"}, headers=como(CONTRALOR)).json()["estatus"]
        == "aprobado"
    )
    assert (
        cliente.put(ruta, json={"estatus": "inventado"}, headers=como(CONTRALOR)).status_code == 422
    )
    acciones = [e.accion for e in db.scalars(select(EventoAuditoria).order_by(EventoAuditoria.id))]
    assert acciones.count("comentario.estatus") == 2


def test_asignar_responsable_valida_a_la_persona(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    _asignar(db, mundo, "Rooms")
    resp_id = _uid(db, RESPONSABLE)
    c = _comentar(cliente, mundo, esc, responsable_id=resp_id).json()
    assert c["responsable_id"] == resp_id and c["responsable"] == RESPONSABLE
    # el responsable del hilo ya puede cambiar el estatus
    ruta = _url(mundo, f"comentarios/{c['id']}/estatus")
    assert (
        cliente.put(ruta, json={"estatus": "explicado"}, headers=como(RESPONSABLE)).status_code
        == 200
    )
    # alguien de otra organización o sin permiso de comentar no puede ser responsable
    invalido = _uid(db, OTRA_ORG)
    assert _comentar(cliente, mundo, esc, responsable_id=invalido).status_code == 422
    base = _url(mundo, f"comentarios/{c['id']}/responsable")
    assert (
        cliente.put(base, json={"responsable_id": None}, headers=como(ANALISTA)).json()[
            "responsable_id"
        ]
        is None
    )
    assert (
        cliente.put(base, json={"responsable_id": resp_id}, headers=como(RESPONSABLE)).status_code
        == 403
    )


# --- Adjuntos -----------------------------------------------------------------------------------


def _subir(
    cliente: TestClient,
    mundo: Mundo,
    cid: int,
    nombre: str,
    contenido: bytes,
    usuario: str = ANALISTA,
):  # type: ignore[no-untyped-def]
    return cliente.post(
        _url(mundo, f"comentarios/{cid}/adjuntos"),
        files={"archivo": (nombre, io.BytesIO(contenido), "application/octet-stream")},
        headers=como(usuario),
    )


def test_adjuntar_y_descargar_una_imagen(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    c = _comentar(cliente, mundo, esc).json()
    r = _subir(cliente, mundo, c["id"], "../../evidencia final.png", PNG)
    assert r.status_code == 201, r.text
    adj = r.json()["adjuntos"][0]
    assert adj["nombre"] == "evidencia final.png" and adj["tamano"] == len(PNG)
    d = cliente.get(
        _url(mundo, f"comentarios/{c['id']}/adjuntos/{adj['id']}"), headers=como(CONTRALOR)
    )
    assert d.status_code == 200 and d.content == PNG
    assert d.headers["content-disposition"].startswith("attachment")
    assert (
        "evidencia final" not in d.headers["content-disposition"]
    )  # el nombre no llega al servidor
    # el archivo vive en disco bajo su hash, no en la base
    fila = db.scalars(select(AdjuntoComentario)).one()
    assert (
        Path(settings.storage_dir) / "adjuntos" / str(mundo.hotel_a) / f"{fila.sha256}.png"
    ).exists()


@pytest.mark.parametrize(
    ("nombre", "contenido", "esperado"),
    [
        ("falso.png", b"MZ\x90\x00 no soy una imagen", 415),  # contenido ≠ extensión
        ("macros.xlsm", b"PK\x03\x04", 415),
        ("programa.exe", b"MZ", 415),
        ("activo.pdf", b"%PDF-1.4\n/OpenAction << /S /JavaScript /JS (app.alert(1)) >>", 415),
        ("vacio.pdf", b"", 400),
    ],
)
def test_adjuntos_peligrosos_se_rechazan_y_quedan_en_la_bitacora(
    cliente: TestClient,
    mundo: Mundo,
    esc: Escenario,
    db: Session,
    nombre: str,
    contenido: bytes,
    esperado: int,
) -> None:
    c = _comentar(cliente, mundo, esc).json()
    assert _subir(cliente, mundo, c["id"], nombre, contenido).status_code == esperado
    assert db.scalars(select(AdjuntoComentario)).all() == []


def test_adjunto_demasiado_grande_y_limite_por_comentario(
    cliente: TestClient, mundo: Mundo, esc: Escenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    c = _comentar(cliente, mundo, esc).json()
    monkeypatch.setattr(settings, "adjunto_max_bytes", 100)
    assert _subir(cliente, mundo, c["id"], "grande.png", PNG + b"\x00" * 200).status_code == 413
    monkeypatch.setattr(settings, "adjunto_max_bytes", 1024)
    monkeypatch.setattr(settings, "adjuntos_max_por_comentario", 2)
    for i in range(2):
        assert _subir(cliente, mundo, c["id"], f"{i}.png", PNG + bytes([i])).status_code == 201
    assert _subir(cliente, mundo, c["id"], "3.png", PNG + b"3").status_code == 409


def test_nadie_descarga_adjuntos_de_otra_seccion_ni_de_otro_hotel(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    _asignar(db, mundo, "Rooms")
    c = _comentar(cliente, mundo, esc, linea="Gasto").json()
    adj = _subir(cliente, mundo, c["id"], "e.png", PNG).json()["adjuntos"][0]
    ruta = _url(mundo, f"comentarios/{c['id']}/adjuntos/{adj['id']}")
    assert cliente.get(ruta, headers=como(CONTRALOR)).status_code == 200
    assert cliente.get(ruta, headers=como(RESPONSABLE)).status_code == 404
    assert cliente.get(ruta, headers=como(OTRA_ORG)).status_code == 404
    assert cliente.get(ruta).status_code == 401
    # y la misma ruta por el hotel B no encuentra el comentario
    otro = f"/api/v1/hoteles/{mundo.hotel_b}/comentarios/{c['id']}/adjuntos/{adj['id']}"
    assert cliente.get(otro, headers=como(CONTRALOR)).status_code == 404


def test_cada_escritura_deja_un_evento(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    c = _comentar(cliente, mundo, esc).json()
    cliente.post(
        _url(mundo, f"comentarios/{c['id']}/respuestas"),
        json={"texto": "ok"},
        headers=como(CONTRALOR),
    )
    cliente.put(
        _url(mundo, f"comentarios/{c['id']}/estatus"),
        json={"estatus": "explicado"},
        headers=como(ANALISTA),
    )
    _subir(cliente, mundo, c["id"], "e.png", PNG)
    acciones = {e.accion for e in db.scalars(select(EventoAuditoria))}
    assert {
        "comentario.creado",
        "comentario.respondido",
        "comentario.estatus",
        "comentario.adjunto",
    } <= acciones
    assert db.scalars(select(ComentarioLinea)).all()


def test_el_excel_exportado_lleva_los_comentarios_como_texto(
    cliente: TestClient, mundo: Mundo, esc: Escenario
) -> None:
    from openpyxl import load_workbook

    _comentar(cliente, mundo, esc, texto='=HYPERLINK("http://x")')
    _comentar(cliente, mundo, esc, bloque="ytd", texto="Acumulado alto")
    r = cliente.get(_url(mundo, "variance/exportar?periodo=2026-08"), headers=como(ANALISTA))
    assert r.status_code == 200
    hoja = load_workbook(io.BytesIO(r.content))["Variance"]
    fila = next(f for f in range(1, hoja.max_row + 1) if hoja.cell(f, 2).value == "Ingreso")
    mes, ytd = hoja.cell(fila, 7), hoja.cell(fila, 12)
    assert mes.data_type == "s" and mes.value.startswith("[Pendiente] =HYPERLINK")
    assert "Acumulado alto" in ytd.value
    assert hoja.cell(4, 7).value == "COMMENTS" and hoja.cell(4, 12).value == "YTD COMMENTS"
