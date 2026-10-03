"""Sentido de la Variación por línea y bloque (mes, acumulado, anual): importar y consultar.

Viene de las fórmulas del Excel de Contraloría (`ingesta/variance_convenciones.py`) y se guarda por
versión de la estructura del reporte. Importar de nuevo **reemplaza** las de esa versión.
"""

from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.orm import Session

from fpa.calculo.variance import Convencion
from fpa.ingesta.variance_convenciones import ConvencionesLeidas
from fpa.modelos.reporte import ConvencionLinea, VersionEstructuraReporte
from fpa.repositorios.reporte import RepositorioReporte
from fpa.servicios.auditoria import auditar

BLOQUES = ("mes", "ytd", "anual")
SUMA_DE_VARIACIONES = "suma_de_variaciones"


def importar_convenciones(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    version: VersionEstructuraReporte,
    leidas: ConvencionesLeidas,
    archivo: str,
) -> tuple[int, list[int]]:
    """Guarda el sentido de cada línea. Devuelve (celdas guardadas, filas del Excel sin línea)."""
    if version.hotel_id != hotel_id:
        raise ValueError("La versión de estructura no pertenece al hotel")
    por_fila = {x.fila_origen: x for x in RepositorioReporte(db, hotel_id).lineas(version.id)}
    sin_linea = sorted(f for f in {*leidas.por_fila, *leidas.compuestas} if f not in por_fila)
    guardadas = 0
    with db.begin_nested():
        db.execute(
            delete(ConvencionLinea).where(
                ConvencionLinea.version_id == version.id, ConvencionLinea.hotel_id == hotel_id
            )
        )
        for fila, bloques in sorted(leidas.por_fila.items()):
            linea = por_fila.get(fila)
            if linea is None or linea.tipo == "seccion":
                continue
            for bloque, sentido in bloques.items():
                db.add(
                    ConvencionLinea(
                        version_id=version.id,
                        hotel_id=hotel_id,
                        linea_id=linea.id,
                        bloque=bloque,
                        convencion=sentido.value,
                    )
                )
                guardadas += 1
        for fila, bloques_comp in sorted(leidas.compuestas.items()):
            linea = por_fila.get(fila)
            if linea is None or linea.tipo == "seccion":
                continue
            for bloque, terminos in bloques_comp.items():
                if (fila, bloque) in {(f, b) for f, d in leidas.por_fila.items() for b in d}:
                    continue
                componentes: dict[int, int] = {}
                for desde, hasta, signo in terminos:
                    for f in range(desde, hasta + 1):
                        destino = por_fila.get(f)
                        if (
                            destino is not None
                            and destino.tipo != "seccion"
                            and destino.id != linea.id
                        ):
                            componentes[destino.id] = componentes.get(destino.id, 0) + signo
                if not componentes:
                    continue
                db.add(
                    ConvencionLinea(
                        version_id=version.id,
                        hotel_id=hotel_id,
                        linea_id=linea.id,
                        bloque=bloque,
                        convencion=SUMA_DE_VARIACIONES,
                        componentes=[[c, s] for c, s in componentes.items() if s != 0],
                    )
                )
                guardadas += 1
        db.flush()
        auditar(
            db,
            organizacion_id=organizacion_id,
            hotel_id=hotel_id,
            usuario_id=usuario_id,
            accion="convenciones.importadas",
            entidad="estructura_reporte",
            entidad_id=version.id,
            detalle={"archivo": archivo, "celdas": guardadas, "filas_sin_linea": sin_linea[:20]},
        )
    return guardadas, sin_linea


def convenciones_por_bloque(
    db: Session, hotel_id: int, version_estructura_id: int
) -> tuple[dict[str, dict[int, Convencion]], dict[str, dict[int, list[tuple[int, int]]]]]:
    """Lo escrito en el Excel de la estructura, por bloque.

    Devuelve (`bloque -> {linea_id: sentido}`, `bloque -> {linea_id: [(componente, signo)]}`): el
    segundo mapa son las líneas cuya Variación es la **suma de las de otras líneas**. Vacíos si no
    se importaron.
    """
    simples: dict[str, dict[int, Convencion]] = {b: {} for b in BLOQUES}
    compuestas: dict[str, dict[int, list[tuple[int, int]]]] = {b: {} for b in BLOQUES}
    for c in RepositorioReporte(db, hotel_id).convenciones(version_estructura_id):
        if c.bloque not in simples:
            continue
        if c.convencion == SUMA_DE_VARIACIONES:
            compuestas[c.bloque][c.linea_id] = [(int(x), int(s)) for x, s in c.componentes or []]
        else:
            simples[c.bloque][c.linea_id] = Convencion(c.convencion)
    return simples, compuestas
