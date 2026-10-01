import os
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from fpa import demo_agosto
from fpa.config import settings
from fpa.repositorios.mapeo import RepositorioMapeo
from fpa.semilla import sembrar_roles, sembrar_torres
from fpa.servicios.variance import calcular_variance

_CARPETA = Path(
    os.environ.get(
        "FPA_DATOS_REALES", Path.home() / "Desktop" / "PLATAFORMA FP&A E INTELIGENCIA HOTELERA"
    )
)


def test_se_niega_a_correr_fuera_de_desarrollo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(settings, "entorno", "produccion")
    with pytest.raises(SystemExit, match="solo corre con FPA_ENTORNO=desarrollo"):
        demo_agosto.cargar_demo(tmp_path)


def test_sin_el_excel_avisa(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "entorno", "desarrollo")
    with pytest.raises(SystemExit, match="No encuentro"):
        demo_agosto.cargar_demo(tmp_path)


@pytest.mark.skipif(
    not (_CARPETA / demo_agosto.EXCEL).exists(), reason="No está el Excel real del Variance"
)
def test_la_demostracion_deja_el_reporte_listo_y_se_puede_repetir(
    monkeypatch: pytest.MonkeyPatch, engine: Engine
) -> None:
    fabrica = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(settings, "entorno", "desarrollo")
    monkeypatch.setattr(demo_agosto, "SessionLocal", fabrica)
    with fabrica() as db:
        sembrar_roles(db)
        sembrar_torres(db)
        db.commit()

    mensajes: list[str] = []
    demo_agosto.cargar_demo(_CARPETA, imprimir=mensajes.append)
    assert any("Mapeo v1 aprobado" in m for m in mensajes)
    demo_agosto.cargar_demo(_CARPETA, imprimir=mensajes.append)  # repetir no duplica nada
    assert any("ya estaba aprobado" in m for m in mensajes)

    with fabrica() as db:
        hotel_id = sembrar_torres(db).id
        repo = RepositorioMapeo(db, hotel_id)
        assert [v.estado for v in repo.versiones()] == ["aprobada"]
        assert {e.cuenta_codigo for e in repo.excluidas(repo.versiones()[0].id)} == {
            "4002013",
            "4003003",
        }
        r = calcular_variance(db, hotel_id=hotel_id, periodo="2026-08")
        assert r.version_plan_id is not None
        assert any("a propósito 2 cuentas" in a for a in r.advertencias)
        sueldos = next(x for x in r.lineas if x.fila_origen == 29)
        assert r.resultado[sueldos.id].mes.actual == Decimal("321190.84")
