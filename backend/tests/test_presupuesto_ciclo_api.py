"""Fase 7.4: calendario fiscal y ciclo de presupuesto (alta, transiciones, aprobación) por API."""

from conftest import Mundo, como
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fpa.modelos import LineaReporte, VersionEstructuraReporte

ANALISTA = "analista_a@test.local"
CONTRALOR = "contralor_ab@test.local"
RESPONSABLE = "responsable_a@test.local"  # usado solo para el 403 de administración


def _url(mundo: Mundo, ruta: str) -> str:
    return f"/api/v1/hoteles/{mundo.hotel_a}/presupuesto/{ruta}"


def _estructura_una_linea(db: Session, hotel_id: int) -> int:
    version = VersionEstructuraReporte(
        hotel_id=hotel_id,
        nombre_archivo="estructura.xlsx",
        sha256="0" * 64,
        estado="vigente",
        n_lineas=1,
        n_detalle=1,
    )
    db.add(version)
    db.flush()
    linea = LineaReporte(
        version_id=version.id,
        hotel_id=hotel_id,
        orden=1,
        tipo="detalle",
        nivel=1,
        descripcion="Mantenimiento",
        clave="mantenimiento",
        fila_origen=1,
    )
    db.add(linea)
    db.flush()
    db.commit()
    return linea.id


def test_responsable_no_puede_crear_ano_fiscal(cliente: TestClient, mundo: Mundo) -> None:
    r = cliente.post(
        _url(mundo, "anos-fiscales"),
        json={"etiqueta": "2026/27", "mes_inicio": 7, "mes_fin": 6},
        headers=como(RESPONSABLE),
    )
    assert r.status_code == 403


def test_contralor_crea_ano_y_genera_periodos(cliente: TestClient, mundo: Mundo) -> None:
    r = cliente.post(
        _url(mundo, "anos-fiscales"),
        json={"etiqueta": "2026/27", "mes_inicio": 7, "mes_fin": 6},
        headers=como(CONTRALOR),
    )
    assert r.status_code == 201, r.text
    ano_id = r.json()["id"]
    r2 = cliente.post(
        _url(mundo, f"anos-fiscales/{ano_id}/periodos/generar"), headers=como(CONTRALOR)
    )
    assert r2.status_code == 200, r2.text
    periodos = [p["periodo"] for p in r2.json()]
    assert periodos == [f"2026-{m:02d}" for m in range(7, 13)] + [
        f"2027-{m:02d}" for m in range(1, 7)
    ]
    r3 = cliente.get(_url(mundo, f"anos-fiscales/{ano_id}/periodos"), headers=como(ANALISTA))
    assert r3.status_code == 200 and len(r3.json()) == 12


def test_flujo_completo_hasta_aprobado(
    cliente: TestClient, db: Session, mundo: Mundo
) -> None:
    linea_id = _estructura_una_linea(db, mundo.hotel_a)

    r = cliente.post(
        _url(mundo, "anos-fiscales"),
        json={"etiqueta": "2026/27", "mes_inicio": 7, "mes_fin": 6},
        headers=como(CONTRALOR),
    )
    ano_id = r.json()["id"]
    cliente.post(_url(mundo, f"anos-fiscales/{ano_id}/periodos/generar"), headers=como(CONTRALOR))

    r = cliente.post(
        _url(mundo, "ciclos"), json={"ano_fiscal_id": ano_id}, headers=como(CONTRALOR)
    )
    assert r.status_code == 201, r.text
    ciclo = r.json()
    ciclo_id = ciclo["id"]
    assert ciclo["estado"] == "borrador"
    assert {t["hacia"] for t in ciclo["transiciones_posibles"]} == {"enviado"}

    r = cliente.get(_url(mundo, "ciclos"), headers=como(ANALISTA))
    assert r.status_code == 200
    assert any(c["id"] == ciclo_id for c in r.json())

    # La línea no tiene sección: solo un rol sin restricción (Contralor) puede capturarla —
    # el alcance por sección se prueba a fondo en test_presupuesto_api.py.
    r = cliente.put(
        _url(mundo, f"ciclos/{ciclo_id}/lineas/{linea_id}"),
        json={"propuesta_anual": "1200000.00"},
        headers=como(CONTRALOR),
    )
    assert r.status_code == 200, r.text

    perfiles = cliente.get(_url(mundo, "perfiles"), headers=como(CONTRALOR)).json()
    uniforme = next(p for p in perfiles if p["nombre"] == "Uniforme")
    r = cliente.post(
        _url(mundo, f"ciclos/{ciclo_id}/lineas/{linea_id}/prorrateo"),
        json={"perfil_distribucion_id": uniforme["id"]},
        headers=como(CONTRALOR),
    )
    assert r.status_code == 200, r.text

    r = cliente.post(
        _url(mundo, f"ciclos/{ciclo_id}/transiciones"),
        json={"hacia": "enviado"},
        headers=como(CONTRALOR),
    )
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "enviado"

    r = cliente.post(
        _url(mundo, f"ciclos/{ciclo_id}/transiciones"),
        json={"hacia": "revision"},
        headers=como(ANALISTA),
    )
    assert r.status_code == 200, r.text

    # Dirección no tiene budget:aprobar: no puede aprobar.
    r = cliente.post(
        _url(mundo, f"ciclos/{ciclo_id}/transiciones"),
        json={"hacia": "aprobado"},
        headers=como(ANALISTA),
    )
    assert r.status_code == 403

    r = cliente.post(
        _url(mundo, f"ciclos/{ciclo_id}/transiciones"),
        json={"hacia": "aprobado"},
        headers=como(CONTRALOR),
    )
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["estado"] == "aprobado"
    assert cuerpo["version_plan_resultante_id"] is not None

    r = cliente.post(
        _url(mundo, f"ciclos/{ciclo_id}/transiciones"),
        json={"hacia": "borrador"},  # reabrir sin nota
        headers=como(CONTRALOR),
    )
    assert r.status_code == 422

    r = cliente.post(
        _url(mundo, f"ciclos/{ciclo_id}/transiciones"),
        json={"hacia": "bloqueado"},
        headers=como(CONTRALOR),
    )
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "bloqueado"
