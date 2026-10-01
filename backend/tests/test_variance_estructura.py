import os
from pathlib import Path

import pytest
from conftest import Mundo
from sqlalchemy.orm import Session

from fpa.ingesta.variance_estructura import (
    TipoLinea,
    leer_variance_estructura,
    leer_variance_estructura_filas,
    normalizar_texto_espaciado,
)
from fpa.repositorios.reporte import RepositorioReporte
from fpa.servicios.cargar_archivo import Resolucion
from fpa.servicios.cargas import DatosArchivo
from fpa.servicios.estructura_reporte import importar_estructura_reporte

_CARPETA_DOCUMENTOS = Path(
    os.environ.get(
        "FPA_DATOS_REALES", Path.home() / "Desktop" / "PLATAFORMA FP&A E INTELIGENCIA HOTELERA"
    )
)
VARIANCE = _CARPETA_DOCUMENTOS / "02. VT August 2026 Variance (Envio) (1).xlsx"

ENCABEZADO = [
    (None, "Account #", "Account Description", "AUGUST"),
    (None, None, None, "Actual"),
]


def hoja(*cuerpo):  # type: ignore[no-untyped-def]
    return [(None,) * 4, *ENCABEZADO, *cuerpo]


def detalle(codigo: str, nombre: str, valor: float = 1.0):  # type: ignore[no-untyped-def]
    return (f"{codigo}{nombre}", codigo, nombre, valor)


EJEMPLO = hoja(
    (None, "E x c h a n g e   R a t e", None, 17.13),
    (None, "O t h e r   I n c o m e", None, None),
    detalle("029-0000-44060-000", "Other Income", 31098.32),
    detalle("029-0000-42045-000", "Service for Cleaning", 5274.88),
    (None, None, "T o t a l   O t h e r   I n c o m e", 36373.2),
    (None, None, None, None),
    (None, "M g m t   &   C h e c k   I n", None, None),
    detalle("029-0111-60010-000", "Salaries", 321190.84),
    detalle("029-0111-60010-000", "Vacation", 6204.36),
    (None, None, "N e t    P r o f i t", 10.0),
    ("Beach Lease", None, "Beach Lease", 0),
)


def test_normaliza_texto_espaciado() -> None:
    assert normalizar_texto_espaciado("T o t a l   O t h e r   I n c o m e") == (
        "Total Other Income"
    )
    assert normalizar_texto_espaciado("N e t    P r o f i t") == "Net Profit"
    assert normalizar_texto_espaciado("M g m t   &   C h e c k   I n") == "Mgmt & Check In"
    assert normalizar_texto_espaciado("Money  Exchg Inc") == "Money Exchg Inc"


def test_clasifica_secciones_detalles_totales_e_informativas() -> None:
    r = leer_variance_estructura_filas(EJEMPLO)
    assert r.es_valido
    assert [(x.tipo, x.descripcion) for x in r.lineas] == [
        (TipoLinea.INFORMATIVA, "Exchange Rate"),
        (TipoLinea.SECCION, "Other Income"),
        (TipoLinea.DETALLE, "Other Income"),
        (TipoLinea.DETALLE, "Service for Cleaning"),
        (TipoLinea.TOTAL, "Total Other Income"),
        (TipoLinea.SECCION, "Mgmt & Check In"),
        (TipoLinea.DETALLE, "Salaries"),
        (TipoLinea.DETALLE, "Vacation"),
        (TipoLinea.SUBTOTAL, "Net Profit"),
        (TipoLinea.INFORMATIVA, "Beach Lease"),
    ]
    assert [x.orden for x in r.lineas] == list(range(1, 11))


def test_asigna_seccion_y_conserva_codigo_repetido() -> None:
    r = leer_variance_estructura_filas(EJEMPLO)
    por_desc = {x.descripcion: x for x in r.lineas}
    assert por_desc["Service for Cleaning"].seccion_orden == 2
    assert por_desc["Total Other Income"].seccion_orden == 2
    assert por_desc["Salaries"].seccion_orden == 6
    assert por_desc["Exchange Rate"].seccion_orden is None
    assert por_desc["Salaries"].codigo_corporativo == por_desc["Vacation"].codigo_corporativo
    assert por_desc["Other Income"].seccion_orden == 2
    assert por_desc["Mgmt & Check In"].seccion_orden is None  # una sección no pertenece a otra


def test_clave_provisional_es_unica_por_orden() -> None:
    r = leer_variance_estructura_filas(EJEMPLO)
    claves = [x.clave for x in r.lineas]
    assert len(set(claves)) == len(claves)
    assert claves[2] == "0003:other-income"


def test_fila_con_cifras_sin_nombre_se_ignora_con_aviso() -> None:
    r = leer_variance_estructura_filas(
        hoja(detalle("029-0000-44060-000", "Other Income"), (None, None, None, "=D3/D4"))
    )
    assert len(r.lineas) == 1
    assert any("sin nombre" in a for a in r.avisos)


def test_aviso_si_se_repite_descripcion_en_la_misma_seccion() -> None:
    r = leer_variance_estructura_filas(
        hoja(
            (None, "O t h e r", None, None),
            detalle("029-0000-1-000", "Igual"),
            detalle("029-0000-2-000", "Igual"),
        )
    )
    assert any("se repiten" in a for a in r.avisos)


