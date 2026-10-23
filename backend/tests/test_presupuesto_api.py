"""Fase 7.2/7.5: captura por área, objetivo y resumen a través de la API."""

from decimal import Decimal

from conftest import Mundo, _crear_usuario, como
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.modelos import LineaReporte, Usuario, VersionEstructuraReporte
from fpa.modelos.identidad import AsignacionDepartamento
from fpa.servicios.presupuesto_ciclo import crear_ano_fiscal, crear_ciclo, crear_periodo_fiscal

RESPONSABLE = "responsable_a@test.local"
CONTRALOR = "contralor_ab@test.local"
DIRECCION = "direccion_a@test.local"
D = Decimal


def _url(mundo: Mundo, ruta: str) -> str:
    return f"/api/v1/hoteles/{mundo.hotel_a}/presupuesto/{ruta}"


def _usuario_id(db: Session, email: str) -> int:
    return db.scalars(select(Usuario.id).where(Usuario.email == email)).one()


def _estructura_dos_secciones(db: Session, hotel_id: int) -> None:
    version = VersionEstructuraReporte(
        hotel_id=hotel_id,
        nombre_archivo="estructura.xlsx",
        sha256="0" * 64,
        estado="vigente",
        n_lineas=4,
        n_detalle=2,
    )
    db.add(version)
    db.flush()
    rooms = LineaReporte(
        version_id=version.id,
        hotel_id=hotel_id,
        orden=1,
        tipo="seccion",
        nivel=0,
        descripcion="Rooms",
        clave="rooms",
        fila_origen=1,
    )
    admin = LineaReporte(
        version_id=version.id,
        hotel_id=hotel_id,
        orden=2,
        tipo="seccion",
        nivel=0,
        descripcion="Admin",
        clave="admin",
        fila_origen=2,
    )
    db.add_all([rooms, admin])
    db.flush()
    db.add_all(
        [
            LineaReporte(
                version_id=version.id,
                hotel_id=hotel_id,
                orden=3,
                tipo="detalle",
                nivel=1,
                seccion_id=rooms.id,
                descripcion="Mantenimiento de habitaciones",
                clave="mant_hab",
                fila_origen=3,
            ),
            LineaReporte(
                version_id=version.id,
                hotel_id=hotel_id,
                orden=4,
                tipo="detalle",
                nivel=1,
                seccion_id=admin.id,
                descripcion="Papelería",
                clave="papeleria",
                fila_origen=4,
            ),
        ]
    )
    db.flush()


def _preparar(db: Session, mundo: Mundo) -> int:
    """Estructura con Rooms/Admin, responsable_a asignado solo a Rooms, y un ciclo abierto."""
    _estructura_dos_secciones(db, mundo.hotel_a)
    db.add(
        AsignacionDepartamento(
            usuario_id=_usuario_id(db, RESPONSABLE), hotel_id=mundo.hotel_a, seccion="Rooms"
        )
    )
    _crear_usuario(db, mundo.org1, DIRECCION, {mundo.hotel_a: "direccion"})
    ano = crear_ano_fiscal(db, hotel_id=mundo.hotel_a, etiqueta="2026/27", mes_inicio=7, mes_fin=6)
    periodos = [f"2026-{m:02d}" for m in range(7, 13)] + [f"2027-{m:02d}" for m in range(1, 7)]
    for periodo in periodos:
        crear_periodo_fiscal(db, ano_fiscal_id=ano.id, periodo=periodo)
    ciclo = crear_ciclo(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        ano_fiscal_id=ano.id,
    )
    db.commit()
    return ciclo.id


def _linea_id(db: Session, descripcion: str) -> int:
    return db.scalars(select(LineaReporte.id).where(LineaReporte.descripcion == descripcion)).one()


def test_responsable_solo_ve_su_seccion(cliente: TestClient, db: Session, mundo: Mundo) -> None:
    ciclo_id = _preparar(db, mundo)
    r = cliente.get(_url(mundo, f"ciclos/{ciclo_id}/lineas"), headers=como(RESPONSABLE))
    assert r.status_code == 200
    descripciones = {x["descripcion"] for x in r.json()}
    assert descripciones == {"Mantenimiento de habitaciones"}


def test_contralor_ve_todas_las_secciones(cliente: TestClient, db: Session, mundo: Mundo) -> None:
    ciclo_id = _preparar(db, mundo)
    r = cliente.get(_url(mundo, f"ciclos/{ciclo_id}/lineas"), headers=como(CONTRALOR))
    assert r.status_code == 200
    descripciones = {x["descripcion"] for x in r.json()}
    assert descripciones == {"Mantenimiento de habitaciones", "Papelería"}


