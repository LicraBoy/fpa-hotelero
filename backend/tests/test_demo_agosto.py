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
EXCEL_VT = "02. VT August 2026 Variance (Envio) (1).xlsx"


def _hay(nombre: str) -> bool:
    return (_CARPETA / nombre).exists() or (demo_agosto.DOCS_ADR / nombre).exists()


def test_se_niega_a_correr_fuera_de_desarrollo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(settings, "entorno", "produccion")
    with pytest.raises(SystemExit, match="solo corre con FPA_ENTORNO=desarrollo"):
        demo_agosto.cargar_demo(tmp_path)


def test_sin_el_excel_avisa(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "entorno", "desarrollo")
    with pytest.raises(SystemExit, match="No encuentro"):
        demo_agosto.cargar_demo(tmp_path, archivo_excel="no-existe.xlsx")


def _preparar(monkeypatch: pytest.MonkeyPatch, engine: Engine) -> sessionmaker:  # type: ignore[type-arg]
    fabrica = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(settings, "entorno", "desarrollo")
    monkeypatch.setattr(demo_agosto, "SessionLocal", fabrica)
    with fabrica() as db:
        sembrar_roles(db)
        sembrar_torres(db)
        db.commit()
    return fabrica


@pytest.mark.skipif(not _hay(demo_agosto.EXCEL), reason="No está el Excel real de Mazatlán")
def test_la_demostracion_de_mazatlan_deja_el_reporte_listo_y_se_puede_repetir(
    monkeypatch: pytest.MonkeyPatch, engine: Engine
) -> None:
    fabrica = _preparar(monkeypatch, engine)
    mensajes: list[str] = []
    demo_agosto.cargar_demo(_CARPETA, imprimir=mensajes.append)
    assert any("Formato detectado: mzt" in m for m in mensajes)
    assert any("Mapeo v1 aprobado" in m for m in mensajes)
    demo_agosto.cargar_demo(_CARPETA, imprimir=mensajes.append)  # repetir no duplica nada
    assert any("ya estaba aprobado" in m for m in mensajes)

    with fabrica() as db:
        hotel_id = sembrar_torres(db).id
        repo = RepositorioMapeo(db, hotel_id)
        assert [v.estado for v in repo.versiones()] == ["aprobada"]
        excluidas = {e.cuenta_codigo for e in repo.excluidas(repo.versiones()[0].id)}
        assert "4003001.010" in excluidas  # la cuenta de mayor importe que el Excel no toma
        agosto = calcular_variance(db, hotel_id=hotel_id, periodo="2026-08")
        assert agosto.version_plan_id is not None
        assert agosto.periodos_ytd == ["2026-07", "2026-08"]
        assert any("a propósito" in a for a in agosto.advertencias)
        cambio = next(x for x in agosto.lineas if x.fila_origen == 9)
        mes = agosto.resultado[cambio.id].mes
        assert (mes.actual, mes.budget) == (Decimal("17.1337"), Decimal("18"))
        assert mes.var == Decimal("0.8663")  # Budget - Actual
        julio = calcular_variance(db, hotel_id=hotel_id, periodo="2026-07")
        cambio_jul = next(x for x in julio.lineas if x.fila_origen == 9)
        assert julio.resultado[cambio_jul.id].mes.actual == Decimal("17.2175")


@pytest.mark.skipif(not _hay(EXCEL_VT), reason="No está el Excel real de Vallarta")
def test_la_demostracion_con_el_archivo_de_vallarta_sigue_funcionando(
    monkeypatch: pytest.MonkeyPatch, engine: Engine
) -> None:
    fabrica = _preparar(monkeypatch, engine)
    mensajes: list[str] = []
    demo_agosto.cargar_demo(_CARPETA, imprimir=mensajes.append, archivo_excel=EXCEL_VT)
    assert any("Formato detectado: vt" in m for m in mensajes)
    with fabrica() as db:
        hotel_id = sembrar_torres(db).id
        r = calcular_variance(db, hotel_id=hotel_id, periodo="2026-08")
        assert r.version_plan_id is not None
        sueldos = next(x for x in r.lineas if x.fila_origen == 29)
        assert r.resultado[sueldos.id].mes.actual == Decimal("321190.84")