def test_sin_encabezado_o_sin_detalle_es_error() -> None:
    assert not leer_variance_estructura_filas([(None, "otra cosa", None, None)]).es_valido
    r = leer_variance_estructura_filas(hoja((None, "O t h e r", None, None)))
    assert not r.es_valido


# --- persistencia --------------------------------------------------------------------------


def _archivo(sha: str = "a" * 64) -> DatosArchivo:
    return DatosArchivo(nombre="variance.xlsx", sha256=sha)


def _importar(db: Session, mundo: Mundo, hotel: int, **kw):  # type: ignore[no-untyped-def]
    return importar_estructura_reporte(
        db,
        organizacion_id=mundo.org1,
        hotel_id=hotel,
        usuario_id=None,
        resultado=kw.pop("resultado", leer_variance_estructura_filas(EJEMPLO)),
        archivo=kw.pop("archivo", _archivo()),
        **kw,
    )


def test_importa_y_guarda_lineas_en_orden_con_secciones(db: Session, mundo: Mundo) -> None:
    res = _importar(db, mundo, mundo.hotel_a, periodo_referencia="2026-08")
    db.commit()
    assert res.resolucion is Resolucion.CREADA
    repo = RepositorioReporte(db, mundo.hotel_a)
    version = repo.vigente()
    assert version is not None and version.n_lineas == 10 and version.n_detalle == 4
    assert version.periodo_referencia == "2026-08"
    lineas = repo.lineas(version.id)
    assert [x.orden for x in lineas] == list(range(1, 11))
    seccion = next(x for x in lineas if x.descripcion == "Other Income" and x.tipo == "seccion")
    detalles = [x for x in lineas if x.tipo == "detalle" and x.seccion_id == seccion.id]
    assert [x.descripcion for x in detalles] == ["Other Income", "Service for Cleaning"]
    assert seccion.seccion_id is None and seccion.nivel == 0


def test_mismo_archivo_es_idempotente(db: Session, mundo: Mundo) -> None:
    _importar(db, mundo, mundo.hotel_a)
    db.commit()
    res = _importar(db, mundo, mundo.hotel_a)
    assert res.resolucion is Resolucion.DUPLICADA
    assert len(RepositorioReporte(db, mundo.hotel_a).versiones()) == 1


def test_otro_archivo_pide_confirmacion_y_luego_reemplaza(db: Session, mundo: Mundo) -> None:
    _importar(db, mundo, mundo.hotel_a)
    db.commit()
    otro = _archivo("b" * 64)
    pide = _importar(db, mundo, mundo.hotel_a, archivo=otro)
    assert pide.resolucion is Resolucion.REQUIERE_CONFIRMACION
    assert len(RepositorioReporte(db, mundo.hotel_a).versiones()) == 1

    res = _importar(db, mundo, mundo.hotel_a, archivo=otro, confirmar_reemplazo=True)
    db.commit()
    assert res.resolucion is Resolucion.REEMPLAZADA
    versiones = RepositorioReporte(db, mundo.hotel_a).versiones()
    assert [v.estado for v in versiones] == ["reemplazada", "vigente"]
    assert versiones[0].reemplazada_en is not None


def test_lectura_invalida_se_rechaza(db: Session, mundo: Mundo) -> None:
    res = _importar(db, mundo, mundo.hotel_a, resultado=leer_variance_estructura_filas([]))
    assert res.resolucion is Resolucion.RECHAZADA
    assert RepositorioReporte(db, mundo.hotel_a).vigente() is None


def test_aislamiento_por_hotel(db: Session, mundo: Mundo) -> None:
    _importar(db, mundo, mundo.hotel_a)
    db.commit()
    assert RepositorioReporte(db, mundo.hotel_b).vigente() is None
    version = RepositorioReporte(db, mundo.hotel_a).vigente()
    assert version is not None
    assert RepositorioReporte(db, mundo.hotel_b).obtener(version.id) is None
    assert RepositorioReporte(db, mundo.hotel_b).lineas(version.id) == []
    # el otro hotel puede tener su propia estructura vigente
    assert _importar(db, mundo, mundo.hotel_b).resolucion is Resolucion.CREADA


# --- archivo real (se salta si no está) ----------------------------------------------------


@pytest.mark.skipif(not VARIANCE.exists(), reason="No está el Excel real del Variance")
def test_hoja_ago_real() -> None:
    r = leer_variance_estructura(VARIANCE)
    assert r.es_valido, r.errores
    assert r.contar(TipoLinea.DETALLE) == 409
    assert [x.orden for x in r.lineas] == list(range(1, len(r.lineas) + 1))
    assert [x.fila_origen for x in r.lineas] == sorted(x.fila_origen for x in r.lineas)
    assert r.contar(TipoLinea.SECCION) >= 10 and r.contar(TipoLinea.TOTAL) >= 10
    primera = next(x for x in r.lineas if x.tipo is TipoLinea.DETALLE)
    assert (primera.fila_origen, primera.codigo_corporativo) == (11, "029-0101-45010-000")
    assert primera.descripcion.startswith("Other Income-001")
    assert any(x.descripcion == "Total Other Income" for x in r.lineas)
    assert not any(" " in x.descripcion and x.descripcion.startswith("T ") for x in r.lineas)