def test_responsable_no_puede_capturar_fuera_de_su_seccion(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    ciclo_id = _preparar(db, mundo)
    linea_admin = _linea_id(db, "Papelería")
    r = cliente.put(
        _url(mundo, f"ciclos/{ciclo_id}/lineas/{linea_admin}"),
        json={"propuesta_anual": "100.00"},
        headers=como(RESPONSABLE),
    )
    assert r.status_code == 404


def test_recorrido_feliz_captura_y_prorrateo_por_perfil(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    ciclo_id = _preparar(db, mundo)
    linea_rooms = _linea_id(db, "Mantenimiento de habitaciones")
    r = cliente.put(
        _url(mundo, f"ciclos/{ciclo_id}/lineas/{linea_rooms}"),
        json={"propuesta_anual": "1200000.00", "nota": "Estimado anual"},
        headers=como(RESPONSABLE),
    )
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "capturada"

    perfiles = cliente.get(_url(mundo, "perfiles"), headers=como(RESPONSABLE))
    assert perfiles.status_code == 200
    uniforme = next(p for p in perfiles.json() if p["nombre"] == "Uniforme")

    r = cliente.post(
        _url(mundo, f"ciclos/{ciclo_id}/lineas/{linea_rooms}/prorrateo"),
        json={"perfil_distribucion_id": uniforme["id"]},
        headers=como(RESPONSABLE),
    )
    assert r.status_code == 200, r.text
    filas = r.json()
    assert len(filas) == 12
    assert sum(Decimal(f["importe"]) for f in filas) == D("1200000.00")


def test_capturar_con_ciclo_fuera_de_borrador_da_409(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    ciclo_id = _preparar(db, mundo)
    linea_rooms = _linea_id(db, "Mantenimiento de habitaciones")
    # El ciclo pasa a "enviado" directo con el servicio: la Fase 7.2 no agrega un endpoint de
    # transición (eso ya existe, sin router, desde la 7.1).
    from fpa.identidad.permisos import Permiso
    from fpa.servicios.presupuesto_ciclo import transicionar

    transicionar(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=_usuario_id(db, "analista_a@test.local"),
        puede=dict.fromkeys(Permiso, True),
        ciclo_id=ciclo_id,
        hacia="enviado",
        nota=None,
    )
    db.commit()
    r = cliente.put(
        _url(mundo, f"ciclos/{ciclo_id}/lineas/{linea_rooms}"),
        json={"propuesta_anual": "100.00"},
        headers=como(RESPONSABLE),
    )
    assert r.status_code == 409


def test_direccion_fija_objetivo_en_cualquier_seccion(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    ciclo_id = _preparar(db, mundo)
    linea_admin = _linea_id(db, "Papelería")  # direccion no tiene sección asignada: ve todo
    r = cliente.put(
        _url(mundo, f"ciclos/{ciclo_id}/lineas/{linea_admin}/objetivo"),
        json={"objetivo": "500.00"},
        headers=como(DIRECCION),
    )
    assert r.status_code == 200, r.text
    assert D(r.json()["objetivo"]) == D("500.00")


def test_responsable_sin_permiso_de_objetivo_da_403(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    ciclo_id = _preparar(db, mundo)
    linea_rooms = _linea_id(db, "Mantenimiento de habitaciones")
    r = cliente.put(
        _url(mundo, f"ciclos/{ciclo_id}/lineas/{linea_rooms}/objetivo"),
        json={"objetivo": "100.00"},
        headers=como(RESPONSABLE),
    )
    assert r.status_code == 403


def test_resumen_refleja_la_cobertura(cliente: TestClient, db: Session, mundo: Mundo) -> None:
    ciclo_id = _preparar(db, mundo)
    linea_rooms = _linea_id(db, "Mantenimiento de habitaciones")
    cliente.put(
        _url(mundo, f"ciclos/{ciclo_id}/lineas/{linea_rooms}"),
        json={"propuesta_anual": "1000.00"},
        headers=como(RESPONSABLE),
    )
    r = cliente.get(_url(mundo, f"ciclos/{ciclo_id}/resumen"), headers=como(DIRECCION))
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["total_lineas"] == 2
    assert cuerpo["lineas_capturadas"] == 1
    assert cuerpo["cobertura_pct"] == "50.00"
    assert D(cuerpo["suma_propuesta"]) == D("1000.00")


def test_resumen_mensual_suma_lo_mensualizado_y_cuenta_lo_pendiente(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    ciclo_id = _preparar(db, mundo)
    linea_rooms = _linea_id(db, "Mantenimiento de habitaciones")
    linea_admin = _linea_id(db, "Papelería")

    # Rooms: capturada y mensualizada (por perfil)
    cliente.put(
        _url(mundo, f"ciclos/{ciclo_id}/lineas/{linea_rooms}"),
        json={"propuesta_anual": "1200.00"},
        headers=como(RESPONSABLE),
    )
    uniforme = next(
        p
        for p in cliente.get(_url(mundo, "perfiles"), headers=como(RESPONSABLE)).json()
        if p["nombre"] == "Uniforme"
    )
    cliente.post(
        _url(mundo, f"ciclos/{ciclo_id}/lineas/{linea_rooms}/prorrateo"),
        json={"perfil_distribucion_id": uniforme["id"]},
        headers=como(RESPONSABLE),
    )
    # Admin: capturada pero sin mensualizar todavía
    r = cliente.put(
        _url(mundo, f"ciclos/{ciclo_id}/lineas/{linea_admin}"),
        json={"propuesta_anual": "500.00"},
        headers=como(CONTRALOR),
    )
    assert r.status_code == 200, r.text

    r = cliente.get(_url(mundo, f"ciclos/{ciclo_id}/resumen-mensual"), headers=como(DIRECCION))
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["lineas_sin_mensualizar"] == 1
    assert len(cuerpo["por_periodo"]) == 12
    assert sum(D(p["propuesta"]) for p in cuerpo["por_periodo"]) == D("1200.00")
    # orden cronológico del año fiscal (julio primero)
    assert [p["periodo"] for p in cuerpo["por_periodo"]][:2] == ["2026-07", "2026-08"]
    # por sección: solo Rooms aporta (Admin está capturada pero sin mensualizar todavía)
    assert [s["seccion"] for s in cuerpo["por_seccion"]] == ["Rooms"]
    assert len(cuerpo["por_seccion"][0]["por_periodo"]) == 12
    assert sum(D(p["propuesta"]) for p in cuerpo["por_seccion"][0]["por_periodo"]) == D("1200.00")
