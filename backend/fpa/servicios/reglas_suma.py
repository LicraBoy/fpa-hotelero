"""Reglas de suma del reporte: importarlas y evaluarlas.

`evaluar_totales` es una función **pura y determinística** (Decimal): dados los valores de las
líneas de detalle, calcula cada total y subtotal siguiendo sus reglas, en el orden que exijan las
dependencias. Una regla que depende de sí misma (directa o indirectamente) es un error.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal

from sqlalchemy import delete
from sqlalchemy.orm import Session

from fpa.ingesta.variance_reglas import ResultadoReglas
from fpa.modelos.reporte import LineaReporte, ReglaSumaLinea, VersionEstructuraReporte
from fpa.repositorios.reporte import RepositorioReporte
from fpa.servicios.auditoria import auditar

CERO = Decimal("0")


class CicloEnReglas(ValueError):
    """Los totales se referencian en círculo y no se pueden calcular."""


def evaluar_totales(
    reglas: Mapping[int, Sequence[tuple[int, int]]],
    valores: Mapping[int, Decimal],
) -> dict[int, Decimal]:
    """`reglas`: línea total -> [(línea componente, signo)]. `valores`: línea -> importe.

    Devuelve el importe de cada línea con regla. Un componente sin valor ni regla cuenta 0.
    """
    resultado: dict[int, Decimal] = {}
    en_curso: set[int] = set()

    def valor(linea: int) -> Decimal:
        if linea in resultado:
            return resultado[linea]
        if linea not in reglas:
            return valores.get(linea, CERO)
        if linea in en_curso:
            raise CicloEnReglas(f"La línea {linea} depende de sí misma")
        en_curso.add(linea)
        total = sum((signo * valor(c) for c, signo in reglas[linea]), CERO)
        en_curso.discard(linea)
        resultado[linea] = total
        return total

    for linea in reglas:
        valor(linea)
    return resultado


def importar_reglas_suma(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int | None,
    version: VersionEstructuraReporte,
    leidas: ResultadoReglas,
) -> int:
    """Reemplaza las reglas de la versión de estructura. Devuelve cuántas reglas quedaron."""
    if version.hotel_id != hotel_id:
        raise ValueError("La versión no pertenece al hotel")
    lineas = RepositorioReporte(db, hotel_id).lineas(version.id)
    por_orden: dict[int, LineaReporte] = {x.orden: x for x in lineas}
    with db.begin_nested():
        db.execute(
            delete(ReglaSumaLinea).where(
                ReglaSumaLinea.version_id == version.id, ReglaSumaLinea.hotel_id == hotel_id
            )
        )
        for regla in leidas.reglas:
            destino = por_orden[regla.orden]
            for orden_componente, signo in regla.componentes:
                db.add(
                    ReglaSumaLinea(
                        version_id=version.id,
                        hotel_id=hotel_id,
                        linea_id=destino.id,
                        componente_id=por_orden[orden_componente].id,
                        signo=signo,
                    )
                )
        db.flush()
        auditar(
            db,
            organizacion_id=organizacion_id,
            hotel_id=hotel_id,
            usuario_id=usuario_id,
            accion="reglas_suma.importadas",
            entidad="estructura_reporte",
            entidad_id=version.id,
            detalle={"n_reglas": len(leidas.reglas), "avisos": leidas.avisos[:10]},
        )
    return len(leidas.reglas)


def reglas_como_mapa(
    db: Session, hotel_id: int, version_id: int
) -> dict[int, list[tuple[int, int]]]:
    """Reglas guardadas como `linea_id -> [(componente_id, signo)]` para `evaluar_totales`."""
    mapa: dict[int, list[tuple[int, int]]] = {}
    for r in RepositorioReporte(db, hotel_id).reglas(version_id):
        mapa.setdefault(r.linea_id, []).append((r.componente_id, r.signo))
    return mapa
